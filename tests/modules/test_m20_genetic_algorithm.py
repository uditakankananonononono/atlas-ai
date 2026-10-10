"""Actual binary genetic algorithm behavior, not scalar Gaussian substitution."""
import itertools
import pytest
from app.modules.m20_general_cognitive_worker.genetic_algorithm import solve

def request(**kw):
 return {'weights':[1.,2.,3.,4.],'population':[[0,0,0,0],[1,0,1,0],[0,1,0,1],[1,1,0,0]],'generations':12,'mutation_rate':.2,'crossover_rate':1.,'tournament_size':2,'elite_count':1,**kw}

def test_actual_genetic_operations_and_independent_objective():
 data=request();r=solve(data,seed=17)
 assert r==solve(data,seed=17)
 assert r['algorithm']=='binary_genetic_algorithm' and r['objective']=='maximize_weighted_bit_sum'
 assert len(r['generation_history'])==13
 assert r['evaluations']==4*13
 assert r['best_score']==sum(w*b for w,b in zip(data['weights'],r['best_genome']))
 scores=[g['best_score'] for g in r['generation_history']]
 assert scores==sorted(scores)
 assert r['best_score']==max(sum(w*b for w,b in zip(data['weights'],bits)) for bits in itertools.product([0,1],repeat=4))
 assert r['global_optimum_guaranteed'] is False
 for g in r['generation_history'][1:]:
  assert len(g['offspring'])==3
  for child in g['offspring']:
   a,b=child['parents'];cut=child['crossover_point']
   assert 1<=cut<4
   pre=a[:cut]+b[cut:]
   expect=[1-v if i in child['mutated_positions'] else v for i,v in enumerate(pre)]
   assert child['genome']==expect
   assert child['score']==sum(w*v for w,v in zip(data['weights'],expect))
   for candidates,winner in zip(child['tournaments'],child['parents']):
    assert sum(w*v for w,v in zip(data['weights'],winner))==max(sum(w*v for w,v in zip(data['weights'],x)) for x in candidates)

@pytest.mark.parametrize('seed',range(8))
def test_small_search_reproduces_oracle_without_claiming_general_optimality(seed):
 d=request(weights=[-1.,2.,3.,-4.],generations=30,mutation_rate=.3)
 r=solve(d,seed)
 assert r['best_score']==5 and r['best_genome']==[0,1,1,0]

@pytest.mark.parametrize('bad',[
 {'weights':[]},{'weights':[float('nan'),1,1,1]}, {'population':[[2,0,0,0],[0,0,0,0]]},
 {'population':[[True,0,0,0],[0,0,0,0]]}, {'population':[[0,0],[1,0]]},
 {'mutation_rate':-1},{'mutation_rate':1.1},{'crossover_rate':2},
 {'generations':0},{'generations':1001},{'generations':True},{'tournament_size':0},
 {'tournament_size':5},{'elite_count':0},{'elite_count':4},
])
def test_invalid_inputs_fail_closed(bad):
 with pytest.raises(ValueError):solve(request(**bad),1)

def test_crossover_and_mutation_are_actual_distinct_operators():
 zero=solve(request(generations=1,mutation_rate=0),2)
 one=solve(request(generations=1,mutation_rate=1),2)
 for a,b in zip(zero['generation_history'][1]['offspring'],one['generation_history'][1]['offspring']):
  assert a['mutated_positions']==[] and b['mutated_positions']==list(range(4))
  assert b['genome']==[1-v for v in a['genome']]
 off=solve(request(generations=1,crossover_rate=0,mutation_rate=0),2)
 for child in off['generation_history'][1]['offspring']:
  assert child['crossover_point'] is None and child['genome']==child['parents'][0]

def test_full_mounted_route_auth_and_actual_result(monkeypatch,oidc_auth_headers):
 from fastapi.testclient import TestClient
 from app.main import app
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app)
 path='/api/v1/api/modules/20/genetic-algorithms/solve'
 assert c.post(path,json={'data':request()}).status_code==401
 r=c.post(path,headers=oidc_auth_headers('tenant-ga','owner'),json={'data':request(),'seed':17})
 assert r.status_code==200 and r.json()['best_score']==10
 assert c.post(path,headers=oidc_auth_headers('tenant-ga','owner'),json={'data':request(mutation_rate=2)}).status_code==422

def test_retained_lineage_bound_and_overflow_refused():
 with pytest.raises(ValueError,match='product'):solve(request(weights=[1]*64,population=[[0]*64]*128,generations=1000))
 with pytest.raises(ValueError,match='overflow'):solve(request(weights=[1e308]*4,population=[[1]*4,[0]*4]))
 for seed in (-1,True,2**32):
  with pytest.raises(ValueError):solve(request(),seed)

def test_catalog_separates_actual_algorithm_from_legacy_reference():
 from app.modules.m20_general_cognitive_worker.cognitive_routes_1960_2009 import methods
 row=next(x for x in methods() if x['method']=='genetic_algorithms')
 assert row['status']=='reference_substitute_only' and row['original_capability_status']=='unverified'
 assert row['actual_implementation']['algorithm']=='binary_genetic_algorithm'
 assert row['actual_implementation']['route']=='/api/v1/api/modules/20/genetic-algorithms/solve'

@pytest.mark.parametrize('elite_count',[2,3])
def test_top_k_elites_preserved_unchanged_and_offspring_count(elite_count):
 d=request(elite_count=elite_count,generations=4)
 result=solve(d,seed=1)
 for previous,current in zip(result['generation_history'],result['generation_history'][1:]):
  ranked=sorted(range(len(previous['population'])),key=lambda i:previous['scores'][i],reverse=True)
  expected=[previous['population'][i] for i in ranked[:elite_count]]
  assert current['population'][:elite_count]==expected
  assert len(current['offspring'])==len(d['population'])-elite_count

def test_seed_changes_lineage_and_route_uses_supplied_seed(monkeypatch,oidc_auth_headers):
 d=request();first=solve(d,seed=1);second=solve(d,seed=2)
 assert first['generation_history']!=second['generation_history']
 from fastapi.testclient import TestClient
 from app.main import app
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app)
 h=oidc_auth_headers('ga-seed','owner')
 for seed,expected in ((1,first),(2,second)):
  response=c.post('/api/v1/api/modules/20/genetic-algorithms/solve',headers=h,json={'data':d,'seed':seed})
  assert response.status_code==200 and response.json()==expected
