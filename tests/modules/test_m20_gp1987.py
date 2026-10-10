"""Actual expression-tree evolution, not supplied polynomial candidate selection."""
import pytest
from app.modules.m20_general_cognitive_worker.genetic_programming import solve,evaluate,paths,subtree,replace

def request(**kw):
 x=[-2.,-1.,0.,1.,2.]
 return {'x':x,'y':[v*v+v+1 for v in x],'population_size':40,'generations':60,'max_depth':5,**kw}

def oracle(tree,x):
 if tree[0]=='x':return x
 if tree[0]=='const':return tree[1]
 a,b=oracle(tree[1],x),oracle(tree[2],x)
 return a+b if tree[0]=='add'else a-b if tree[0]=='sub'else a*b

@pytest.mark.parametrize('seed',[0,1,2])
def test_actual_tree_search_learns_quadratic(seed):
 d=request();r=solve(d,seed)
 assert r==solve(d,seed) and r['best_score']<1e-8
 assert len(r['history'])==61 and r['history'][-1]['generation']==60
 assert r['best_predictions']==[oracle(r['best_program'],x)for x in d['x']]
 assert r['global_optimum_guaranteed'] is False
 assert r['best_score']==sum((p-y)**2 for p,y in zip(r['best_predictions'],d['y']))/len(d['x'])

def test_independent_actual_crossover_mutation_and_objective_receipts():
 d=request(population_size=8,generations=4,mutation_rate=1.,crossover_rate=1.)
 r=solve(d,19)
 changed=False
 for prev,cur in zip(r['history'],r['history'][1:]):
  assert cur['population'][0]==prev['best_program']
  for index,child in enumerate(cur['offspring'],1):
   a,b=child['parents'];pa,pb=child['crossover_paths']
   def get(t,path):
    for i in path:t=t[i]
    return t
   def put(t,path,value):
    if not path:return value
    t=[*t];t[path[0]]=put(t[path[0]],path[1:],value);return t
   crossed=put(a,pa,get(b,pb))
   assert child['crossover_accepted'] is True or child['pre_mutation']==a
   pre=crossed if child['crossover_accepted']else a
   assert child['pre_mutation']==pre
   expected=put(pre,child['mutation_path'],child['mutation_subtree'])
   assert child['program']==expected
   assert cur['population'][index]==expected
   mse=sum((oracle(expected,x)-y)**2 for x,y in zip(d['x'],d['y']))/len(d['x'])
   assert child['score']==mse==cur['scores'][index]
   changed|=expected!=a
   for contest,parent in zip(child['tournaments'],child['parents']):
    assert sum((oracle(parent,x)-y)**2 for x,y in zip(d['x'],d['y']))<=min(sum((oracle(t,x)-y)**2 for x,y in zip(d['x'],d['y']))for t in contest)
 assert changed

def test_safe_tree_evaluation_and_structural_replace():
 tree=['add',['mul',['x'],['x']],['const',1]]
 assert evaluate(tree,3)==10 and subtree(tree,[1,2])==['x']
 assert replace(tree,[2],['const',2])==['add',['mul',['x'],['x']],['const',2]]
 assert tree[2]==['const',1]
 assert paths(tree)==[[],[1],[1,1],[1,2],[2]]
 for bad in (['exec','evil'],['const',True],['mul',['x']],['x',1]):
  with pytest.raises(ValueError):evaluate(bad,1)

@pytest.mark.parametrize('bad',[{'x':[]},{'y':[1]},{'x':[True]*5},{'y':[float('nan')]*5},{'population_size':1},{'population_size':129},{'generations':0},{'generations':1001},{'max_depth':1},{'max_depth':7},{'mutation_rate':2},{'crossover_rate':-1},{'tournament_size':0}])
def test_invalid_inputs_refuse(bad):
 with pytest.raises(ValueError):solve(request(**bad),1)

def test_mounted_production_route(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);path='/api/v1/api/modules/20/genetic-programming/solve';d=request(population_size=4,generations=2)
 assert c.post(path,json={'data':d}).status_code==401
 r=c.post(path,headers=oidc_auth_headers('gp','owner'),json={'data':d,'seed':4})
 assert r.status_code==200 and r.json()==solve(d,4)
 assert c.post(path,headers=oidc_auth_headers('gp','owner'),json={'data':request(max_depth=7)}).status_code==422
