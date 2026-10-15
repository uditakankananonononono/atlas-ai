"""P235 b321: bounded odd-prime quadratic congruences, Jacobi and Hensel.
Exact ints only, argument-order type then range checks. Primes3..31 verified.
Residue lists include zero; nonresidue lists do not. Sorted distinct roots.
Jacobi numerator-99..99, denominator odd1..99. Prime power exponent1..3.
Quadratic coefficients0..p-1, including linear/constant degeneracies.
Two-square pairs nonnegative a<=b, [] if none. Histograms indexed0..p-1.
Gauss exponents count x²modp, not complex-valued Gauss sums. No IO/mutation.
"""
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry':raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:%s:%s' % (name,code))
        return fail
from math import isqrt
SCOPE='PARTIAL bounded odd-prime quadratic congruences and exact residue witnesses'
NOT_CLAIMED=('cryptographic security','large-integer scalability','complex Gauss sums','global novelty','production readiness')

def _v(name,v,label,lo,hi):
    if type(v) is not int:make_fail(name)('bad_type:'+label)
    if not lo<=v<=hi:make_fail(name)('bad_value:'+label)

def _prime(name,p):
    _v(name,p,'prime',3,31)
    if p%2==0 or any(p%d==0 for d in range(3,isqrt(p)+1,2)):make_fail(name)('not_odd_prime')

def _sqrt(a,p):
    a%=p
    if a==0:return [0]
    if pow(a,(p-1)//2,p)!=1:return []
    if p%4==3:r=pow(a,(p+1)//4,p)
    else:
        q=p-1;s=0
        while q%2==0:q//=2;s+=1
        z=2
        while pow(z,(p-1)//2,p)!=p-1:z+=1
        c=pow(z,q,p);r=pow(a,(q+1)//2,p);t=pow(a,q,p);order=s
        while t!=1:
            i=1;v=t*t%p
            while v!=1:v=v*v%p;i+=1
            b=pow(c,1<<(order-i-1),p);r=r*b%p;c=b*b%p;t=t*c%p;order=i
    return sorted({r,(-r)%p})

def jacobi_symbol(numerator,denominator):
    name='jacobi_symbol';_v(name,numerator,'numerator',-99,99);_v(name,denominator,'denominator',1,99)
    if denominator%2==0:make_fail(name)('not_odd_denominator')
    a=numerator%denominator;n=denominator;sign=1
    while a:
        while a%2==0:
            a//=2
            if n%8 in (3,5):sign=-sign
        a,n=n,a
        if a%4==3 and n%4==3:sign=-sign
        a%=n
    return sign if n==1 else 0

def prime_quadratic_residues(prime):
    _prime('prime_quadratic_residues',prime)
    return [0]+[a for a in range(1,prime) if pow(a,(prime-1)//2,prime)==1]

def prime_quadratic_nonresidues(prime):
    _prime('prime_quadratic_nonresidues',prime)
    return [a for a in range(1,prime) if pow(a,(prime-1)//2,prime)==prime-1]

def prime_modular_square_roots(prime,value):
    name='prime_modular_square_roots';_prime(name,prime);_v(name,value,'value',0,prime-1)
    return _sqrt(value,prime)

def prime_power_square_roots(prime,exponent,value):
    name='prime_power_square_roots';_prime(name,prime);_v(name,exponent,'exponent',1,3);_v(name,value,'value',0,prime**exponent-1)
    roots=_sqrt(value,prime);modulus=prime
    for _ in range(1,exponent):
        next_roots=[]
        for r in roots:
            derivative=2*r%prime;rhs=((value-r*r)//modulus)%prime
            digits=[rhs*pow(derivative,-1,prime)%prime] if derivative else range(prime) if rhs==0 else []
            next_roots.extend(r+d*modulus for d in digits)
        roots=next_roots;modulus*=prime
    return sorted(roots)

def quadratic_congruence_roots(prime,a,b,c):
    name='quadratic_congruence_roots';_prime(name,prime)
    for label,v in (('a',a),('b',b),('c',c)):_v(name,v,label,0,prime-1)
    if a==0:
        if b:return [(-c*pow(b,-1,prime))%prime]
        return list(range(prime)) if c==0 else []
    inverse=pow(2*a,-1,prime)
    return sorted({(r-b)*inverse%prime for r in _sqrt((b*b-4*a*c)%prime,prime)})

def prime_sum_two_squares(prime):
    _prime('prime_sum_two_squares',prime)
    if prime%4==3:return []
    out=set()
    for r in _sqrt(prime-1,prime):
        a,b=prime,r
        while b*b>prime:a,b=b,a%b
        remainder=prime-b*b;t=isqrt(remainder)
        if t*t==remainder:out.add(tuple(sorted((b,t))))
    return sorted(out)

def _counts(prime,difference):
    residues=prime_quadratic_residues(prime);out=[0]*prime
    for a in residues:
        for b in residues:out[(a-b if difference else a+b)%prime]+=1
    return out

def quadratic_residue_addition_counts(prime):
    _prime('quadratic_residue_addition_counts',prime)
    return _counts(prime,False)

def quadratic_residue_difference_counts(prime):
    _prime('quadratic_residue_difference_counts',prime)
    return _counts(prime,True)

def prime_quadratic_gauss_exponents(prime):
    _prime('prime_quadratic_gauss_exponents',prime);out=[0]*prime
    # x² increments2x+1,modularfinite-differenceaccumulation.
    square=0;delta=1
    for _ in range(prime):out[square]+=1;square=(square+delta)%prime;delta=(delta+2)%prime
    return out
