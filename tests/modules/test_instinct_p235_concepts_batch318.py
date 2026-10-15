from itertools import product
from copy import deepcopy
import pytest,runpy,sys,types,builtins
from app.modules.instinct_doc import p235_concepts_batch318 as m
NAMES=('gf16_multiply','gf16_inverse','gf16_power','gf16_trace','gf16_norm','gf16_multiplicative_order','gf16_frobenius_orbit','gf16_minimal_polynomial','gf16_primitive_elements','gf16_discrete_log')


def multiply(a,b):
    # Fullcarrylesspolynomialthenlongdivide,fundamentallynotshift/reduceeachstep.
    polynomial=0
    for i in range(4):
        for j in range(4):
            if a>>i&1 and b>>j&1:polynomial^=1<<(i+j)
    while polynomial>=16:polynomial^=19<<(polynomial.bit_length()-5)
    return polynomial


def power(a,e):
    out=1
    for _ in range(e):out=multiply(out,a)
    return out


def minpoly(a):
    for degree in range(1,5):
        for lower in range(1<<degree):
            coefficients=[lower>>i&1 for i in range(degree)]+[1];value=0
            for i,c in enumerate(coefficients):
                if c:value^=power(a,i)
            if value==0:return coefficients


def exact(a,b):
    assert type(a) is type(b)
    if type(b) in (list,tuple):
        assert len(a)==len(b)
        for x,y in zip(a,b):exact(x,y)
    else:assert a==b


def call(name,*args):
    old=deepcopy(args);out=getattr(m,name)(*args);assert args==old;return out


def test_all_field_elements_longdivision_annihilator_oracles():
    orders={}
    for a in range(16):
        for b in range(16):exact(call(NAMES[0],a,b),multiply(a,b))
        for e in range(31):exact(call(NAMES[2],a,e),power(a,e))
        trace=0
        for exponent in (1,2,4,8):trace^=power(a,exponent)
        exact(call(NAMES[3],a),trace);exact(call(NAMES[4],a),int(a!=0));orbit=[]
        for e in (1,2,4,8):
            v=power(a,e)
            if v not in orbit:orbit.append(v)
        exact(call(NAMES[6],a),orbit);exact(call(NAMES[7],a),minpoly(a))
        if a:
            inverse=next(b for b in range(1,16) if multiply(a,b)==1);exact(call(NAMES[1],a),inverse);orders[a]=next(e for e in range(1,16) if power(a,e)==1);exact(call(NAMES[5],a),orders[a])
            for target in range(1,16):exact(call(NAMES[9],a,target),next((e for e in range(15) if power(a,e)==target),None))
    exact(call(NAMES[8]),[a for a,d in orders.items() if d==15])
    assert m.gf16_multiply(8,2)==3
    assert m.gf16_minimal_polynomial(2)==[1,1,0,0,1]
    # Everytripleassociativity/everypairtraceadditivity,independentidentities.
    for a,b,c in product(range(16),repeat=3):assert m.gf16_multiply(m.gf16_multiply(a,b),c)==m.gf16_multiply(a,m.gf16_multiply(b,c))
    for a,b in product(range(16),repeat=2):assert m.gf16_trace(a^b)==m.gf16_trace(a)^m.gf16_trace(b)


class I(int):pass


def fail(name,args,code):
    old=deepcopy(args)
    with pytest.raises(ValueError) as e:getattr(m,name)(*args)
    assert str(e.value)=='P235:'+name+':'+code;assert args==old


def test_all_argument_bounds_order_scope():
    for name in NAMES:
        if name==NAMES[8]:continue
        labels=('left','right') if name==NAMES[0] else ('element','exponent') if name==NAMES[2] else ('base','target') if name==NAMES[9] else ('element',)
        lows=(0,0) if name in (NAMES[0],NAMES[2]) else (1,1) if name==NAMES[9] else (1,) if name in (NAMES[1],NAMES[5]) else (0,)
        highs=(15,30) if name==NAMES[2] else (15,)*len(labels)
        for slot,(label,lo,hi) in enumerate(zip(labels,lows,highs)):
            for v,kind in ((None,'bad_type:'),(True,'bad_type:'),(I(lo),'bad_type:'),(float(lo),'bad_type:'),(lo-1,'bad_value:'),(hi+1,'bad_value:')):
                args=list(lows);args[slot]=v
                for later in range(slot+1,len(args)):args[later]=None
                fail(name,args,kind+label)
    assert m.SCOPE=='PARTIAL exact GF16 arithmetic, Frobenius minimal polynomials and discrete logarithm witnesses'
    assert m.NOT_CLAIMED==('cryptographic security','large-field scalability','AGI-like intelligence','global novelty','production readiness')


def test_isolation_registry_guard():
    for name in (NAMES[6],NAMES[7],NAMES[8]):
        args=[] if name==NAMES[8] else [2];out=call(name,*args);expected=deepcopy(out);out.clear();exact(call(name,*args),expected)
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
