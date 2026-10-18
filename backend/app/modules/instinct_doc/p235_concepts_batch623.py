import importlib.util
"""p235 concepts batch 623: bounded exact cover on small universes.

SCOPE: PARTIAL bounded exact cover: exact-cover counting and search, selection
checks, coverage diagnostics, intersection and frequency structure, essential sets.

NOT_CLAIMED: set cover minimization or approximation; universes over 12 elements
or more than 16 sets; dancing-links performance; weighted or colored variants;
global novelty; production readiness.

Representation: a universe is the integer range 1..n with 1<=n<=12. `sets` is a
list of 1..16 subsets; each subset is a nonempty list of at most n universe
elements, sorted strictly ascending (no duplicates). A `pick` is a list of set
indices (0-based), sorted strictly ascending. An exact cover is a pick whose sets
are pairwise disjoint and whose union is the whole universe. Solutions are
returned as sorted index lists in lexicographic order; the solver branches on the
smallest uncovered element and tries candidate sets in index order.

Refusal codes (ValueError, message 'P235:<fn>:<code>'):
n: 'bad_type:n', 'bad_value:n' (outside 1..12).
sets: 'bad_type:sets', 'bad_length:sets' (not 1..16), 'bad_type:sets[i]',
'bad_length:sets[i]' (empty or over n entries), 'bad_type:sets[i][j]',
'bad_value:sets[i][j]' (outside 1..n), 'bad_order:sets[i]' (not strictly
ascending).
pick: 'bad_type:pick', 'bad_length:pick' (over len(sets)), 'bad_type:pick[i]',
'bad_value:pick[i]' (outside 0..len(sets)-1), 'bad_order:pick' (not strictly
ascending).
cover_all refuses 'too_many:solutions' when more than 32 exact covers exist.
Check order: n, then sets structure, then each set in index order (type, length,
then each entry's type, value, then ascending order), then pick (type, length,
then each entry's type, value, then ascending order).
"""

SCOPE='PARTIAL bounded exact cover: exact-cover counting and search, selection checks, coverage diagnostics, intersection and frequency structure, essential sets'
NOT_CLAIMED=('set cover minimization or approximation','universes over 12 elements or more than 16 sets','dancing-links performance','weighted or colored variants','global novelty','production readiness')

def _absent(name):
    try:return importlib.util.find_spec(name) is None
    except (ImportError,ValueError):return True

try:from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ImportError as exc:
    if exc.name!='app.modules.instinct_doc.p235_concepts_registry' or not _absent(exc.name):raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:%s:%s' % (name,code))
        return fail


def _inst(name,n,sets):
    f=make_fail(name)
    if type(n) is not int:f('bad_type:n')
    if not 1<=n<=12:f('bad_value:n')
    if type(sets) is not list:f('bad_type:sets')
    if not 1<=len(sets)<=16:f('bad_length:sets')
    for i,s in enumerate(sets):
        if type(s) is not list:f('bad_type:sets[%s]'%i)
        if not 1<=len(s)<=n:f('bad_length:sets[%s]'%i)
        for j,x in enumerate(s):
            if type(x) is not int:f('bad_type:sets[%s][%s]'%(i,j))
            if not 1<=x<=n:f('bad_value:sets[%s][%s]'%(i,j))
        for j in range(len(s)-1):
            if s[j]>=s[j+1]:f('bad_order:sets[%s]'%i)
    m=len(sets)
    masks=[]
    for s in sets:
        mask=0
        for x in s:mask|=1<<(x-1)
        masks.append(mask)
    return n,sets,m,masks

def _pick(name,m,pick):
    f=make_fail(name)
    if type(pick) is not list:f('bad_type:pick')
    if len(pick)>m:f('bad_length:pick')
    for i,x in enumerate(pick):
        if type(x) is not int:f('bad_type:pick[%s]'%i)
        if not 0<=x<=m-1:f('bad_value:pick[%s]'%i)
    for i in range(len(pick)-1):
        if pick[i]>=pick[i+1]:f('bad_order:pick')
    return pick

def _solve(n,m,masks,cap):
    full=(1<<n)-1;by_el=[[] for _ in range(n)]
    for i,mask in enumerate(masks):
        for x in range(n):
            if mask>>x&1:by_el[x].append(i)
    out=[]
    def rec(covered,pick):
        if covered==full:out.append(pick);return len(out)>=cap
        x=-1
        for e in range(n):
            if not covered>>e&1:x=e;break
        for i in by_el[x]:
            if masks[i]&covered==0:
                if rec(covered|masks[i],pick+[i]):return True
        return False
    rec(0,[])
    return out

def cover_count(n,sets):
    """Exact number of exact covers (full enumeration, no cap)."""
    n,sets,m,masks=_inst('cover_count',n,sets)
    return len(_solve(n,m,masks,65536))

def cover_exists(n,sets):
    """True iff at least one exact cover exists."""
    n,sets,m,masks=_inst('cover_exists',n,sets)
    return len(_solve(n,m,masks,1))>0

def cover_first(n,sets):
    """First exact cover in lexicographic order of sorted index lists, or []."""
    n,sets,m,masks=_inst('cover_first',n,sets)
    sols=_solve(n,m,masks,65536)
    return min(sorted(p) for p in sols) if sols else []

def cover_all(n,sets):
    """All exact covers as sorted index lists in lexicographic order.

    Refuses 'too_many:solutions' when more than 32 exact covers exist."""
    n,sets,m,masks=_inst('cover_all',n,sets)
    sols=_solve(n,m,masks,33)
    if len(sols)>32:make_fail('cover_all')('too_many:solutions')
    return sorted(sorted(p) for p in sols)

def is_cover(n,sets,pick):
    """True iff pick is an exact cover of the universe."""
    n,sets,m,masks=_inst('is_cover',n,sets);_pick('is_cover',m,pick)
    seen=0
    for i in pick:
        if masks[i]&seen:return False
        seen|=masks[i]
    return seen==(1<<n)-1

def uncovered_elements(n,sets,pick):
    """Sorted elements of 1..n covered by no set in pick (possibly all)."""
    n,sets,m,masks=_inst('uncovered_elements',n,sets);_pick('uncovered_elements',m,pick)
    seen=0
    for i in pick:seen|=masks[i]
    return [x for x in range(1,n+1) if not seen>>(x-1)&1]

def overcovered_elements(n,sets,pick):
    """Sorted elements covered by two or more sets in pick."""
    n,sets,m,masks=_inst('overcovered_elements',n,sets);_pick('overcovered_elements',m,pick)
    once=0;multi=0
    for i in pick:
        multi|=once&masks[i];once|=masks[i]
    return [x for x in range(1,n+1) if multi>>(x-1)&1]

def set_intersections(sets,n):
    """Symmetric len(sets) x len(sets) matrix of pairwise intersection sizes.

    The diagonal holds the set sizes. n declares the universe and is validated."""
    n,sets,m,masks=_inst('set_intersections',n,sets)
    M=[]
    for i in range(m):
        row=[]
        for j in range(m):row.append(bin(masks[i]&masks[j]).count('1'))
        M.append(row)
    return M

def element_frequency(n,sets):
    """Per-element count of sets containing it, for elements 1..n in order."""
    n,sets,m,masks=_inst('element_frequency',n,sets)
    out=[0]*n
    for mask in masks:
        for x in range(n):
            if mask>>x&1:out[x]+=1
    return out

def essential_sets(n,sets):
    """Sorted indices of sets that alone cover some element.

    Such a set belongs to every exact cover; a zero-frequency element means no
    exact cover exists and contributes nothing."""
    n,sets,m,masks=_inst('essential_sets',n,sets)
    out=set()
    for x in range(n):
        owners=[i for i in range(m) if masks[i]>>x&1]
        if len(owners)==1:out.add(owners[0])
    return sorted(out)
