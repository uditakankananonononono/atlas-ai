"""P235 b641 finite ground uninterpreted-function equality, PARTIAL only.
Terms exact tuple1..12 of (symbol,children), symbol exact int0..7; children
exact tuple0..2 of exact indices strictly below the node index. Every use
of a symbol has the same arity. Repeated syntactic nodes allowed. Equality
and disequality lists exact tuples<=16 of exact (left,right) indices;
repeats/order allowed. No variables, new terms or infinite-term semantics.
Classes are smallest node indices. Explicit equalities merged in input
order, then first lex congruent pair merged until stable. Trace exact tuple
<=11 triples (kind,left,right), kind0 explicit or1 congruence; only actual
merges recorded, node indices not representatives. Verifier exact replay.
Ground model certificate exact tuple of one label per term, ints0..11:
checks asserted equalities/disequalities and equal-label argument vectors
imply equal output labels for equal symbols. Extra label identifications
allowed. Model returns (canonical_labels, function_rows) where each row
(symbol,argument_labels,result_label), sorted unique. This is a model of
the supplied ground terms, not a full infinite function interpretation.
Validation all types positional first, shapes/caps next, values last;
term arity consistency and scalar relational checks in values phase.
Adjacent b303/b372/b384 first-order unification/rewriting, b373 semigroup
congruences, DFA quotients: none claimed. No substitution, variables,
rewrite system, automata, operation-table enumeration, solver integration,
IO, model-count or general satisfiability claim beyond this ground theory.
"""
from importlib.util import find_spec
try:
 from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
 if exc.name!='app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
 def make_fail(name):
  def fail(code):raise ValueError('P235:%s:%s'%(name,code))
  return fail
SCOPE='PARTIAL: bounded ground uninterpreted-function equality'
NOT_CLAIMED=('first-order unification b303 b372','rewriting b384','semigroup congruences b373','DFA quotients','global novelty','production readiness')

def _types(n,label,obj,kind):
 f=make_fail(n)
 if type(obj) is not tuple:f('bad_type:'+label)
 for row in obj:
  if kind=='labels':
   if type(row) is not int:f('bad_type:'+label)
   continue
  if type(row) is not tuple:f('bad_type:'+label)
  for pos,v in enumerate(row):
   if kind=='terms' and pos==1:
    if type(v) is not tuple:f('bad_type:'+label)
    if any(type(x) is not int for x in v):f('bad_type:'+label)
   elif type(v) is not int:f('bad_type:'+label)

def _shape(n,label,obj,kind,count):
 f=make_fail(n)
 if kind=='terms':
  if not 1<=len(obj)<=12 or any(len(r)!=2 for r in obj):f('bad_shape:'+label)
  if any(len(r[1])>2 for r in obj):f('bad_shape:'+label)
 elif kind=='pairs':
  if len(obj)>16 or any(len(r)!=2 for r in obj):f('bad_shape:'+label)
 elif kind=='trace':
  if len(obj)>11 or any(len(r)!=3 for r in obj):f('bad_shape:'+label)
 elif len(obj)!=count:f('bad_shape:'+label)

def _values(n,label,obj,kind,count):
 f=make_fail(n)
 if kind=='terms':
  arity={}
  for i,(s,args) in enumerate(obj):
   if not 0<=s<=7 or any(not 0<=a<i for a in args):f('bad_value:'+label)
   if s in arity and arity[s]!=len(args):f('bad_value:arity')
   arity[s]=len(args)
 elif kind=='labels':
  if any(not 0<=v<=11 for v in obj):f('bad_value:'+label)
 elif kind=='pairs':
  if any(not 0<=v<count for r in obj for v in r):f('bad_value:'+label)
 else:
  if any(not 0<=k<=1 or not 0<=a<count or not 0<=b<count for k,a,b in obj):f('bad_value:'+label)

def _check(n,terms,eq,extra=(),scalars=()):
 args=(('terms',terms,'terms'),('equalities',eq,'pairs'))+extra
 for label,obj,kind in args:_types(n,label,obj,kind)
 for label,v in scalars:
  if type(v) is not int:make_fail(n)('bad_type:'+label)
 for label,obj,kind in args:_shape(n,label,obj,kind,len(terms))
 for label,obj,kind in args:_values(n,label,obj,kind,len(terms))
 for label,v in scalars:
  if not 0<=v<len(terms):make_fail(n)('bad_value:'+label)

def _close(terms,eq):
 labels=list(range(len(terms)));trace=[]
 def merge(a,b,kind):
  x,y=labels[a],labels[b]
  if x==y:return False
  lo,hi=min(x,y),max(x,y)
  for k in range(len(labels)):
   if labels[k]==hi:labels[k]=lo
  trace.append((kind,a,b));return True
 for a,b in eq:merge(a,b,0)
 while True:
  found=False
  for i,(s,args) in enumerate(terms):
   for j in range(i+1,len(terms)):
    t,other=terms[j]
    if s==t and tuple(labels[a] for a in args)==tuple(labels[a] for a in other):
     if merge(i,j,1):found=True;break
   if found:break
  if not found:return tuple(labels),tuple(trace)

def ground_classes(terms,equalities):
 _check('ground_classes',terms,equalities);return _close(terms,equalities)[0]

def ground_equal(terms,equalities,left,right):
 _check('ground_equal',terms,equalities,scalars=(('left',left),('right',right)));d=_close(terms,equalities)[0];return d[left]==d[right]

def ground_entailed_pairs(terms,equalities):
 _check('ground_entailed_pairs',terms,equalities);d=_close(terms,equalities)[0]
 return tuple((i,j) for i in range(len(d)) for j in range(i+1,len(d)) if d[i]==d[j])

def ground_conflicts(terms,equalities,disequalities):
 _check('ground_conflicts',terms,equalities,(('disequalities',disequalities,'pairs'),));d=_close(terms,equalities)[0]
 return tuple(k for k,(a,b) in enumerate(disequalities) if d[a]==d[b])

def ground_consistent(terms,equalities,disequalities):
 _check('ground_consistent',terms,equalities,(('disequalities',disequalities,'pairs'),));d=_close(terms,equalities)[0]
 return all(d[a]!=d[b] for a,b in disequalities)

def ground_model(terms,equalities):
 _check('ground_model',terms,equalities);d=_close(terms,equalities)[0]
 return d,tuple(sorted({(s,tuple(d[a] for a in args),d[i]) for i,(s,args) in enumerate(terms)}))

def ground_verify_model(terms,equalities,disequalities,labels):
 _check('ground_verify_model',terms,equalities,(('disequalities',disequalities,'pairs'),('labels',labels,'labels')))
 if any(labels[a]!=labels[b] for a,b in equalities) or any(labels[a]==labels[b] for a,b in disequalities):return False
 table={}
 for i,(s,args) in enumerate(terms):
  key=(s,tuple(labels[a] for a in args))
  if key in table and table[key]!=labels[i]:return False
  table[key]=labels[i]
 return True

def ground_merge_trace(terms,equalities):
 _check('ground_merge_trace',terms,equalities);return _close(terms,equalities)

def ground_verify_trace(terms,equalities,trace):
 _check('ground_verify_trace',terms,equalities,(('trace',trace,'trace'),));return trace==_close(terms,equalities)[1]

def ground_redundant_equalities(terms,equalities):
 _check('ground_redundant_equalities',terms,equalities);out=[]
 for k,(a,b) in enumerate(equalities):
  d=_close(terms,equalities[:k]+equalities[k+1:])[0]
  if d[a]==d[b]:out.append(k)
 return tuple(out)
