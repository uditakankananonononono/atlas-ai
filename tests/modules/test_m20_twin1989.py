"""Stateful scalar linear twin assimilates observations, not residual-only arrays."""
import pytest
from app.modules.m20_general_cognitive_worker.digital_twin import TwinRegistry

def create(registry,name='asset'):
 return registry.create(name,state=0.,variance=4.,timestamp=0.,transition=1.,control_gain=2.,process_noise=.5,measurement_noise=1.)

def test_independent_kalman_recurrence_observed_state_and_forecast():
 r=TwinRegistry('a');create(r)
 first=r.assimilate('asset',timestamp=2.,observation=7.,control=1.)
 # xpred=2; Ppred=5; innovation5; K=5/6; updated37/6, P5/6.
 assert first['state']==pytest.approx(37/6) and first['variance']==pytest.approx(5/6)
 h=first['history'][0]
 assert h['predicted_state']==2 and h['predicted_variance']==5
 assert h['innovation']==5 and h['gain']==pytest.approx(5/6) and h['observation']==7
 forecast=r.forecast('asset',timestamp=4.,control=-1.)
 assert forecast['state']==pytest.approx(25/6) and forecast['variance']==pytest.approx(11/6)
 assert r.get('asset')==first
 second=r.assimilate('asset',timestamp=4.,observation=3.,control=-1.)
 gain=(11/6)/(17/6)
 assert second['state']==pytest.approx(25/6+gain*(3-25/6))
 assert second['variance']==pytest.approx((1-gain)*(11/6))
 assert len(second['history'])==2 and second['timestamp']==4
 assert second['source_truth_verified'] is False

def test_transition_and_prediction_uncertainty_drive_actual_updates():
 r=TwinRegistry('a');r.create('m',state=3,variance=2,timestamp=1,transition=.5,control_gain=1,process_noise=.2,measurement_noise=2)
 f=r.forecast('m',timestamp=3,control=4)
 assert f['state']==5.5 and f['variance']==pytest.approx(.9)
 updated=r.assimilate('m',timestamp=3,observation=8,control=4)
 assert updated['history'][0]['gain']==pytest.approx(.9/2.9)
 assert updated['state']==pytest.approx(5.5+.9/2.9*2.5)

@pytest.mark.parametrize('timestamp',[0,-1,True,float('nan')])
def test_out_of_order_invalid_timestamp_preserves_state(timestamp):
 r=TwinRegistry('a');before=create(r)
 with pytest.raises(ValueError):r.assimilate('asset',timestamp=timestamp,observation=1)
 assert r.get('asset')==before

def test_missing_duplicate_and_tenant_store_isolation():
 a,b=TwinRegistry('a'),TwinRegistry('b');create(a)
 with pytest.raises(KeyError):b.get('asset')
 with pytest.raises(ValueError):create(a)
 a.assimilate('asset',timestamp=1,observation=2)
 assert b.names()==[]

@pytest.mark.parametrize('bad',[{'variance':-1},{'measurement_noise':0},{'process_noise':-1},{'state':True},{'transition':float('inf')},{'timestamp':float('nan')}])
def test_model_parameters_refuse(bad):
 r=TwinRegistry('a');d=dict(state=0,variance=1,timestamp=0,transition=1,control_gain=1,process_noise=.1,measurement_noise=1);d.update(bad)
 with pytest.raises(ValueError):r.create('m',**d)
 assert r.names()==[]

def test_nonfinite_and_overflow_update_atomic_and_read_copy():
 r=TwinRegistry('a');before=create(r)
 with pytest.raises(ValueError):r.assimilate('asset',timestamp=1,observation=float('inf'))
 with pytest.raises(ValueError):r.assimilate('asset',timestamp=1,observation=1,control=1e308)
 assert r.get('asset')==before
 copy=r.get('asset');copy['state']=100;assert r.get('asset')['state']==0

def test_production_routes_authenticated_tenant_no_cross_read(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker import digital_twin_routes as routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_registries',{})
 routes.bind_registry(TwinRegistry('a'))
 c=TestClient(app);path='/api/v1/api/modules/20/digital-twins';d={'name':'asset','state':0,'variance':4,'timestamp':0,'transition':1,'control_gain':2,'process_noise':.5,'measurement_noise':1}
 assert c.post(path,json=d).status_code==401
 h=oidc_auth_headers('a','owner');assert c.post(path,headers=h,json=d).status_code==201
 update=c.post(path+'/asset/assimilate',headers=h,json={'timestamp':2,'observation':7,'control':1})
 assert update.status_code==200 and update.json()['state']==pytest.approx(37/6)
 assert c.get(path+'/asset',headers=oidc_auth_headers('b','owner')).status_code==503
 assert c.post(path+'/asset/assimilate',headers=h,json={'timestamp':2,'observation':9}).status_code==422

def test_multiple_observations_match_independent_scalar_filter():
 r=TwinRegistry('a');r.create('m',state=2,variance=3,timestamp=0,transition=.8,control_gain=1.2,process_noise=.4,measurement_noise=.7)
 state,variance,time=2.,3.,0.
 for timestamp,observation,control in [(1,3,.5),(3,0,-1),(4,5,2),(7,-2,0)]:
  pred=.8*state+1.2*control;p=.8**2*variance+.4*(timestamp-time);k=p/(p+.7)
  state=pred+k*(observation-pred);variance=(1-k)*p;time=timestamp
  actual=r.assimilate('m',timestamp=timestamp,observation=observation,control=control)
  assert actual['state']==pytest.approx(state)and actual['variance']==pytest.approx(variance)
  assert actual['history'][-1]['innovation']==pytest.approx(observation-pred)

def test_zero_uncertainty_then_process_noise_and_model_history_bounds():
 r=TwinRegistry('a');r.create('m',state=2,variance=0,timestamp=0,process_noise=0,measurement_noise=1)
 updated=r.assimilate('m',timestamp=1,observation=10)
 assert updated['state']==2 and updated['variance']==0 and updated['history'][-1]['gain']==0
 for t in range(2,1001):r.assimilate('m',timestamp=t,observation=2)
 before=r.get('m')
 with pytest.raises(ValueError,match='history limit'):r.assimilate('m',timestamp=1001,observation=2)
 assert r.get('m')==before
 for i in range(127):create(r,str(i))
 with pytest.raises(ValueError,match='model limit'):create(r,'overflow')

def test_atomic_timestamp_race_only_one_observation_commits():
 from concurrent.futures import ThreadPoolExecutor
 r=TwinRegistry('a');create(r)
 def update(value):
  try:r.assimilate('asset',timestamp=1,observation=value);return 'committed'
  except ValueError:return 'refused'
 with ThreadPoolExecutor(max_workers=2)as pool:out=list(pool.map(update,[2,3]))
 assert sorted(out)==['committed','refused'] and len(r.get('asset')['history'])==1

def test_lock_serializes_observation_while_first_prediction_is_blocked(monkeypatch):
 import threading
 from concurrent.futures import ThreadPoolExecutor
 r=TwinRegistry('a');create(r);entered=threading.Event();release=threading.Event();second_started=threading.Event();concurrent=threading.Event()
 original=r._prediction;count=0;guard=threading.Lock()
 def blocked(*args):
  nonlocal count
  with guard:count+=1;index=count
  if index==1:
   entered.set();assert release.wait(5)
  else:concurrent.set()
  return original(*args)
 monkeypatch.setattr(r,'_prediction',blocked)
 def update(value):
  if value==3:second_started.set()
  try:r.assimilate('asset',timestamp=1,observation=value);return 'committed'
  except ValueError:return 'refused'
 with ThreadPoolExecutor(max_workers=2)as pool:
  first=pool.submit(update,2);assert entered.wait(5)
  second=pool.submit(update,3);assert second_started.wait(5)
  try:assert not concurrent.wait(.2)
  finally:release.set()
  assert sorted([first.result(),second.result()])==['committed','refused']
 assert len(r.get('asset')['history'])==1

def test_forecast_default_control_hand_value_and_not_committed():
 r=TwinRegistry('a');create(r);before=r.get('asset')
 default=r.forecast('asset',timestamp=2)
 assert default==r.forecast('asset',timestamp=2,control=0)
 assert default['state']==0 and default['variance']==5 and default['committed'] is False
 assert r.get('asset')==before

def test_registry_and_model_identity_boundaries():
 from app.modules.m20_general_cognitive_worker.digital_twin_routes import bind_registry
 try:bind_registry(object())
 except Exception as exc:assert isinstance(exc,ValueError) and 'TwinRegistry required' in str(exc)
 else:pytest.fail('invalid registry accepted')
 for tenant in ('','  ',1):
  with pytest.raises(ValueError):TwinRegistry(tenant)
 r=TwinRegistry('a');assert create(r,'a'*120)['name']=='a'*120
 for name in ('a'*121,'','  '):
  with pytest.raises(ValueError):create(r,name)

def test_forecast_and_error_routes_actual_tenant_and_state(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker import digital_twin_routes as routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_registries',{})
 store=TwinRegistry('a');create(store);routes.bind_registry(store)
 c=TestClient(app);path='/api/v1/api/modules/20/digital-twins';headers=oidc_auth_headers('a','owner')
 before=c.get(path+'/asset',headers=headers).json()
 response=c.post(path+'/asset/forecast',headers=headers,json={'timestamp':2})
 assert response.status_code==200 and response.json()['state']==0 and response.json()['variance']==5
 assert response.json()['committed'] is False
 assert c.get(path+'/asset',headers=headers).json()==before
 assert c.post(path+'/asset/forecast',headers=oidc_auth_headers('b','owner'),json={'timestamp':2}).status_code==503
 assert c.get(path+'/missing',headers=headers).status_code==404
 assert c.post(path+'/missing/assimilate',headers=headers,json={'timestamp':1,'observation':1}).status_code==404
 assert c.post(path+'/asset/forecast',headers=headers,json={'timestamp':2,'extra':1}).status_code==422
 assert c.post(path,headers=headers,json={'name':'new','state':0,'variance':1,'timestamp':0,'extra':1}).status_code==422
