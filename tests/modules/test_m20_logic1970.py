"""Independent truth-table entailment and resolution-certificate checks."""
import itertools
import pytest
from app.modules.m20_general_cognitive_worker.propositional_reasoning import reason

def holds(clause,assignment):return any(assignment[abs(x)]==(x>0) for x in clause)

def check_proof(data,result):
 proof=result['resolution_proof'];known=[]
 initial=data['clauses']+[[-q]for q in data['query']]
 for step in proof:
  clause=set(step['clause'])
  if step['source'] is not None:assert clause==set(initial[step['source']])
  else:
   a,b=[known[i]for i in step['parents']];p=step['pivot']
   assert p in a and -p in b
   assert clause==(a-{p})|(b-{-p})
  known.append(clause)
 assert known[-1]==set()

@pytest.mark.parametrize('clauses,query',[
 ([[1,2],[-1,3],[-2,3]],[3]),
 ([[1,2],[-1,3],[-2,3]],[1]),
 ([[1],[-1]],[2]),
 ([[1,2],[-1,-2]],[1,2]),
 ([[1,-1]],[2]),
 ([[]],[1]),
 ([[1,2],[-1,-2]],[3]),
])
def test_truth_table_oracle_and_independently_checked_resolution(clauses,query):
 d={'clauses':clauses,'query':query};r=reason(d)
 variables=sorted({abs(x)for c in clauses+[query]for x in c})
 models=[dict(zip(variables,bits))for bits in itertools.product([False,True],repeat=len(variables))]
 models=[a for a in models if all(holds(c,a)for c in clauses)]
 entailed=all(holds(query,a)for a in models)
 assert r['status']==('entailed'if entailed else 'not_entailed')
 if entailed:check_proof(d,r)
 else:
  a={int(k):v for k,v in r['counterexample'].items()}
  assert all(holds(c,a)for c in clauses) and not holds(query,a)
 assert r['real_world_truth_verified'] is False

@pytest.mark.parametrize('bad',[
 {'clauses':'bad','query':[1]}, {'clauses':[[0]],'query':[1]},
 {'clauses':[[True]],'query':[1]}, {'clauses':[[1]],'query':[]},
 {'clauses':[[1]],'query':[1.5]}, {'clauses':[[33]],'query':[1]},
 {'clauses':[[1]]*129,'query':[1]},
])
def test_malformed_logic_refuses(bad):
 with pytest.raises(ValueError):reason(bad)

def test_budget_exhaustion_does_not_claim_entailment_or_countermodel():
 r=reason({'clauses':[[1,2],[-1,3],[-2,3]],'query':[3],'max_steps':1})
 assert r['status']=='inconclusive' and r['counterexample'] is None

def test_production_mounted_reasoning_route(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);path='/api/v1/api/modules/20/propositional-reasoning/entail'
 d={'clauses':[[1,2],[-1,3],[-2,3]],'query':[3]}
 assert c.post(path,json=d).status_code==401
 r=c.post(path,headers=oidc_auth_headers('logic','owner'),json=d)
 assert r.status_code==200 and r.json()==reason(d)
 check_proof(d,r.json())
 assert c.post(path,headers=oidc_auth_headers('logic','owner'),json={'clauses':[[0]],'query':[1]}).status_code==422

def test_generated_cnf_corpus_matches_truth_tables_and_proof_checks():
 import random
 rng=random.Random(53)
 for _ in range(120):
  variables=list(range(1,5));clauses=[]
  for _ in range(rng.randrange(1,9)):
   subset=rng.sample(variables,rng.randrange(1,4));clauses.append([v if rng.randrange(2)else -v for v in subset])
  query=[v if rng.randrange(2)else -v for v in rng.sample(variables,rng.randrange(1,3))]
  test_truth_table_oracle_and_independently_checked_resolution(clauses,query)

@pytest.mark.parametrize('limit',[0,True,50001])
def test_invalid_work_budget_refuses(limit):
 with pytest.raises(ValueError):reason({'clauses':[[1]],'query':[1],'max_steps':limit})

def test_nonentailment_with_partial_assignment_fills_valid_total_model():
 d={'clauses':[[1,-1]],'query':[2]};r=reason(d)
 assert r['status']=='not_entailed' and set(r['counterexample'])=={'1','2'}
 assert r['counterexample']['2'] is False
