"""Coupled binary GA: independent quadratic oracle, seeded random initialization."""
import itertools,random
import pytest
from app.modules.m20_general_cognitive_worker.genetic_algorithm import solve,solve_quadratic

def request(**kw):
 return {'weights':[-3.,-3.,-3.,-3.,-3.,-3.], 'interactions':[[i,j,2.] for i in range(6) for j in range(i+1,6)], 'population_size':24,'generations':40,'mutation_rate':.2,'crossover_rate':.9,'elite_count':2,**kw}

def score(d,g):
 return sum(w*b for w,b in zip(d['weights'],g))+sum(c*g[i]*g[j] for i,j,c in d['interactions'])

@pytest.mark.parametrize('seed',range(10))
def test_deceptive_coupled_search_matches_independent_oracle(seed):
 d=request();r=solve_quadratic(d,seed)
 oracle=max((score(d,g),g) for g in itertools.product([0,1],repeat=6))
 assert r['best_score']==oracle[0]==12.
 assert tuple(r['best_genome'])==oracle[1]
 assert score(d,[0]*6)==0 and all(score(d,[int(i==j) for i in range(6)])<0 for j in range(6))
 assert r['objective']=='maximize_binary_quadratic' and r['initialization']=='seeded_random_binary'
 assert r['global_optimum_guaranteed'] is False
 assert r==solve_quadratic(d,seed)
 rng=random.Random(seed);expected=[[rng.randrange(2) for _ in range(6)] for _ in range(24)]
 assert r['generation_history'][0]['population']==expected
 assert r['evaluations']==24*41
 previous=None
 for h in r['generation_history']:
  assert h['scores']==[score(d,g) for g in h['population']]
  assert h['best_score']==max(h['scores'])
  if previous:
   ranked=sorted(range(24),key=lambda i:previous['scores'][i],reverse=True)
   assert h['population'][:2]==[previous['population'][i] for i in ranked[:2]]
   for child in h['offspring']:
    a,b=child['parents'];cut=child['crossover_point'];raw=a if cut is None else a[:cut]+b[cut:]
    assert child['genome']==[1-v if i in child['mutated_positions'] else v for i,v in enumerate(raw)]
    assert child['score']==score(d,child['genome'])
    for choices,winner in zip(child['tournaments'],child['parents']):assert score(d,winner)==max(map(lambda g:score(d,g),choices))
  previous=h

def test_frustrated_signed_interactions_and_seed_changes():
 d=request(weights=[.2,-.4,.5,0.],interactions=[[0,1,4.],[1,2,-5.],[2,3,3.],[0,3,-2.]],population_size=16,generations=35)
 oracle=max(score(d,g) for g in itertools.product([0,1],repeat=4))
 for seed in (1,2,3):assert solve_quadratic(d,seed)['best_score']==oracle
 assert solve_quadratic(d,1)['generation_history']!=solve_quadratic(d,2)['generation_history']

@pytest.mark.parametrize('bad',[
 {'interactions':[]},{'interactions':[[0,0,1]]},{'interactions':[[0,6,1]]},
 {'interactions':[[True,1,1]]},{'interactions':[[0,1,float('nan')]]},
 {'interactions':[[0,1,0]]},{'interactions':[[0,1,1],[1,0,2]]},
 {'interactions':[[0,1]]},{'interactions':'bad'}, {'population_size':1},
 {'population_size':129},{'population_size':True},{'population':[[0]*6]*2},
 {'weights':[]},{'generations':True},{'mutation_rate':2},{'elite_count':24}
])
def test_invalid_quadratic_inputs_refuse(bad):
 with pytest.raises(ValueError):solve_quadratic(request(**bad),1)

def test_exact_mounted_production_route(monkeypatch,oidc_auth_headers):
 from fastapi.testclient import TestClient
 from app.main import app
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);path='/api/v1/api/modules/20/genetic-algorithms/solve-quadratic'
 assert c.post(path,json={'data':request()}).status_code==401
 headers=oidc_auth_headers('ga02','owner')
 for seed in (1,2):
  r=c.post(path,headers=headers,json={'data':request(),'seed':seed})
  assert r.status_code==200 and r.json()==solve_quadratic(request(),seed)
 assert c.post(path,headers=headers,json={'data':request(interactions=[])}).status_code==422

@pytest.mark.parametrize('seed',[-1,True,2**32])
def test_seed_refusal(seed):
 with pytest.raises(ValueError):solve_quadratic(request(),seed)

def test_bound_and_overflow_refusal():
 with pytest.raises(ValueError,match='product'):solve_quadratic(request(weights=[1]*64,interactions=[[0,1,1]],population_size=128,generations=1000))
 with pytest.raises(ValueError,match='overflow'):solve_quadratic(request(weights=[1e308]*6),1)
