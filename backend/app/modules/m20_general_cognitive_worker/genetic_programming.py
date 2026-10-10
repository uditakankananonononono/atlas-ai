"""Bounded actual expression-tree GP. No eval, exec or caller code execution."""
from copy import deepcopy
import math,random
OPS=('add','sub','mul')
def validate(tree,depth=0):
    if depth>=6 or not isinstance(tree,list)or not tree:raise ValueError('bounded expression tree required')
    op=tree[0]
    if op=='x' and len(tree)==1:return
    if op=='const'and len(tree)==2 and type(tree[1])in(int,float)and math.isfinite(tree[1]):return
    if op in OPS and len(tree)==3:
        validate(tree[1],depth+1);validate(tree[2],depth+1);return
    raise ValueError('tree requires x, finite const, or binary add/sub/mul')
def _evaluate(tree,x):
    if tree[0]=='x':return x
    if tree[0]=='const':return tree[1]
    a,b=_evaluate(tree[1],x),_evaluate(tree[2],x)
    value=a+b if tree[0]=='add'else a-b if tree[0]=='sub'else a*b
    if not math.isfinite(value):raise ValueError('program evaluation overflow')
    return value
def evaluate(tree,x):
    validate(tree)
    if type(x)not in(int,float)or not math.isfinite(x):raise ValueError('finite input required')
    return _evaluate(tree,x)
def paths(tree):
    result=[[]]
    if tree[0]in OPS:
        for child in (1,2):result.extend([[child]+p for p in paths(tree[child])])
    return result
def subtree(tree,path):
    for i in path:tree=tree[i]
    return deepcopy(tree)
def replace(tree,path,value):
    if not path:return deepcopy(value)
    result=deepcopy(tree);result[path[0]]=replace(result[path[0]],path[1:],value);return result
def depth(tree):return 1+max(depth(tree[1]),depth(tree[2]))if tree[0]in OPS else 1

def solve(data,seed=0):
    if not isinstance(data,dict):raise ValueError('data requires object')
    if type(seed)is not int or not 0<=seed<=2**32-1:raise ValueError('seed requires uint32')
    x,y=data.get('x'),data.get('y')
    if not isinstance(x,list)or not isinstance(y,list)or not 2<=len(x)<=64 or len(x)!=len(y)or any(type(v)not in(int,float)or not math.isfinite(v)for v in x+y):raise ValueError('x/y require2..64 aligned finite numbers')
    def integer(key,default,lo,hi):
        v=data.get(key,default)
        if type(v)is not int or not lo<=v<=hi:raise ValueError(f'{key} requires integer{lo}..{hi}')
        return v
    def rate(key,default):
        v=data.get(key,default)
        if type(v)not in(int,float)or not math.isfinite(v)or not 0<=v<=1:raise ValueError(f'{key} requires finite[0,1]')
        return v
    size=integer('population_size',40,2,128);generations=integer('generations',60,1,1000);maximum=integer('max_depth',5,2,6);tournament=integer('tournament_size',3,1,size)
    mutation=rate('mutation_rate',.3);crossover=rate('crossover_rate',.8)
    if (generations+1)*size*(2**maximum-1)*len(x)>3000000:raise ValueError('evaluation work product exceeds3000000')
    if (generations+1)*size*(2**maximum-1)>300000:raise ValueError('retained work product exceeds300000')
    rng=random.Random(seed)
    def grow(remaining):
        if remaining==1 or rng.random()<.35:return ['x']if rng.random()<.6 else ['const',rng.choice([-2,-1,0,1,2])]
        return [rng.choice(OPS),grow(remaining-1),grow(remaining-1)]
    def score(program):
        try:value=sum((_evaluate(program,v)-target)**2 for v,target in zip(x,y))/len(x)
        except OverflowError as exc:raise ValueError('fitness overflow')from exc
        if not math.isfinite(value):raise ValueError('fitness overflow')
        return value
    population=[grow(maximum)for _ in range(size)];scores=[score(t)for t in population];evaluations=size;history=[]
    def snapshot(generation,offspring):
        best=min(range(size),key=lambda i:scores[i]);history.append({'generation':generation,'population':deepcopy(population),'scores':scores[:],'best_program':deepcopy(population[best]),'best_score':scores[best],'offspring':offspring})
    snapshot(0,[])
    for generation in range(1,generations+1):
        best=min(range(size),key=lambda i:scores[i]);new=[deepcopy(population[best])];children=[]
        for _ in range(size-1):
            parents=[];contests=[]
            for _ in range(2):
                indices=[rng.randrange(size)for _ in range(tournament)];winner=min(indices,key=lambda i:scores[i]);parents.append(deepcopy(population[winner]));contests.append([deepcopy(population[i])for i in indices])
            child=deepcopy(parents[0]);crosspaths=None;crossaccepted=False
            if rng.random()<crossover:
                pa,pb=rng.choice(paths(parents[0])),rng.choice(paths(parents[1]));crosspaths=[pa,pb]
                proposed=replace(parents[0],pa,subtree(parents[1],pb))
                if depth(proposed)<=maximum:child=proposed;crossaccepted=True
            pre=deepcopy(child);mutationpath=None;mutationtree=None
            if rng.random()<mutation:
                mutationpath=rng.choice(paths(child));mutationtree=grow(maximum-len(mutationpath));child=replace(child,mutationpath,mutationtree)
            new.append(child);children.append({'parents':parents,'tournaments':contests,'crossover_paths':crosspaths,'crossover_accepted':crossaccepted,'pre_mutation':pre,'mutation_path':mutationpath,'mutation_subtree':mutationtree,'program':deepcopy(child)})
        population=new;scores=[score(t)for t in population];evaluations+=size
        for i,c in enumerate(children,1):c['score']=scores[i]
        snapshot(generation,children)
    best=min(range(size),key=lambda i:scores[i]);program=deepcopy(population[best])
    return {'algorithm':'expression_tree_genetic_programming','seed':seed,'best_program':program,'best_score':scores[best],'best_predictions':[_evaluate(program,v)for v in x],'evaluations':evaluations,'history':history,'global_optimum_guaranteed':False,'scope':'Bounded single-variable add/sub/mul expression-tree symbolic regression, not arbitrary program synthesis or verified generalization.'}
