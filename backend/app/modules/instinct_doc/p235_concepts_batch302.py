"""P235|L184 b302:exact combinatorics on binary words.
Word is an exactstr of 1..12 characters over the alphabet 'a','b'. Validation
order:type/empty/length/alphabet. Counting functions take exactint n 1..8 and
exactint k 1..3 (bool and int subclasses refused;both types are checked before
either range,n before k). De Bruijn takes exactint n 1..5. ValueError
P235:<name>:<code>. No IO,text or mutation. Results are fresh values:lists of
strs or ints,strs,ints,bools. Lyndon word:strictly smaller than every proper
rotation. Border:a proper non-empty prefix that is also a suffix,reported by
length ascending. De Bruijn output is the lexicographically least cyclic
binary sequence of length 2**n containing every n-bit word,written with
characters '0' and '1'.
"""
from math import gcd
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry':
        raise
    def make_fail(name):
        def fail(code):
            raise ValueError("P235:%s:%s" % (name, code))
        return fail
SCOPE='PARTIAL exact bounded binary word combinatorics,not string library or compression scheme'
NOT_CLAIMED=('arbitrary alphabets','long words','global novelty','production readiness')


def _word(name,w):
    fail=make_fail(name)
    if type(w) is not str:fail('bad_type:word')
    if not w:fail('bad_value:empty')
    if len(w)>12:fail('too_long:word')
    if any(c not in 'ab' for c in w):fail('bad_value:alphabet')
    return w


def _count_args(name,n,k):
    fail=make_fail(name)
    if type(n) is not int:fail('bad_type:n')
    if type(k) is not int:fail('bad_type:k')
    if not 1<=n<=8:fail('bad_value:n')
    if not 1<=k<=3:fail('bad_value:k')


def _duval(w):
    n=len(w);i=0;out=[]
    while i<n:
        j=i+1;k=i
        while j<n and w[k]<=w[j]:
            k=i if w[k]<w[j] else k+1
            j+=1
        while i<=k:
            out.append(w[i:i+j-k]);i+=j-k
    return out


def cw_lyndon_factorization_exact(w):
    """Unique nonincreasing factorization into Lyndon words (Duval)."""
    return _duval(_word('cw_lyndon_factorization_exact',w))


def cw_is_lyndon_exact(w):
    """True when the word is itself a Lyndon word."""
    return len(_duval(_word('cw_is_lyndon_exact',w)))==1


def cw_border_lengths_exact(w):
    """Lengths of all proper non-empty borders,ascending (failure chain)."""
    w=_word('cw_border_lengths_exact',w);n=len(w);pi=[0]*n
    for i in range(1,n):
        k=pi[i-1]
        while k and w[i]!=w[k]:k=pi[k-1]
        if w[i]==w[k]:k+=1
        pi[i]=k
    out=[];k=pi[-1]
    while k:out.append(k);k=pi[k-1]
    return out[::-1]


def cw_bwt_exact(w):
    """Burrows-Wheeler transform:[last column of the sorted rotations,index of
    the first sorted rotation equal to the word].
    """
    w=_word('cw_bwt_exact',w);n=len(w)
    rots=sorted(w[i:]+w[:i] for i in range(n))
    return [''.join(r[-1] for r in rots),rots.index(w)]


def cw_standard_factorization_exact(w):
    """[u,v] for a Lyndon word w=uv with v its least proper suffix (the longest
    proper Lyndon suffix). A non-Lyndon word refuses bad_value:not_lyndon,then
    a single letter refuses bad_value:too_short.
    """
    fail=make_fail('cw_standard_factorization_exact');w=_word('cw_standard_factorization_exact',w)
    if len(_duval(w))!=1:fail('bad_value:not_lyndon')
    if len(w)<2:fail('bad_value:too_short')
    k=min(range(1,len(w)),key=lambda i:w[i:])
    return [w[:k],w[k:]]


def cw_distinct_squares_exact(w):
    """Number of distinct non-empty factors of the form uu."""
    w=_word('cw_distinct_squares_exact',w);n=len(w)
    return len({w[i:i+2*h] for h in range(1,n//2+1) for i in range(n-2*h+1) if w[i:i+h]==w[i+h:i+2*h]})


def cw_primitive_root_exact(w):
    """[root,exponent] with root primitive and root*exponent equal to the word."""
    w=_word('cw_primitive_root_exact',w);n=len(w)
    p=next(d for d in range(1,n+1) if n%d==0 and w[:d]*(n//d)==w)
    return [w[:p],n//p]


def cw_necklace_count_exact(n,k):
    """Number of necklaces of length n over k letters (Burnside over rotations)."""
    _count_args('cw_necklace_count_exact',n,k)
    return sum(k**gcd(r,n) for r in range(n))//n


def _mobius(d):
    out=1;p=2
    while d>1:
        if d%p==0:
            d//=p
            if d%p==0:return 0
            out=-out
        p+=1
    return out


def cw_lyndon_count_exact(n,k):
    """Number of Lyndon words of length n over k letters (Moebius inversion)."""
    _count_args('cw_lyndon_count_exact',n,k)
    return sum(_mobius(d)*k**(n//d) for d in range(1,n+1) if n%d==0)//n


def cw_debruijn_exact(n):
    """Lexicographically least binary de Bruijn sequence of order n."""
    fail=make_fail('cw_debruijn_exact')
    if type(n) is not int:fail('bad_type:n')
    if not 1<=n<=5:fail('bad_value:n')
    a=[0]*(n+1);seq=[]
    def db(t,p):
        if t>n:
            if n%p==0:seq.extend(a[1:p+1])
        else:
            a[t]=a[t-p];db(t+1,p)
            if a[t-p]==0:
                a[t]=1;db(t+1,t)
    db(1,1)
    return ''.join(map(str,seq))
