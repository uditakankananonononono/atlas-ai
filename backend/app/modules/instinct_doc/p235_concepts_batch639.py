"""P235 b639: bounded exact Egyptian-fraction and harmonic arithmetic.
All pure exact rational arithmetic on caller-supplied values, no I/O and no
retrieval. A positive rational is given as exact int numerator p and exact
int denominator q, each 1..10**6, p < q (a proper fraction); a unit-fraction
decomposition is a tuple of 0..20 distinct exact int denominators, each in
2..10**12; unit_sum accepts any tuple, duplicates included, since it is a
plain sum, not a decomposition validator (only is_egyptian_decomposition
enforces distinctness). greedy_egyptian returns the Fibonacci-Sylvester
greedy expansion (fresh tuple of denominators, strictly increasing),
refusing bad_value:denominator_cap if a greedy denominator would exceed
10**12; it needs no length guard because greedy denominators are at least
the Sylvester terms 2,3,7,43,1807,3263443,10650056950807, so at most six
fit under the cap. engel_expansion returns the Engel denominator sequence
(weakly increasing, fresh tuple), refusing bad_value:expansion_long above
20 terms (a live guard: engel_expansion(999999,1000000) trips it) and
bad_value:denominator_cap at the same 10**12 ceiling.
sylvester_sequence(n) returns the first n terms (a0=2,
a(k+1)=a(k)*(a(k)-1)+1) for n in 0..6, which keeps every term at most
10**12. harmonic_number(n) is the exact H_n for n in 0..400 (H_0 = 0);
harmonic_range_sum(lo,hi) is the exact sum of 1/k for lo..hi inclusive,
1<=lo<=hi<=400. unit_sum(terms) sums 1/d over the supplied denominators;
is_egyptian_decomposition(p,q,terms) checks sum(1/d) == p/q with distinct
denominators; greedy_is_minimal is not claimed: the greedy expansion is what
it is, with no optimality statement. Checks run in three phases: exact type
of every argument in positional order first (bool refused before isinstance,
int subclasses refused, bad_type:<tag>/bad_type:bool_<tag>), then every
argument's value in positional order (bad_value:<tag>_abs, then
bad_value:<tag>_range), then relations across arguments
(bad_relation:not_proper, bad_relation:range_order). Within the terms tuple,
tuple type and length precede all element types, which precede all element
values; relations come last (bad_relation:not_proper before
bad_relation:dup_terms where both apply). For the three-argument functions
the full order is: p,q types; terms tuple type; terms length; all entry
types; p,q values; all entry values; relations.
Lists are built only after every cap is checked. Nothing here claims optimal
or minimal decompositions, continues-fraction convergents, Farey structure,
asymptotics, or any real-world meaning.
SCOPE: caller supplies every value; the module computes exact greedy/Engel
expansions, Sylvester terms, harmonic sums and decomposition checks over the
bounded ranges.
NOT_CLAIMED: minimality or optimality of any expansion, non-greedy Egyptian
existence results, continued fractions, irrational or transcendental
content, asymptotics, randomness, retrieval, novelty, production readiness.
"""
from fractions import Fraction
from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:%s:%s'%(name,code))
        return fail

_ABS=10**12
_PQMAX=10**6
_DENMAX=10**12
_TMAX=20
_SYLMAX=6
_HMAX=400

def _types(fail,args,tags):
    for a,t in zip(args,tags):
        if isinstance(a,bool):fail('bad_type:bool_%s'%t)
        if type(a) is not int:fail('bad_type:%s'%t)

def _vals(fail,args,tags,lo,hi):
    for a,t in zip(args,tags):
        if abs(a)>_ABS:fail('bad_value:%s_abs'%t)
        if not lo<=a<=hi:fail('bad_value:%s_range'%t)

def _pq(fail,p,q):
    _types(fail,(p,q),('p','q'));_vals(fail,(p,q),('p','q'),1,_PQMAX)
    if p>=q:fail('bad_relation:not_proper')

def _greedy(fail,p,q):
    r=Fraction(p,q);out=[]
    while r:
        d=-(-r.denominator//r.numerator)
        if d>_DENMAX:fail('bad_value:denominator_cap')
        out.append(d);r-=Fraction(1,d)
    return tuple(out)

def greedy_egyptian(p,q):
    fail=make_fail('greedy_egyptian');_pq(fail,p,q)
    return _greedy(fail,p,q)

def greedy_egyptian_length(p,q):
    fail=make_fail('greedy_egyptian_length');_pq(fail,p,q)
    return len(_greedy(fail,p,q))

def engel_expansion(p,q):
    fail=make_fail('engel_expansion');_pq(fail,p,q)
    r=Fraction(p,q);out=[]
    while r:
        d=-(-r.denominator//r.numerator)
        if d>_DENMAX:fail('bad_value:denominator_cap')
        out.append(d);r=r*d-1
        if len(out)>_TMAX:fail('bad_value:expansion_long')
    return tuple(out)

def sylvester_sequence(n):
    fail=make_fail('sylvester_sequence')
    _types(fail,(n,),('n',));_vals(fail,(n,),('n',),0,_SYLMAX)
    out=[];a=2
    for _ in range(n):out.append(a);a=a*(a-1)+1
    return tuple(out)

def harmonic_number(n):
    fail=make_fail('harmonic_number')
    _types(fail,(n,),('n',));_vals(fail,(n,),('n',),0,_HMAX)
    return sum((Fraction(1,k) for k in range(1,n+1)),Fraction(0))

def harmonic_range_sum(lo,hi):
    fail=make_fail('harmonic_range_sum')
    _types(fail,(lo,hi),('lo','hi'));_vals(fail,(lo,hi),('lo','hi'),1,_HMAX)
    if lo>hi:fail('bad_relation:range_order')
    return sum((Fraction(1,k) for k in range(lo,hi+1)),Fraction(0))

def _terms(fail,terms):
    if isinstance(terms,bool):fail('bad_type:bool_terms')
    if type(terms) is not tuple:fail('bad_type:terms')
    if not 0<=len(terms)<=_TMAX:fail('bad_value:terms_length')
    for i,d in enumerate(terms):
        if isinstance(d,bool):fail('bad_type:bool_terms_%d'%i)
        if type(d) is not int:fail('bad_type:terms_%d'%i)
    for i,d in enumerate(terms):
        if abs(d)>_ABS:fail('bad_value:terms_%d_abs'%i)
        if not 2<=d<=_DENMAX:fail('bad_value:terms_%d_range'%i)

def unit_sum(terms):
    fail=make_fail('unit_sum');_terms(fail,terms)
    return sum((Fraction(1,d) for d in terms),Fraction(0))

def is_egyptian_decomposition(p,q,terms):
    fail=make_fail('is_egyptian_decomposition')
    _types(fail,(p,q),('p','q'))
    if isinstance(terms,bool):fail('bad_type:bool_terms')
    if type(terms) is not tuple:fail('bad_type:terms')
    if not 0<=len(terms)<=_TMAX:fail('bad_value:terms_length')
    for i,d in enumerate(terms):
        if isinstance(d,bool):fail('bad_type:bool_terms_%d'%i)
        if type(d) is not int:fail('bad_type:terms_%d'%i)
    _vals(fail,(p,q),('p','q'),1,_PQMAX)
    for i,d in enumerate(terms):
        if abs(d)>_ABS:fail('bad_value:terms_%d_abs'%i)
        if not 2<=d<=_DENMAX:fail('bad_value:terms_%d_range'%i)
    if p>=q:fail('bad_relation:not_proper')
    if len(set(terms))!=len(terms):fail('bad_relation:dup_terms')
    return sum((Fraction(1,d) for d in terms),Fraction(0))==Fraction(p,q)

def sylvester_partial_sum(n):
    fail=make_fail('sylvester_partial_sum')
    _types(fail,(n,),('n',));_vals(fail,(n,),('n',),0,_SYLMAX)
    return sum((Fraction(1,d) for d in sylvester_sequence(n)),Fraction(0))

def egyptian_remainder(p,q,terms):
    fail=make_fail('egyptian_remainder')
    _types(fail,(p,q),('p','q'))
    if isinstance(terms,bool):fail('bad_type:bool_terms')
    if type(terms) is not tuple:fail('bad_type:terms')
    if not 0<=len(terms)<=_TMAX:fail('bad_value:terms_length')
    for i,d in enumerate(terms):
        if isinstance(d,bool):fail('bad_type:bool_terms_%d'%i)
        if type(d) is not int:fail('bad_type:terms_%d'%i)
    _vals(fail,(p,q),('p','q'),1,_PQMAX)
    for i,d in enumerate(terms):
        if abs(d)>_ABS:fail('bad_value:terms_%d_abs'%i)
        if not 2<=d<=_DENMAX:fail('bad_value:terms_%d_range'%i)
    if p>=q:fail('bad_relation:not_proper')
    return Fraction(p,q)-sum((Fraction(1,d) for d in terms),Fraction(0))
