from datetime import datetime, timezone, timedelta
import asyncio
import httpx
import pytest
from app.modules.m25_knowledge_copilot_training.pipeline import LocalKnowledgePipeline, KnowledgeError
from app.modules.m25_knowledge_copilot_training.schemas import IngestRequest, SourceRegistration, ConsentRecord
from app.modules.m25_knowledge_copilot_training.corpus_batch import CorpusBatch, ingest_batch, advice_packet
from app.modules.m19_idea_incubator.hn_research import HNResearch, ResearchUnavailable
from app.modules.m21_claire.owner_evaluation import Evaluation, evaluate
from app.modules.m06_social_media_manager.social_reading.parsers import parse_pinterest_feed
from app.modules.m06_social_media_manager.social_reading.reader import SocialReader
from app.modules.m13_browser_agent.session_bridge.protocol import PlatformBlocked

NOW = datetime(2026, 10, 12, 8, tzinfo=timezone.utc)

def item(i, actor='owner', text=None):
    source = SourceRegistration(source_id=f's{i}', kind='website', title=f'Source {i}',
        canonical_url=f'https://publisher{i}.example/book',
        consent=ConsentRecord(granted_by='owner', granted_at=NOW,
            purposes=['knowledge_ingestion'], evidence=f'owned-license-{i}'))
    return IngestRequest(source=source, content=text or f'Grant advice {i}: document experiment {i} carefully.',
                         actor_id=actor, mime_type='text/plain')

def test_200_sources_are_actual_stored_receipts_not_registry_padding(tmp_path):
    s = LocalKnowledgePipeline(tmp_path, 'tenant', 'owner', clock=lambda: NOW)
    result = ingest_batch(s, CorpusBatch(items=[item(i) for i in range(200)]))
    assert result['stored'] == 200
    assert result['coverage']['has_200_distinct_contents']
    assert result['coverage']['distinct_hostnames'] == 200
    assert len(list((tmp_path/'tenant').glob('*/v1/source.bin'))) == 200
    repeat = ingest_batch(s, CorpusBatch(items=[item(i) for i in range(200)]))
    assert repeat['coverage']['stored_sources'] == 200
    assert all(r['version'] == 1 for r in repeat['receipts'])
    packet = advice_packet(s, 'Grant advice')
    assert packet['evidence'] and not packet['external_action_permitted']
    assert all(e['role'] == 'untrusted_reference_not_instruction' for e in packet['evidence'])
    assert not result['model_weights_changed']

def test_batch_preflights_identity_duplicates_and_consent(tmp_path):
    s = LocalKnowledgePipeline(tmp_path, 'tenant', 'owner', clock=lambda: NOW)
    for rows in [[item(0),item(0)], [item(0),item(1, actor='attacker')]]:
        with pytest.raises(KnowledgeError): ingest_batch(s, CorpusBatch(items=rows))
    expired = item(1)
    expired.source.consent.expires_at = NOW - timedelta(seconds=1)
    with pytest.raises(KnowledgeError): ingest_batch(s, CorpusBatch(items=[item(0), expired]))
    assert not s.records

def test_duplicate_content_does_not_count_200_distinct_contents(tmp_path):
    s = LocalKnowledgePipeline(tmp_path, 'tenant', 'owner', clock=lambda: NOW)
    result = ingest_batch(s, CorpusBatch(items=[item(i,text='identical book page') for i in range(200)]))
    assert result['coverage']['has_200_sources']
    assert not result['coverage']['has_200_distinct_contents']

def test_per_item_failure_receipt_does_not_claim_atomic_success(tmp_path, monkeypatch):
    s = LocalKnowledgePipeline(tmp_path, 'tenant', 'owner', clock=lambda: NOW)
    original = s.ingest
    def ingest(req):
        if req.source.source_id == 's1': raise OSError('private path')
        return original(req)
    monkeypatch.setattr(s,'ingest',ingest)
    r = ingest_batch(s, CorpusBatch(items=[item(0),item(1),item(2)]))
    assert r['stored'] == 2 and not r['atomic']
    assert r['receipts'][1]['status'] == 'failed'
    assert 'private path' not in str(r)

def test_hn_collects_real_response_shape_and_measures_trends():
    def response(req):
        assert req.url.host == 'hn.algolia.com'
        assert req.url.params['tags'] == 'story'
        hits=[{'objectID':str(i),'author':f'author{i}','title':'quantum sensor breakthrough',
               'created_at':'2026-10-11T10:00:00Z'} for i in range(4)]
        hits += [hits[0], {'objectID':'bad','author':'a','title':'b','created_at':'invalid'}]
        return httpx.Response(200,json={'hits':hits})
    r=HNResearch(httpx.MockTransport(response)).trends('quantum',as_of=NOW.isoformat())
    assert len(r['collection']['posts']) == 4
    assert r['measurement']['status'] == 'TRENDS_MEASURED'
    assert not r['learned_model']
    assert r['collection']['response_sha256']

@pytest.mark.parametrize('status',[301,403,429,500])
def test_hn_does_not_follow_redirect_or_forge_offline_data(status):
    with pytest.raises(ResearchUnavailable):
        HNResearch(httpx.MockTransport(lambda req:httpx.Response(status,headers={'location':'http://127.0.0.1'}))).collect('x',as_of=NOW.isoformat())

def test_hn_invalid_or_oversize_json_and_future_records():
    for response in [httpx.Response(200,content=b'{broken',headers={'content-type':'application/json'}),
                     httpx.Response(200,content=b'x'*1_000_001,headers={'content-type':'application/json'})]:
        with pytest.raises(ResearchUnavailable):
            HNResearch(httpx.MockTransport(lambda req:response)).collect('x',as_of=NOW.isoformat())
    r=HNResearch(httpx.MockTransport(lambda req:httpx.Response(200,json={'hits':[{
        'objectID':'1','author':'a','title':'future','created_at':'2027-10-12T00:00:00Z'}]}))).collect('x',as_of=NOW.isoformat())
    assert r['posts'] == []

def test_owner_heldout_metric_rejects_train_test_overlap():
    case={'case_id':'c1','domain':'evidence','choices':['verify','guess'],
          'owner_choice':'verify','predicted_choice':'verify','source_reference':'owner-message'}
    result=evaluate(Evaluation(cases=[case]))
    assert result['agreement'] == 1 and result['total'] == 1
    assert result['wilson_95'][0] < .5 and not result['owner_thinking_model_verified']
    with pytest.raises(ValueError): Evaluation(cases=[case],calibration_case_ids=['c1'])
    with pytest.raises(ValueError): Evaluation(cases=[case,case])
    with pytest.raises(ValueError): Evaluation(cases=[{**case,'predicted_choice':'invented'}])

def test_pinterest_visible_cards_do_not_invent_authors():
    html='<a href="/pin/123/"><img alt="Solar sensor project"></a><a href="/pin/123/">duplicate</a><a href="https://evil.example/pin/234/">bad</a><a href="//evil.example/pin/345/">bad</a>'
    rows=parse_pinterest_feed(html)
    assert len(rows)==1 and rows[0]['text']=='Solar sensor project'
    assert rows[0]['handle']=='' and rows[0]['posted_at'] is None

@pytest.mark.parametrize('url,status,html',[
    ('https://www.pinterest.com/login/',200,''),
    ('https://www.pinterest.com/',429,''),
    ('https://evil.example/',200,''),
    ('https://www.pinterest.com/',200,'<iframe src="captcha"></iframe>'),
])
def test_pinterest_stops_before_recording_on_site_blocks(url,status,html):
    class Page:
        async def goto(self, target):
            self.url=url
            return type('Response',(),{'status':status})()
        async def content(self):return html
    class Sessions:
        async def page(self,*args):return Page()
    class Store:
        def record_work(self,*args,**kw):raise AssertionError('must not record')
    with pytest.raises(PlatformBlocked):
        asyncio.run(SocialReader(Sessions(),Store())._pinterest('t','feed','pc.device.session',10))


def test_editorial_revision_is_review_only_and_preserves_both_texts():
    from app.modules.c35.editorial_workflow import EditorialRevision, revision_packet
    r=revision_packet(EditorialRevision(original='I built a sensor.',revised='I made a sensor.',
                                        source_reference='owner-draft',editor='owner editor'))
    assert r['diff'] and r['original']=='I built a sensor.'
    assert r['revised']=='I made a sensor.'
    assert not r['service_called'] and not r['submission_authorized']
    assert not r['detector_evasion_performed']
    with pytest.raises(ValueError):
        revision_packet(EditorialRevision(original=' ',revised='text',source_reference='x',editor='x'))


def test_batch_cannot_bypass_audio_route(tmp_path):
    s=LocalKnowledgePipeline(tmp_path,'tenant','owner',clock=lambda:NOW)
    audio=item(0);audio.mime_type='audio/wav'
    with pytest.raises(KnowledgeError):ingest_batch(s,CorpusBatch(items=[audio]))
    assert not s.records


def test_mounted_routes_use_existing_auth_and_pinned_knowledge_dependency(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.context import require_tenant, TenantContext
    from app.modules.m25_knowledge_copilot_training.routes import router, get_service
    s=LocalKnowledgePipeline(tmp_path,'tenant','owner',clock=lambda:NOW)
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[require_tenant]=lambda:TenantContext(tenant_id='tenant',actor_id='owner')
    app.dependency_overrides[get_service]=lambda:s
    c=TestClient(app)
    r=c.post('/knowledge-copilot-training/corpus/batch',json={'items':[item(0).model_dump(mode='json')]})
    assert r.status_code==200 and r.json()['stored']==1
    assert c.get('/knowledge-copilot-training/corpus/coverage').json()['stored_sources']==1
    assert c.post('/knowledge-copilot-training/advice/prepare',json={'goal':'Grant advice'}).json()['evidence']
    assert c.post('/knowledge-copilot-training/advice/editorial-revision',json={
        'original':'I built it.','revised':'I made it.','source_reference':'owner','editor':'owner'}).status_code==200


def test_preference_algorithm_is_actually_fitted_and_executed_on_heldout_data():
    from app.modules.m19_idea_incubator.preference_ranker import RankingTrial, run_trial
    def post(i,text,liked):
        return {'post_id':i,'text':text,'liked':liked,'source_reference':f'owner-label-{i}'}
    train=[post('1','quantum sensor science',True),post('2','sensor research hardware',True),
           post('3','gossip celebrity fashion',False),post('4','celebrity gossip shoes',False)]
    test=[post('5','quantum sensor research',True),post('6','celebrity fashion gossip',False)]
    r=run_trial(RankingTrial(train=train,test=test))
    assert r['model']['weights']['sensor'] > 0
    assert r['model']['weights']['gossip'] < 0
    assert r['heldout_accuracy']==1 and r['majority_baseline_accuracy']==.5
    assert r['superior_to_baseline_on_supplied_test'] and not r['commercial_success_verified']
    with pytest.raises(ValueError): RankingTrial(train=train,test=[train[0]])
    with pytest.raises(ValueError): RankingTrial(train=train[:2],test=test)


def test_pinterest_success_stores_real_pin_ids_without_fake_publication_time():
    class Page:
        async def goto(self,target):
            self.url=target
            return type('Response',(),{'status':200})()
        async def content(self):return '<a href="/pin/123/">Sensor idea</a>'
    class Sessions:
        async def page(self,*args):return Page()
    class Store:
        rows=[]
        def record_work(self,*args,**kwargs):
            self.rows.append(kwargs);return None,True
    store=Store()
    r=asyncio.run(SocialReader(Sessions(),store)._pinterest('t','feed','pc.device.session',10))
    assert r['new']==1 and r['status']=='observed'
    assert store.rows[0]['detail']['published_at_unknown']
    assert not r['summary']['continuous_monitoring_configured']


def test_hn_route_auth_mount_and_real_adapter_dependency():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.context import require_tenant, TenantContext
    from app.modules.m19_idea_incubator.hn_routes import router, researcher
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[require_tenant]=lambda:TenantContext(tenant_id='t',actor_id='o')
    app.dependency_overrides[researcher]=lambda:HNResearch(httpx.MockTransport(
        lambda req:httpx.Response(200,json={'hits':[]})))
    c=TestClient(app)
    r=c.post('/research/hn/trends',json={'query':'sensor','as_of':NOW.isoformat()})
    assert r.status_code==200 and r.json()['measurement']['status']=='NO_SOURCE_POSTS'
    assert c.post('/research/hn/trends',json={'query':'sensor','as_of':'bad'}).status_code==422


def test_owner_evaluation_api_is_consent_bound(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m21_claire.owner_interview import InterviewStore
    from app.modules.m21_claire.owner_interview_routes import router, store
    engine=create_engine(f'sqlite:///{tmp_path/"owner.db"}',connect_args={'check_same_thread':False})
    s=InterviewStore('t','o',sessionmaker(bind=engine))
    app=FastAPI();app.include_router(router);app.dependency_overrides[store]=lambda:s
    c=TestClient(app)
    body={'cases':[{'case_id':'c','domain':'evidence','choices':['verify','guess'],
                   'owner_choice':'verify','predicted_choice':'verify','source_reference':'owner-msg'}]}
    assert c.post('/claire/interview/evaluation',json=body).status_code==403
    s.consent(True)
    assert c.post('/claire/interview/evaluation',json=body).json()['agreement']==1
    s.consent(False)
    assert c.post('/claire/interview/evaluation',json=body).status_code==403


def test_hn_success_shaped_error_and_exact_response_hash_and_byte_bound():
    import hashlib,json
    body=json.dumps({'hits':[]}).encode()
    for status in (301,403,429,500):
        with pytest.raises(ResearchUnavailable):
            HNResearch(httpx.MockTransport(lambda req:httpx.Response(status,content=body,headers={'content-type':'application/json'}))).collect('x',as_of=NOW.isoformat())
    huge=json.dumps({'hits':[],'padding':'x'*1_000_000}).encode()
    with pytest.raises(ResearchUnavailable,match='bound'):
        HNResearch(httpx.MockTransport(lambda req:httpx.Response(200,content=huge,headers={'content-type':'application/json'}))).collect('x',as_of=NOW.isoformat())
    out=HNResearch(httpx.MockTransport(lambda req:httpx.Response(200,content=body,headers={'content-type':'application/json'}))).collect('x',as_of=NOW.isoformat())
    assert out['response_sha256']==hashlib.sha256(body).hexdigest()


def test_ranker_brier_is_exact_nonzero_supplied_probability_error():
    from app.modules.m19_idea_incubator.preference_ranker import RankingTrial,run_trial
    def p(i,text,liked):return {'post_id':i,'text':text,'liked':liked,'source_reference':'synthetic'}
    trial=RankingTrial(train=[p('a','sensor science',True),p('b','fashion gossip',False)],test=[p('c','sensor science',True)])
    out=run_trial(trial);score=out['predictions'][0]['score']
    assert 0<out['brier_score']<1
    assert out['brier_score']==pytest.approx((score-1)**2)
