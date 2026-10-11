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

from copy import deepcopy
from app.modules.m20_general_cognitive_worker import scientific_protocol as core

def error(p,msg):
 with pytest.raises(ValueError)as e:core.check(p)
 assert str(e.value)==msg

@pytest.mark.parametrize('change,msg',[('predeclared','explicit predeclared protocol required'),('variables','distinct operational variable IDs required'),('thresholds','ordered disjoint effect thresholds and integer minimum_per_group[1,128] required'),('minimum','ordered disjoint effect thresholds and integer minimum_per_group[1,128] required'),('control_dup','unique control IDs required'),('confound_dup','unique confounds with boolean controlled required'),('confound_bool','unique confounds with boolean controlled required'),('artifact_kind','supported artifact kind and unique artifact_ref required'),('artifact_dup','supported artifact kind and unique artifact_ref required'),('observation_dup','unique observations bound to known group and exact protocol required'),('group','unique observations bound to known group and exact protocol required'),('protocol','unique observations bound to known group and exact protocol required'),('source','observation source requires bounded nonempty string'),('numeric','observation value requires rational string/integer')])
def test_protocol_validators(change,msg):
 p=packet();q=p['scientific_protocol']
 if change=='predeclared':q['predeclared']=1
 elif change=='variables':q['outcome_variable']['id']='group'
 elif change=='thresholds':q['prediction']['minimum_effect']=0
 elif change=='minimum':q['prediction']['minimum_per_group']=True
 elif change=='control_dup':q['controls']*=2
 elif change=='confound_dup':q['confounds']*=2
 elif change=='confound_bool':q['confounds'][0]['controlled']=1
 elif change=='artifact_kind':q['replication_artifacts'][0]['kind']='unknown'
 elif change=='artifact_dup':q['replication_artifacts'].append(deepcopy(q['replication_artifacts'][0]))
 elif change=='observation_dup':p['scientific_observations'].append(deepcopy(p['scientific_observations'][0]))
 elif change=='group':p['scientific_observations'][0]['group']='unknown'
 elif change=='protocol':p['scientific_observations'][0]['protocol_id']='different'
 elif change=='source':p['scientific_observations'][0]['source']=''
 else:p['scientific_observations'][0]['value']=True
 error(p,msg)


def test_exact_thresholds_order_sparse_no_data_artifact_gaps():
 p=packet();p['scientific_observations'][2]['value']=3;p['scientific_observations'][3]['value']=5;assert core.check(p)['effect']=='2' and core.check(p)['status']=='confirming_supplied_data'
 p['scientific_observations'][2]['value']=1;p['scientific_observations'][3]['value']=3;assert core.check(p)['effect']=='0' and core.check(p)['status']=='disconfirming_supplied_data'
 p['scientific_observations']=[];r=core.check(p);assert r['effect'] is None and r['group_means']=={'control':None,'treatment':None} and r['status']=='inconclusive_insufficient_data'
 p=packet();p['scientific_protocol']['replication_artifacts']=[];r=core.check(p);assert r['replication_missing_kinds']==['analysis','data','protocol'] and r['replication_artifacts_complete'] is False and r['replication_performed'] is False
 p=packet();before=deepcopy(p);r=core.check(p);assert p==before;p['scientific_observations'].reverse();assert core.check(p)==r
 assert [x['id']for x in r['observations']]==['c1','c2','t1','t2'] and r['predeclaration_verified'] is False and r['statistical_significance'] is None
 assert r['observations'][0]['source']=='c1' and r['protocol_source']=='protocol:p' and r['controls'][0]['source']=='control'

@pytest.mark.parametrize('name,cap,minimum',[('controls',32,1),('confounds',32,0),('replication_artifacts',16,0)])
def test_protocol_row_caps(name,cap,minimum):
 p=packet();q=p['scientific_protocol'];row=q[name][0];q[name]=[{**deepcopy(row),('artifact_ref'if name=='replication_artifacts'else'id'):str(i)}for i in range(cap)];core.check(p)
 q[name].append({**deepcopy(row),('artifact_ref'if name=='replication_artifacts'else'id'):'overflow'});error(p,name+' requires bounded object list')
 if minimum:q[name]=[];error(p,name+' requires bounded object list')
 else:q[name]=[];core.check(p)


def test_observation_minimum_procedure_bounds_and_effect_limit():
 p=packet();p['scientific_observations']=[{**p['scientific_observations'][0],'id':str(i),'group':'control'if i<128 else'treatment'}for i in range(256)];p['scientific_protocol']['prediction']['minimum_per_group']=128;assert core.check(p)['group_counts']=={'control':128,'treatment':128}
 p['scientific_observations'].append({**p['scientific_observations'][0],'id':'overflow'});error(p,'scientific_observations requires bounded object list')
 p=packet();p['scientific_protocol']['prediction']['minimum_per_group']=129;error(p,'ordered disjoint effect thresholds and integer minimum_per_group[1,128] required')
 p=packet();p['scientific_protocol']['procedure']=[str(i)for i in range(32)];r=core.check(p);assert r['procedure']==p['scientific_protocol']['procedure']
 p['scientific_protocol']['procedure'].append('overflow');error(p,'procedure requires bounded text list')
 p['scientific_protocol']['procedure']=[];error(p,'procedure requires bounded text list')
 p=packet();p['scientific_protocol']['procedure']=['same','same'];error(p,'procedure requires unique keys')
 p=packet();p['scientific_protocol']['prediction']['minimum_per_group']=1;p['scientific_observations']=[{**p['scientific_observations'][0],'value':-10**12},{**p['scientific_observations'][2],'value':10**12}];error(p,'computed effect/mean rational components exceed10**12')
