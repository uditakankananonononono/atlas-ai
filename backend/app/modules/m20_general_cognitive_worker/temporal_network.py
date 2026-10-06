"""Finite simple temporal network consistency and implied time-gap bounds.

All times are relative scalar values in a declared unit, not calendar bookings.
Difference constraints solved by all-pairs shortest paths, not event sorting.
"""
from __future__ import annotations
import math
from .measured_learning import text


def temporal(p):
    events=p.get('temporal_events');constraints=p.get('time_constraints');unit=text(p.get('time_unit'),'time_unit')
    if not isinstance(events,list) or not 1<=len(events)<=64 or any(not isinstance(e,str) or not e for e in events) or len(set(events))!=len(events):raise ValueError('1..64 unique event ids required')
    if not isinstance(constraints,list) or len(constraints)>1000:raise ValueError('<=1000 explicit time_constraints required')
    n=len(events);index={e:i for i,e in enumerate(events)};d=[[math.inf]*n for _ in events]
    for i in range(n):d[i][i]=0.
    def pair(row):
        a=row.get('from');b=row.get('to')
        if a not in index or b not in index:raise ValueError('known temporal event ids required')
        return index[a],index[b]
    for row in constraints:
        a,b=pair(row);low=row.get('minimum_gap');high=row.get('maximum_gap')
        if low is None and high is None:raise ValueError('at least one finite gap bound required')
        for v in (low,high):
            if v is not None and (type(v) not in (int,float) or not math.isfinite(v)):raise ValueError('finite gap bounds required')
        if low is not None and high is not None and low>high:raise ValueError('minimum_gap exceeds maximum_gap')
        if high is not None:d[a][b]=min(d[a][b],float(high))
        if low is not None:d[b][a]=min(d[b][a],-float(low))
    for k in range(n):
        for i in range(n):
            if not math.isfinite(d[i][k]):continue
            for j in range(n):
                if not math.isfinite(d[k][j]):continue
                candidate=d[i][k]+d[k][j]
                if not math.isfinite(candidate):raise ValueError('time-bound arithmetic overflow')
                if candidate<d[i][j]:d[i][j]=candidate
    if any(d[i][i]<-1e-9 for i in range(n)):
        return {'status':'inconsistent','time_unit':unit,'queries':[],'witness_relative_times':None,'boundary':'Negative constraint cycle: no assignment satisfies all supplied time-gap bounds.'}
    queries=p.get('time_queries',[])
    if not isinstance(queries,list) or len(queries)>1000:raise ValueError('bounded time_queries list required')
    answers=[]
    for q in queries:
        a,b=pair(q);low=-d[b][a] if math.isfinite(d[b][a]) else None;high=d[a][b] if math.isfinite(d[a][b]) else None
        threshold=q.get('at_least')
        if threshold is not None and (type(threshold) not in (int,float) or not math.isfinite(threshold)):raise ValueError('finite at_least query required')
        answers.append({'from':events[a],'to':events[b],'minimum_implied_gap':low,'maximum_implied_gap':high,
                        'guaranteed_at_least':(low is not None and low>=threshold-1e-9) if threshold is not None else None,
                        'possible_at_least':(high is None or high>=threshold-1e-9) if threshold is not None else None})
    # Virtual source with zero edges to every event gives a feasible potential.
    times=[min(0.,*(d[j][i] for j in range(n))) for i in range(n)]
    violations=[]
    for row in constraints:
        a,b=pair(row);gap=times[b]-times[a]
        if row.get('minimum_gap') is not None:violations.append(max(0,row['minimum_gap']-gap))
        if row.get('maximum_gap') is not None:violations.append(max(0,gap-row['maximum_gap']))
    residual=max(violations,default=0.)
    if residual>1e-8:raise ValueError('temporal witness failed numerical validation')
    return {'status':'consistent','time_unit':unit,'queries':answers,'witness_relative_times':dict(zip(events,times)),'constraint_violation':residual,
            'boundary':'Actual finite relative-time difference-constraint closure. Null bounds mean unbounded, not fabricated timestamps. Witness is one feasible assignment; absolute anchor unspecified. Tolerance1e-9. No calendar scheduling, timezone conversion or real-world temporal evidence verification.'}
