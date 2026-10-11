"""Rubric-anchor evidence validation, not psychometrics or credential decisions."""
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Rubric','url':'https://example.org/rubric'}
def payload(peer=False):return {'objective':'Review supplied artifact','source':SRC,'artifact_id':'artifact','author_id':'author','assessment_rubric':[{'criterion_id':'reasoning','anchors':[{'level':0,'description':'No supported steps','required_features':[]},{'level':1,'description':'Checked step','required_features':['checked_step']}],'source':'fixture:rubric'}],'assessment_evidence':[{'evidence_id':'e','artifact_id':'artifact','features':['checked_step'],'source':'fixture:artifact'}],'assessment_ratings':[{'rating_id':'r','criterion_id':'reasoning','rater_id':'peer'if peer else 'author','level':1,'evidence_ids':['e']}],'assessment_controls':{'anonymized':peer,'conflict_checked':True,'conflicted_rater_ids':[],'author_response':'I agree'}}
def run(method='self_assessment',p=None):return execute(method,payload()if p is None else p)['result']['rubric_assessment']

def test_self_anchored_evidence_computation_and_honesty():
 r=run();assert r['mode']=='self' and r['status']=='assessed'
 assert r['rating_reports']==[{'rating_id':'r','criterion_id':'reasoning','rater_id':'author','level':1,'evidence_ids':['e'],'missing_required_features':[],'supported':True,'missing_evidence':False,'conflicted':False}]
 assert r['criterion_reports']==[{'criterion_id':'reasoning','supported_levels':[1],'disagreement':False,'highest_anchor_supported':True,'missing_ratings':False}]
 assert r['source_truth_verified'] is False and r['mastery'] is None and r['credential_decision'] is None

def test_missing_evidence_never_supported_or_highest_anchor():
 p=payload();p['assessment_ratings'][0]['evidence_ids']=[];r=run(p=p)
 assert r['rating_reports'][0]['supported'] is False and r['rating_reports'][0]['missing_evidence'] is True and r['rating_reports'][0]['missing_required_features']==['checked_step']
 assert r['criterion_reports'][0]['highest_anchor_supported'] is False and r['criterion_reports'][0]['supported_levels']==[]

def test_peer_controls_conflicts_disagreement_not_averaged():
 p=payload(True);p['assessment_ratings'].append({'rating_id':'r2','criterion_id':'reasoning','rater_id':'peer2','level':0,'evidence_ids':['e']})
 r=run('peer_assessment',p);assert r['mode']=='peer' and r['criterion_reports'][0]['supported_levels']==[0,1] and r['criterion_reports'][0]['disagreement'] is True and r['criterion_reports'][0]['highest_anchor_supported'] is None
 assert 'mean_score'not in r and r['controls']==p['assessment_controls']
 p['assessment_controls']['conflicted_rater_ids']=['peer'];r=run('peer_assessment',p);assert r['rating_reports'][0]['supported'] is False and r['rating_reports'][0]['conflicted'] is True
 for field in ['anonymized','conflict_checked']:
  p=payload(True);p['assessment_controls'][field]=False
  with pytest.raises(LearningReasoningError):run('peer_assessment',p)

def test_self_peer_identity_and_unknown_references_refuse():
 p=payload(True)
 with pytest.raises(LearningReasoningError):run(p=p)
 p=payload()
 with pytest.raises(LearningReasoningError):run('peer_assessment',p)
 for field,value in [('criterion_id','unknown'),('level',2),('evidence_ids',['unknown'])]:
  p=payload();p['assessment_ratings'][0][field]=value
  with pytest.raises(LearningReasoningError):run(p=p)
 p=payload();p['assessment_evidence'][0]['artifact_id']='different'
 with pytest.raises(LearningReasoningError):run(p=p)

def test_missing_feature_and_no_ratings_reports():
 p=payload();p['assessment_evidence'][0]['features']=[];r=run(p=p);assert r['rating_reports'][0]['supported'] is False
 p=payload();p['assessment_ratings']=[];r=run(p=p);assert r['criterion_reports'][0]['missing_ratings'] is True and r['criterion_reports'][0]['highest_anchor_supported'] is False

@pytest.mark.parametrize('field,value',[('assessment_rubric',[]),('assessment_evidence',[[]]),('assessment_ratings',[[]]),('assessment_controls',[]),('artifact_id',''),('author_id','')])
def test_invalid_shapes(field,value):
 p=payload();p[field]=value
 with pytest.raises(LearningReasoningError):run(p=p)

def test_anchor_types_duplicate_evidence_and_ratings():
 for field in ['assessment_evidence','assessment_ratings','assessment_rubric']:
  p=payload();p[field]*=2
  with pytest.raises(LearningReasoningError):run(p=p)
 p=payload();p['assessment_rubric'][0]['anchors'][0]['level']=True
 with pytest.raises(LearningReasoningError):run(p=p)
 p=payload();p['assessment_rubric'][0]['anchors'][1]['required_features']=['checked_step','checked_step']
 with pytest.raises(LearningReasoningError):run(p=p)

def test_mounted_auth_minimal_refusal_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method,peer in [('self_assessment',False),('peer_assessment',True)]:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method;p=payload(peer)
  assert c.post(path,json={'payload':p}).status_code==401
  assert c.post(path,headers=h,json={'payload':p}).status_code==200
  assert c.post(path,headers=h,json={'payload':{'objective':'x','source':SRC}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**p,'resource_refs':[{'tenant_id':'b'}]}}).status_code==403

def test_full_rubric_evidence_echo_order_zero_anchor_missing():
 p=payload();r=run(p=p);assert r['rubric']==p['assessment_rubric'] and r['evidence']==p['assessment_evidence'] and r['controls']==p['assessment_controls']
 p['assessment_ratings'][0].update(level=0,evidence_ids=[]);r=run(p=p);assert r['rating_reports'][0]['missing_required_features']==[] and r['rating_reports'][0]['supported'] is False
 assert r['boundary']=='Declared observable-feature rubric anchors and supplied artifact evidence only; self/peer identity/control declarations are not independently verified. Disagreement retained without averaging, no mastery, psychometrics or credential decision.'

@pytest.mark.parametrize('field,value',[('anonymized',1),('conflict_checked',1),('conflicted_rater_ids','peer'),('author_response','')])
def test_controls_literal_types_and_text(field,value):
 p=payload();p['assessment_controls'][field]=value
 with pytest.raises(LearningReasoningError):run(p=p)

def test_caps_and_duplicate_pair():
 p=payload();p['assessment_rubric']=[{**p['assessment_rubric'][0],'criterion_id':str(i)}for i in range(32)];p['assessment_ratings']=[]
 assert len(run(p=p)['criterion_reports'])==32
 p['assessment_rubric'].append({**p['assessment_rubric'][0],'criterion_id':'32'})
 with pytest.raises(LearningReasoningError):run(p=p)
 p=payload();p['assessment_ratings'].append({**p['assessment_ratings'][0],'rating_id':'different'})
 with pytest.raises(LearningReasoningError):run(p=p)
 p=payload();p['assessment_rubric'][0]['anchors']=[{'level':i,'description':'observable','required_features':[]}for i in range(16)];p['assessment_ratings']=[];assert len(run(p=p)['rubric'][0]['anchors'])==16
 p['assessment_rubric'][0]['anchors'].append({'level':16,'description':'observable','required_features':[]})
 with pytest.raises(LearningReasoningError):run(p=p)

def test_peer_author_refuses_without_anonymization_mask():
 from app.modules.m20_general_cognitive_worker.anchored_assessment import assess
 p=payload(True);p['assessment_ratings'][0]['rater_id']='author'
 with pytest.raises(ValueError,match='rater identity differs from self/peer mode'):assess('peer',p)

@pytest.mark.parametrize('level',[True,1.0,101])
def test_anchor_level_type_and_cap(level):
 from app.modules.m20_general_cognitive_worker.anchored_assessment import assess
 p=payload();p['assessment_rubric'][0]['anchors'][1]['level']=level
 with pytest.raises(ValueError,match='unique integer anchor levels'):assess('self',p)

def test_anchor_minimum_duplicates_and_rating_level_types():
 from app.modules.m20_general_cognitive_worker.anchored_assessment import assess
 p=payload();assert assess('self',p)['status']=='assessed'
 p['assessment_rubric'][0]['anchors']=p['assessment_rubric'][0]['anchors'][:1]
 with pytest.raises(ValueError,match='anchors requires bounded object list'):assess('self',p)
 p=payload();p['assessment_rubric'][0]['anchors'][1]['level']=0
 with pytest.raises(ValueError,match='unique integer anchor levels'):assess('self',p)
 for level in [True,1.0]:
  p=payload();p['assessment_ratings'][0]['level']=level
  with pytest.raises(ValueError,match='known criterion and integer anchor level required'):assess('self',p)
 p=payload();p['assessment_rubric']=[];p['assessment_ratings']=[]
 with pytest.raises(ValueError,match='assessment_rubric requires bounded object list'):assess('self',p)

def test_evidence_and_peer_ratings_exact_1000_caps():
 from app.modules.m20_general_cognitive_worker.anchored_assessment import assess
 p=payload(True);p['assessment_evidence']=[{**p['assessment_evidence'][0],'evidence_id':str(i)}for i in range(1000)];p['assessment_ratings']=[{**p['assessment_ratings'][0],'rating_id':str(i),'rater_id':'peer'+str(i),'evidence_ids':['0']}for i in range(1000)]
 assert len(assess('peer',p)['rating_reports'])==1000
 for field,key in [('assessment_evidence','evidence_id'),('assessment_ratings','rating_id')]:
  from copy import deepcopy
  q=deepcopy(p);extra={**q[field][0],key:'extra'}
  if field=='assessment_ratings':extra['rater_id']='extra'
  q[field].append(extra)
  with pytest.raises(ValueError,match=field+' requires bounded object list'):assess('peer',q)

def test_keys_caps_types_nontext_and_duplicate_unmasked():
 from app.modules.m20_general_cognitive_worker.anchored_assessment import assess
 for field in ['features','evidence_ids','conflicted_rater_ids']:
  for value in [{'e':1},[5]]:
   p=payload()
   target=p['assessment_evidence'][0]if field=='features'else p['assessment_ratings'][0]if field=='evidence_ids'else p['assessment_controls']
   target[field]=value
   with pytest.raises(ValueError,match='requires bounded text list|requires bounded nonempty string'):assess('self',p)
 for field in ['features','evidence_ids']:
  p=payload();target=p['assessment_evidence'][0]if field=='features'else p['assessment_ratings'][0];target[field]=['e','e']
  with pytest.raises(ValueError,match='requires unique keys'):assess('self',p)
 for field in ['features','evidence_ids','conflicted_rater_ids']:
  p=payload();p['assessment_evidence']=[{**p['assessment_evidence'][0],'evidence_id':str(i)}for i in range(65)];p['assessment_ratings'][0]['evidence_ids']=['0']
  target=p['assessment_evidence'][0]if field=='features'else p['assessment_ratings'][0]if field=='evidence_ids'else p['assessment_controls']
  target[field]=[str(i)for i in range(64)];assess('self',p)
  target[field].append('64')
  with pytest.raises(ValueError,match='requires bounded text list'):assess('self',p)

@pytest.mark.parametrize('container,field,label',[('root','artifact_id','artifact_id'),('root','author_id','author_id'),('rubric','criterion_id','criterion_id'),('rubric','source','rubric source'),('anchor','description','anchor description'),('evidence','evidence_id','evidence_id'),('evidence','artifact_id','evidence artifact_id'),('evidence','source','evidence source'),('rating','rating_id','rating_id'),('rating','criterion_id','rating criterion_id'),('rating','rater_id','rater_id')])
def test_text_fields_core_exact_refusal(container,field,label):
 from app.modules.m20_general_cognitive_worker.anchored_assessment import assess
 p=payload();target={'root':p,'rubric':p['assessment_rubric'][0],'anchor':p['assessment_rubric'][0]['anchors'][0],'evidence':p['assessment_evidence'][0],'rating':p['assessment_ratings'][0]}[container];target[field]=[]
 with pytest.raises(ValueError,match='^'+label+' requires bounded nonempty string$'):assess('self',p)

def test_rating_id_duplicate_distinct_pair_and_core_ref_errors():
 from app.modules.m20_general_cognitive_worker.anchored_assessment import assess
 p=payload(True);p['assessment_ratings'].append({**p['assessment_ratings'][0],'rater_id':'different'})
 with pytest.raises(ValueError,match='unique rating IDs and criterion/rater pairs required'):assess('peer',p)
 for key,value,message in [('criterion_id','unknown','known criterion and integer anchor level required'),('level',2,'known anchor level/evidence IDs required'),('evidence_ids',['unknown'],'known anchor level/evidence IDs required')]:
  p=payload();p['assessment_ratings'][0][key]=value
  with pytest.raises(ValueError,match=message):assess('self',p)

def test_reverse_order_multirecord_echo_and_lower_anchor():
 from app.modules.m20_general_cognitive_worker.anchored_assessment import assess
 p=payload(True);p['assessment_rubric']=[{'criterion_id':c,'source':'fixture:'+c,'anchors':[{'level':1,'description':'higher','required_features':['z','a']},{'level':0,'description':'lower','required_features':[]}]}for c in ['z','a']]
 p['assessment_evidence']=[{'evidence_id':e,'artifact_id':'artifact','features':['z','a'],'source':'fixture:'+e}for e in ['z','a']]
 p['assessment_controls']['conflicted_rater_ids']=['zconflict','aconflict']
 p['assessment_ratings']=[{'rating_id':c+r,'criterion_id':c,'rater_id':r,'level':0,'evidence_ids':['z','a']}for c in ['z','a']for r in ['zpeer','apeer']]
 out=assess('peer',p)
 assert [r['criterion_id']for r in out['rubric']]==['a','z'] and [e['evidence_id']for e in out['evidence']]==['a','z']
 assert all([a['level']for a in r['anchors']]==[0,1]and r['anchors'][1]['required_features']==['a','z']for r in out['rubric'])
 assert all(e['features']==['a','z']for e in out['evidence']) and out['controls']['conflicted_rater_ids']==['aconflict','zconflict']
 assert [r['criterion_id']for r in out['criterion_reports']]==['a','z'] and all(r['highest_anchor_supported']is False for r in out['criterion_reports'])
 assert [(r['criterion_id'],r['rater_id'],r['rating_id'])for r in out['rating_reports']]==[('a','apeer','aapeer'),('a','zpeer','azpeer'),('z','apeer','zapeer'),('z','zpeer','zzpeer')]
 assert all(r['evidence_ids']==['a','z']for r in out['rating_reports'])
