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

from copy import deepcopy
from app.modules.m20_general_cognitive_worker import claim_integration as core

def error(p,msg):
 with pytest.raises(ValueError)as e:core.check('integrative_thinking',p)
 assert str(e.value)==msg

@pytest.mark.parametrize('field,cap,minimum',[('reasoning_claims',128,1),('reasoning_assumptions',128,0),('reasoning_resolutions',128,0),('reasoning_frames',16,1)])
def test_row_bounds(field,cap,minimum):
 p=payload();p[field]=[{**deepcopy(p[field][0]),'id':field+str(i)}for i in range(cap)]
 if field=='reasoning_claims':p['reasoning_resolutions'][0]['premise_ids']=['p'];p['reasoning_resolutions'][0]['resolves_claim_ids']=[p[field][0]['id']]
 elif field=='reasoning_assumptions':p['reasoning_resolutions'][0]['premise_ids']=['z']
 elif field=='reasoning_frames':
  for c in p['reasoning_claims']:c['frame_id']=p[field][0]['id']
 core.check('integrative_thinking',p)
 p[field].append({**deepcopy(p[field][0]),'id':'overflow'});error(p,field+' requires bounded object list')
 if minimum:p[field]=[];error(p,field+' requires bounded object list')
 else:p[field]=[];core.check('integrative_thinking',p)


def test_schema_domains_and_constraint_bounds():
 p=payload();p['reasoning_schema'].update({str(i):['v']for i in range(30)});core.check('integrative_thinking',p)
 p['reasoning_schema']['overflow']=['v'];error(p,'reasoning_schema requires1..32 features')
 p=payload();p['reasoning_schema']={};error(p,'reasoning_schema requires1..32 features')
 p=payload();p['reasoning_schema']['color']=['red','blue']+[str(i)for i in range(14)];core.check('integrative_thinking',p)
 p['reasoning_schema']['color'].append('overflow');error(p,'schema values requires bounded text list')
 p=payload();p['reasoning_schema']['color']=[];error(p,'schema values requires bounded text list')
 p=payload();p['reasoning_frames'][0]['constraints']*=32;core.check('integrative_thinking',p)
 p['reasoning_frames'][0]['constraints'].append(deepcopy(p['reasoning_frames'][0]['constraints'][0]));error(p,'frame constraints requires bounded object list')
 p=payload();p['reasoning_schema']['color']=['red','blue']+[str(i)for i in range(14)];p['reasoning_frames'][0]['constraints'][0]['allowed_values']=p['reasoning_schema']['color'];core.check('integrative_thinking',p)
 p['reasoning_frames'][0]['constraints'][0]['allowed_values'].append('overflow');error(p,'schema values requires bounded text list')
 p=payload();p['reasoning_frames'][0]['constraints'][0]['allowed_values']=[];error(p,'constraint values requires bounded text list')

@pytest.mark.parametrize('change,msg',[
 ('duplicate_frame','unique frame IDs required'),('unknown_constraint_feature','known constraint feature and schema values required'),('unknown_constraint_value','known constraint feature and schema values required'),('duplicate_claim','globally unique evidence IDs with schema feature/value required'),('duplicate_assumption_claim','globally unique evidence IDs with schema feature/value required'),('unknown_claim_feature','globally unique evidence IDs with schema feature/value required'),('unknown_claim_value','globally unique evidence IDs with schema feature/value required'),('unknown_frame','known claim frame required'),('duplicate_resolution','unique resolutions with known schema and evidence references required'),('unknown_premise','unique resolutions with known schema and evidence references required'),('assumption_as_claim','unique resolutions with known schema and evidence references required'),('resolution_feature','unique resolutions with known schema and evidence references required'),('resolution_value','unique resolutions with known schema and evidence references required')])
def test_exact_validators(change,msg):
 p=payload()
 if change=='duplicate_frame':p['reasoning_frames']*=2
 elif change=='unknown_constraint_feature':p['reasoning_frames'][0]['constraints'][0]['feature']='unknown'
 elif change=='unknown_constraint_value':p['reasoning_frames'][0]['constraints'][0]['allowed_values']=['unknown']
 elif change=='duplicate_claim':p['reasoning_claims'].append(deepcopy(p['reasoning_claims'][0]))
 elif change=='duplicate_assumption_claim':p['reasoning_assumptions'][0]['id']='z'
 elif change=='unknown_claim_feature':p['reasoning_claims'][0]['feature']='unknown'
 elif change=='unknown_claim_value':p['reasoning_claims'][0]['value']='unknown'
 elif change=='unknown_frame':p['reasoning_claims'][0]['frame_id']='unknown'
 elif change=='duplicate_resolution':p['reasoning_resolutions']*=2
 elif change=='unknown_premise':p['reasoning_resolutions'][0]['premise_ids']=['unknown']
 elif change=='assumption_as_claim':p['reasoning_resolutions'][0]['resolves_claim_ids']=['p']
 elif change=='resolution_feature':p['reasoning_resolutions'][0]['feature']='unknown'
 else:p['reasoning_resolutions'][0]['value']='unknown'
 error(p,msg)

@pytest.mark.parametrize('bank,field,label',[('reasoning_frames','source','frame source'),('reasoning_claims','id','reasoning_claims id'),('reasoning_claims','source','reasoning_claims source'),('reasoning_assumptions','source','reasoning_assumptions source'),('reasoning_resolutions','source','resolution source')])
def test_text_source_validators(bank,field,label):
 p=payload();p[bank][0][field]='';error(p,label+' requires bounded nonempty string')

@pytest.mark.parametrize('field,label',[('premise_ids','premise_ids'),('resolves_claim_ids','resolves_claim_ids')])
def test_empty_and_duplicate_reference_sets(field,label):
 p=payload();p['reasoning_resolutions'][0][field]=[];error(p,label+' requires bounded text list')
 p=payload();p['reasoning_resolutions'][0][field]=['z','z'];error(p,label+' requires unique keys')


def test_every_resolution_support_gate_independent():
 p=payload();r=p['reasoning_resolutions'][0];r['premise_ids']=['z','a'];out=run('dialectical_reasoning',p)
 assert out['resolution_reports'][0]['contradicting_premise_ids']==['a'] and out['unresolved_features']==['color']
 p=payload();r=p['reasoning_resolutions'][0];r['premise_ids']=['s'];out=run('dialectical_reasoning',p)
 assert out['resolution_reports'][0]['supporting_premise_ids']==[] and out['resolution_reports'][0]['supported'] is False
 p=payload();p['reasoning_resolutions'][0]['resolves_claim_ids']=['z'];out=run('dialectical_reasoning',p)
 assert out['resolution_reports'][0]['uncovered_claim_ids']==['a'] and out['resolution_reports'][0]['supported'] is False
 p=payload();p['reasoning_resolutions'][0]['resolves_claim_ids'].append('s');out=run('dialectical_reasoning',p)
 assert out['resolution_reports'][0]['wrong_feature_claim_ids']==['s'] and out['resolution_reports'][0]['supported'] is False
 p=payload();p['reasoning_claims'][1]['value']='red';out=run('dialectical_reasoning',p)
 assert out['contradictions']==[] and out['status']=='no_conflicts' and out['resolution_reports'][0]['supported'] is False


def test_competing_resolutions_no_silent_winner_and_no_resolution():
 p=payload();p['reasoning_resolutions'].append({'id':'a','feature':'color','value':'blue','premise_ids':['a'],'resolves_claim_ids':['a','z'],'source':'a'})
 r=run('dialectical_reasoning',p);assert r['status']=='no_supported_resolution' and r['competing_resolution_features']==r['unresolved_features']==['color']
 assert [x['id']for x in r['resolution_reports']]==['a','r'] and all(x['supported']for x in r['resolution_reports'])
 p['reasoning_resolutions']=[];r=run('dialectical_reasoning',p);assert r['unresolved_features']==['color'] and r['resolution_reports']==[]


def test_unsorted_evidence_frames_sources_and_all_constraints():
 p=payload();p['reasoning_frames'].reverse();p['reasoning_assumptions'].append({'id':'a0','feature':'shape','value':'round','source':'a0'});p['reasoning_resolutions'][0]['premise_ids']=['z','p','a0']
 r=run('dialectical_reasoning',p)
 assert [x['id']for x in r['claims']]==['a','s','z'] and [x['id']for x in r['assumptions']]==['a0','p'] and [x['id']for x in r['frames']]==['f1','f2']
 assert r['resolution_reports'][0]['premise_ids']==['a0','p','z'] and r['resolution_reports'][0]['premise_sources']==['a0','p','z'] and r['resolution_reports'][0]['resolves_claim_ids']==['a','z']
 p=payload();p['reasoning_frames'][1]['constraints'][0]['allowed_values']=['red'];p['reasoning_frames'][1]['constraints'].append({'feature':'color','allowed_values':['blue'],'source':'contrary'})
 r=run('integrative_thinking',p);assert r['resolution_reports'][0]['violated_frames']==['f2']
 assert r['invented_synthesis'] is None and r['boundary']=='Finite sourced schema feature/value contradictions and caller-supplied resolutions only. A resolution must cite agreeing premises without same-feature contrary premises, cover all conflicting claims and, for integration, satisfy every supplied frame constraint. Competing supported values stay unresolved. No independent truth, novel synthesis or real-world conflict resolution.'


def test_constraint_value_cap_and_reference_caps_unmasked():
 p=payload();p['reasoning_schema']['color']=['red','blue']+[str(i)for i in range(14)];p['reasoning_frames'][0]['constraints'][0]['allowed_values']=list(p['reasoning_schema']['color']);core.check('integrative_thinking',p)
 p['reasoning_frames'][0]['constraints'][0]['allowed_values'].append('overflow');error(p,'constraint values requires bounded text list')
 p=payload();p['reasoning_claims']=[{'id':str(i),'feature':'color','value':'red','frame_id':'f1','source':str(i)}for i in range(128)];r=p['reasoning_resolutions'][0];r['resolves_claim_ids']=[str(i)for i in range(128)];r['premise_ids']=[str(i)for i in range(64)];core.check('integrative_thinking',p)
 r['premise_ids'].append('64');error(p,'premise_ids requires bounded text list')
 r['premise_ids']=['0'];r['resolves_claim_ids'].append('overflow');error(p,'resolves_claim_ids requires bounded text list')
