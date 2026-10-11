"""Five-module plain-source C4 snapshot checks; no original-history claim."""
import hashlib
import hmac
import importlib
import json
import sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from app.modules.m21_claire import meemee_webhook_security as w
from app.modules.m21_claire import meemee_secret_scrub as s
from app.modules.m21_claire import meemee_rate_quota as q
from app.modules.m21_claire import meemee_approval_grants as a
from app.modules.m21_claire import meemee_device_protocol as d
UTC=timezone.utc
DAY=datetime(2026,10,11,tzinfo=UTC)
KEY=b'local synthetic fixture'


def exact(exc,message,fn):
    with pytest.raises(exc) as e:fn()
    assert str(e.value)==message


def test_webhook_signature_real_digest():
    expected='sha256='+hmac.new(b'fixture',b'100.{}',hashlib.sha256).hexdigest()
    assert w.compute_signature('fixture','100',b'{}')==expected
    for now,allowed in [(99,True),(101,True),(98,False),(102,False)]:
        assert w.verify_signature('fixture','100',b'{}',expected,now=now,tolerance_seconds=1) is allowed
    assert w.verify_signature('fixture','100',b'{}',expected,now=100,tolerance_seconds=0)
    assert not w.verify_signature('fixture','100',b'{}',expected,now=100,tolerance_seconds=-1)
    assert not w.verify_signature('fixture','bad',b'{}',expected,now=100)


@pytest.mark.parametrize('signature',[None,7,'md5=x','sha256=é','sha256=wrong'])
def test_signature_shape_refused(signature):
    assert not w.verify_signature('fixture','100',b'{}',signature,now=100)


def test_webhook_url_exact_echo_port_and_all_addresses():
    calls=[]
    def resolver(h,p):calls.append((h,p));return ['8.8.8.8','1.1.1.1']
    url='https://public.example.invalid:8443/hook?x=1#frag'
    assert w.validate_webhook_url(url,resolver=resolver)==url
    assert calls==[('public.example.invalid',8443)]
    exact(ValueError,'webhook URL resolves to a private or reserved address',lambda:w.validate_webhook_url(url,resolver=lambda h,p:['8.8.8.8','127.0.0.1']))
    exact(ValueError,'webhook URL must not contain credentials',lambda:w.validate_webhook_url('https://u:p@public.example.invalid',resolver=resolver))
    exact(ValueError,'webhook URL must use HTTPS',lambda:w.validate_webhook_url('http://public.example.invalid',resolver=resolver))


def test_marker_independent_hash_and_unicode_length():
    value='fixture café'
    assert s.marker(value)=='[REDACTED:'+hashlib.sha256(value.encode()).hexdigest()[:16]+':12]'
    assert s.marker(value)!=s.marker(value+'x')


@pytest.mark.parametrize('prefix',['github'+'_pat_','gh'+'p_','gh'+'o_','gh'+'s_','gh'+'u_','sk-'])
def test_scrub_token_threshold(prefix):
    assert s.scrub_text(prefix+'a'*19)==prefix+'a'*19
    token=prefix+'a'*20
    assert s.scrub_text('pre '+token+' post')=='pre '+s.marker(token)+' post'


@pytest.mark.parametrize('name',['password','passwd','api_key','api-key','access_token','access-token','secret'])
def test_assignment_scrub_preserves_key_and_marker(name):
    assert s.scrub_text(name+': '+'a'*7)==name+': '+'a'*7
    assert s.scrub_text(name+': '+'a'*8+'; tail')==name+'='+s.marker('a'*8)+'; tail'


def test_bearer_case_and_threshold_and_plain():
    assert s.scrub_text('Bearer '+'a'*15)=='Bearer '+'a'*15
    token='bEaReR '+'a'*16
    assert s.scrub_text(token)==s.marker(token)
    assert s.scrub_text('plain note')=='plain note'


@pytest.mark.parametrize('limit,window',[(0,1),(-1,1),(True,1),(1,0),(1,-1),(1,True),(1.5,1)])
def test_rate_config_exact(limit,window):
    exact(ValueError,'rate limit and window must be positive integers',lambda:q.FixedWindowLimiter(limit,window))


def test_rate_window_boundaries_identity_and_cleanup():
    r=q.FixedWindowLimiter(2,10,clock=lambda:25)
    assert r.hit('actor',now=9)==(True,1,10)
    assert r.hit('actor',now=9)==(True,0,10)
    assert r.hit('actor',now=9)==(False,0,10)
    assert r.hit('other',now=9)==(True,1,10)
    assert r.hit('actor',now=10)==(True,1,20)
    assert r.hit('clock')==(True,1,30)
    assert r.cleanup(now=20)==0
    assert r.cleanup(now=21)==2
    assert r.cleanup(now=31)==1


@pytest.mark.parametrize('v',[0,-1,True,1.2])
def test_quota_limit_exact(v):exact(ValueError,'daily quota must be a positive integer',lambda:q.QuotaStore(v))


def test_quota_day_utc_and_transaction_counts():
    assert q.quota_day(datetime(2026,10,11,1,tzinfo=timezone(timedelta(hours=3)))).isoformat()=='2026-10-10'
    exact(ValueError,'quota clock must include a timezone',lambda:q.quota_day(datetime(2026,10,11)))
    store=q.QuotaStore(2);store.set_limit('actor',1)
    assert store.consume_job('actor',DAY)==dict(day='2026-10-11',used=1,limit=1,remaining=0)
    exact(q.QuotaExceeded,'daily job quota exceeded (1)',lambda:store.consume_job('actor',DAY))
    assert store.status('actor',DAY)['used']==1
    assert store.consume_job('actor',DAY+timedelta(days=1))['used']==1
    assert store.status('other',DAY)==dict(day='2026-10-11',used=0,limit=2,remaining=2)
    assert store.delete_principal('actor')==dict(quota_usage=2,quota_limits=1)
    assert store.delete_principal('actor')==dict(quota_usage=0,quota_limits=0)
    assert store.limit('actor')==2


def test_expiry_offset_naive_and_none():
    assert a.normalize_expiry(None) is None
    assert a.normalize_expiry(' 2026-10-11T03:00:00+03:00 ')==DAY.isoformat()
    assert a.normalize_expiry('2026-10-11T00:00:00z')==DAY.isoformat()
    assert a.normalize_expiry('2026-10-11T00:00:00')==DAY.isoformat()
    exact(ValueError,'expires_at must be an ISO 8601 timestamp',lambda:a.normalize_expiry('bad'))
    assert a.utc_moment(DAY.replace(tzinfo=None))==DAY


@pytest.mark.parametrize('value',[[],{'x':float('nan')},{'x':float('inf')},{1:'bad'},{'x':set()}])
def test_invalid_constraints_exact(value):
    message='argument_constraints must be an object' if isinstance(value,list) else 'argument_constraints must contain finite JSON values'
    exact(ValueError,message,lambda:a.validate_constraints(value))


@pytest.mark.parametrize('left,right,expected',[(True,1,False),(1,True,False),(1,1.0,True),(None,None,True),('1',1,False),([1,2],[1],False),([1,2],(1,2),False),({'x':1},{'x':1,'y':2},False)])
def test_constraint_recursive_types(left,right,expected):assert a.constraints_match({'v':left},{'v':right}) is expected


def test_constraints_none_bad_missing_and_extra():
    assert a.constraints_match(None,None)
    assert a.constraints_match({},None)
    assert not a.constraints_match({'x':1},None)
    assert not a.constraints_match({'x':1},[])
    assert not a.constraints_match({'x':float('nan')},{'x':1})
    assert a.constraints_match({'v':{'a':[1,True,None]}},{'v':{'a':[1,True,None]},'extra':1})


def test_grant_exact_expiry_and_scope_deletion():
    store=a.ApprovalGrantStore()
    for args in [('', 'tool','issuer'),('actor','','issuer'),('actor','tool','')]:
        exact(ValueError,'principal, tool and granted_by are required',lambda args=args:store.grant(*args))
    store.grant('actor','b','issuer',expires_at=DAY.isoformat(),argument_constraints={'v':1})
    store.grant('actor','a','issuer');store.grant('other','a','issuer')
    assert store.allows('actor','b',now=DAY-timedelta(seconds=1),arguments={'v':1})
    assert not store.allows('actor','b',now=DAY,arguments={'v':1})
    assert not store.allows('actor','b',now=DAY-timedelta(seconds=1),arguments={'v':2})
    assert not store.allows('actor','missing',now=DAY)
    assert store.active_count('actor',now=DAY)==1
    assert [r['tool'] for r in store.list('actor')]==['a','b']
    assert store.revoke('actor','a') and not store.revoke('actor','a') and not store.revoke('actor','missing')
    assert not store.allows('actor','a',now=DAY)
    assert store.delete_principal('actor')==2
    assert store.list('actor')==[] and len(store.list('other'))==1


def command(**kw):return d.make_command('device','click',{'x':1},KEY,issued_at=100,nonce='nonce',command_id='cmd',**kw)


def test_command_canonical_sign_and_verified_fields():
    x=command();unsigned={k:v for k,v in x.items() if k!='signature'}
    assert d.canonical_json({'z':1,'a':'é'})=='{"a":"é","z":1}'.encode()
    assert x['signature']==hmac.new(KEY,json.dumps(unsigned,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode(),hashlib.sha256).hexdigest()
    r=d.verify_command(x,KEY,now=100,expected_device_id='device',allowed_capabilities={'click'})
    assert (r.command_id,r.device_id,r.capability,r.arguments,r.issued_at,r.nonce)==('cmd','device','click',{'x':1},100,'nonce')
    r.arguments['x']=3;assert x['arguments']['x']==1


@pytest.mark.parametrize('field,value',[('version',True),('version',2),('issued_at',True),('command_id',''),('device_id',''),('capability',''),('nonce',''),('arguments',[])])
def test_command_envelope_shape(field,value):
    x=command();x[field]=value
    exact(ValueError,'invalid command envelope',lambda:d.verify_command(x,KEY,now=100))


@pytest.mark.parametrize('sig',[1,'é','wrong'])
def test_command_signature(sig):
    x=command();x['signature']=sig;exact(ValueError,'invalid command signature',lambda:d.verify_command(x,KEY,now=100))


def test_command_freshness_bindings_and_nonce_inclusive():
    x=command()
    for now in [99,101]:assert d.verify_command(x,KEY,now=now,tolerance=1).nonce=='nonce'
    for now in [98,102]:exact(ValueError,'stale command',lambda now=now:d.verify_command(x,KEY,now=now,tolerance=1))
    exact(ValueError,'command addressed to another device',lambda:d.verify_command(x,KEY,now=100,expected_device_id='other'))
    exact(PermissionError,'capability not declared by device',lambda:d.verify_command(x,KEY,now=100,allowed_capabilities=set()))
    clock=[99];guard=d.ReplayGuard(1,lambda:clock[0]);d.verify_command(x,KEY,now=99,tolerance=1,replay_guard=guard)
    clock[0]=101;exact(ValueError,'replayed command',lambda:d.verify_command(x,KEY,now=101,tolerance=1,replay_guard=guard))
    clock[0]=102;assert guard.claim('nonce')


@pytest.mark.parametrize('kw',[{'issued_at':True},{'nonce':''},{'command_id':''}])
def test_make_command_keyword_types(kw):
    exact(ValueError,'invalid command fields',lambda:d.make_command('device','click',{},KEY,**kw))


def test_inventory_header_matches_actual_computed_rows():
    import re
    from app.modules.m21_claire.meemee_merge_inventory import inventory_report,inventory_rows
    report=inventory_report();rows=inventory_rows()
    assert len(rows)==report['total_capabilities']==45
    assert report['by_disposition']=={'PORTED':15,'ALREADY_PRESENT':15,'REJECTED':12,'DEFERRED':3}
    text=(Path(__file__).resolve().parents[2]/'docs/C4_INVENTORY_COUNT_CORRECTION.md').read_text()
    assert 'Result: 45 capabilities inventoried' in text
    for label,count in report['by_disposition'].items():assert f'- {count} {label}' in text
    table=[line for line in text.splitlines() if ' | ' in line and line.split(' | ')[3] in report['by_disposition']]
    assert len(table)==len(rows)


def test_rate_minimum_default_and_lowered_limit_remaining():
    assert q.FixedWindowLimiter(1,1).hit('actor',now=0)==(True,0,1)
    default=q.FixedWindowLimiter();assert default.limit==60 and default.window==60
    store=q.QuotaStore();assert store.default==100
    store.set_limit('actor',3)
    for _ in range(3):store.consume_job('actor',DAY)
    store.set_limit('actor',1);assert store.status('actor',DAY)['remaining']==0


def test_timezone_none_offset_custom():
    from datetime import tzinfo
    class Unknown(tzinfo):
        def utcoffset(self,dt):return None
    exact(ValueError,'quota clock must include a timezone',lambda:q.quota_day(DAY.replace(tzinfo=Unknown())))


def test_constraint_recursive_invalid_and_mismatch():
    for bad in [{'x':{'y':object()}},{'x':[float('nan')]}]:
        exact(ValueError,'argument_constraints must contain finite JSON values',lambda bad=bad:a.validate_constraints(bad))
        assert not a.constraints_match(bad,{'x':{}})
        exact(ValueError,'argument_constraints must contain finite JSON values',lambda bad=bad:a.ApprovalGrantStore().grant('actor','tool','issuer',argument_constraints=bad))
    for lhs,rhs in [({'x':1},'x'),([1,2],[1,3]),([1,2],[1,2,3]),(1,'1'),(1,float('nan'))]:
        assert not a.constraints_match({'v':lhs},{'v':rhs})
    store=a.ApprovalGrantStore();store.grant('actor','tool','issuer');store.revoke('actor','tool');assert store.active_count('actor',DAY)==0


def test_device_defaults_generation_freeze_and_shapes():
    from dataclasses import FrozenInstanceError
    x=d.make_command('device','click',{},KEY,issued_at=100)
    assert len(x['nonce'])==len(x['command_id'])==32
    assert d.ReplayGuard().ttl==300
    assert d.verify_command(x,KEY,now=400).issued_at==100
    exact(ValueError,'stale command',lambda:d.verify_command(x,KEY,now=401))
    obj=d.verify_command(x,KEY,now=100)
    with pytest.raises(FrozenInstanceError):obj.nonce='changed'
    for device,cap in [(5,'click'),('device',5)]:
        exact(ValueError,'invalid command fields',lambda device=device,cap=cap:d.make_command(device,cap,{},KEY))
    for kw in [{'nonce':5},{'command_id':5}]:
        exact(ValueError,'invalid command fields',lambda kw=kw:d.make_command('device','click',{},KEY,**kw))
    exact(ValueError,'invalid command envelope',lambda:d.verify_command([],KEY,now=100))
    for field in ['device_id','command_id','nonce','capability']:
        env=command();env[field]=5;exact(ValueError,'invalid command envelope',lambda env=env:d.verify_command(env,KEY,now=100))
    g=d.ReplayGuard(1,clock=lambda:100);assert g.claim('n');assert g._seen['n']==101


def test_webhook_defaults_userinfo_host_resolver_and_zone(monkeypatch):
    sig=w.compute_signature('fixture','100',b'{}')
    assert w.verify_signature('fixture','100',b'{}',sig,now=400)
    assert not w.verify_signature('fixture','100',b'{}',sig,now=401)
    url='https://public.example.invalid/h'
    calls=[]
    monkeypatch.setattr(w.socket,'getaddrinfo',lambda host,port:(calls.append((host,port)) or [(0,0,0,'',('8.8.8.8',port))]))
    assert w.validate_webhook_url(url)==url
    assert calls==[('public.example.invalid',443)]
    for bad in ['https:///hook','https://user@public.example.invalid','https://:pw@public.example.invalid']:
        message='webhook URL must use HTTPS' if bad=='https:///hook' else 'webhook URL must not contain credentials'
        exact(ValueError,message,lambda bad=bad:w.validate_webhook_url(bad,resolver=lambda h,p:['8.8.8.8']))
    assert w.validate_webhook_url(url,resolver=lambda h,p:['2001:4860:4860::8888%zone'])==url
