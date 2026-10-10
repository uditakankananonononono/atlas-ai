"""Actual binary-genome genetic search over a supplied weighted-bit objective.

Tournament selection, one-point crossover, independent bit mutation and elitism.
No convergence/global-optimum guarantee or claim of general cognition. Inputs
and objective are supplied, not independently verified. No external effects.
"""
import math,random

def solve(data,seed=0):
    if not isinstance(data,dict):raise ValueError('data must be an object')
    weights=data.get('weights');population=data.get('population')
    if not isinstance(weights,list) or not 2<=len(weights)<=64 or any(type(w) not in (int,float) or not math.isfinite(w) for w in weights):raise ValueError('weights require 2..64 finite numbers')
    n=len(weights)
    if not isinstance(population,list) or not 2<=len(population)<=128:raise ValueError('population requires 2..128 genomes')
    if any(not isinstance(g,list) or len(g)!=n or any(type(b) is not int or b not in (0,1) for b in g) for g in population):raise ValueError('genomes require aligned exact binary integers')
    if type(seed) is not int or not 0<=seed<=2**32-1:raise ValueError('seed requires uint32')
    def integer(key,default,lo,hi):
        v=data.get(key,default)
        if type(v) is not int or not lo<=v<=hi:raise ValueError(f'{key} requires integer {lo}..{hi}')
        return v
    def rate(key,default):
        v=data.get(key,default)
        if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1:raise ValueError(f'{key} requires finite [0,1]')
        return v
    generations=integer('generations',20,1,1000);size=len(population)
    tournament=integer('tournament_size',2,1,size);elite=integer('elite_count',1,1,size-1)
    mutation=rate('mutation_rate',1/n);crossover=rate('crossover_rate',.8)
    # Bound retained lineage as well as runtime; no unbounded response growth.
    if generations*size*n>100000:raise ValueError('generation/population/genome product exceeds 100000')
    def score(genome):
        value=sum(w*b for w,b in zip(weights,genome))
        if not math.isfinite(value):raise ValueError('objective overflow')
        return value
    rng=random.Random(seed);population=[g[:] for g in population];evaluations=0
    def evaluated(pop):
        nonlocal evaluations
        scores=[score(g) for g in pop];evaluations+=len(pop);return scores
    scores=evaluated(population)
    def snapshot(index,children):
        best=max(range(size),key=lambda i:scores[i])
        return {'generation':index,'population':[g[:] for g in population],'scores':scores[:],
                'best_genome':population[best][:],'best_score':scores[best],'offspring':children}
    history=[snapshot(0,[])]
    for generation in range(1,generations+1):
        ranked=sorted(range(size),key=lambda i:scores[i],reverse=True)
        new=[population[i][:] for i in ranked[:elite]];children=[]
        while len(new)<size:
            parents=[];contests=[]
            for _ in range(2):
                indices=[rng.randrange(size) for _ in range(tournament)]
                winner=max(indices,key=lambda i:scores[i]);parents.append(population[winner][:]);contests.append([population[i][:] for i in indices])
            cut=rng.randrange(1,n) if rng.random()<crossover else None
            child=parents[0][:] if cut is None else parents[0][:cut]+parents[1][cut:]
            positions=[i for i in range(n) if rng.random()<mutation]
            child=[1-bit if i in positions else bit for i,bit in enumerate(child)]
            children.append({'parents':parents,'tournaments':contests,'crossover_point':cut,
                             'mutated_positions':positions,'genome':child[:]})
            new.append(child)
        population=new;scores=evaluated(population)
        for index,child in enumerate(children):child['score']=scores[elite+index]
        history.append(snapshot(generation,children))
    best=max(range(size),key=lambda i:scores[i])
    return {'algorithm':'binary_genetic_algorithm','objective':'maximize_weighted_bit_sum',
            'best_genome':population[best][:],'best_score':scores[best],'evaluations':evaluations,
            'generation_history':history,'seed':seed,'global_optimum_guaranteed':False,
            'scope':'Actual binary genetic algorithm on supplied weighted-bit objective only; no general optimizer or cognition claim.'}
