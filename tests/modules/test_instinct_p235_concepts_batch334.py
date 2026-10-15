import copy,itertools as it,random,pytest
from app.modules.instinct_doc import p235_concepts_batch334 as m
class T(tuple):pass
class I(int):pass
NAMES=('dfa_accept_word','dfa_language_count','dfa_shortest_accepted_word','dfa_equivalence_witness','dfa_minimize_exact','dfa_complement','dfa_intersection','dfa_union','dfa_reachable_trim','dfa_state_distinguishers')

def accept(a,w,state=None):
 state=a[1] if state is None else state
 for s in w:state=a[0][state][s]
 return state in a[2]

def words(n):return [w for k in range(n+1) for w in it.product((0,1),repeat=k)]

def witness(a,b,sa=None,sb=None):
 # Iterative signature refinement associates each pair with shortest word;
 # exhaustive words up to product-size minus1 suffice for distinct states.
 for w in words(len(a[0])*len(b[0])-1):
  if accept(a,w,sa)!=accept(b,w,sb):return w
 return None

def exact(a,b):
 assert type(a) is type(b)
 if type(b) in (list,tuple):
  assert len(a)==len(b)
  for x,y in zip(a,b):exact(x,y)
 else:assert a==b

def check(a):
 old=copy.deepcopy(a);n=len(a[0]);menu=words(min(6,n+1))
 for w in menu:exact(m.dfa_accept_word(a,w),accept(a,w))
 for length in (0,1,2,4,8):exact(m.dfa_language_count(a,length),sum(accept(a,w) for w in it.product((0,1),repeat=length)))
 exact(m.dfa_shortest_accepted_word(a),next((w for w in words(n-1) if accept(a,w)),None))
 trim=m.dfa_reachable_trim(a);small,mapping=m.dfa_minimize_exact(a);comp=m.dfa_complement(a)
 # Independent Moore partition refinement,including reachable-set restriction.
 reach={a[1]}
 while True:
  new=reach|{t for s in reach for t in a[0][s]}
  if new==reach:break
  reach=new
 blocks=[set(s for s in reach if (s in a[2])==flag) for flag in (False,True)];blocks=[b for b in blocks if b]
 while True:
  which={s:i for i,B in enumerate(blocks) for s in B};new=[]
  for B in blocks:
   bins={}
   for s in B:bins.setdefault(tuple(which[t] for t in a[0][s]),set()).add(s)
   new.extend(bins.values())
  if len(new)==len(blocks):break
  blocks=new
 assert len(small[0])==len(blocks)
 assert len(trim[0])==len(reach) and trim[1]==small[1]==0
 for i in range(n):assert (mapping[i] is None)==(i not in reach)
 for B in blocks:assert len({mapping[i] for i in B})==1
 for w in menu:
  assert accept(trim,w)==accept(small,w)==accept(a,w)
  assert accept(comp,w) is not accept(a,w)
 expected=[(i,j,witness(a,a,i,j)) for i in range(n) for j in range(i+1,n)] if n<=2 else None
 if expected is not None:exact(m.dfa_state_distinguishers(a),expected)
 assert a==old
 out=m.dfa_minimize_exact(a);out[1].clear();assert m.dfa_minimize_exact(a)[1]==mapping

def test_exhaustive_small_and_products():
 automata=[]
 for n in (1,2):
  for flat in it.product(range(n),repeat=2*n):
   table=tuple(flat[2*i:2*i+2] for i in range(n))
   for start in range(n):
    for flags in it.product((0,1),repeat=n):
     a=(table,start,tuple(i for i,v in enumerate(flags) if v));check(a);automata.append(a)
 for a,b in it.product(automata[::8],repeat=2):
  exact(m.dfa_equivalence_witness(a,b),witness(a,b))
  intersection=m.dfa_intersection(a,b);union=m.dfa_union(a,b)
  for w in words(4):
   assert accept(intersection,w)==(accept(a,w) and accept(b,w))
   assert accept(union,w)==(accept(a,w) or accept(b,w))
 rng=random.Random(334)
 for _ in range(35):
  a=(tuple(tuple(rng.randrange(4) for _ in range(2)) for _ in range(4)),rng.randrange(4),tuple(i for i in range(4) if rng.randrange(2)));check(a)


def test_validation_scope_guard(monkeypatch):
 A=(((0,0),),0,())
 for name in NAMES:
  def args(a):return (a,()) if name=='dfa_accept_word' else ((a,0) if name=='dfa_language_count' else ((a,A) if name in ('dfa_equivalence_witness','dfa_intersection','dfa_union') else (a,)))
  def fail(a,code):
   old=copy.deepcopy(a)
   with pytest.raises(ValueError) as e:getattr(m,name)(*args(a))
   assert str(e.value)=='P235:'+name+':'+code and a==old
  for a in (None,[],T(A),(),A+(0,)):fail(a,'bad_type:automaton_a')
  for table in (None,[],T(((0,0),))):fail((table,0,()),'bad_type:transitions_a')
  for table in ((),((0,0),)*5):fail((table,0,()),'bad_value:size_a')
  for row in (None,[],T((0,0)),(),(0,),(0,0,0)):fail(((row,),0,()),'bad_type:row_a')
  for i in range(2):
   for bad in (None,True,I(0),0.0,-1,1):
    row=[0,0];row[i]=bad;fail(((tuple(row),),0,()),'bad_type:target_a' if type(bad) is not int else 'bad_value:target_a')
  for bad in (None,True,I(0),0.0,-1,1):fail((A[0],bad,()),'bad_type:start_a' if type(bad) is not int else 'bad_value:start_a')
  for f in (None,[],T(())):fail((A[0],0,f),'bad_type:finals_a')
  fail((A[0],0,(0,0)),'bad_value:finals_length_a')
  for bad in (None,True,I(0),0.0,-1,1):fail((A[0],0,(bad,)),'bad_type:final_a' if type(bad) is not int else 'bad_value:final_a')
  fail((((0,0),(1,1)),0,(0,0)),'bad_value:finals_unique_a')
  fail((A[0],0,(None,None)),'bad_value:finals_length_a')
  fail((((0,0),(0,0)),0,(5,5)),'bad_value:final_a')
  fail(((A[0],None,(None,))),'bad_type:start_a')
  fail((((None,0),),None,None),'bad_type:target_a')
 for name in ('dfa_equivalence_witness','dfa_intersection','dfa_union'):
  with pytest.raises(ValueError) as e:getattr(m,name)(A,None)
  assert str(e.value)=='P235:'+name+':bad_type:automaton_b'
 for name in ('dfa_equivalence_witness','dfa_intersection','dfa_union'):
  with pytest.raises(ValueError) as e:getattr(m,name)(None,None)
  assert str(e.value)=='P235:'+name+':bad_type:automaton_a'
 for w,code in ((None,'bad_type:word'),(T(()),'bad_type:word'),((0,)*9,'bad_value:word_length'),((2,)*9,'bad_value:word_length'),((True,),'bad_type:symbol'),((2,),'bad_value:symbol')):
  with pytest.raises(ValueError) as e:m.dfa_accept_word(A,w)
  assert str(e.value)=='P235:dfa_accept_word:'+code
 for fn in (m.dfa_accept_word,m.dfa_language_count):
  with pytest.raises(ValueError) as e:fn(None,None)
  assert str(e.value)=='P235:'+fn.__name__+':bad_type:automaton_a'
 for length in (None,True,I(0),0.0,-1,9):
  with pytest.raises(ValueError) as e:m.dfa_language_count(A,length)
  assert str(e.value)=='P235:dfa_language_count:'+('bad_type:length' if type(length) is not int else 'bad_value:length')
 assert m.SCOPE=='PARTIAL: exact bounded total binary DFA language algebra and canonical minimization'
 assert m.NOT_CLAIMED==('regex parsing','unbounded scalability','global novelty','production readiness')
 import pathlib,builtins,importlib.util
 source=pathlib.Path(m.__file__).read_text();original=builtins.__import__
 def execute(missing):
  def custom(name,*args,**kwargs):
   if name=='app.modules.instinct_doc.p235_concepts_registry':raise ModuleNotFoundError('blocked',name=missing)
   return original(name,*args,**kwargs)
  ns={'__builtins__':dict(vars(builtins),__import__=custom)};exec(compile(source,'standalone','exec'),ns);return ns
 assert execute('app.modules.instinct_doc.p235_concepts_registry')['dfa_language_count'](A,0)==0
 with pytest.raises(ModuleNotFoundError):execute('other_dependency')
 monkeypatch.setattr(importlib.util,'find_spec',lambda name:object())
 with pytest.raises(ModuleNotFoundError):execute('app.modules.instinct_doc.p235_concepts_registry')

def test_full_word_cap_and_witness_minimality():
 A=(((0,1),(0,1)),0,(1,));B=(((1,0),(1,0)),0,(0,))
 exact(m.dfa_accept_word(A,(1,)*8),True)
 TRI=(((2,1),(0,0),(0,0)),0,(2,))
 exact(m.dfa_reachable_trim(TRI),(((1,2),(0,0),(0,0)),0,(1,)))
 exact(m.dfa_minimize_exact(TRI)[0],(((1,2),(0,0),(0,0)),0,(1,)))
 C=(((1,2),(0,0),(0,0)),0,())
 exact(m.dfa_intersection(C,C),(((1,2),(0,0),(0,0)),0,()))
 exact(m.dfa_union(C,C),(((1,2),(0,0),(0,0)),0,()))
 # Enumerate short prefixes of every reported4state distinguisher to pin
 # witness validity and shortlex minimality without a full length15tree.
 rng=random.Random(109334)
 for _ in range(20):
  a=(tuple(tuple(rng.randrange(4) for _ in range(2)) for _ in range(4)),0,tuple(i for i in range(4) if rng.randrange(2)))
  for i,j,w in m.dfa_state_distinguishers(a):
   if w is not None:
    assert accept(a,w,i)!=accept(a,w,j)
    assert all(accept(a,v,i)==accept(a,v,j) for v in words(len(w)) if (len(v),v)<(len(w),w))
