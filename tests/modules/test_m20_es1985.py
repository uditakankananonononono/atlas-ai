"""Actual DE/rand/1/bin evolution, independent operator draws and objectives."""
import math,random
import pytest
from app.modules.m20_general_cognitive_worker.differential_evolution import solve

def request(**kw):return {'objective':'sphere','bounds':[[-5.,5.],[-5.,5.]],'population_size':24,'generations':80,**kw}
def score(name,x):return sum(v*v for v in x)if name=='sphere'else sum(100*(x[i+1]-x[i]**2)**2+(1-x[i])**2 for i in range(len(x)-1))

@pytest.mark.parametrize('seed',range(5))
def test_sphere_actual_population_evolves_to_known_optimum(seed):
 d=request();r=solve(d,seed)
 assert r==solve(d,seed) and r['best_score']<1e-7
 assert r['best_score']==score('sphere',r['best_vector'])
 assert len(r['history'])==81 and r['history'][-1]['generation']==80
 assert r['evaluations']==24*81 and r['global_optimum_guaranteed'] is False
 for prev,cur in zip(r['history'],r['history'][1:]):
  assert cur['scores']==[score('sphere',x)for x in cur['population']]
  assert all(b<=a for a,b in zip(prev['scores'],cur['scores']))

@pytest.mark.parametrize('seed',[0,1,2])
def test_nonseparable_rosenbrock_search(seed):
 r=solve(request(objective='rosenbrock',bounds=[[-2,2],[-1,3]],population_size=32,generations=180),seed)
 assert r['best_score']<.01 and math.dist(r['best_vector'],[1,1])<.15

def test_independent_all_donor_mutation_crossover_selection_and_rng():
 d=request(population_size=5,generations=3,mutation_factor=.8,crossover_rate=.3);rng=random.Random(31)
 initial=[[rng.uniform(lo,hi)for lo,hi in d['bounds']]for _ in range(5)]
 r=solve(d,31);assert r['history'][0]['population']==initial
 accepted=rejected=forced=False
 for previous,current in zip(r['history'],r['history'][1:]):
  pop=previous['population'];scores=previous['scores'];expect=[]
  for target in range(5):
   donors=rng.sample([i for i in range(5)if i!=target],3)
   a,b,c=[pop[i]for i in donors]
   raw=[a[j]+.8*(b[j]-c[j])for j in range(2)]
   mutant=[max(lo,min(hi,v))for v,(lo,hi)in zip(raw,d['bounds'])]
   forced_index=rng.randrange(2);draws=[rng.random()for _ in range(2)]
   indices=[j for j in range(2)if draws[j]<.3 or j==forced_index]
   trial=[mutant[j]if j in indices else pop[target][j]for j in range(2)]
   trialscore=score('sphere',trial);take=trialscore<=scores[target]
   child=current['trials'][target]
   assert child=={'target_index':target,'donor_indices':donors,'mutant':mutant,'forced_index':forced_index,'crossed_indices':indices,'trial':trial,'trial_score':trialscore,'accepted':take}
   expect.append(trial if take else pop[target]);accepted|=take;rejected|=not take;forced|=draws[forced_index]>=.3
  assert current['population']==expect
 assert accepted and rejected and forced

@pytest.mark.parametrize('bad',[{'population_size':3},{'population_size':129},{'generations':0},{'generations':1001},{'generations':True},{'mutation_factor':0},{'mutation_factor':2.0001},{'crossover_rate':-1},{'crossover_rate':1.01},{'bounds':[]},{'bounds':[[1,1]]},{'bounds':[[True,2]]},{'bounds':[[0,float('inf')]]},{'objective':'other'},{'objective':'rosenbrock','bounds':[[0,1]]}])
def test_invalid_inputs_refuse(bad):
 with pytest.raises(ValueError):solve(request(**bad),1)

def test_work_boundary_and_coefficient_edges():
 with pytest.raises(ValueError,match='product'):solve(request(bounds=[[-1,1]]*16,population_size=128,generations=48),1)
 assert solve(request(population_size=4,generations=1,mutation_factor=2.,crossover_rate=0),1)['history'][1]['trials'][0]['crossed_indices']
 for seed in (-1,True,2**32):
  with pytest.raises(ValueError):solve(request(),seed)

def test_mounted_production_route_auth_exact_seed(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);path='/api/v1/api/modules/20/differential-evolution/solve';d=request(population_size=5,generations=2)
 assert c.post(path,json={'data':d}).status_code==401
 for seed in (1,2):
  r=c.post(path,headers=oidc_auth_headers('de','owner'),json={'data':d,'seed':seed})
  assert r.status_code==200 and r.json()==solve(d,seed)
 assert c.post(path,headers=oidc_auth_headers('de','owner'),json={'data':request(population_size=3)}).status_code==422

def test_actual_counted_scores_iteration_limit_seed_and_overflow():
 import sys
 from app.modules.m20_general_cognitive_worker import differential_evolution
 calls=[]
 def profile(frame,event,arg):
  if event=='call'and frame.f_code.co_name=='score'and frame.f_code.co_filename==differential_evolution.__file__:calls.append(1)
 old=sys.getprofile()
 try:
  sys.setprofile(profile);r=solve(request(population_size=4,generations=7),3)
 finally:sys.setprofile(old)
 assert r['evaluations']==len(calls)==32 and len(r['history'])==8
 d=request(bounds=[[-1,1]],population_size=4)
 assert len(solve({**d,'generations':1000},1)['history'])==1001
 with pytest.raises(ValueError,match='generations'):solve({**d,'generations':1001},1)
 with pytest.raises(ValueError,match='objective overflow'):solve(request(bounds=[[-1e200,1e200]]*2,generations=1),1)
 assert solve(request(population_size=4,generations=1),1)['history']!=solve(request(population_size=4,generations=1),2)['history']

def test_population_validation_happens_before_donor_sampling():
 with pytest.raises(ValueError,match='population_size requires integer4..128'):
  solve(request(population_size=3,generations=1),1)

def test_rosenbrock_exact_receipts_and_best_argmin_before_convergence():
 d=request(objective='rosenbrock',bounds=[[-2,2],[-1,3]],population_size=5,generations=3)
 r=solve(d,13)
 for h in r['history']:
  assert h['scores']==[score('rosenbrock',x)for x in h['population']]
  index=min(range(5),key=lambda i:h['scores'][i])
  assert h['best_score']==h['scores'][index]
  assert h['best_vector']==h['population'][index]
  for trial in h['trials']:assert trial['trial_score']==score('rosenbrock',trial['trial'])
 final=r['history'][-1];index=min(range(5),key=lambda i:final['scores'][i])
 assert r['best_score']==min(final['scores']) and r['best_vector']==final['population'][index]
 assert max(final['scores'])>min(final['scores'])

def test_boundary_clipped_equal_fitness_trial_is_accepted(monkeypatch):
 from app.modules.m20_general_cognitive_worker import differential_evolution
 class AtBoundary(random.Random):
  def uniform(self,lo,hi):return hi
 monkeypatch.setattr(differential_evolution.random,'Random',AtBoundary)
 r=solve(request(bounds=[[0.,1.]],population_size=4,generations=1,mutation_factor=2.,crossover_rate=0.),17)
 assert r['history'][0]['population']==[[1.]]*4
 for trial in r['history'][1]['trials']:
  assert trial['mutant']==trial['trial']==[1.]
  assert trial['trial_score']==1. and trial['accepted'] is True
