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

def test_search_discovers_optimum_absent_from_random_start():
 d=request();r=solve_quadratic(d,1)
 assert r['generation_history'][0]['best_score']<12
 assert r['generation_history'][-1]['best_score']==12
 assert any(h['best_score']==12 for h in r['generation_history'][1:])

def test_no_exhaustive_oracle_hidden_in_solver():
 import inspect
 from app.modules.m20_general_cognitive_worker import genetic_algorithm
 text=inspect.getsource(genetic_algorithm)
 assert 'itertools' not in text and 'product(' not in text

def test_quadratic_work_bound_and_reverse_pair_equivalence():
 with pytest.raises(ValueError,match='quadratic evaluation'):
  solve_quadratic(request(weights=[1]*64,interactions=[[i,j,1] for i in range(64) for j in range(i+1,64)],population_size=128,generations=10))
 a=request();b=request(interactions=[[j,i,c] for i,j,c in a['interactions']])
 assert solve_quadratic(a,1)==solve_quadratic(b,1)

def test_ga01_result_bytes_preserved_against_versioned_reference():
 # Fixed recorded GA01 fixture keeps regression proof independent of shared core.
 import hashlib,json
 d={'weights':[1.,2.,3.,4.],'population':[[0,0,0,0],[1,0,1,0],[0,1,0,1],[1,1,0,0]],'generations':12,'mutation_rate':.2,'crossover_rate':1.,'tournament_size':2,'elite_count':1}
 result=json.dumps(solve(d,17),sort_keys=True,separators=(',',':')).encode()
 assert hashlib.sha256(result).hexdigest()=='4f853851e86459b3ef2674e9486074eaa33a2a7a8de175b8026c006928feb8a9'

def test_random_initialization_and_first_generation_share_one_advancing_rng():
 # Independent draw-by-draw oracle for operators, not an output copied from solver.
 d=request(population_size=5,generations=1,elite_count=1,tournament_size=3,mutation_rate=.4,crossover_rate=.7)
 seed=37;rng=random.Random(seed);n=len(d['weights']);size=d['population_size']
 initial=[[rng.randrange(2) for _ in range(n)] for _ in range(size)]
 scores=[score(d,g) for g in initial]
 elite=initial[max(range(size),key=lambda i:scores[i])]
 expected=[]
 for _ in range(size-1):
  contests=[];parents=[]
  for _ in range(2):
   indices=[rng.randrange(size) for _ in range(d['tournament_size'])]
   winner=max(indices,key=lambda i:scores[i])
   contests.append([initial[i] for i in indices]);parents.append(initial[winner])
  cut=rng.randrange(1,n) if rng.random()<d['crossover_rate'] else None
  raw=parents[0] if cut is None else parents[0][:cut]+parents[1][cut:]
  mutations=[i for i in range(n) if rng.random()<d['mutation_rate']]
  genome=[1-v if i in mutations else v for i,v in enumerate(raw)]
  expected.append({'parents':parents,'tournaments':contests,'crossover_point':cut,
                   'mutated_positions':mutations,'genome':genome,'score':score(d,genome)})
 actual=solve_quadratic(d,seed)
 assert actual['generation_history'][0]['population']==initial
 assert actual['generation_history'][1]['offspring']==expected
 assert actual['generation_history'][1]['population']==[elite]+[x['genome'] for x in expected]
