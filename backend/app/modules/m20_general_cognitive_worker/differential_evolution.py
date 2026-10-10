"""Actual synchronous DE/rand/1/bin, bounded benchmark minimization."""
import math,random

def solve(data,seed=0):
    if not isinstance(data,dict):raise ValueError('data requires object')
    if type(seed)is not int or not 0<=seed<=2**32-1:raise ValueError('seed requires uint32')
    objective=data.get('objective');bounds=data.get('bounds')
    if objective not in ('sphere','rosenbrock'):raise ValueError('objective requires sphere or rosenbrock')
    if not isinstance(bounds,list)or not 1<=len(bounds)<=16:raise ValueError('bounds require1..16 dimensions')
    for pair in bounds:
        if not isinstance(pair,list)or len(pair)!=2 or any(type(v)not in (int,float)or not math.isfinite(v)for v in pair):raise ValueError('bounds require finite numeric pairs')
        lo,hi=pair
        if not lo<hi or not math.isfinite(hi-lo):raise ValueError('bounds require finite positive width')
    if objective=='rosenbrock'and len(bounds)<2:raise ValueError('rosenbrock requires2+ dimensions')
    def integer(key,default,low,high):
        v=data.get(key,default)
        if type(v)is not int or not low<=v<=high:raise ValueError(f'{key} requires integer{low}..{high}')
        return v
    size=integer('population_size',24,4,128);generations=integer('generations',80,1,1000)
    factor=data.get('mutation_factor',.8);rate=data.get('crossover_rate',.7)
    if type(factor)not in (int,float)or not math.isfinite(factor)or not 0<factor<=2:raise ValueError('mutation_factor requires finite(0,2]')
    if type(rate)not in (int,float)or not math.isfinite(rate)or not 0<=rate<=1:raise ValueError('crossover_rate requires finite[0,1]')
    if (generations+1)*size*len(bounds)>100000:raise ValueError('retained work product exceeds100000')
    def score(vector):
        try:value=sum(v*v for v in vector)if objective=='sphere'else sum(100*(vector[i+1]-vector[i]**2)**2+(1-vector[i])**2 for i in range(len(vector)-1))
        except OverflowError as exc:raise ValueError('objective overflow')from exc
        if not math.isfinite(value):raise ValueError('objective overflow')
        return value
    rng=random.Random(seed);population=[[rng.uniform(lo,hi)for lo,hi in bounds]for _ in range(size)]
    scores=[score(x)for x in population];evaluations=size;history=[]
    def snapshot(generation,trials):
        best=min(range(size),key=lambda i:scores[i]);history.append({'generation':generation,'population':[x[:]for x in population],'scores':scores[:],'best_vector':population[best][:],'best_score':scores[best],'trials':trials})
    snapshot(0,[])
    for generation in range(1,generations+1):
        new=[];new_scores=[];trials=[]
        for target in range(size):
            donors=rng.sample([i for i in range(size)if i!=target],3);a,b,c=[population[i]for i in donors]
            raw=[a[j]+factor*(b[j]-c[j])for j in range(len(bounds))]
            if any(not math.isfinite(v)for v in raw):raise ValueError('mutation overflow')
            mutant=[max(lo,min(hi,v))for v,(lo,hi)in zip(raw,bounds)]
            forced=rng.randrange(len(bounds));draws=[rng.random()for _ in bounds]
            indices=[j for j in range(len(bounds))if draws[j]<rate or j==forced]
            trial=[mutant[j]if j in indices else population[target][j]for j in range(len(bounds))]
            trial_score=score(trial);evaluations+=1;accepted=trial_score<=scores[target]
            new.append(trial if accepted else population[target][:]);new_scores.append(trial_score if accepted else scores[target])
            trials.append({'target_index':target,'donor_indices':donors,'mutant':mutant,'forced_index':forced,'crossed_indices':indices,'trial':trial,'trial_score':trial_score,'accepted':accepted})
        population=new;scores=new_scores;snapshot(generation,trials)
    best=min(range(size),key=lambda i:scores[i])
    return {'algorithm':'differential_evolution_rand_1_bin','objective':objective,'seed':seed,'best_vector':population[best][:],'best_score':scores[best],'evaluations':evaluations,'history':history,'global_optimum_guaranteed':False,'scope':'Bounded continuous differential evolution on sphere/Rosenbrock only, not arbitrary objectives or all evolutionary computation.'}
