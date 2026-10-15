"""P235|L184 b318: exactGF16 definedbyGF2[x]/(x4+x+1),bitmask19.

Fieldints exact0..15,biticofx^i. Nonzeroargs1..15. Exponents exactint0..30.
Validationargumentorder,typebeforerange. Productcarrylessmod19;addXOR.
Tracea+a²+a4+a8,norma15(0->0),orderleastpositivepower1. Frobeniusorbit
successivesquaresstartingarguntilearliestrepeat. MinpolynomialascendingGF2
coefficientsincludingmonicleading1;zero->[0,1],one->[1,1]. Dlogleastexponent
0..14withbase^e=target,Noneoutsidesubgroup. Primitiveelementsascendingorder15.
NoIO/mutation/crypto/security/scalabilityclaims. P235:<function>:<code>errors.
"""
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry':raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:%s:%s' % (name,code))
        return fail
SCOPE='PARTIAL exact GF16 arithmetic, Frobenius minimal polynomials and discrete logarithm witnesses'
NOT_CLAIMED=('cryptographic security','large-field scalability','AGI-like intelligence','global novelty','production readiness')


def _value(name,v,label='element',lo=0,hi=15):
    fail=make_fail(name)
    if type(v) is not int:fail('bad_type:'+label)
    if not lo<=v<=hi:fail('bad_value:'+label)


def _multiply(a,b):
    out=0
    while b:
        if b&1:out^=a
        b>>=1;a<<=1
        if a&16:a^=19
    return out


def _power(a,e):
    out=1
    while e:
        if e&1:out=_multiply(out,a)
        a=_multiply(a,a);e>>=1
    return out


def _orbit(a):
    out=[]
    while a not in out:out.append(a);a=_multiply(a,a)
    return out


def gf16_multiply(left,right):
    """Fieldproductmodx4+x+1."""
    name='gf16_multiply';_value(name,left,'left');_value(name,right,'right')
    return _multiply(left,right)


def gf16_inverse(element):
    """Nonzeroa inverse=a14."""
    name='gf16_inverse';_value(name,element,lo=1)
    return _power(element,14)


def gf16_power(element,exponent):
    """Power0..30,0^0=1formalunit."""
    name='gf16_power';_value(name,element);_value(name,exponent,'exponent',0,30)
    return _power(element,exponent)


def gf16_trace(element):
    """GF16/GF2trace,integerbit0/1."""
    _value('gf16_trace',element);a=element;trace=0
    for _ in range(4):trace^=a;a=_multiply(a,a)
    return trace


def gf16_norm(element):
    """GF16/GF2norm,integer0forzero,1otherwise,computedfieldpower15."""
    _value('gf16_norm',element)
    return _power(element,15)


def gf16_multiplicative_order(element):
    """Leastpositiveorder,nonzeroonly,divisorof15."""
    _value('gf16_multiplicative_order',element,lo=1)
    for d in (1,3,5,15):
        if _power(element,d)==1:return d


def gf16_frobenius_orbit(element):
    """UniqueorbitstartingelementunderFrobeniussquare."""
    _value('gf16_frobenius_orbit',element)
    return _orbit(element)


def gf16_minimal_polynomial(element):
    """Product(X+conjugate)overdistinctFrobeniusorbit,GF2coefficients."""
    _value('gf16_minimal_polynomial',element);coefficients=[1]
    for conjugate in _orbit(element):
        nxt=[0]*(len(coefficients)+1)
        for j,c in enumerate(coefficients):nxt[j]^=_multiply(c,conjugate);nxt[j+1]^=c
        coefficients=nxt
    return coefficients


def gf16_primitive_elements():
    """Allnonzeroelementsoforder15,ascending."""
    return [a for a in range(1,16) if _power(a,3)!=1 and _power(a,5)!=1]


def gf16_discrete_log(base,target):
    """Leastexponent0..14orNoneifoutsidebasegeneratedsubgroup."""
    name='gf16_discrete_log';_value(name,base,'base',1);_value(name,target,'target',1)
    value=1
    for exponent in range(15):
        if value==target:return exponent
        value=_multiply(value,base)
    return None
