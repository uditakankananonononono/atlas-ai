"""Actual particle-swarm recurrence and multidimensional benchmark checks."""
import random,math
import pytest
from app.modules.m20_general_cognitive_worker.particle_swarm import solve

def request(**kw):
 return {'objective':'sphere','bounds':[[-5.,5.],[-5.,5.]],'particles':24,'iterations':90,**kw}

def fitness(name,x):
 if name=='sphere':return sum(v*v for v in x)
 return sum(100*(x[i+1]-x[i]**2)**2+(1-x[i])**2 for i in range(len(x)-1))

@pytest.mark.parametrize('seed',range(5))
def test_multidimensional_swarm_converges_to_analytic_sphere_optimum(seed):
 r=solve(request(),seed)
 assert r['best_score']<1e-6
 assert r['objective']=='sphere' and r['global_optimum_guaranteed'] is False
 assert r==solve(request(),seed)
 assert r['evaluations']==24*91
 assert r['best_score']==fitness('sphere',r['best_position'])
 scores=[h['global_best_score']for h in r['history']];assert scores==sorted(scores,reverse=True)

@pytest.mark.parametrize('seed',[0,1,2])
def test_coupled_rosenbrock_benchmark(seed):
 d=request(objective='rosenbrock',bounds=[[-2.,2.],[-1.,3.]],particles=32,iterations=180)
 r=solve(d,seed)
 assert r['best_score']<.02 and r['best_score']==fitness('rosenbrock',r['best_position'])
 assert math.dist(r['best_position'],[1.,1.])<.2

def test_independent_first_update_rng_and_velocity_equation():
 d=request(particles=4,iterations=2,inertia=.6,cognitive=1.3,social=1.7)
 seed=17;rng=random.Random(seed);positions=[];velocities=[]
 for _ in range(4):
  positions.append([rng.uniform(lo,hi)for lo,hi in d['bounds']])
  velocities.append([rng.uniform(-(hi-lo)*.1,(hi-lo)*.1)for lo,hi in d['bounds']])
 scores=[fitness('sphere',p)for p in positions];best=positions[min(range(4),key=lambda i:scores[i])]
 nextpositions=[];nextvelocities=[]
 for p,v in zip(positions,velocities):
  nv=[];np=[]
  for j,(lo,hi) in enumerate(d['bounds']):
   r1,r2=rng.random(),rng.random()
   speed=.6*v[j]+1.3*r1*(p[j]-p[j])+1.7*r2*(best[j]-p[j])
   raw=p[j]+speed;clamped=max(lo,min(hi,raw));nv.append(speed if clamped==raw else 0.);np.append(clamped)
  nextpositions.append(np);nextvelocities.append(nv)
 actual=solve(d,seed);zero,one=actual['history'][:2]
 assert zero['positions']==positions and zero['velocities']==velocities
 assert one['positions']==nextpositions and one['velocities']==nextvelocities
 assert one['scores']==[fitness('sphere',p)for p in nextpositions]
 for history in actual['history']:
  assert history['scores']==[fitness('sphere',p)for p in history['positions']]
  assert history['personal_best_scores']==[fitness('sphere',p)for p in history['personal_best_positions']]
  for p in history['positions']:assert all(lo<=v<=hi for v,(lo,hi)in zip(p,d['bounds']))

@pytest.mark.parametrize('bad',[
 {'objective':'arbitrary'},{'bounds':[]},{'bounds':[[1,1]]},{'bounds':[[2,1]]},
 {'bounds':[[True,2]]},{'bounds':[[0,float('inf')]]},{'particles':1},
 {'particles':129},{'iterations':0},{'iterations':True},{'inertia':-1},
 {'cognitive':float('nan')},{'social':5},{'objective':'rosenbrock','bounds':[[0,1]]},
])
def test_invalid_inputs_refuse(bad):
 with pytest.raises(ValueError):solve(request(**bad),1)

def test_retained_work_bound_and_objective_overflow_refused():
 with pytest.raises(ValueError,match='product'):solve(request(bounds=[[-1,1]]*16,particles=128,iterations=1000))
 with pytest.raises(ValueError):solve(request(bounds=[[-1e308,1e308]]*2))
 for seed in (-1,True,2**32):
  with pytest.raises(ValueError):solve(request(),seed)

def test_production_mounted_route_seed_and_validation(monkeypatch,oidc_auth_headers):
 from fastapi.testclient import TestClient
 from app.main import app
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);path='/api/v1/api/modules/20/particle-swarm/solve'
 d=request(particles=4,iterations=2)
 assert c.post(path,json={'data':d}).status_code==401
 for seed in (1,2):
  r=c.post(path,headers=oidc_auth_headers('pso','owner'),json={'data':d,'seed':seed})
  assert r.status_code==200 and r.json()==solve(d,seed)
 assert c.post(path,headers=oidc_auth_headers('pso','owner'),json={'data':request(particles=1)}).status_code==422
