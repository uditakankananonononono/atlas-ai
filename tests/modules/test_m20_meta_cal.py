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
  with pytest.raises(ValueError):a.ingest([{**rows[0],'prediction_id':'invalid-'+str(change),**change}])

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

def test_unmasked_record_validation_and_exact_boundaries(tmp_path):
 p=predictor(tmp_path);base=data()[0]
 for i,change in enumerate([{'resolved_at':1},{'confidence':1.0001},{'confidence':-.0001},{'confidence':float('nan')},{'confidence':float('inf')},{'confidence':True},{'outcome':None},{'outcome':1},{'claim_class':'x'*241}]):
  with pytest.raises(ValueError):p.ingest([{**base,'prediction_id':f'bad{i}',**change}])
 assert p.records=={}
 assert p.ingest([{**base,'prediction_id':'x'*240,'claim_class':'c'*240,'confidence':1.}])['inserted']==1


def test_single_resolution_time_inclusive_window_and_confidence_one(tmp_path):
 p=predictor(tmp_path);rows=[{**r,'confidence':1.}for r in data()[:20]];p.ingest(rows)
 for as_of in (2.,32.):
  result=p.predict('synthetic-binary',1.,as_of=as_of)
  assert result['status']=='calibrated'and result['bin_index']==4
 assert p.predict('synthetic-binary',1.,as_of=32.01)['status']=='abstained'


def test_batch_and_total_record_caps_and_duplicate_no_write(tmp_path):
 p=predictor(tmp_path);base=data()[0];batch=[{**base,'prediction_id':f'b{i}'}for i in range(1000)]
 with pytest.raises(ValueError):p.ingest(batch+[{**base,'prediction_id':'extra'}])
 assert p.ingest(batch)['inserted']==1000
 revision=p._revision;assert p.ingest(batch)['inserted']==0 and p._revision==revision
 assert p.repo.read(p.kind)[0]==revision
 assert p.ingest([{**r,'prediction_id':'second'+r['prediction_id']}for r in batch])['total']==2000
 with pytest.raises(ValueError):p.ingest([{**base,'prediction_id':'2001'}])
 assert len(p.records)==2000


@pytest.mark.parametrize('change',[{'confidence':1.5},{'confidence':float('nan')},{'as_of':float('nan')},{'as_of':True},{'claim_class':''}])
def test_predict_validation_before_abstention(tmp_path,change):
 p=predictor(tmp_path);args={'claim_class':'synthetic-binary','confidence':.9,'as_of':3};args.update(change)
 with pytest.raises(ValueError):p.predict(**args)


def test_output_honesty_provenance_window_estimator_and_abstain(tmp_path):
 p=predictor(tmp_path);rows=data();p.ingest(rows);r=p.predict('synthetic-binary',.9,as_of=3)
 selected=sorted((x for x in rows if x['confidence']==.9),key=lambda x:x['prediction_id'])
 assert r['source_truth_verified'] is False
 assert r['training_provenance']==[{'prediction_source':x['prediction_source'],'outcome_source':x['outcome_source']}for x in selected]
 assert r['window_start']==-27 and r['window_end']==3 and r['raw_confidence']==.9 and r['bin_index']==4
 assert r['estimator']=='Beta(1,1) binomial posterior mean within fixed confidence bin'
 assert p.predict('other',.9,as_of=3)['corrected_confidence'] is None


def test_mounted_stale_invalid_type_and_bind_refusals(tmp_path,monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker import calibration_predictor_routes as routes
 try:routes.bind_predictor(object())
 except Exception as exc:assert isinstance(exc,ValueError)
 else:assert False,'invalid predictor accepted'
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_predictors',{})
 a,b=predictor(tmp_path),predictor(tmp_path);a.ingest(data()[:1]);routes.bind_predictor(b)
 c=TestClient(app);h=oidc_auth_headers('a','owner');path='/api/v1/api/modules/20/calibration-predictor'
 assert c.post(path+'/ingest',headers=h,json={'records':data()[1:2]}).status_code==409
 assert c.post(path+'/ingest',headers=h,json={'records':[{'outcome':None}]}).status_code==422
 assert c.post(path+'/predict',headers=h,json={'extra':1}).status_code==422
