from itertools import product
from copy import deepcopy
from math import isqrt
import pytest,runpy,sys,types,builtins
from app.modules.instinct_doc import p235_concepts_batch321 as m
NAMES=('jacobi_symbol','prime_quadratic_residues','prime_quadratic_nonresidues','prime_modular_square_roots','prime_power_square_roots','quadratic_congruence_roots','prime_sum_two_squares','quadratic_residue_addition_counts','quadratic_residue_difference_counts','prime_quadratic_gauss_exponents')
PRIMES=(3,5,7,11,13,17,19,23,29,31)
def exact(a,b):
    assert type(a) is type(b)
    if type(b) in (list,tuple):
        assert len(a)==len(b)
        for x,y in zip(a,b):exact(x,y)
    else:assert a==b

def call(name,*args):
    old=deepcopy(args);out=getattr(m,name)(*args);assert args==old;return out

def jacobi(a,n):
    # Primefactorizationandactualsquareenumeration,notreciprocity.
    value=1;d=3
    while n>1:
        if n%d==0:
            r=a%d;legendre=0 if r==0 else 1 if any(x*x%d==r for x in range(d)) else -1
            value*=legendre;n//=d
        else:d+=2
    return value

def test_exhaustive_quadratic_oracles():
    for n in range(1,100,2):
        for a in range(-99,100):exact(call(NAMES[0],a,n),jacobi(a,n))
    for p in PRIMES:
        residues=sorted({x*x%p for x in range(p)})
        exact(call(NAMES[1],p),residues);exact(call(NAMES[2],p),[x for x in range(p) if x not in residues])
        for value in range(p):exact(call(NAMES[3],p,value),[x for x in range(p) if x*x%p==value])
        for e in range(1,4):
            modulus=p**e;roots={}
            for x in range(modulus):roots.setdefault(x*x%modulus,[]).append(x)
            for value in range(modulus):exact(call(NAMES[4],p,e,value),roots.get(value,[]))
        for a,b,c in product(range(p),repeat=3):exact(call(NAMES[5],p,a,b,c),[x for x in range(p) if (a*x*x+b*x+c)%p==0])
        pairs=[(a,b) for a in range(isqrt(p)+1) for b in range(a,isqrt(p)+1) if a*a+b*b==p];exact(call(NAMES[6],p),pairs)
        sums=[0]*p;diffs=[0]*p
        for a,b in product(residues,repeat=2):sums[(a+b)%p]+=1;diffs[(a-b)%p]+=1
        exact(call(NAMES[7],p),sums);exact(call(NAMES[8],p),diffs)
        exact(call(NAMES[9],p),[sum(x*x%p==r for x in range(p)) for r in range(p)])
    assert m.jacobi_symbol(2,15)==1
    assert m.prime_modular_square_roots(13,10)==[6,7]
    assert m.prime_power_square_roots(3,3,0)==[0,9,18]
    assert m.quadratic_congruence_roots(5,0,0,0)==list(range(5))
    assert m.prime_sum_two_squares(13)==[(2,3)]
class I(int):pass

def fail(name,args,code):
    old=deepcopy(args)
    with pytest.raises(ValueError) as e:getattr(m,name)(*args)
    assert str(e.value)=='P235:'+name+':'+code;assert args==old

def test_bounds_validation_order():
    for name in NAMES:
        specs=[('numerator',-99,99),('denominator',1,99)] if name==NAMES[0] else [('prime',3,31)]
        if name==NAMES[3]:specs += [('value',0,30)]
        if name==NAMES[4]:specs += [('exponent',1,3),('value',0,31**3-1)]
        if name==NAMES[5]:specs += [(k,0,30) for k in ('a','b','c')]
        good=[0,99] if name==NAMES[0] else [31]+([0] if name==NAMES[3] else [3,0] if name==NAMES[4] else [0,0,0] if name==NAMES[5] else [])
        for slot,(label,lo,hi) in enumerate(specs):
            for v,kind in ((None,'bad_type:'),(True,'bad_type:'),(I(lo),'bad_type:'),(float(lo),'bad_type:'),(lo-1,'bad_value:'),(hi+1,'bad_value:')):
                args=good[:];args[slot]=v
                for later in range(slot+1,len(args)):args[later]=None
                fail(name,args,kind+label)
            args=good[:];args[slot]=hi;call(name,*args)
        if name!=NAMES[0]:
            for bad in (4,9,15,21,25,27):fail(name,[bad]+[None]*(len(good)-1),'not_odd_prime')
    fail(NAMES[0],[0,98],'not_odd_denominator')
    for p in PRIMES:
        fail(NAMES[3],[p,p],'bad_value:value')
        for e in (1,2,3):fail(NAMES[4],[p,e,p**e],'bad_value:value')
        for slot in (1,2,3):
            args=[p,0,0,0];args[slot]=p;fail(NAMES[5],args,'bad_value:'+('a','b','c')[slot-1])
    assert m.SCOPE=='PARTIAL bounded odd-prime quadratic congruences and exact residue witnesses'
    assert m.NOT_CLAIMED==('cryptographic security','large-integer scalability','complex Gauss sums','global novelty','production readiness')

def test_isolation_registry_guard():
    for name in NAMES[1:]:
        args=[13]+([10] if name==NAMES[3] else [2,0] if name==NAMES[4] else [1,2,3] if name==NAMES[5] else [])
        out=call(name,*args);expected=deepcopy(out);out.clear();exact(call(name,*args),expected)
    key='app.modules.instinct_doc.p235_concepts_registry';old=sys.modules.get(key);original=builtins.__import__;fake=types.ModuleType(key);sentinel=object();fake.make_fail=lambda name:sentinel
    try:
        sys.modules[key]=fake;assert runpy.run_path(m.__file__)['make_fail']('x') is sentinel;del sys.modules[key]
        def broken(name,*a,**k):
            if name==key:raise ModuleNotFoundError('missing',name='other_dependency')
            return original(name,*a,**k)
        builtins.__import__=broken
        with pytest.raises(ModuleNotFoundError) as e:runpy.run_path(m.__file__)
        assert e.value.name=='other_dependency'
    finally:
        builtins.__import__=original
        if old is None:sys.modules.pop(key,None)
        else:sys.modules[key]=old
