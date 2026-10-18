"""P235 b634: bounded exact integer-partition and composition counting.
All pure exact integer arithmetic on caller-supplied arguments, no I/O and no
retrieval. An integer partition of n is a nonincreasing tuple of positive
parts summing to n; a composition is an ordered tuple. Every count is an
exact int computed by recurrence or enumeration over bounded ranges; lists
are returned as fresh sorted tuples and never share structure with the input.
partition_list orders partitions in decreasing lexicographic tuple order;
composition_list_bounded orders compositions in increasing lexicographic
order. composition_list_bounded refuses bad_value:too_many when the exact
count would exceed 200 rows, computed before any row is built.
Caps: n, k, m, b exact ints in 0..60 (conjugate parts 1..60, sum at most 60,
at most 12 entries). Checks run in three phases: the exact type of every
argument in positional order first (bool refused before any isinstance,
int subclasses refused, bad_type:<tag> / bad_type:bool_<tag>), then every
argument's value in positional order (absolute cap bad_value:<tag>_abs, then
range bad_value:<tag>_range), then relations across arguments. Within the
conjugate partition argument, the tuple type precedes its length and all
entry types precede all entry values, then the nonincreasing relation
(bad_relation:not_partition). Nothing here claims set partitions, Stirling or
Bell numbers, generating-function algebra, asymptotics, random sampling, or
any unbounded enumeration; outputs are exact finite counts and bounded lists
only.
SCOPE: caller supplies every parameter; the module only counts and lists
integer partitions and bounded/weak compositions over the bounded ranges.
NOT_CLAIMED: no set partitions or Stirling/Bell families, no graphs, no
generating functions, no asymptotic estimates, no randomness, no retrieval,
no novelty claim.
"""
from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:%s:%s'%(name,code))
        return fail

_ABS=10**12
_NMAX=60
_LIST_NMAX=12
_LIST_ROWS=200

def _itype(fail,args,tags):
    for a,t in zip(args,tags):
        if isinstance(a,bool):fail('bad_type:bool_%s'%t)
        if type(a) is not int:fail('bad_type:%s'%t)

def _ivalue(fail,args,tags,hi):
    for a,t in zip(args,tags):
        if abs(a)>_ABS:fail('bad_value:%s_abs'%t)
        if not 0<=a<=hi:fail('bad_value:%s_range'%t)

def _p_table(n):
    t=[[0]*(n+1) for _ in range(n+1)]
    for i in range(n+1):t[i][0]=1
    for i in range(1,n+1):
        for j in range(1,n+1):
            t[i][j]=t[i-1][j]+(t[i][j-i] if j>=i else 0)
    return t

def partition_count(n):
    fail=make_fail('partition_count')
    _itype(fail,(n,),('n',));_ivalue(fail,(n,),('n',),_NMAX)
    return _p_table(n)[n][n]

def partition_count_parts(n,k):
    fail=make_fail('partition_count_parts')
    _itype(fail,(n,k),('n','k'));_ivalue(fail,(n,k),('n','k'),_NMAX)
    if k==0:return 1 if n==0 else 0
    if k>n:return 0
    t=[[0]*(n+1) for _ in range(k+1)]
    t[0][0]=1
    for i in range(1,k+1):
        for j in range(1,n+1):
            t[i][j]=t[i-1][j-1]+(t[i][j-i] if j>=i else 0)
    return t[k][n]

def partition_count_max_part(n,m):
    fail=make_fail('partition_count_max_part')
    _itype(fail,(n,m),('n','m'));_ivalue(fail,(n,m),('n','m'),_NMAX)
    if m==0:return 1 if n==0 else 0
    t=[0]*(n+1);t[0]=1
    for part in range(1,m+1):
        for j in range(part,n+1):t[j]+=t[j-part]
    return t[n]

def partition_count_distinct(n):
    fail=make_fail('partition_count_distinct')
    _itype(fail,(n,),('n',));_ivalue(fail,(n,),('n',),_NMAX)
    t=[0]*(n+1);t[0]=1
    for part in range(1,n+1):
        for j in range(n,part-1,-1):t[j]+=t[j-part]
    return t[n]

def partition_count_odd(n):
    fail=make_fail('partition_count_odd')
    _itype(fail,(n,),('n',));_ivalue(fail,(n,),('n',),_NMAX)
    t=[0]*(n+1);t[0]=1
    for part in range(1,n+1,2):
        for j in range(part,n+1):t[j]+=t[j-part]
    return t[n]

def partition_list(n):
    fail=make_fail('partition_list')
    _itype(fail,(n,),('n',));_ivalue(fail,(n,),('n',),_LIST_NMAX)
    out=[]
    def rec(rem,hi,cur):
        if rem==0:out.append(tuple(cur));return
        for p in range(min(hi,rem),0,-1):
            cur.append(p);rec(rem-p,p,cur);cur.pop()
    rec(n,n,[])
    return tuple(out)

def partition_conjugate(partition):
    fail=make_fail('partition_conjugate')
    if isinstance(partition,bool):fail('bad_type:bool_partition')
    if type(partition) is not tuple:fail('bad_type:partition')
    if not 0<=len(partition)<=12:fail('bad_value:partition_length')
    for i,p in enumerate(partition):
        if isinstance(p,bool):fail('bad_type:bool_partition_%d'%i)
        if type(p) is not int:fail('bad_type:partition_%d'%i)
    for i,p in enumerate(partition):
        if abs(p)>_ABS:fail('bad_value:partition_%d_abs'%i)
        if not 1<=p<=_NMAX:fail('bad_value:partition_%d_range'%i)
    if sum(partition)>_NMAX:fail('bad_value:partition_sum')
    for i in range(len(partition)-1):
        if partition[i]<partition[i+1]:fail('bad_relation:not_partition')
    if not partition:return ()
    return tuple(sum(1 for p in partition if p>j) for j in range(partition[0]))

def composition_count_bounded(n,k,b):
    fail=make_fail('composition_count_bounded')
    _itype(fail,(n,k,b),('n','k','b'));_ivalue(fail,(n,k,b),('n','k','b'),_NMAX)
    if k==0:return 1 if n==0 else 0
    if b==0:return 0
    t=[[0]*(n+1) for _ in range(k+1)]
    t[0][0]=1
    for i in range(1,k+1):
        for j in range(n+1):
            lo=max(0,j-b)
            t[i][j]=sum(t[i-1][lo:j]) if j>0 else 0
    return t[k][n]

def composition_count_weak(n,k):
    fail=make_fail('composition_count_weak')
    _itype(fail,(n,k),('n','k'));_ivalue(fail,(n,k),('n','k'),_NMAX)
    if k==0:return 1 if n==0 else 0
    c=1
    for i in range(1,k):c=c*(n+k-i)//i
    return c

def composition_list_bounded(n,k,b):
    fail=make_fail('composition_list_bounded')
    _itype(fail,(n,k,b),('n','k','b'));_ivalue(fail,(n,k,b),('n','k','b'),_NMAX)
    if k==0:
        return () if n else ((),)
    if b==0:return ()
    t=[[0]*(n+1) for _ in range(k+1)]
    t[0][0]=1
    for i in range(1,k+1):
        for j in range(n+1):
            lo=max(0,j-b)
            t[i][j]=sum(t[i-1][lo:j]) if j>0 else 0
    if t[k][n]>_LIST_ROWS:fail('bad_value:too_many')
    out=[]
    def rec(rem,parts,cur):
        if parts==1:
            if 1<=rem<=b:out.append(tuple(cur)+(rem,))
            return
        for p in range(1,min(b,rem-(parts-1))+1):
            cur.append(p);rec(rem-p,parts-1,cur);cur.pop()
    rec(n,k,[])
    return tuple(out)
