"""Explicit non-reproduction track: generic list/record operations, not target oracles.
State retains original input, optional second argument and current intermediate value.
No operation returns any complete PSB2 task's answer by itself. The language is manually
extended after inspecting benchmark types/definitions, which limits generalization claims.
"""
import itertools
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]/'e7_library_transfer'))
import dsl

def scalar_map(x, fn):
    return [fn(a) for a in x]

def suffix_max(x):
    return list(reversed(list(itertools.accumulate(reversed(x), max))))

def records(x):
    # General split records: (left sublist, right sublist), nonempty left and right.
    return [(x[:i],x[i:]) for i in range(1,len(x))] if len(x)>1 else [(x,[])]

def first_negative(x):
    return next((i for i,v in enumerate(x) if v<0), -1)

def argmin_last(x):
    # Generic last minimum, except first exact zero. Mirrors published cut tie policy.
    zeros = [i for i,v in enumerate(x) if v==0]
    return zeros[0] if zeros else max(range(len(x)), key=lambda i:(-x[i],i))

# Appended order is fixed, base primitive order unchanged. Functions accept (current, inputs).
OPS = {k:(lambda x, args, fn=f:fn(x)) for k,(f,_) in dsl.PRIMS.items()}
OPS.update({
    'floor3': lambda x,a: scalar_map(x, lambda v:v//3),
    'minus2': lambda x,a: scalar_map(x, lambda v:v-2),
    'alternating_double': lambda x,a:[v*2 if i%2==0 else v for i,v in enumerate(x)],
    'digit_sum': lambda x,a:scalar_map(x,lambda v:v//10+v%10),
    'first_negative_index': lambda x,a:first_negative(x),
    'suffix_max': lambda x,a:suffix_max(x),
    'retain_equal_original': lambda x,a:[v for v,m in zip(a[0],x) if v==m],
    'splits': lambda x,a:records(x),
    'balance': lambda x,a:[abs(sum(l)-sum(r)) for l,r in x],
    'argmin': lambda x,a:argmin_last(x),
    'select_split': lambda x,a:records(a[0])[x],
    'pairs': lambda x,a:list(itertools.combinations(x,2)),
    'matching_sum': lambda x,a:[pair for pair in x if sum(pair)==a[1]],
    'first_pair': lambda x,a:x[0],
})
# Names are a superset but learning/search functions remain e7's functions.
PRIMS = {k:(v,False) for k,v in OPS.items()}

def apply_prog(prog, inputs, lib):
    value=inputs[0]
    for name in dsl.flat(prog,lib):
        value=OPS[name](value,inputs)
    return value

def safe_apply(prog, inputs, lib):
    try:
        return apply_prog(prog,inputs,lib)
    except (ValueError,TypeError,IndexError,KeyError):
        return None

def enumerate_progs(lib,max_depth=4):
    for depth in range(1,max_depth+1):
        yield from itertools.product(list(OPS)+list(lib),repeat=depth)

def solve(task,lib,budget,max_depth=4):
    for n,p in enumerate(enumerate_progs(lib,max_depth),1):
        if n>budget: return None,budget
        if all(safe_apply(p,i,lib)==o for i,o in task['train']): return p,n
    return None,n

def verify(task,p,lib):
    return all(safe_apply(p,i,lib)==o for i,o in task['test'])

# Independent hand-specified expressivity witnesses only. NEVER used by learn/solve.
WITNESSES = {
    'basement':('cumsum','first_negative_index'),
    'fuel-cost':('floor3','minus2','sum'),
    'leaders':('suffix_max','retain_equal_original'),
    'luhn':('alternating_double','digit_sum','sum'),
    'cut-vector':('splits','balance','argmin','select_split'),
    'find-pair':('pairs','matching_sum','first_pair'),
}
