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
