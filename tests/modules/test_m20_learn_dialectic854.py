"""Declared sourced claim contradictions and premise-linked resolution checks."""
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Fixture','url':'https://example.org/frames'}
def payload():return {'source':SRC,'reasoning_schema':{'color':['red','blue'],'shape':['round','square']},'reasoning_claims':[{'id':'z','frame_id':'f1','feature':'color','value':'red','source':'z'},{'id':'a','frame_id':'f2','feature':'color','value':'blue','source':'a'},{'id':'s','frame_id':'f1','feature':'shape','value':'round','source':'s'}],'reasoning_assumptions':[{'id':'p','feature':'color','value':'red','source':'p'}],'reasoning_resolutions':[{'id':'r','feature':'color','value':'red','premise_ids':['z','p'],'resolves_claim_ids':['z','a'],'source':'r'}],'reasoning_frames':[{'id':'f1','constraints':[{'feature':'color','allowed_values':['red'],'source':'c1'}],'source':'f1'},{'id':'f2','constraints':[{'feature':'color','allowed_values':['blue'],'source':'c2'}],'source':'f2'}]}
def run(method,p):return execute(method,p)['result']['dialectic_check'if method=='dialectical_reasoning'else'integration_check']
def test_dialectic_conflict_and_premise_supported_resolution():
 r=run('dialectical_reasoning',payload());assert r['contradictions']==[{'feature':'color','values':['blue','red'],'claim_ids':['a','z']}]
 assert r['resolution_reports'][0]['supported'] is True and r['unresolved_features']==[] and r['source_truth_verified'] is False
 p=payload();p['reasoning_resolutions'][0]['premise_ids']=['a'];r=run('dialectical_reasoning',p)
 assert r['resolution_reports'][0]['supported'] is False and r['unresolved_features']==['color']
def test_integration_checks_every_frame_preserves_tradeoff():
 r=run('integrative_thinking',payload());assert r['status']=='no_supported_resolution' and r['resolution_reports'][0]['violated_frames']==['f2'] and r['unresolved_features']==['color']
 p=payload();p['reasoning_frames'][1]['constraints'][0]['allowed_values']=['blue','red'];r=run('integrative_thinking',p)
 assert r['status']=='supported_resolution' and r['resolution_reports'][0]['supported'] is True
@pytest.mark.parametrize('method',['dialectical_reasoning','integrative_thinking'])
def test_minimal_refuses(method):
 with pytest.raises(LearningReasoningError):run(method,{'source':SRC})
def test_mounted_auth_and_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method in ['dialectical_reasoning','integrative_thinking']:
  p=payload();path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':p}).status_code==401
  assert c.post(path,headers=h,json={'payload':p}).status_code==200
  assert c.post(path,headers=h,json={'payload':{'source':SRC}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**p,'resource_refs':[{'tenant_id':'b'}]}}).status_code==403
