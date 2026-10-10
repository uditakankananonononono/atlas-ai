"""Resolved provenance-bound class calibration, held-out proper-score proof."""
import math,sqlalchemy as sa
import pytest
from app.modules.m20_general_cognitive_worker.calibration_predictor import CalibrationPredictor
from app.modules.m20_general_cognitive_worker.meta_persistence import MetaRepository

def predictor(tmp_path,tenant='a'):
 r=MetaRepository(sa.create_engine(f'sqlite:///{tmp_path}/cal.sqlite'),tenant_id=tenant);r.create_schema();return CalibrationPredictor.load(r)

def data(prefix='train',claim_class='synthetic-binary'):
 return [{'prediction_id':f'{prefix}-{i}-{j}','claim_class':claim_class,'confidence':p,'outcome':j<int(actual*40),'prediction_source':f'fixture:prediction:{prefix}-{i}-{j}','outcome_source':f'fixture:label:{prefix}-{i}-{j}','predicted_at':1.,'resolved_at':2.} for i,(p,actual)in enumerate([(0.1,.1),(.3,.2),(.5,.4),(.7,.5),(.9,.6)])for j in range(40)]

def test_heldout_brier_logloss_and_reliability_improve_without_leakage(tmp_path):
 p=predictor(tmp_path);p.ingest(data());held=data('heldout');raw=[];corrected=[];truth=[]
 for r in held:
  result=p.predict(r['claim_class'],r['confidence'],as_of=3.)
  assert result['status']=='calibrated' and result['training_prediction_ids']==sorted(x['prediction_id']for x in data()if int(x['confidence']*5)==int(r['confidence']*5))
  assert all(not x.startswith('heldout')for x in result['training_prediction_ids'])
  raw.append(r['confidence']);corrected.append(result['corrected_confidence']);truth.append(r['outcome'])
 def brier(scores):return sum((v-int(y))**2 for v,y in zip(scores,truth))/len(scores)
 def logloss(scores):return -sum(math.log(v if y else 1-v)for v,y in zip(scores,truth))/len(scores)
 assert brier(corrected)<brier(raw) and logloss(corrected)<logloss(raw)
 assert sum(abs(corrected[i*40]-sum(truth[i*40:(i+1)*40])/40)for i in range(5))<sum(abs(raw[i*40]-sum(truth[i*40:(i+1)*40])/40)for i in range(5))
 assert predictor(tmp_path).predict('synthetic-binary',.9,as_of=3.)==p.predict('synthetic-binary',.9,as_of=3.)
 assert predictor(tmp_path,'b').predict('synthetic-binary',.9,as_of=3.)['status']=='abstained'

def test_sparse_ood_class_and_time_window_abstain(tmp_path):
 p=predictor(tmp_path);p.ingest(data()[:5])
 assert p.predict('synthetic-binary',.1,as_of=3.)['status']=='abstained'
 p.ingest(data()[5:])
 for cls,c,t in [('different',.9,3),('synthetic-binary',.01,3),('synthetic-binary',.99,3),('synthetic-binary',.9,1.5),('synthetic-binary',.9,100.)]:
  assert p.predict(cls,c,as_of=t)['status']=='abstained'

def test_changed_labels_change_estimate_duplicate_exclusion_and_invalid_provenance(tmp_path):
 a,b=predictor(tmp_path),predictor(tmp_path,'b');rows=data();a.ingest(rows)
 flipped=[{**r,'outcome':not r['outcome']}for r in rows];b.ingest(flipped)
 assert a.predict('synthetic-binary',.9,as_of=3.)['corrected_confidence']!=b.predict('synthetic-binary',.9,as_of=3.)['corrected_confidence']
 assert a.ingest(rows)['inserted']==0
 with pytest.raises(ValueError,match='identity'):a.ingest(flipped)
 for change in [{'outcome':None},{'outcome_source':''},{'prediction_source':''},{'resolved_at':0},{'confidence':True}]:
  with pytest.raises(ValueError):a.ingest([{**rows[0],**change}])

def test_commit_failure_stale_writer_atomic(tmp_path,monkeypatch):
 a,b=predictor(tmp_path),predictor(tmp_path);a.ingest(data()[:1])
 with pytest.raises(RuntimeError,match='stale'):b.ingest(data()[1:2])
 assert b.records=={}
 before=a.records.copy()
 def fail(session):raise RuntimeError('rollback')
 monkeypatch.setattr(a.repo,'_before_commit',fail)
 with pytest.raises(RuntimeError):a.ingest(data()[1:2])
 assert a.records==before==predictor(tmp_path).records

def test_production_routes_prediction_and_tenant_isolation(tmp_path,monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker import calibration_predictor_routes as routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_predictors',{})
 routes.bind_predictor(predictor(tmp_path));c=TestClient(app);path='/api/v1/api/modules/20/calibration-predictor';h=oidc_auth_headers('a','owner')
 assert c.post(path+'/ingest',json={'records':data()}).status_code==401
 assert c.post(path+'/ingest',headers=h,json={'records':data()}).status_code==200
 r=c.post(path+'/predict',headers=h,json={'claim_class':'synthetic-binary','confidence':.9,'as_of':3})
 assert r.status_code==200 and r.json()['status']=='calibrated'
 assert c.post(path+'/predict',headers=oidc_auth_headers('b','owner'),json={'claim_class':'synthetic-binary','confidence':.9,'as_of':3}).status_code==503

def test_known_bin_estimate_exact_minimum_and_no_future_labels(tmp_path):
 p=predictor(tmp_path);rows=data()[:20];p.ingest(rows)
 result=p.predict('synthetic-binary',.1,as_of=3.)
 assert result['sample_size']==20 and result['successes']==4
 assert result['corrected_confidence']==5/22
 p2=predictor(tmp_path,'b');p2.ingest(rows[:19]);assert p2.predict('synthetic-binary',.1,as_of=3.)['status']=='abstained'
 future=[{**r,'prediction_id':'future'+r['prediction_id'],'resolved_at':10}for r in rows]
 p.ingest(future);assert p.predict('synthetic-binary',.1,as_of=3.)==result
 assert p.predict('synthetic-binary',.1,as_of=32.)['status']=='calibrated'
 assert p.predict('synthetic-binary',.1,as_of=41.)['status']=='abstained'

def test_missing_provenance_refuses_before_record_publish(tmp_path):
 p=predictor(tmp_path);row=data()[0];row.pop('outcome_source')
 try:p.ingest([row])
 except Exception as exc:assert isinstance(exc,ValueError) and 'outcome_source' in str(exc)
 else:assert False,'unbound outcome provenance accepted'
 assert p.records=={}
