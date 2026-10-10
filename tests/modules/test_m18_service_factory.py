"""Authenticated actual M18 service path, fake transport only."""
import tempfile,shutil,json,os
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.modules.m18_side_hustle_scraper.service_factory import *
from app.modules.m18_side_hustle_scraper.lane_http import FakeHttpClient

@pytest.fixture
def root():
    p=Path(tempfile.mkdtemp(prefix='m18-factory-',dir=Path.home()));p.chmod(0o700)
    yield p
    shutil.rmtree(p)


def test_provision_missing_owner_pending_and_restart(root):
    with pytest.raises(FactoryUnavailable):CollectorServiceFactory(root)._validate('t','a')
    provision(root,'t','a',known_new=True)
    with pytest.raises(FactoryUnavailable):provision(root,'t','a',known_new=True)
    f=CollectorServiceFactory(root)
    with f.service('t','a') as s:
        assert s._tenant_id=='t'
        assert all(c.limiter is s._bound_limiter for c in s._collectors.values())
    with pytest.raises(OwnerMismatch):
        with f.service('t','other'):pass
    _,work=paths(root,'t');DispatchIntentWAL(work,'t').begin('example.org',__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    with pytest.raises(FactoryUnavailable):
        with CollectorServiceFactory(root).service('t','a'):pass


def test_http_six_endpoints_owner_and_unprovisioned(root,monkeypatch,oidc_auth_headers):
    from app.modules.m18_side_hustle_scraper import routes as r
    provision(root,'t','a',known_new=True)
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    monkeypatch.setenv('ATLAS_M18_DURABLE_ROOT',str(root));monkeypatch.setattr(r,'_factory',CollectorServiceFactory(root,http=FakeHttpClient()))
    app=FastAPI();app.include_router(r.router)
    with TestClient(app) as c:
        requests=[('POST','/blueprints',{'query':'demo'}),('POST','/feasibility',{}),('POST','/collect',{'query':'demo','platforms':['hacker_news'],'limit_per_platform':1}),('POST','/rank',{'query':'demo'}),('POST','/refresh',None),('GET','/freshness',None)]
        for method,path,data in requests:
            assert c.request(method,'/side-hustle-scraper'+path,json=data,headers=oidc_auth_headers('t','other')).status_code==403
            assert c.request(method,'/side-hustle-scraper'+path,json=data,headers=oidc_auth_headers('absent','a')).status_code==503
            assert c.request(method,'/side-hustle-scraper'+path,json=data).status_code in (401,403)
        assert c.get('/side-hustle-scraper/freshness',headers=oidc_auth_headers('t','a')).status_code==200


def test_missing_db_does_not_auto_create(root):
    provision(root,'t','a',known_new=True);_,work=paths(root,'t');(work/'documents.sqlite3').unlink()
    with pytest.raises(FactoryUnavailable):
        with CollectorServiceFactory(root).service('t','a'):pass
    assert not (work/'documents.sqlite3').exists()


def test_actual_http_collect_snapshot_before_fake_fetch(root,monkeypatch,oidc_auth_headers):
    from app.modules.m18_side_hustle_scraper import routes as r
    from app.modules.m18_side_hustle_scraper.lane_rate_limit_state import read_snapshot
    from datetime import datetime,timezone
    provision(root,'t','a',known_new=True)
    http=FakeHttpClient();url='https://hn.algolia.com/api/v1/search?query=demo&tags=story&hitsPerPage=1'
    http.add(url,json.dumps({'hits':[]}))
    original=http.fetch;seen=[];_,work=paths(root,'t')
    def fetch(url,**kw):
        assert DispatchIntentWAL(work,'t').read()['pending'] is None
        state=read_snapshot(next(work.glob('m18-pacing-*')),tenant_id='t',now=datetime.now(timezone.utc))
        assert state.states['hn.algolia.com'].total_requests==1
        assert kw['policy'].max_redirects==0
        seen.append(url);return original(url,**kw)
    http.fetch=fetch
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setenv('ATLAS_M18_DURABLE_ROOT',str(root));monkeypatch.setattr(r,'_factory',CollectorServiceFactory(root,http=http))
    app=FastAPI();app.include_router(r.router)
    with TestClient(app) as c:
        result=c.post('/side-hustle-scraper/collect',json={'query':'demo','platforms':['hacker_news'],'limit_per_platform':1},headers=oidc_auth_headers('t','a'))
        assert result.status_code==200 and seen==[url]


def test_robots_and_refresh_shared_wal(root,monkeypatch):
    from app.modules.m18_side_hustle_scraper.lane_models import SourceKind
    provision(root,'t','a',known_new=True)
    http=FakeHttpClient();http.add('https://example.org/robots.txt','User-agent: *\nAllow: /\n');http.add('https://example.org/page','page content');http.add('https://example.net/refetch','updated')
    original=http.fetch;seen=[];_,work=paths(root,'t')
    def fetch(url,**kw):
        assert DispatchIntentWAL(work,'t').read()['pending'] is None
        from app.modules.m18_side_hustle_scraper.lane_rate_limit_state import read_snapshot
        from datetime import datetime,timezone
        from urllib.parse import urlsplit
        state=read_snapshot(next(work.glob('m18-pacing-*')),tenant_id='t',now=datetime.now(timezone.utc))
        assert state.states[urlsplit(url).netloc].total_requests==1
        seen.append(url);return original(url,**kw)
    http.fetch=fetch
    monkeypatch.setenv('ATLAS_M18_PUBLIC_URLS','https://example.org/page')
    f=CollectorServiceFactory(root,http=http,sleeper=lambda n:None)
    with f.service('t','a') as s:
        robots=s._collectors['public_web'].robots
        assert robots.check('https://example.org/page').allowed
        # Same-host next page cannot dispatch while no-op sleep leaves pacing active.
        _,error=s._collectors['public_web']._get('https://example.org/page')
        assert error and seen==['https://example.org/robots.txt']
        assert s._bound_refetcher('https://example.net/refetch',SourceKind.HACKER_NEWS)['status']==200
        assert seen[-1]=='https://example.net/refetch'


def test_actual_second_process_factory_pending_and_tenant_isolation(root):
    import subprocess,sys
    from datetime import datetime,timezone
    provision(root,'t','a',known_new=True);provision(root,'other','b',known_new=True)
    _,work=paths(root,'t')
    f=CollectorServiceFactory(root)
    with f.service('t','a') as service:service._pipeline.repository.record_event('t','canary',{'kept':'yes'})
    script="""import json,sys
from app.modules.m18_side_hustle_scraper.service_factory import CollectorServiceFactory
f=CollectorServiceFactory(sys.argv[1])
with f.service('t','a') as s: print(json.dumps(s._pipeline.repository.events('t',kind='canary')))
with f.service('other','b') as s: print(json.dumps(s._pipeline.repository.events('other',kind='canary')))
"""
    result=subprocess.run([sys.executable,'-c',script,str(root)],capture_output=True,text=True,check=True)
    lines=result.stdout.splitlines();assert json.loads(lines[0])[0]['payload']=={'kept':'yes'} and json.loads(lines[1])==[]
    DispatchIntentWAL(work,'t').begin('x',datetime.now(timezone.utc))
    result=subprocess.run([sys.executable,'-c',script,str(root)],capture_output=True,text=True)
    assert result.returncode!=0 and result.stdout==''

@pytest.mark.parametrize('fault',['registry','profile','database','pacing','intent'])
def test_corrupt_warm_factory_denies_before_transport(root,fault):
    provision(root,'t','a',known_new=True);http=FakeHttpClient();f=CollectorServiceFactory(root,http=http)
    with f.service('t','a'):pass
    registry,work=paths(root,'t')
    if fault=='registry':registry.write_text('{')
    if fault=='profile':
        data=json.loads(registry.read_text());data['profile']='wrong';registry.write_text(json.dumps(data))
    if fault=='database':(work/'documents.sqlite3').write_bytes(b'not sqlite')
    if fault=='pacing':next(work.glob('m18-pacing-*')).write_text('{')
    if fault=='intent':next(work.glob('m18-intent-*')).write_text('{')
    with pytest.raises(FactoryUnavailable):
        with f.service('t','a'):pass
    assert not http.requests


def test_sync_real_collector_blueprint_adapter(root):
    import asyncio
    from app.modules.m18_side_hustle_scraper.schemas import DiscoverIn
    provision(root,'t','a',known_new=True)
    http=FakeHttpClient()
    for sub in ('sidehustle','Entrepreneur','smallbusiness','passive_income'):
        http.add('https://www.reddit.com/r/'+sub+'/search.json?q=demo&restrict_sr=1&sort=relevance&t=year&limit=1',json.dumps({'data':{'children':[]}}))
    calls=[]
    async def generate(prompt,*a):calls.append(prompt);return 'fixture','[]'
    # Advance wall clock so retries/same-host pacing is truly rechecked.
    from datetime import datetime,timezone,timedelta
    now=[datetime.now(timezone.utc)]
    def sleep(n):now[0]+=timedelta(seconds=n)
    f=CollectorServiceFactory(root,http=http,generate=generate,sleeper=sleep,clock=lambda:now[0])
    with f.service('t','a') as s:assert asyncio.run(s.discover(DiscoverIn(query='demo',platforms=['reddit'],limit_per_platform=4)))==[]
    assert len(http.requests)==4 and len(calls)==1


def test_cached_database_replacement_refused(root):
    provision(root,'t','a',known_new=True);f=CollectorServiceFactory(root)
    with f.service('t','a'):pass
    _,work=paths(root,'t');db=work/'documents.sqlite3';data=db.read_bytes();db.unlink();db.write_bytes(data);db.chmod(0o600)
    with pytest.raises(FactoryUnavailable):
        with f.service('t','a'):pass


def test_schema_invalid_database_refused_without_repair(root):
    provision(root,'t','a',known_new=True);_,work=paths(root,'t')
    db=work/'documents.sqlite3';db.unlink()
    with sqlite3.connect(db) as conn:
        for table in ('documents','events','freshness_state'):conn.execute('CREATE TABLE '+table+' (wrong TEXT)')
    db.chmod(0o600);before=db.read_bytes()
    with pytest.raises(FactoryUnavailable):
        with CollectorServiceFactory(root).service('t','a'):pass
    assert db.read_bytes()==before

@pytest.mark.parametrize('value',['/tmp','/dev/shm','/run','/tmp/../tmp','relative'])
def test_factory_volatile_roots_refused(value):
    with pytest.raises(FactoryUnavailable):CollectorServiceFactory(value)


def test_positive_owner_blueprint_feasibility_routes(root,monkeypatch,oidc_auth_headers):
    from app.modules.m18_side_hustle_scraper import routes as r
    provision(root,'t','a',known_new=True)
    http=FakeHttpClient()
    for sub in ('sidehustle','Entrepreneur','smallbusiness','passive_income'):
        http.add('https://www.reddit.com/r/'+sub+'/search.json?q=demo&restrict_sr=1&sort=relevance&t=year&limit=1',json.dumps({'data':{'children':[]}}))
    from datetime import datetime,timezone,timedelta
    now=[datetime.now(timezone.utc)]
    def sleep(n):now[0]+=timedelta(seconds=n)
    blueprint={'title':'demo','steps':['test'],'tools':[],'complexity':1,'automation_level':0,'monetisation':[],'source_urls':[]}
    feasibility={'strengths':[],'weaknesses':[],'opportunities':[],'threats':[],'market_saturation':0,'barrier_to_entry':0,'evidence_quality':0,'viability_score':0,'score_explanation':['fixture not model quality'],'sensitivities':[],'first_experiment':'test','max_test_budget':0,'recommendation':'test'}
    async def generate(prompt,*a):return 'fixture',json.dumps(feasibility if 'SWOT' in prompt else [blueprint])
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setenv('ATLAS_M18_DURABLE_ROOT',str(root));monkeypatch.setattr(r,'_factory',CollectorServiceFactory(root,http=http,generate=generate,sleeper=sleep,clock=lambda:now[0]))
    app=FastAPI();app.include_router(r.router)
    with TestClient(app) as c:
        headers=oidc_auth_headers('t','a')
        result=c.post('/side-hustle-scraper/blueprints',json={'query':'demo','platforms':['reddit'],'limit_per_platform':4},headers=headers)
        assert result.status_code==200 and result.json()[0]['title']=='demo'
        result=c.post('/side-hustle-scraper/feasibility',json={'blueprint':blueprint,'user':{}},headers=headers)
        assert result.status_code==200 and result.json()['viability_score']==0
    assert len(http.requests)==4


def test_service_same_tenant_operations_serialized(root):
    from concurrent.futures import ThreadPoolExecutor
    import threading,time
    provision(root,'t','a',known_new=True);f=CollectorServiceFactory(root);entered=[];first=threading.Event();release=threading.Event()
    def one():
        with f.service('t','a'):entered.append(1);first.set();release.wait(2)
    def two():
        first.wait(2)
        with f.service('t','a'):entered.append(2)
    with ThreadPoolExecutor(2) as ex:
        a=ex.submit(one);b=ex.submit(two);assert first.wait(2);time.sleep(.03);assert entered==[1];release.set();a.result();b.result()
    assert entered==[1,2]
