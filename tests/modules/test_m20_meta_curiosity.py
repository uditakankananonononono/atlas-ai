"""Bounded supplied local corpus investigations, not autonomous discovery."""
from copy import deepcopy
import pytest
import sqlalchemy as sa
from app.modules.m20_general_cognitive_worker.curiosity_investigator import CuriosityInvestigator
from app.modules.m20_general_cognitive_worker.meta_persistence import MetaRepository

def investigator(tmp_path,tenant='a'):
 r=MetaRepository(sa.create_engine(f'sqlite:///{tmp_path}/curiosity.sqlite'),tenant_id=tenant);r.create_schema();return CuriosityInvestigator.load(r)
def source(key='s',answers=None):return {'source_id':key,'provenance':'fixture:'+key,'answers':{'question-key':'known answer'}if answers is None else answers}
def question(key='q',probability=.5,relevance=1,cost=1,frequency=1,lookup='question-key'):
 return {'question_id':key,'question':'What is the answer?','lookup_key':lookup,'prior_probability':probability,'decision_relevance':relevance,'cost':cost,'frequency':frequency,'source_ids':['s']}
def setup(m):return m.authorize([source()],preauthorized=True,budget=5)

def test_information_rubric_outperforms_frequency_and_executes(tmp_path):
 m=investigator(tmp_path);setup(m)
 rows=[question('low',.01,.1,1,100),question('high',.5,1,1,1),question('costly',.5,.8,4,5)];m.enqueue(rows)
 ranked=m.queue();assert [r['question_id']for r in ranked]==['high','costly','low']
 assert ranked[0]['priority']==1 and ranked[0]['uncertainty_bits']==1 and ranked[0]['expected_learning_value'] is None
 assert max(rows,key=lambda r:r['frequency'])['question_id']=='low'
 result=m.run(max_cost=1);assert result['spent']==1 and result['remaining_budget']==4
 assert result['investigations'][0]['question_id']=='high' and result['investigations'][0]['status']=='answered'
 assert result['investigations'][0]['answer']=='known answer' and result['investigations'][0]['gap_narrowed'] is True
 assert result['investigations'][0]['source_records']==[{'source_id':'s','provenance':'fixture:s','lookup_key':'question-key','answer':'known answer'}]
 assert m.state['questions']['high']['status']=='answered' and m.state['questions']['low']['status']=='unresolved'
 assert m.state['results']['high']==result['investigations'][0]
 assert investigator(tmp_path).state==m.state and investigator(tmp_path,'b').state['questions']=={}

def test_budget_no_answer_conflict_duplicate_and_no_disallowed_lookup(tmp_path):
 m=investigator(tmp_path);setup(m);m.enqueue([question(cost=2,lookup='missing')]);revision=m._revision
 assert m.run(max_cost=1)['investigations']==[] and m._revision==revision
 r=m.run(max_cost=2);assert r['investigations'][0]['status']=='no_answer' and r['investigations'][0]['gap_narrowed'] is False and r['spent']==2
 assert r['investigations'][0]['source_records']==[{'source_id':'s','provenance':'fixture:s','lookup_key':'missing','answer':None}]
 rev=m._revision;assert m.enqueue([question(cost=2,lookup='missing')])['inserted']==0 and m._revision==rev
 assert m.run(max_cost=5)['investigations']==[] and m.state['spent']==2
 with pytest.raises(ValueError):m.enqueue([question(cost=3,lookup='missing')])
 with pytest.raises(ValueError):m.enqueue([{**question('bad'),'source_ids':['forbidden']}])
 conflict=investigator(tmp_path,'conflict');conflict.authorize([source(),source('second',{'question-key':'other answer'})],preauthorized=True,budget=2)
 conflict.enqueue([{**question(),'source_ids':['s','second']}]);result=conflict.run(max_cost=2)['investigations'][0]
 assert result['status']=='conflicting_sources' and result['answer'] is None and result['gap_narrowed'] is False
 assert [row['source_id']for row in result['source_records']]==['s','second']

def test_authorization_and_invalid_unmasked_guards(tmp_path):
 m=investigator(tmp_path)
 with pytest.raises(ValueError):m.enqueue([question()])
 for value in [False,1,'yes']:
  with pytest.raises(ValueError):m.authorize([source()],preauthorized=value,budget=5)
 setup(m)
 for change in [{'question_id':''},{'lookup_key':''},{'question':''},{'prior_probability':True},{'prior_probability':float('nan')},{'prior_probability':1.1},{'decision_relevance':-.1},{'cost':0},{'cost':True},{'frequency':0},{'source_ids':[]},{'source_ids':['s','s']}]:
  with pytest.raises(ValueError):m.enqueue([{**question('fresh'),**change}])
 assert m.state['questions']=={}
 for cost in [-1,True,float('nan'),1001]:
  with pytest.raises(ValueError):m.run(max_cost=cost)

def test_atomic_stale_and_rollback(tmp_path,monkeypatch):
 a,b=investigator(tmp_path),investigator(tmp_path);setup(a)
 with pytest.raises(RuntimeError,match='stale'):setup(b)
 assert b.state['sources']=={}
 a.enqueue([question()]);before=deepcopy(a.state)
 def fail(session):raise RuntimeError('rollback')
 monkeypatch.setattr(a.repo,'_before_commit',fail)
 with pytest.raises(RuntimeError):a.run(max_cost=1)
 assert a.state==before==investigator(tmp_path).state

@pytest.mark.parametrize('probability',[0,1])
def test_no_uncertainty_has_zero_rubric_priority(tmp_path,probability):
 m=investigator(tmp_path);setup(m);m.enqueue([question(probability=probability)])
 assert m.queue()[0]['priority']==0
 assert m.run(max_cost=1)['investigations']==[]

def test_mounted_tenant_auth_authorization_and_results(tmp_path,monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker import curiosity_investigator_routes as routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_investigators',{})
 with pytest.raises(ValueError):routes.bind_investigator(object())
 m=investigator(tmp_path);routes.bind_investigator(m);c=TestClient(app);p='/api/v1/api/modules/20/curiosity-investigator';h=oidc_auth_headers('a','owner')
 payload={'sources':[source()],'preauthorized':True,'budget':5}
 assert c.post(p+'/authorize',json=payload).status_code==401
 assert c.post(p+'/authorize',headers=h,json=payload).status_code==200
 assert c.post(p+'/enqueue',headers=h,json={'records':[question()]}).status_code==200
 assert c.get(p+'/queue',headers=h).json()['queue'][0]['question_id']=='q'
 assert c.post(p+'/run',headers=h,json={'max_cost':1}).json()['investigations'][0]['gap_narrowed'] is True
 assert c.get(p+'/queue',headers=oidc_auth_headers('b','owner')).status_code==503
 assert c.post(p+'/run',headers=h,json={'extra':1}).status_code==422
 stale=investigator(tmp_path);m.enqueue([question('new')]);routes.bind_investigator(stale)
 assert c.post(p+'/enqueue',headers=h,json={'records':[question('stale')]}).status_code==409

def test_total_budget_exhaustion_and_cheaper_skip(tmp_path):
 m=investigator(tmp_path);m.authorize([source()],preauthorized=True,budget=2)
 m.enqueue([question('first',cost=1),question('second',cost=1),question('third',cost=1)])
 r=m.run(max_cost=2);assert [x['question_id']for x in r['investigations']]==['first','second'] and r['total_spent']==2 and r['remaining_budget']==0
 assert m.run(max_cost=1000)['investigations']==[]
 with pytest.raises(ValueError):setup(m)
 skip=investigator(tmp_path,'skip');setup(skip);skip.enqueue([question('expensive',cost=2),question('cheap',relevance=.1,cost=1)])
 assert skip.run(max_cost=1)['investigations'][0]['question_id']=='cheap'

def test_source_shape_guards_exact_caps_and_question_total(tmp_path):
 m=investigator(tmp_path)
 for records in [[],[source('same'),source('same')],[source(str(i))for i in range(33)],[{**source(),'answers':[]}],[{**source(),'answers':{'k':''}}]]:
  with pytest.raises(ValueError):m.authorize(records,preauthorized=True,budget=5)
 for budget in [0,1000.1,True,float('nan')]:
  with pytest.raises(ValueError):m.authorize([source()],preauthorized=True,budget=budget)
 assert m.authorize([source(str(i))for i in range(32)],preauthorized=True,budget=1000)['budget']==1000
 rows=[{**question(str(i)),'source_ids':['0']}for i in range(1000)]
 assert m.enqueue(rows)['inserted']==1000
 with pytest.raises(ValueError):m.enqueue([{**question('1001'),'source_ids':['0']}])
 assert len(m.state['questions'])==1000

def test_mounted_invalid_authority_and_overflow(tmp_path,monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker import curiosity_investigator_routes as routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_investigators',{})
 m=investigator(tmp_path);routes.bind_investigator(m);c=TestClient(app);p='/api/v1/api/modules/20/curiosity-investigator';h=oidc_auth_headers('a','owner')
 assert c.post(p+'/authorize',headers=h,json={'sources':[source()],'preauthorized':1,'budget':5}).status_code==422
 setup(m)
 assert c.post(p+'/enqueue',headers=h,json={'records':[{**question(),'source_ids':['forbidden']}]}).status_code==422
 assert c.post(p+'/run',headers=h,json={'max_cost':10**400}).status_code==422

def test_exact_priority_components_order_flips_and_id_ties(tmp_path):
 m=investigator(tmp_path);setup(m)
 m.enqueue([question('costly',relevance=.8,cost=4),question('a',relevance=.5,cost=1),question('z',relevance=.5,cost=1)])
 ranked=m.queue();assert [r['question_id']for r in ranked]==['a','z','costly']
 assert ranked[2]['priority']==.2
 assert all(r['rubric']=='binary entropy times supplied decision relevance divided by supplied lookup cost'for r in ranked)
 relevance=investigator(tmp_path,'relevance');setup(relevance)
 relevance.enqueue([question('z-high',relevance=1,cost=2),question('a-low',relevance=.1,cost=1)])
 assert [r['question_id']for r in relevance.queue()]==['z-high','a-low']
 cost=investigator(tmp_path,'cost');setup(cost)
 cost.enqueue([question('a-expensive',relevance=1,cost=4),question('z-cheap',relevance=.8,cost=1)])
 assert [r['question_id']for r in cost.queue()]==['z-cheap','a-expensive']

@pytest.mark.parametrize('change',[{'decision_relevance':1.5},{'cost':1000.1},{'frequency':True},{'frequency':1.5},{'frequency':'3'},{'frequency':1000001}])
def test_unmasked_question_upper_and_type_guards(tmp_path,change):
 m=investigator(tmp_path);setup(m)
 with pytest.raises(ValueError):m.enqueue([{**question('fresh'),**change}])
 assert m.state['questions']=={}

def test_exact_cost_frequency_source_count_and_sorted_ids(tmp_path):
 m=investigator(tmp_path);ids=[f's{i:02}'for i in range(32)]
 m.authorize([source(key)for key in ids],preauthorized=True,budget=1000)
 r={**question(cost=1000,frequency=1000000),'source_ids':ids[::-1]}
 assert m.enqueue([r])['inserted']==1 and m.queue()[0]['source_ids']==ids
 assert m.state['questions']['q']['cost']==1000 and m.state['questions']['q']['frequency']==1000000
 with pytest.raises(ValueError):m.enqueue([{**question('33'),'source_ids':ids+['extra']}])

@pytest.mark.parametrize('record',[{'source_id':'','provenance':'fixture','answers':{}},{'source_id':'s','provenance':'','answers':{}},{'source_id':'s','answers':{}},[]])
def test_source_guard_errors_are_valueerror(tmp_path,record):
 m=investigator(tmp_path)
 with pytest.raises(ValueError):m.authorize([record],preauthorized=True,budget=1)
 assert m.state['sources']=={}

def test_answer_cap_question_shape_and_unauthorized_run(tmp_path):
 m=investigator(tmp_path)
 with pytest.raises(ValueError):m.run(max_cost=1)
 answers={str(i):'answer'for i in range(1000)}
 assert m.authorize([source(answers=answers)],preauthorized=True,budget=1)['status']=='local_corpus_authorized'
 other=investigator(tmp_path,'other')
 with pytest.raises(ValueError):other.authorize([source(answers={**answers,'1001':'answer'})],preauthorized=True,budget=1)
 with pytest.raises(ValueError):m.enqueue([[]])
 with pytest.raises(ValueError):m.enqueue([question(str(i))for i in range(1001)])

def test_full_investigation_record_honesty_and_mounted_boundary(tmp_path,monkeypatch,oidc_auth_headers):
 m=investigator(tmp_path);setup(m);m.enqueue([question()]);result=m.run(max_cost=1)['investigations'][0]
 assert result=={'question_id':'q','question':'What is the answer?','status':'answered','answer':'known answer','gap_narrowed':True,'source_records':[{'source_id':'s','provenance':'fixture:s','lookup_key':'question-key','answer':'known answer'}],'cost':1,'priority':1,'source_truth_verified':False,'boundary':m.boundary}
 from app.main import app
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker import curiosity_investigator_routes as routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_investigators',{});routes.bind_investigator(m)
 response=TestClient(app).get('/api/v1/api/modules/20/curiosity-investigator/queue',headers=oidc_auth_headers('a','owner'))
 assert response.status_code==200 and response.json()['boundary']==m.boundary

def test_equal_priority_id_order_not_insertion_order(tmp_path):
 m=investigator(tmp_path);setup(m);m.enqueue([question('b'),question('a')])
 assert [r['question_id']for r in m.queue()]==['a','b']
 assert [r['question_id']for r in m.run(max_cost=2)['investigations']]==['a','b']
