"""Sourced predeclared falsification scoring and actual replication artifacts."""
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Fixture','url':'https://example.org/protocol'}
def packet():return {'source':SRC,'problem':'Treatment comparison','scientific_protocol':{'id':'p','hypothesis':'Treatment outcome exceeds control by at least2','source':'protocol:p','predeclared':True,'independent_variable':{'id':'group','operational_definition':'Assigned control/treatment label','source':'iv'},'outcome_variable':{'id':'score','unit':'points','operational_definition':'Recorded test score','source':'dv'},'prediction':{'minimum_effect':2,'falsify_at_or_below':0,'minimum_per_group':2},'controls':[{'id':'same-test','description':'Same scoring procedure','source':'control'}],'procedure':['assign group','measure score'],'confounds':[{'id':'c','description':'Unequal prior score','controlled':True,'source':'confound'}],'replication_artifacts':[{'kind':'protocol','artifact_ref':'repo:protocol','source':'a1'},{'kind':'data','artifact_ref':'repo:data','source':'a2'},{'kind':'analysis','artifact_ref':'repo:analysis','source':'a3'}]},'scientific_observations':[{'id':'c1','group':'control','value':1,'protocol_id':'p','source':'c1'},{'id':'c2','group':'control','value':3,'protocol_id':'p','source':'c2'},{'id':'t1','group':'treatment','value':4,'protocol_id':'p','source':'t1'},{'id':'t2','group':'treatment','value':6,'protocol_id':'p','source':'t2'}]}
def run(p):return execute('scientific_thinking',p)['result']['scientific_check']
def test_predeclared_effect_scored_and_replication_checklist():
 r=run(packet());assert r['effect']=='3' and r['group_means']=={'control':'2','treatment':'5'} and r['status']=='confirming_supplied_data'
 assert r['replication_missing_kinds']==[] and r['replication_artifacts_complete'] is True and r['replication_performed'] is False and r['hypothesis_truth_verified'] is False
 p=packet();p['scientific_observations'][2]['value']=0;p['scientific_observations'][3]['value']=2;assert run(p)['status']=='disconfirming_supplied_data'
 p=packet();p['scientific_observations'][2]['value']=2;p['scientific_observations'][3]['value']=4;assert run(p)['status']=='inconclusive_supplied_data'
def test_sparse_data_and_uncontrolled_confound():
 p=packet();p['scientific_observations']=p['scientific_observations'][:3];assert run(p)['status']=='inconclusive_insufficient_data'
 p=packet();p['scientific_protocol']['confounds'][0]['controlled']=False;r=run(p);assert r['status']=='inconclusive_uncontrolled_confounds' and r['uncontrolled_confound_ids']==['c']
def test_no_protocol_minimal_refuses():
 with pytest.raises(LearningReasoningError):run({'source':SRC,'problem':'x'})
def test_mounted_auth_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner');path='/api/v1/api/modules/20/learning-reasoning-810-859/scientific_thinking';p=packet()
 assert c.post(path,json={'payload':p}).status_code==401
 assert c.post(path,headers=h,json={'payload':p}).status_code==200
 assert c.post(path,headers=h,json={'payload':{'source':SRC,'problem':'x'}}).status_code==422
 assert c.post(path,headers=h,json={'payload':{**p,'resource_refs':[{'tenant_id':'b'}]}}).status_code==403
