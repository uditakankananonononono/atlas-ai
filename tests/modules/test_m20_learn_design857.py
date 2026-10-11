"""Supplied prototype revision and finite typed algorithm DAG execution."""
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Fixture','url':'https://example.org/design'}
def design():return {'source':SRC,'problem':'Access','design_brief':{'audience':'supplied participant group','constraints':[{'id':'c','feature':'cost','minimum':0,'maximum':10,'source':'brief:c'}]},'design_prototypes':[{'id':'a','features':{'cost':12},'source':'prototype:a'},{'id':'b','features':{'cost':8},'source':'prototype:b'}],'design_feedback':[{'id':'e','prototype_id':'a','feature':'cost','suggested_value':6,'source':'participant:e'}],'design_revisions':[{'id':'r','base_prototype_id':'a','feedback_ids':['e'],'changes':{'cost':6},'source':'revision:r'}]}
def compute():return {'source':SRC,'problem':'Sum','algorithm_inputs':[{'id':'x','type':'number','value':2},{'id':'y','type':'number','value':3}],'algorithm_nodes':[{'id':'sum','op':'add','args':['x','y'],'source':'node:sum'},{'id':'double','op':'multiply','args':['sum','x'],'source':'node:double'}],'algorithm_outputs':['double'],'algorithm_tests':[{'id':'test','inputs':{'x':4,'y':1},'expected_outputs':{'double':20},'source':'test:test'}]}
def run(method,p):return execute(method,p)['result']['design_check'if method=='design_thinking'else'algorithm_run']
def test_design_checks_prototypes_and_feedback_bound_revision():
 r=run('design_thinking',design());assert r['prototype_reports']==[{'id':'a','violated_constraints':['c'],'feasible':False,'source':'prototype:a'},{'id':'b','violated_constraints':[],'feasible':True,'source':'prototype:b'}]
 assert r['revision_reports'][0]['supported'] is True and r['revision_reports'][0]['features']=={'cost':'6'} and r['revision_reports'][0]['violated_constraints']==[]
 p=design();p['design_revisions'][0]['changes']['cost']=7;r=run('design_thinking',p);assert r['revision_reports'][0]['supported'] is False and r['revision_reports'][0]['unbacked_features']==['cost']
def test_algorithm_executes_typed_dag_and_supplied_tests():
 r=run('computational_thinking',compute());assert r['outputs']=={'double':'10'} and r['execution_order']==['sum','double']
 assert r['test_reports']==[{'id':'test','actual_outputs':{'double':'20'},'expected_outputs':{'double':'20'},'passed':True,'source':'test:test'}]
 assert r['complexity']=={'model':'unit-cost arithmetic on bounded rational/boolean scalars','input_count':2,'node_count':2,'edge_count':4,'per_execution_steps':2,'test_execution_steps':2,'time_bound':'O(I + V + E) per execution; O((T+1)*(I+V+E)) including tests','space_bound':'O(I+V+E+T*O) including reports'}
 assert r['source_truth_verified'] is False and r['general_computational_thinking'] is None
@pytest.mark.parametrize('method',['design_thinking','computational_thinking'])
def test_minimal_refuses(method):
 with pytest.raises(LearningReasoningError):run(method,{'source':SRC,'problem':'x'})
def test_mounted_auth_and_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method,p in [('design_thinking',design()),('computational_thinking',compute())]:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':p}).status_code==401
  assert c.post(path,headers=h,json={'payload':p}).status_code==200
  assert c.post(path,headers=h,json={'payload':{'source':SRC,'problem':'x'}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**p,'resource_refs':[{'tenant_id':'b'}]}}).status_code==403
