"""Exact predecessor-closed knapsack for SMALL explicit repair DAGs.

Classical optimization, not a new algorithm. Exponential worst case: at most
20 candidates. Costs/values are declared abstract integers, not token/dollar
estimates. Caller supplies provenance; missing edges cannot be detected here.
"""
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json

@dataclass(frozen=True)
class Candidate:
    key: str
    cost: int
    value: int
    parents: tuple[str,...] = ()
    executable: bool = True


def validate(nodes):
    if not isinstance(nodes,(list,tuple)) or len(nodes)>20:raise ValueError('1..20 candidate bound (empty allowed)')
    seen=set()
    for n in nodes:
        if not isinstance(n,Candidate) or type(n.key) is not str or not n.key or n.key in seen:raise ValueError('unique nonempty keys required')
        if type(n.cost) is not int or n.cost<1 or type(n.value) is not int or n.value<0:raise ValueError('positive integer cost, nonnegative value required')
        if type(n.parents) is not tuple or any(type(p) is not str or p not in seen for p in n.parents) or len(set(n.parents))!=len(n.parents):raise ValueError('parents must precede node, no cycles or duplicates')
        if type(n.executable) is not bool:raise ValueError('boolean executable required')
        seen.add(n.key)


def frontier(nodes):
    """Enumerate dependency ideals once, retaining best reward per exact cost.

Invariant: after step k, states contain every executable predecessor-closed
subset of first k nodes. Omitting node preserves state; adding it is allowed
iff all its predecessors are present. Thus the output is exact at every cap.
    """
    validate(nodes);indices={n.key:i for i,n in enumerate(nodes)}
    states=[(0,0,0)]
    for i,n in enumerate(nodes):
        need=sum(1<<indices[p] for p in n.parents)
        if n.executable:
            states += [(mask|(1<<i),cost+n.cost,value+n.value) for mask,cost,value in states if mask&need==need]
    best={}
    for mask,cost,value in states:
        keys=tuple(n.key for i,n in enumerate(nodes) if mask>>i&1)
        if cost not in best or value>best[cost]['value'] or value==best[cost]['value'] and keys<best[cost]['keys']:
            best[cost]={'cost':cost,'value':value,'keys':keys}
    out=[];record=-1
    for cost,p in sorted(best.items()):
        if p['value']>record:out.append(p);record=p['value']
    return out


def supported_points(points):
    """All Pareto points optimal for SOME lambda>=0, including ties.

Pairwise linear inequalities give an exact rational feasible lambda interval.
This is stronger than a finite lambda sweep, not a rerun of MemoRepair code.
    """
    out=[]
    for p in points:
        lo=Fraction(0);hi=None
        for q in points:
            dc=p['cost']-q['cost'];dv=p['value']-q['value']
            if dc>0:hi=min(hi,Fraction(dv,dc)) if hi is not None else Fraction(dv,dc)
            elif dc<0:lo=max(lo,Fraction(dv,dc))
        if hi is None or lo<=hi:out.append(p)
    return out


def greedy(nodes,cap):
    validate(nodes)
    if type(cap) is not int or cap<0:raise ValueError('nonnegative integer cap')
    by={n.key:n for n in nodes};chosen=set();spent=0
    def closure(key):
        return {key}.union(*(closure(p) for p in by[key].parents))
    while True:
        options=[]
        for n in nodes:
            extra=closure(n.key)-chosen
            cost=sum(by[k].cost for k in extra);value=sum(by[k].value for k in extra)
            if extra and cost+spent<=cap and all(by[k].executable for k in extra):
                options.append((Fraction(value,cost),value,-cost,n.key,extra))
        if not options:break
        *_,extra=max(options,key=lambda x:x[:4]);chosen|=extra;spent=sum(by[k].cost for k in chosen)
    return {'cost':spent,'value':sum(by[k].value for k in chosen),'keys':tuple(n.key for n in nodes if n.key in chosen)}


def replay(nodes,selected,*,evidence_version):
    """Pure executable artifact testbed, not an LLM simulation.

Every selected artifact recomputes as version + its parent values. Withheld
artifacts are not visible. Receipt binds DAG, selection, source version/output;
it proves integrity/replay consistency when rechecked, NOT global optimality.
    """
    validate(nodes)
    if type(evidence_version) is not int or evidence_version<1:raise ValueError('positive integer evidence version')
    if type(selected) not in (list,tuple) or len(set(selected))!=len(selected):raise ValueError('unique selection sequence required')
    keys=set(selected);by={n.key:n for n in nodes}
    if keys-set(by):raise ValueError('unknown candidate')
    values={}
    for n in nodes:
        if n.key in keys:
            if not n.executable or not set(n.parents)<=values.keys():raise ValueError('not executable predecessor closure')
            values[n.key]=evidence_version+sum(values[p] for p in n.parents)
    payload={'nodes':[{'key':n.key,'cost':n.cost,'value':n.value,'parents':n.parents,'executable':n.executable} for n in nodes],
             'selected':sorted(keys),'evidence_version':evidence_version,'outputs':values}
    raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
    return {'outputs':values,'receipt_sha256':sha256(raw).hexdigest()}
