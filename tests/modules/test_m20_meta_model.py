"""Finite declared Bayesian hypotheses. Synthetic truth, not world discovery."""
from copy import deepcopy
from fractions import Fraction
from itertools import product
import math
import pytest
import sqlalchemy as sa
from app.modules.m20_general_cognitive_worker.bayesian_models import BayesianModelRegistry
from app.modules.m20_general_cognitive_worker.meta_persistence import MetaRepository

def registry(tmp_path,tenant='a'):
 r=MetaRepository(sa.create_engine(f'sqlite:///{tmp_path}/models.sqlite'),tenant_id=tenant);r.create_schema();return BayesianModelRegistry.load(r)
def hypotheses(p=.5):return {'a':{'prior':p,'assumptions':{'state':'A'}},'b':{'prior':1-p,'assumptions':{'state':'B'}}}
def configure(r,p=.5):return r.configure(hypotheses(p),partition_source='fixture:closed-two-worlds',conditional_independence=True)
def evidence(i,a,b):return {'evidence_id':str(i),'source':f'fixture:observation:{i}','observation':f'observed-{i}','likelihoods':{'a':a,'b':b}}

def test_exhaustive_exact_small_bayes_and_order_independence(tmp_path):
 for k,(p,aa,ab,ba,bb)in enumerate(product([Fraction(1,4),Fraction(1,2)],repeat=5)):
  r=registry(tmp_path,str(k));configure(r,float(p));rows=[evidence('1',float(aa),float(ab)),evidence('2',float(ba),float(bb))];r.ingest(rows)
  expected=p*aa*ba/(p*aa*ba+(1-p)*ab*bb);s=r.compare()
  assert s['status']=='compared' and s['posteriors']['a']==pytest.approx(float(expected))
  assert sum(s['posteriors'].values())==pytest.approx(1)
  other=registry(tmp_path,'reverse'+str(k));configure(other,float(p));other.ingest(rows[::-1]);assert other.compare()==s
  assert s['evidence_ids']==['1','2'] and s['source_truth_verified'] is False
  assert 0<=s['entropy_bits']<=1.00000001

def test_contradiction_zero_likelihood_missing_and_uncertainty(tmp_path):
 r=registry(tmp_path);assert r.compare()['posteriors'] is None
 configure(r);assert r.compare()['status']=='abstained'
 r.ingest([evidence(1,.8,.2)]);assert r.compare()['posteriors']['a']==pytest.approx(.8)
 r.ingest([evidence(2,.2,.8)]);s=r.compare();assert s['posteriors']['a']==pytest.approx(.5) and s['current_best'] is None and s['entropy_bits']==pytest.approx(1)
 r.ingest([evidence(3,0,1)]);assert r.compare()['posteriors']=={'a':0,'b':1}
 r.ingest([evidence(4,1,0)]);assert r.compare()['status']=='abstained' and r.compare()['posteriors'] is None
 missing=registry(tmp_path,'missing');configure(missing);missing.ingest([{**evidence(1,.8,.2),'likelihoods':{'a':.8}}]);assert missing.compare()['reason']=='missing_likelihoods'
 missing2=registry(tmp_path,'missing2');configure(missing2);missing2.ingest([{**evidence(1,.8,.2),'likelihoods':None}]);assert missing2.compare()['posteriors'] is None

def test_versions_history_restart_duplicate_and_isolation(tmp_path):
 r=registry(tmp_path);configure(r);rows=[evidence(1,.8,.2)];r.ingest(rows);rev=r._revision;state=deepcopy(r.state)
 assert r.ingest(rows)['inserted']==0 and r._revision==rev and r.repo.read(r.kind)[0]==rev
 with pytest.raises(ValueError):r.ingest([evidence(1,.2,.8)])
 assert r.state==state
 r.configure(hypotheses(.25),partition_source='fixture:changed',conditional_independence=True)
 assert r.state['version']==2 and r.state['history']==[state|{'history':[]}]
 assert r.compare()['posteriors'] is None and r.state['evidence']=={}
 fresh=registry(tmp_path);assert fresh.state==r.state
 fresh.ingest(rows);assert fresh.compare()['posteriors']['a']==pytest.approx(4/7)
 assert registry(tmp_path,'b').state is None

@pytest.mark.parametrize('change',[{'source':''},{'observation':''},{'evidence_id':''},{'likelihoods':{'a':True,'b':.2}},{'likelihoods':{'a':float('nan'),'b':.2}},{'likelihoods':{'a':float('inf'),'b':.2}},{'likelihoods':{'a':-.1,'b':.2}},{'likelihoods':{'a':1.1,'b':.2}},{'likelihoods':{'alien':.2}}])
def test_invalid_evidence_atomic_fresh_ids(tmp_path,change):
 r=registry(tmp_path);configure(r);before=deepcopy(r.state)
 with pytest.raises(ValueError):r.ingest([{**evidence('fresh',.8,.2),**change}])
 assert r.state==before

def test_invalid_configuration_and_missing_contract(tmp_path):
 r=registry(tmp_path)
 for h,source,independent in [(hypotheses(),'source',False),(hypotheses(),' ',True),({'a':hypotheses()['a']},'source',True),(hypotheses(float('nan')),'source',True),({'a':{'prior':True,'assumptions':{}},'b':{'prior':0,'assumptions':{}}},'source',True),({'a':{'prior':.2,'assumptions':{}},'b':{'prior':.2,'assumptions':{}}},'source',True)]:
  with pytest.raises(ValueError):r.configure(h,partition_source=source,conditional_independence=independent)
 assert r.state is None
 with pytest.raises(ValueError):r.ingest([evidence(1,.8,.2)])

def test_stale_rollback_and_numeric_stability(tmp_path,monkeypatch):
 a,b=registry(tmp_path),registry(tmp_path);configure(a)
 with pytest.raises(RuntimeError,match='stale'):configure(b)
 assert b.state is None
 before=deepcopy(a.state)
 def fail(session):raise RuntimeError('rollback')
 monkeypatch.setattr(a.repo,'_before_commit',fail)
 with pytest.raises(RuntimeError):a.ingest([evidence(1,.8,.2)])
 assert a.state==before==registry(tmp_path).state
 c=registry(tmp_path);c.ingest([evidence(i,1e-100,2e-100)for i in range(1000)])
 assert c.compare()['posteriors']['b']> .999 and math.isfinite(c.compare()['entropy_bits'])
 with pytest.raises(ValueError):c.ingest([evidence('1001',.1,.2)])

def test_mounted_authenticated_routes_and_errors(tmp_path,monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 from app.modules.m20_general_cognitive_worker import bayesian_model_routes as routes
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_registries',{})
 with pytest.raises(ValueError):routes.bind_registry(object())
 r=registry(tmp_path);routes.bind_registry(r);c=TestClient(app);h=oidc_auth_headers('a','owner');path='/api/v1/api/modules/20/bayesian-models'
 payload={'hypotheses':hypotheses(),'partition_source':'fixture:partition','conditional_independence':True}
 assert c.post(path+'/configure',json=payload).status_code==401
 assert c.post(path+'/configure',headers=h,json=payload).status_code==200
 assert c.post(path+'/evidence',headers=h,json={'records':[evidence(1,.8,.2)]}).status_code==200
 result=c.get(path,headers=h);assert result.status_code==200 and result.json()['posteriors']['a']==pytest.approx(.8)
 assert c.get(path,headers=oidc_auth_headers('b','owner')).status_code==503
 assert c.post(path+'/configure',headers=h,json={'extra':1}).status_code==422
 assert c.post(path+'/evidence',headers=h,json={'records':[evidence(2,True,.2)]}).status_code==422
 stale=registry(tmp_path);r.ingest([evidence(2,.2,.8)]);routes.bind_registry(stale)
 assert c.post(path+'/evidence',headers=h,json={'records':[evidence(3,.8,.2)]}).status_code==409
