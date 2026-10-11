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
