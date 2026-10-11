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

from copy import deepcopy
from app.modules.m20_general_cognitive_worker import design_algorithms as core

def error(fn,p,msg):
 with pytest.raises(ValueError)as e:fn(p)
 assert str(e.value)==msg

@pytest.mark.parametrize('op,args,value',[('add',[2,3],'5'),('subtract',[2,3],'-1'),('multiply',[2,3],'6'),('divide',[2,3],'2/3'),('less_than',[2,3],True),('equal',[2,3],False),('and',[True,False],False),('or',[True,False],True),('not',[True],False),('select',[False,2,3],'3')])
def test_all_operations(op,args,value):
 p=compute();p['algorithm_inputs']=[{'id':str(i),'type':'boolean'if type(v)is bool else'number','value':v}for i,v in enumerate(args)];p['algorithm_nodes']=[{'id':'n','op':op,'args':[str(i)for i in range(len(args))],'source':'n'}];p['algorithm_outputs']=['n'];p['algorithm_tests']=[]
 assert core.algorithm(p)['outputs']=={'n':value}

@pytest.mark.parametrize('change,msg',[('duplicate_input','unique typed number/boolean inputs required'),('bad_type','unique typed number/boolean inputs required'),('bool_number','input value requires rational string/integer'),('duplicate_node','unique supported typed nodes with exact arity required'),('arity','unique supported typed nodes with exact arity required'),('unknown_arg','known argument/output references required'),('unknown_output','known argument/output references required'),('cycle','algorithm must be acyclic'),('mismatch','node argument type mismatch'),('zero','algorithm division by zero'),('overflow','algorithm result rational components exceed10**12'),('test_input','unique tests with exact input/output schema required'),('test_output','unique tests with exact input/output schema required'),('duplicate_test','unique tests with exact input/output schema required')])
def test_algorithm_errors(change,msg):
 p=compute()
 if change=='duplicate_input':p['algorithm_inputs']*=2
 elif change=='bad_type':p['algorithm_inputs'][0]['type']='string'
 elif change=='bool_number':p['algorithm_inputs'][0]['value']=True
 elif change=='duplicate_node':p['algorithm_nodes'].append(deepcopy(p['algorithm_nodes'][0]))
 elif change=='arity':p['algorithm_nodes'][0]['args']=['x']
 elif change=='unknown_arg':p['algorithm_nodes'][0]['args'][0]='unknown'
 elif change=='unknown_output':p['algorithm_outputs']=['unknown']
 elif change=='cycle':p['algorithm_nodes'][0]['args'][0]='double'
 elif change=='mismatch':p['algorithm_inputs'][0].update(type='boolean',value=True)
 elif change=='zero':p['algorithm_nodes'][0]['op']='divide';p['algorithm_inputs'][1]['value']=0
 elif change=='overflow':p['algorithm_inputs'][0]['value']=10**12
 elif change=='test_input':p['algorithm_tests'][0]['inputs']={'x':4}
 elif change=='test_output':p['algorithm_tests'][0]['expected_outputs']={'unknown':20}
 else:p['algorithm_tests']*=2
 error(core.algorithm,p,msg)


def test_select_boolean_branch_and_failed_test_and_sorted_topology():
 p=compute();p['algorithm_inputs']=[{'id':'cond','type':'boolean','value':True},{'id':'t','type':'boolean','value':False},{'id':'f','type':'boolean','value':True}];p['algorithm_nodes']=[{'id':'n','op':'select','args':['cond','t','f'],'source':'n'}];p['algorithm_outputs']=['n'];p['algorithm_tests']=[]
 assert core.algorithm(p)['outputs']=={'n':False}
 p=compute();p['algorithm_tests'][0]['expected_outputs']['double']=19;assert core.algorithm(p)['test_reports'][0]['passed'] is False
 p['algorithm_nodes'].reverse();assert core.algorithm(p)['execution_order']==['sum','double']
 p=compute();p['algorithm_nodes']=[{'id':k,'op':'add','args':['x','y'],'source':k}for k in ['z','a']];p['algorithm_outputs']=['z','a'];p['algorithm_tests']=[];r=core.algorithm(p)
 assert r['execution_order']==['a','z'] and list(r['outputs'])==['a','z']

@pytest.mark.parametrize('field,cap',[('algorithm_inputs',32),('algorithm_nodes',64),('algorithm_tests',64)])
def test_algorithm_caps(field,cap):
 p=compute()
 if field=='algorithm_inputs':p[field]=[{'id':str(i),'type':'number','value':1}for i in range(cap)];p['algorithm_nodes']=[];p['algorithm_outputs']=['0'];p['algorithm_tests']=[]
 elif field=='algorithm_nodes':p[field]=[{**deepcopy(p[field][0]),'id':str(i)}for i in range(cap)];p['algorithm_outputs']=['x'];p['algorithm_tests']=[]
 else:p[field]=[{**deepcopy(p[field][0]),'id':str(i)}for i in range(cap)]
 core.algorithm(p)
 p[field].append({**deepcopy(p[field][0]),'id':'overflow'});error(core.algorithm,p,field+' requires bounded object list')

@pytest.mark.parametrize('change,msg',[('constraint_dup','unique constraints with minimum<=maximum required'),('interval','unique constraints with minimum<=maximum required'),('prototype_dup','unique prototype IDs required'),('feedback_dup','unique feedback bound to known prototype feature required'),('feedback_base','unique feedback bound to known prototype feature required'),('feedback_feature','unique feedback bound to known prototype feature required'),('revision_dup','unique revisions with known base, feedback and changed features required'),('revision_base','unique revisions with known base, feedback and changed features required'),('revision_ref','unique revisions with known base, feedback and changed features required'),('revision_feature','unique revisions with known base, feedback and changed features required')])
def test_design_errors(change,msg):
 p=design()
 if change=='constraint_dup':p['design_brief']['constraints']*=2
 elif change=='interval':p['design_brief']['constraints'][0]['minimum']=11
 elif change=='prototype_dup':p['design_prototypes']*=2
 elif change=='feedback_dup':p['design_feedback']*=2
 elif change=='feedback_base':p['design_feedback'][0]['prototype_id']='unknown'
 elif change=='feedback_feature':p['design_feedback'][0]['feature']='unknown'
 elif change=='revision_dup':p['design_revisions']*=2
 elif change=='revision_base':p['design_revisions'][0]['base_prototype_id']='unknown'
 elif change=='revision_ref':p['design_revisions'][0]['feedback_ids']=['unknown']
 else:p['design_revisions'][0]['changes']={'unknown':1}
 error(core.design,p,msg)


def test_revision_wrong_prototype_feedback_constraints_and_missing_feature():
 p=design();p['design_feedback'][0]['prototype_id']='b';r=core.design(p)['revision_reports'][0]
 assert r['wrong_prototype_feedback_ids']==['e'] and r['unbacked_features']==['cost'] and r['supported'] is False
 p=design();p['design_feedback'][0]['suggested_value']=11;p['design_revisions'][0]['changes']['cost']=11;r=core.design(p)['revision_reports'][0]
 assert r['unbacked_features']==[] and r['violated_constraints']==['c'] and r['supported'] is False
 p=design();p['design_brief']['constraints'][0]['feature']='missing';assert core.design(p)['prototype_reports'][1]['feasible'] is False
 p=design();p['design_prototypes'][1]['features']['cost']=0;assert core.design(p)['prototype_reports'][1]['feasible'] is True
 p['design_prototypes'][1]['features']['cost']=10;assert core.design(p)['prototype_reports'][1]['feasible'] is True

@pytest.mark.parametrize('field,cap',[('design_prototypes',64),('design_feedback',128),('design_revisions',64)])
def test_design_caps(field,cap):
 p=design();p[field]=[{**deepcopy(p[field][0]),'id':str(i)}for i in range(cap)]
 if field=='design_prototypes':p['design_feedback'][0]['prototype_id']='0';p['design_revisions'][0]['base_prototype_id']='0'
 elif field=='design_feedback':p['design_revisions'][0]['feedback_ids']=['0']
 core.design(p);p[field].append({**deepcopy(p[field][0]),'id':'overflow'});error(core.design,p,field+' requires bounded object list')


def test_feature_constraint_output_ref_bounds_and_sources():
 p=design();p['design_brief']['constraints']=[{**p['design_brief']['constraints'][0],'id':str(i)}for i in range(32)];core.design(p);p['design_brief']['constraints'].append({**p['design_brief']['constraints'][0],'id':'overflow'});error(core.design,p,'brief constraints requires bounded object list')
 p=design();p['design_prototypes'][0]['features'].update({str(i):1 for i in range(31)});core.design(p);p['design_prototypes'][0]['features']['overflow']=1;error(core.design,p,'prototype features requires1..32 numeric features')
 p=compute();p['algorithm_nodes']=[];p['algorithm_tests']=[];p['algorithm_inputs']=[{'id':str(i),'type':'number','value':1}for i in range(32)];p['algorithm_outputs']=[str(i)for i in range(32)];core.algorithm(p);p['algorithm_outputs'].append('overflow');error(core.algorithm,p,'algorithm_outputs requires bounded text list')
 p=design();r=core.design(p);assert r['audience']=='supplied participant group' and r['constraint_sources']=={'c':'brief:c'} and r['revision_reports'][0]['feedback_sources']==['participant:e'] and r['participant_validation_performed'] is False and r['invented_prototype'] is None

@pytest.mark.parametrize('fn,bank,label',[(core.design,'design_prototypes','prototype source'),(core.design,'design_feedback','feedback source'),(core.design,'design_revisions','revision source'),(core.algorithm,'algorithm_nodes','node source'),(core.algorithm,'algorithm_tests','test source')])
def test_source_text(fn,bank,label):
 p=design()if fn==core.design else compute();p[bank][0]['source']='';error(fn,p,label+' requires bounded nonempty string')


def test_r2_actual_failed_tests_sorted_counts_and_node_sources():
 p=compute();p['algorithm_tests']=[{**deepcopy(p['algorithm_tests'][0]),'id':'z','expected_outputs':{'double':19}},{**deepcopy(p['algorithm_tests'][0]),'id':'a'}]
 r=core.algorithm(p);assert [t['id']for t in r['test_reports']]==['a','z']
 assert r['test_reports'][1]['actual_outputs']=={'double':'20'} and r['test_reports'][1]['expected_outputs']=={'double':'19'} and r['test_reports'][1]['passed'] is False
 assert r['node_sources']=={'sum':'node:sum','double':'node:double'} and r['complexity']['test_execution_steps']==4


def simple_algorithm(op,inputs,args):
 p=compute();p['algorithm_inputs']=[{'id':k,'type':kind,'value':v}for k,kind,v in inputs];p['algorithm_nodes']=[{'id':'n','op':op,'args':args,'source':'n'}];p['algorithm_outputs']=['n'];p['algorithm_tests']=[];return p


def test_r2_boolean_equal_select_types_and_strict_less():
 p=simple_algorithm('not',[('b','boolean',1)],['b']);error(core.algorithm,p,'input value boolean required')
 p=simple_algorithm('equal',[('b','boolean',True),('x','number',1)],['b','x']);error(core.algorithm,p,'node argument type mismatch')
 p=simple_algorithm('select',[('x','number',1),('y','number',2)],['x','x','y']);error(core.algorithm,p,'node argument type mismatch')
 p=simple_algorithm('select',[('b','boolean',True),('x','number',1)],['b','x','b']);error(core.algorithm,p,'node argument type mismatch')
 p=simple_algorithm('less_than',[('x','number',1)],['x','x']);assert core.algorithm(p)['outputs']=={'n':False}
 p=simple_algorithm('not',[('b','boolean',True)],['b']);p['algorithm_tests']=[{'id':'t','inputs':{'b':True},'expected_outputs':{'n':0},'source':'t'}];error(core.algorithm,p,'expected output boolean required')
 p=compute();p['algorithm_tests'][0]['expected_outputs']['double']=True;error(core.algorithm,p,'expected output requires rational string/integer')


def test_r2_algorithm_identity_arity_minimum_and_rational_boundaries():
 p=compute();p['algorithm_nodes'][0]['id']='x';error(core.algorithm,p,'unique supported typed nodes with exact arity required')
 p=compute();p['algorithm_nodes'][0]['args'].append('x');error(core.algorithm,p,'unique supported typed nodes with exact arity required')
 p=compute();p['algorithm_outputs']=[];error(core.algorithm,p,'algorithm_outputs requires bounded text list')
 p=compute();p['algorithm_inputs']=[];error(core.algorithm,p,'algorithm_inputs requires bounded object list')
 p=simple_algorithm('add',[('x','number',10**12),('zero','number',0)],['x','zero']);assert core.algorithm(p)['outputs']=={'n':str(10**12)}
 p['algorithm_inputs'][1]['value']=1;error(core.algorithm,p,'algorithm result rational components exceed10**12')
 p=simple_algorithm('divide',[('x','number','1/1000000'),('y','number',1000000)],['x','y']);assert core.algorithm(p)['outputs']=={'n':'1/1000000000000'}
 p['algorithm_inputs'][1]['value']=1000001;error(core.algorithm,p,'algorithm result rational components exceed10**12')


def test_r2_design_suggestion_feature_match_preservation_wrong_refs_equal_interval():
 p=design();p['design_feedback'][0]['suggested_value']=True;error(core.design,p,'suggested_value requires rational string/integer')
 p=design();p['design_prototypes'][0]['features']['other']=6;p['design_feedback'][0]['feature']='other';r=core.design(p)['revision_reports'][0];assert r['unbacked_features']==['cost'] and r['supported'] is False
 p=design();p['design_prototypes'][0]['features']['other']=6;p['design_brief']['constraints'].append({'id':'other','feature':'other','minimum':6,'maximum':6,'source':'other'});r=core.design(p)['revision_reports'][0]
 assert r['features']=={'cost':'6','other':'6'} and r['supported'] is True and r['violated_constraints']==[]
 p=design();p['design_feedback'].append({'id':'wrong','prototype_id':'b','feature':'cost','suggested_value':6,'source':'wrong'});p['design_revisions'][0]['feedback_ids']=['e','wrong'];r=core.design(p)['revision_reports'][0]
 assert r['unbacked_features']==[] and r['wrong_prototype_feedback_ids']==['wrong'] and r['supported'] is False


def test_r2_design_minima_feedback_ref_cap():
 p=design();p['design_prototypes']=[];error(core.design,p,'design_prototypes requires bounded object list')
 p=design();p['design_prototypes'][0]['features']={};error(core.design,p,'prototype features requires1..32 numeric features')
 p=design();p['design_revisions'][0]['changes']={};error(core.design,p,'changes requires1..32 numeric features')
 p=design();p['design_brief']['constraints']=[];error(core.design,p,'brief constraints requires bounded object list')
 p=design();p['design_feedback']=[{**p['design_feedback'][0],'id':str(i)}for i in range(65)];p['design_revisions'][0]['feedback_ids']=[str(i)for i in range(64)];assert core.design(p)['revision_reports'][0]['supported'] is True
 p['design_revisions'][0]['feedback_ids'].append('64');error(core.design,p,'feedback_ids requires bounded text list')
 p['design_revisions'][0]['feedback_ids']=[];error(core.design,p,'feedback_ids requires bounded text list')


def test_r2_design_text_fresh_validator_errors():
 p=design();p['design_prototypes'][0]['features']={'':1};error(core.design,p,'prototype features key requires bounded nonempty string')
 p=design();p['design_brief']['audience']='';error(core.design,p,'brief audience requires bounded nonempty string')
 p=design();p['design_brief']['constraints'][0]['id']='';error(core.design,p,'constraint id requires bounded nonempty string')
 p=design();p['design_brief']['constraints'][0]['feature']='';error(core.design,p,'constraint feature requires bounded nonempty string')
 p=design();p['design_brief']['constraints'][0]['source']='';error(core.design,p,'constraint source requires bounded nonempty string')


def test_r2_unsorted_prototypes_revisions_violations_features():
 p=design();p['design_prototypes']=[{'id':k,'features':{'z':12,'a':12},'source':k}for k in ['z','a']];p['design_brief']['constraints']=[{'id':k,'feature':k,'minimum':0,'maximum':10,'source':k}for k in ['z','a']];p['design_feedback']=[];p['design_revisions']=[]
 r=core.design(p);assert [x['id']for x in r['prototype_reports']]==['a','z'] and r['prototype_reports'][0]['violated_constraints']==['a','z']
 p['design_feedback']=[{'id':k,'prototype_id':'z','feature':k,'suggested_value':6,'source':k}for k in ['z','a']];p['design_revisions']=[{'id':k,'base_prototype_id':'z','feedback_ids':['z','a'],'changes':{'z':6,'a':6},'source':k}for k in ['z','a']]
 r=core.design(p);assert [x['id']for x in r['revision_reports']]==['a','z'] and list(r['revision_reports'][0]['features'])==['a','z'] and r['revision_reports'][0]['feedback_ids']==['a','z']


def test_r2_set_ref_and_unbacked_sort_fixed_seed():
 import subprocess,os,sys
 code='''from app.modules.m20_general_cognitive_worker.design_algorithms import design
names=['z','q','m','j','h','f','d','c']
p={'design_brief':{'audience':'a','constraints':[{'id':'c','feature':'z','minimum':0,'maximum':10,'source':'c'}]},'design_prototypes':[{'id':'p','features':{k:1 for k in names},'source':'p'}],'design_feedback':[{'id':k,'prototype_id':'p','feature':k,'suggested_value':2,'source':k}for k in names],'design_revisions':[{'id':'r','base_prototype_id':'p','feedback_ids':names,'changes':{k:3 for k in names},'source':'r'}]}
r=design(p)['revision_reports'][0]
assert r['feedback_ids']==['c','d','f','h','j','m','q','z']
assert r['unbacked_features']==['c','d','f','h','j','m','q','z']
'''
 r=subprocess.run([sys.executable,'-c',code],env={**os.environ,'PYTHONHASHSEED':'0'},capture_output=True,text=True);assert r.returncode==0,r.stderr
