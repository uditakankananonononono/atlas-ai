"""Synthetic class survival forecasts and durable refresh recommendations."""
import math,random
from copy import deepcopy
import pytest
import sqlalchemy as sa
from app.modules.m20_general_cognitive_worker.decay_survival import DecaySurvival
from app.modules.m20_general_cognitive_worker.meta_persistence import MetaRepository

def model(tmp_path,tenant='a'):
 r=MetaRepository(sa.create_engine(f'sqlite:///{tmp_path}/decay.sqlite'),tenant_id=tenant);r.create_schema();return DecaySurvival.load(r)
def history(prefix='train',rate=.1,cls='slow',n=300):
 rng=random.Random(12)
 rows=[]
 for i in range(n):
  duration=rng.expovariate(rate);censor=10.;rows.append({'history_id':f'{prefix}-{i}','fact_class':cls,'source':f'fixture:{prefix}:{i}','started_at':0.,'ended_at':min(duration,censor),'changed':duration<=censor})
 return rows

def test_survival_known_classes_censoring_heldout_quality(tmp_path):
 m=model(tmp_path);slow=history();fast=history('fast',.4,'fast');m.ingest(slow+fast)
 for cls,rows,rate in [('slow',slow,.1),('fast',fast,.4)]:
  r=m.forecast(cls,horizon=5,as_of=11);events=sum(x['changed']for x in rows);exposure=sum(x['ended_at']for x in rows)
  assert r['status']=='forecast' and r['events']==events and r['censored']==len(rows)-events
  assert r['exposure']==pytest.approx(exposure) and r['gamma_shape']==events+1 and r['gamma_rate']==pytest.approx(exposure+1)
  expected=1-((exposure+1)/(exposure+6))**(events+1)
  assert r['stale_probability']==pytest.approx(expected)
  assert r['rate_mean']==pytest.approx((events+1)/(exposure+1)) and r['rate_stddev']==pytest.approx(math.sqrt(events+1)/(exposure+1))
  rng=random.Random(55);truth=[rng.expovariate(rate)<=5 for _ in range(1000)];p=r['stale_probability']
  assert abs(p-sum(truth)/len(truth))<.06
  assert sum((p-y)**2 for y in truth)<sum((.5-y)**2 for y in truth)
  assert all(not ident.startswith('held')for ident in r['history_ids'])
 assert m.forecast('fast',horizon=5,as_of=11)['stale_probability']>m.forecast('slow',horizon=5,as_of=11)['stale_probability']
 assert model(tmp_path).forecast('slow',horizon=5,as_of=11)==m.forecast('slow',horizon=5,as_of=11)
 assert model(tmp_path,'b').forecast('slow',horizon=5,as_of=11)['status']=='abstained'

def test_horizons_sparse_future_and_honesty(tmp_path):
 m=model(tmp_path);m.ingest(history(n=39))
 assert m.forecast('slow',horizon=5,as_of=11)['status']=='abstained'
 m.ingest(history()[39:]);values=[m.forecast('slow',horizon=h,as_of=11)['stale_probability']for h in [0,1,5,100]]
 assert values[0]==0 and values==sorted(values)
 assert m.forecast('slow',horizon=5,as_of=-1)['status']=='abstained'
 assert m.forecast('unknown',horizon=5,as_of=11)['stale_probability'] is None
 r=m.forecast('slow',horizon=5,as_of=11);assert r['source_truth_verified'] is False and r['current_freshness'] is None
 assert r['history_sources']==[m.state['histories'][key]['source']for key in r['history_ids']]
 no_events=model(tmp_path,'none');no_events.ingest([{**r,'history_id':f'no{i}','changed':False,'ended_at':10}for i,r in enumerate(history(n=40))]);assert no_events.forecast('slow',horizon=5,as_of=11)['reason']=='sparse_class'

@pytest.mark.parametrize('change',[{'changed':1},{'source':''},{'history_id':''},{'fact_class':''},{'started_at':True},{'started_at':float('nan')},{'ended_at':float('inf')},{'ended_at':0}])
def test_invalid_history_atomic(tmp_path,change):
 m=model(tmp_path)
 with pytest.raises(ValueError):m.ingest([{**history(n=1)[0],**change}])
 assert m.state=={'histories':{},'facts':{},'due':{}}

def test_due_queue_transitions_and_restarts(tmp_path):
 m=model(tmp_path);m.ingest(history());m.track('fact','slow',source='fixture:fact',confirmed_at=11)
 assert m.evaluate(as_of=12)['due']==[]
 r=m.evaluate(as_of=21);assert len(r['due'])==1 and r['due'][0]['fact_id']=='fact' and r['due'][0]['reason']=='predicted_stale_probability_at_least_half'
 assert r['due'][0]['source']=='fixture:fact' and r['due'][0]['stale_probability']>=.5
 assert model(tmp_path).state==m.state
 m.refresh('fact',confirmed_at=21,source='fixture:reconfirmation');assert m.state['due']=={}
 assert m.evaluate(as_of=22)['due']==[]
 assert m.state['facts']['fact']['source']=='fixture:reconfirmation'
 with pytest.raises(ValueError):m.refresh('fact',confirmed_at=20,source='source')
 with pytest.raises(ValueError):m.evaluate(as_of=20)
 assert model(tmp_path,'b').state['due']=={}

def test_duplicate_stale_rollback_and_limits(tmp_path,monkeypatch):
 a,b=model(tmp_path),model(tmp_path);rows=history();a.ingest(rows);rev=a._revision
 assert a.ingest(rows)['inserted']==0 and a._revision==rev
 with pytest.raises(ValueError):a.ingest([{**rows[0],'changed':not rows[0]['changed']}])
 with pytest.raises(RuntimeError,match='stale'):b.ingest(rows)
 assert b.state['histories']=={}
 before=deepcopy(a.state)
 def fail(session):raise RuntimeError('rollback')
 monkeypatch.setattr(a.repo,'_before_commit',fail)
 with pytest.raises(RuntimeError):a.track('fact','slow',source='fixture',confirmed_at=11)
 assert a.state==before==model(tmp_path).state
 for rows in [[],history(n=1001)]:
  with pytest.raises(ValueError):a.ingest(rows)
 for horizon in [-1,100.001,True,float('nan')]:
  with pytest.raises(ValueError):a.forecast('slow',horizon=horizon,as_of=11)

def test_mounted_routes_auth_errors_and_tenant(tmp_path,monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker import decay_survival_routes as routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_models',{})
 with pytest.raises(ValueError):routes.bind_model(object())
 m=model(tmp_path);routes.bind_model(m);c=TestClient(app);p='/api/v1/api/modules/20/decay-survival';h=oidc_auth_headers('a','owner')
 assert c.post(p+'/ingest',json={'records':history()}).status_code==401
 assert c.post(p+'/ingest',headers=h,json={'records':history()}).status_code==200
 assert c.post(p+'/forecast',headers=h,json={'fact_class':'slow','horizon':5,'as_of':11}).json()['status']=='forecast'
 assert c.post(p+'/forecast',headers=oidc_auth_headers('b','owner'),json={'fact_class':'slow','horizon':5,'as_of':11}).status_code==503
 assert c.post(p+'/forecast',headers=h,json={'extra':1}).status_code==422
 assert c.post(p+'/track',headers=h,json={'fact_id':'f','fact_class':'slow','source':'fixture','confirmed_at':11}).status_code==200
 assert c.post(p+'/evaluate',headers=h,json={'as_of':21}).json()['due'][0]['fact_id']=='f'
 assert c.post(p+'/refresh',headers=h,json={'fact_id':'f','source':'fixture:new','confirmed_at':21}).status_code==200
 stale=model(tmp_path);m.track('g','slow',source='fixture',confirmed_at=11);routes.bind_model(stale)
 assert c.post(p+'/evaluate',headers=h,json={'as_of':22}).status_code==409

def test_exact_sample_event_time_boundaries_and_false_alarm(tmp_path):
 m=model(tmp_path);rows=[{'history_id':str(i),'fact_class':'c','source':f'fixture:{i}','started_at':0.,'ended_at':10.,'changed':i<5}for i in range(40)]
 m.ingest(rows);r=m.forecast('c',horizon=10,as_of=10)
 assert r['events']==5 and r['censored']==35 and r['exposure']==400
 assert r['stale_probability']==pytest.approx(1-(401/411)**6)
 assert m.forecast('c',horizon=10,as_of=9.999)['status']=='abstained'
 other=model(tmp_path,'four');other.ingest([{**row,'changed':int(row['history_id'])<4}for row in rows]);assert other.forecast('c',horizon=10,as_of=10)['status']=='abstained'
 # Fixed holdout changed-by-5 truth, threshold policy versus always-due baseline.
 rng=random.Random(55);truth=[rng.expovariate(.01)<=5 for _ in range(1000)]
 slow=model(tmp_path,'slow');slow.ingest(history('slow',.01));p=slow.forecast('slow',horizon=5,as_of=11)['stale_probability']
 false_alarms=sum((p>=.5)and not y for y in truth);always_false_alarms=sum(not y for y in truth)
 assert false_alarms==0<always_false_alarms

def test_history_limit_and_timestamp_validation_unmasked(tmp_path):
 m=model(tmp_path);base=history(n=1)[0]
 for field in ['started_at','ended_at']:
  for value in [True,float('nan'),float('inf')]:
   with pytest.raises(ValueError):m.ingest([{**base,'history_id':f'{field}{value}',field:value}])
 for n in [0,1001]:
  with pytest.raises(ValueError):m.ingest([{**base,'history_id':str(i)}for i in range(n)])
 for prefix in ['a','b']:assert m.ingest([{**base,'history_id':f'{prefix}{i}'}for i in range(1000)])['inserted']==1000
 with pytest.raises(ValueError):m.ingest([{**base,'history_id':'2001'}])
 assert len(m.state['histories'])==2000
