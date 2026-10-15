import itertools as it,copy,pytest
from app.modules.instinct_doc import p235_concepts_batch373 as m
NAMES=('semigroup_power_orbits','semigroup_minimal_generating_sets','semigroup_green_l_classes','semigroup_green_r_classes','semigroup_two_sided_ideals','semigroup_congruences','semigroup_automorphisms','semigroup_regular_inverses','semigroup_nilpotency_index','semigroup_idempotent_generated_subsemigroup')
class T(tuple):pass
class I(int):pass

def exact(a,b):
 assert type(a) is type(b)
 if type(b) in (list,tuple):
  assert len(a)==len(b)
  for x,y in zip(a,b):exact(x,y)
 else:assert a==b

def associative(t):return all(t[t[a][b]][c]==t[a][t[b][c]] for a,b,c in it.product(range(len(t)),repeat=3))

def words(t,seeds):
 # All left-associated words through length n+1,complete by reachable
 # state path shortening in the right-multiplication transition graph.
 values=set()
 for k in range(1,len(t)+2):
  for word in it.product(seeds,repeat=k):
   v=word[0]
   for a in word[1:]:v=t[v][a]
   values.add(v)
 return values

def oracle(t):
 n=len(t);subsets=[s for k in range(1,n+1) for s in it.combinations(range(n),k)];orbits=[]
 for a in range(n):
  seq=[a]
  for _ in range(2*n+1):seq.append(t[seq[-1]][a])
  stop=next(j for j in range(1,len(seq)) if seq[j] in seq[:j]);split=seq[:stop].index(seq[stop]);orbits.append((tuple(seq[:split]),tuple(seq[split:stop])))
 generating=[s for s in subsets if len(words(t,s))==n]
 minimal=sorted(s for s in generating if not any(set(v)<set(s) for v in generating))
 left=lambda a,b:a==b or any(t[x][b]==a for x in range(n))
 right=lambda a,b:a==b or any(t[b][x]==a for x in range(n))
 def classes(rel):return sorted(set(tuple(b for b in range(n) if rel(a,b) and rel(b,a)) for a in range(n)))
 ideals=[s for s in subsets if all(t[a][b] in s for a,b in it.product(range(n),repeat=2) if a in s or b in s)]
 parts=set()
 for labels in it.product(range(n),repeat=n):
  blocks=tuple(sorted(set(tuple(i for i in range(n) if labels[i]==label) for label in labels)))
  if all(all((labels[a]!=labels[b] or labels[c]!=labels[d] or labels[t[a][c]]==labels[t[b][d]]) for a,b,c,d in it.product(range(n),repeat=4)) for _ in (0,)):parts.add(blocks)
 autos=[p for p in it.permutations(range(n)) if tuple(tuple(p[t[a][b]] for b in range(n)) for a in range(n))==tuple(tuple(t[p[a]][p[b]] for b in range(n)) for a in range(n))]
 inverses=[tuple(b for b in range(n) if t[a][t[b][a]]==a and t[b][t[a][b]]==b) for a in range(n)]
 zero=[z for z in range(n) if all(t[a][b]==z for a,b in it.product(range(n),repeat=2) if a==z or b==z)]
 nil=None
 if zero:
  for k in range(1,n+2):
   values=set()
   for word in it.product(range(n),repeat=k):
    v=word[0]
    for b in word[1:]:v=t[v][b]
    values.add(v)
   if values==set(zero):nil=k;break
 idem=words(t,tuple(a for a in range(n) if t[a][a]==a))
 return [orbits,minimal,classes(left),classes(right),sorted(ideals),sorted(parts),autos,inverses,nil,sorted(idem)]

def check(t):
 for name,value in zip(NAMES,oracle(t)):
  before=copy.deepcopy(t);a=getattr(m,name)(t);exact(a,value);assert t==before
  if type(a) is list:a.clear();exact(getattr(m,name)(t),value)

def test_semigroup_word_partition_and_mutual_reachability_oracles():
 counts=[]
 for n in (1,2,3):
  count=0
  for entries in it.product(range(n),repeat=n*n):
   t=tuple(tuple(entries[i*n:(i+1)*n]) for i in range(n))
   if associative(t):check(t);count+=1
  counts.append(count)
 assert counts==[1,8,113]
 # Four-element cyclic group,left/right zero bands,rectangular band,
 # nilpotent truncated addition,and Boolean meet.
 tables=[tuple(tuple((a+b)%4 for b in range(4)) for a in range(4)),tuple(tuple(a for b in range(4)) for a in range(4)),tuple(tuple(b for b in range(4)) for a in range(4)),tuple(tuple(2*(a//2)+b%2 for b in range(4)) for a in range(4)),tuple(tuple(min(3,a+b+1) for b in range(4)) for a in range(4)),tuple(tuple(a&b for b in range(4)) for a in range(4))]
 for t in tables:check(t)
 # Inclusion-minimal sizes need not coincide: cyclic C6 would exceed cap;
 # C4 has generators(1),(3),not generator sets containing either.
 exact(m.semigroup_minimal_generating_sets(tables[0]),[(1,),(3,)])
 exact(m.semigroup_nilpotency_index(tables[4]),4)
 exact(m.semigroup_green_l_classes(tables[1]),[(0,1,2,3)])
 exact(m.semigroup_green_r_classes(tables[1]),[(0,),(1,),(2,),(3,)])


def test_validation_fallback_and_types(monkeypatch):
 for name in NAMES:
  def fail(t,code):
   before=copy.deepcopy(t)
   with pytest.raises(ValueError) as e:getattr(m,name)(t)
   assert str(e.value)=='P235:'+name+':'+code and t==before
  for t in (None,[],T(((0,),))):fail(t,'bad_type:table')
  fail((),'bad_value:size');fail(((0,)*5,)*5,'bad_value:size')
  for r in (None,[],T((0,))):fail((r,),'bad_type:row')
  fail(((),),'bad_value:row_length');fail(((0,0),),'bad_value:row_length')
  for pos in range(2):
   for v in (None,True,I(0),0.0,-1,2):
    row=[0,1];row[pos]=v;fail((tuple(row),(0,1)),'bad_type:entry' if type(v) is not int else 'bad_value:entry')
  fail(((2,True),(0,1)),'bad_type:entry')
  fail(((2,0),None),'bad_value:entry')
  fail(((0,1),(0,0)),'bad_value:associativity')
 assert m.SCOPE=='PARTIAL: exact bounded finite semigroup structure,not free-group reduction or group-presentation solving'
 assert m.NOT_CLAIMED==('infinite semigroups','group presentation solving','global novelty','production readiness')
 import pathlib,builtins,importlib.util
 source=pathlib.Path(m.__file__).read_text();original=builtins.__import__
 def execute(missing):
  def custom(name,*args,**kwargs):
   if name=='app.modules.instinct_doc.p235_concepts_registry':raise ModuleNotFoundError('blocked',name=missing)
   return original(name,*args,**kwargs)
  ns={'__builtins__':dict(vars(builtins),__import__=custom)};exec(compile(source,'standalone','exec'),ns);return ns
 assert execute('app.modules.instinct_doc.p235_concepts_registry')['semigroup_nilpotency_index'](((0,),))==1
 with pytest.raises(ModuleNotFoundError):execute('other_dependency')
 monkeypatch.setattr(importlib.util,'find_spec',lambda name:object())
 with pytest.raises(ModuleNotFoundError):execute('app.modules.instinct_doc.p235_concepts_registry')

@pytest.fixture(autouse=True)
def finite_closure_work(monkeypatch):
 import sys
 guarded=('semigroup_green_r_classes','semigroup_minimal_generating_sets','semigroup_idempotent_generated_subsemigroup')
 for name in guarded:
  original=getattr(m,name)
  def wrap(t,original=original,name=name):
   count=0
   def trace(frame,event,arg):
    nonlocal count
    if frame.f_code.co_name!=name:return None
    if event=='line':
     count+=1
     if count>2000:raise AssertionError('finite semigroup closure did not terminate')
    return trace
   previous=sys.gettrace();sys.settrace(trace)
   try:return original(t)
   finally:sys.settrace(previous)
  monkeypatch.setattr(m,name,wrap)
