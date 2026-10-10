"""Actual bounded continuous particle swarm, no GA alias or optimum shortcut."""
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
    def coefficient(key,default,high):
        v=data.get(key,default)
        if type(v)not in (int,float)or not math.isfinite(v)or not 0<=v<=high:raise ValueError(f'{key} requires finite0..{high}')
        return v
    size=integer('particles',24,2,128);iterations=integer('iterations',90,1,1000)
    inertia=coefficient('inertia',.7,1.);cognitive=coefficient('cognitive',1.5,4.);social=coefficient('social',1.5,4.)
    if (iterations+1)*size*len(bounds)>100000:raise ValueError('retained work product exceeds100000')
    def score(position):
        try:
            value=sum(v*v for v in position)if objective=='sphere'else sum(100*(position[i+1]-position[i]**2)**2+(1-position[i])**2 for i in range(len(position)-1))
        except OverflowError as exc:raise ValueError('objective overflow')from exc
        if not math.isfinite(value):raise ValueError('objective overflow')
        return value
    rng=random.Random(seed);positions=[];velocities=[]
    for _ in range(size):
        positions.append([rng.uniform(lo,hi)for lo,hi in bounds])
        velocities.append([rng.uniform(-(hi-lo)*.1,(hi-lo)*.1)for lo,hi in bounds])
    scores=[score(p)for p in positions];personal=[p[:]for p in positions];personal_scores=scores[:]
    best=min(range(size),key=lambda i:personal_scores[i]);global_best=personal[best][:];global_score=personal_scores[best];history=[]
    def snapshot(step):
        history.append({'iteration':step,'positions':[p[:]for p in positions],'velocities':[v[:]for v in velocities],
                        'scores':scores[:],'personal_best_positions':[p[:]for p in personal],
                        'personal_best_scores':personal_scores[:],'global_best_position':global_best[:],'global_best_score':global_score})
    snapshot(0)
    for step in range(1,iterations+1):
        new_positions=[];new_velocities=[]
        for index,(p,v)in enumerate(zip(positions,velocities)):
            nextp=[];nextv=[]
            for j,(lo,hi)in enumerate(bounds):
                r1,r2=rng.random(),rng.random()
                speed=inertia*v[j]+cognitive*r1*(personal[index][j]-p[j])+social*r2*(global_best[j]-p[j])
                raw=p[j]+speed
                if not math.isfinite(raw)or not math.isfinite(speed):raise ValueError('velocity overflow')
                clamped=max(lo,min(hi,raw));nextp.append(clamped);nextv.append(speed if clamped==raw else 0.)
            new_positions.append(nextp);new_velocities.append(nextv)
        positions=new_positions;velocities=new_velocities;scores=[score(p)for p in positions]
        for i in range(size):
            if scores[i]<personal_scores[i]:personal[i]=positions[i][:];personal_scores[i]=scores[i]
        best=min(range(size),key=lambda i:personal_scores[i])
        if personal_scores[best]<global_score:global_best=personal[best][:];global_score=personal_scores[best]
        snapshot(step)
    return {'algorithm':'continuous_particle_swarm','objective':objective,'seed':seed,'best_position':global_best,'best_score':global_score,
            'evaluations':size*(iterations+1),'history':history,'global_optimum_guaranteed':False,
            'scope':'Bounded continuous PSO on sphere/Rosenbrock benchmarks; not arbitrary objectives, discrete swarm behavior or general cognition.'}
