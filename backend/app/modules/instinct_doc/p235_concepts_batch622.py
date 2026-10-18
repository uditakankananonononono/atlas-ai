"""P235 b622 bounded binary constraint propagation, PARTIAL only.
Domains: exact tuple of 1..4 exact tuples, each sorted unique ints0..3,
length0..4. Empty domains allowed and mean inconsistent. Constraints: exact
sorted tuple of <=6 (i,j,pairs), 0<=i<j<n, no repeated (i,j); pairs exact
sorted unique tuple of <=16 exact (a,b) pairs, ints0..3. Pairs may contain
values outside the domains; those have no effect. Missing pairs of variables
have universal relations. Validation phases: outer types, all shapes/caps,
all element types, all ranges, all sortedness/uniqueness; domains before
constraints within each phase. Then scalar arguments in order type/range.
Support/revise arcs require distinct variable indices. Revision returns
(new_domains, removed_values). Arc closure repeatedly visits ordered arcs
lexicographically and deletes the smallest unsupported value, one at a time.
Trace is exact tuple of (i,j,value) deletions, <=16. Verify requires the
complete deterministic trace, including no missing or extra steps.
Path closure is strong path consistency: directed relation composition
including diagonal identities, repeated to a fixed point. Returns
(domains, all i<j relations), including universal relations where relevant.
Singleton shaving repeatedly AC-tests each singleton; first failing value
lexicographically is removed, then AC closure repeated, to fixed point.
Assignment exact tuple of n ints0..3; violations reports domain violations
(-1,i) then failed explicit constraints (i,j), ordered. No assignment search.
Adjacent to SAT, decision tables, relational algebra, graph constraint
models and zones; no novelty for those general families. No completeness
claim for local consistency, optimization, learning, external data or IO.
"""
from importlib.util import find_spec
try:
 from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
 if exc.name!='app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
 def make_fail(name):
  def fail(code):raise ValueError('P235:%s:%s'%(name,code))
  return fail
SCOPE='PARTIAL: bounded exact binary constraint propagation'
NOT_CLAIMED=('general SAT solving','decision tables','relational algebra novelty','graph novelty','zone arithmetic','complete satisfiability','global novelty','production readiness')

def _check(n,d,c):
 f=make_fail(n)
 if type(d) is not tuple:f('bad_type:domains')
 if type(c) is not tuple:f('bad_type:constraints')
 if not 1<=len(d)<=4:f('bad_shape:domains')
 if any(type(r) is not tuple for r in d):f('bad_type:domains')
 if any(len(r)>4 for r in d):f('bad_shape:domains')
 if len(c)>6:f('bad_shape:constraints')
 for row in c:
  if type(row) is not tuple:f('bad_type:constraints')
  if len(row)!=3:f('bad_shape:constraints')
  if type(row[2]) is not tuple:f('bad_type:pairs')
  if len(row[2])>16:f('bad_shape:pairs')
  for p in row[2]:
   if type(p) is not tuple:f('bad_type:pairs')
   if len(p)!=2:f('bad_shape:pairs')
 if any(type(v) is not int for r in d for v in r):f('bad_type:domains')
 for i,j,pairs in c:
  if type(i) is not int or type(j) is not int:f('bad_type:indices')
  if any(type(v) is not int for p in pairs for v in p):f('bad_type:pairs')
 if any(not 0<=v<=3 for r in d for v in r):f('bad_value:domains')
 for i,j,pairs in c:
  if not 0<=i<j<len(d):f('bad_value:indices')
  if any(not 0<=v<=3 for p in pairs for v in p):f('bad_value:pairs')
 if any(tuple(sorted(set(r)))!=r for r in d):f('bad_value:domain_order')
 if tuple(sorted(c))!=c or len({(i,j) for i,j,_ in c})!=len(c):f('bad_value:constraint_order')
 if any(tuple(sorted(set(p)))!=p for _,_,p in c):f('bad_value:pair_order')

def _scalar(n,label,x,hi):
 if type(x) is not int:make_fail(n)('bad_type:'+label)
 if not 0<=x<=hi:make_fail(n)('bad_value:'+label)

def _arc(n,d,c,i,j):
 _check(n,d,c);_scalar(n,'i',i,len(d)-1);_scalar(n,'j',j,len(d)-1)
 if i==j:make_fail(n)('bad_value:arc')

def _allowed(c,i,j,a,b):
 for x,y,pairs in c:
  if (i,j)==(x,y):return (a,b) in pairs
  if (j,i)==(x,y):return (b,a) in pairs
 return True

def _supports(d,c,i,j,a):
 return tuple(b for b in d[j] if _allowed(c,i,j,a,b))

def csp_supports(d,c,i,j,value):
 n='csp_supports';_arc(n,d,c,i,j);_scalar(n,'value',value,3)
 if value not in d[i]:make_fail(n)('bad_value:membership')
 return _supports(d,c,i,j,value)

def csp_revise(d,c,i,j):
 _arc('csp_revise',d,c,i,j)
 removed=tuple(a for a in d[i] if not _supports(d,c,i,j,a))
 return tuple(tuple(a for a in r if a not in removed) if k==i else r for k,r in enumerate(d)),removed

def _ac(d,c):
 d=list(d);trace=[]
 while True:
  found=None
  for i in range(len(d)):
   for j in range(len(d)):
    if i!=j:
     for a in d[i]:
      if not _supports(d,c,i,j,a):found=(i,j,a);break
     if found is not None:break
   if found is not None:break
  if found is None:return tuple(d),tuple(trace)
  i,j,a=found;d[i]=tuple(v for v in d[i] if v!=a);trace.append(found)

def csp_arc_close(d,c):
 _check('csp_arc_close',d,c);return _ac(d,c)[0]

def csp_arc_trace(d,c):
 _check('csp_arc_trace',d,c);return _ac(d,c)

def csp_verify_arc_trace(d,c,trace):
 n='csp_verify_arc_trace';_check(n,d,c);f=make_fail(n)
 if type(trace) is not tuple:f('bad_type:trace')
 if len(trace)>16:f('bad_shape:trace')
 for row in trace:
  if type(row) is not tuple:f('bad_type:trace')
  if len(row)!=3:f('bad_shape:trace')
 if any(type(v) is not int for r in trace for v in r):f('bad_type:trace')
 for i,j,a in trace:
  if not 0<=i<len(d) or not 0<=j<len(d) or i==j or not 0<=a<=3:f('bad_value:trace')
 return trace==_ac(d,c)[1]

def csp_is_arc_consistent(d,c):
 _check('csp_is_arc_consistent',d,c)
 return _ac(d,c)[0]==d

def csp_path_close(d,c):
 _check('csp_path_close',d,c);n=len(d)
 r={(i,j):{(a,b) for a in d[i] for b in d[j] if (a==b if i==j else _allowed(c,i,j,a,b))} for i in range(n) for j in range(n)}
 while True:
  changed=False
  for i in range(n):
   for j in range(n):
    for k in range(n):
     keep={(a,b) for a,b in r[i,j] if any((a,t) in r[i,k] and (t,b) in r[k,j] for t in d[k])}
     if keep!=r[i,j]:r[i,j]=keep;changed=True
  if not changed:break
 out=tuple(tuple(a for a in d[i] if (a,a) in r[i,i]) for i in range(n))
 return out,tuple((i,j,tuple(sorted(r[i,j]))) for i in range(n) for j in range(i+1,n))

def csp_singleton_close(d,c):
 _check('csp_singleton_close',d,c);d=_ac(d,c)[0]
 while True:
  failed=None
  for i,r in enumerate(d):
   for a in r:
    trial=d[:i]+((a,),)+d[i+1:]
    if any(not row for row in _ac(trial,c)[0]):failed=(i,a);break
   if failed is not None:break
  if failed is None:return d
  i,a=failed;d=d[:i]+(tuple(v for v in d[i] if v!=a),)+d[i+1:];d=_ac(d,c)[0]

def _assignment(n,d,c,values):
 _check(n,d,c);f=make_fail(n)
 if type(values) is not tuple:f('bad_type:values')
 if len(values)!=len(d):f('bad_shape:values')
 if any(type(v) is not int for v in values):f('bad_type:values')
 if any(not 0<=v<=3 for v in values):f('bad_value:values')

def _violations(d,c,values):
 return tuple((-1,i) for i,r in enumerate(d) if values[i] not in r)+tuple((i,j) for i,j,p in c if (values[i],values[j]) not in p)

def csp_violations(d,c,values):
 _assignment('csp_violations',d,c,values);return _violations(d,c,values)

def csp_assignment_ok(d,c,values):
 _assignment('csp_assignment_ok',d,c,values);return not _violations(d,c,values)
