import itertools as it,random,pytest
from app.modules.instinct_doc import p235_concepts_batch641 as m

def relation_oracle(terms,eq):
 n=len(terms);rel={(i,i) for i in range(n)}|set(eq)|{(b,a) for a,b in eq}
 while True:
  new=rel|{(a,c) for a,b in rel for bb,c in rel if b==bb}
  for i,(s,args) in enumerate(terms):
   for j,(t,other) in enumerate(terms):
    if s==t and all((a,b) in rel for a,b in zip(args,other)):new.add((i,j))
  if new==rel:return tuple(min(j for j in range(n) if (i,j) in rel) for i in range(n))
  rel=new

def models(terms):
 # All set partitions as restricted-growth strings, independent model oracle.
 def grow(prefix):
  if len(prefix)==len(terms):yield prefix;return
  for v in range(max(prefix,default=-1)+2):yield from grow(prefix+(v,))
 for labels in grow(()):
  if all(s!=t or tuple(labels[a] for a in args)!=tuple(labels[a] for a in other) or labels[i]==labels[j] for i,(s,args) in enumerate(terms) for j,(t,other) in enumerate(terms)):yield labels

def cases():
 r=random.Random(641)
 yield ((0,()),(1,()),(2,(0,)),(2,(1,)),(3,(2,)),(3,(3,))),((0,1),)
 yield ((0,()),(0,()),(1,(0,0)),(1,(1,1))),()
 yield ((0,()),),((0,0),)
 for n in range(1,13):
  for _ in range(10):
   terms=[];arities={0:0,1:0,2:1,3:2}
   for i in range(n):
    s=r.randrange(4) if i else r.randrange(2);terms.append((s,tuple(r.randrange(i) for _ in range(arities[s]))))
   eq=tuple((r.randrange(n),r.randrange(n)) for _ in range(r.randrange(8)))
   yield tuple(terms),eq


def test_relation_closure_and_all_public_queries():
 r=random.Random(642)
 for terms,eq in cases():
  before=repr((terms,eq));d=relation_oracle(terms,eq);n=len(terms)
  assert m.ground_classes(terms,eq)==d
  pairs=tuple((i,j) for i in range(n) for j in range(i+1,n) if d[i]==d[j])
  assert m.ground_entailed_pairs(terms,eq)==pairs
  for i,j in it.product(range(n),repeat=2):assert m.ground_equal(terms,eq,i,j)==(d[i]==d[j])
  diseq=tuple((r.randrange(n),r.randrange(n)) for _ in range(6))
  conflicts=tuple(k for k,(a,b) in enumerate(diseq) if d[a]==d[b])
  assert m.ground_conflicts(terms,eq,diseq)==conflicts
  assert m.ground_consistent(terms,eq,diseq)==(not conflicts)
  got,rows=m.ground_model(terms,eq);assert got==d
  assert rows==tuple(sorted(set((s,tuple(d[a] for a in args),d[i]) for i,(s,args) in enumerate(terms))))
  assert m.ground_verify_model(terms,eq,(),d)
  assert m.ground_verify_model(terms,eq,diseq,d)==(not conflicts)
  red=tuple(k for k,(a,b) in enumerate(eq) if (lambda q:q[a]==q[b])(relation_oracle(terms,eq[:k]+eq[k+1:])))
  assert m.ground_redundant_equalities(terms,eq)==red
  final,trace=m.ground_merge_trace(terms,eq)
  assert final==d and len(trace)<=n-1
  assert m.ground_verify_trace(terms,eq,trace)
  if trace:
   assert not m.ground_verify_trace(terms,eq,trace[:-1])
   assert not m.ground_verify_trace(terms,eq,trace+trace[:1]) if len(trace)<11 else True
  assert repr((terms,eq))==before


def test_models_exhaustive_partitions_and_least_model():
 fixtures=(((0,()),(1,()),(2,(0,)),(2,(1,))),((0,()),(0,()),(1,(0,0)),(1,(1,1))),((0,()),(1,()),(2,(0,1)),(2,(1,0))))
 for terms in fixtures:
  universe=tuple(it.product(range(len(terms)),repeat=2))
  for eq in ((),((0,1),),((2,3),),((0,1),(2,3))):
   good=[labels for labels in models(terms) if all(labels[a]==labels[b] for a,b in eq)]
   expected=tuple(min(j for j in range(len(terms)) if all(d[i]==d[j] for d in good)) for i in range(len(terms)))
   assert m.ground_classes(terms,eq)==expected
   for labels in it.product(range(2),repeat=len(terms)):
    valid=all(labels[a]==labels[b] for a,b in eq) and all(s!=t or tuple(labels[a] for a in args)!=tuple(labels[a] for a in other) or labels[i]==labels[j] for i,(s,args) in enumerate(terms) for j,(t,other) in enumerate(terms))
    assert m.ground_verify_model(terms,eq,(),labels)==valid


def test_trace_fixed_redundancy_and_caps():
 terms=((0,()),(1,()),(2,(0,)),(2,(1,)),(3,(2,)),(3,(3,)))
 eq=((1,0),(0,1))
 assert m.ground_merge_trace(terms,eq)==((0,0,2,2,4,4),((0,1,0),(1,2,3),(1,4,5)))
 assert m.ground_redundant_equalities(terms,eq)==(0,1)
 assert m.ground_redundant_equalities(terms,((0,1),))==()
 assert not m.ground_verify_trace(terms,eq,((0,0,1),(1,2,3),(1,4,5)))
 assert not m.ground_verify_model(terms,(),(),(0,1,2,2,3,4))
 assert m.ground_verify_model(terms,(),(),(11,)*6)
 full=((0,()),)*12;d,t=m.ground_merge_trace(full,())
 assert d==(0,)*12 and len(t)==11 and m.ground_verify_trace(full,(),t)
 assert m.ground_classes(full,((0,11),)*16)==(0,)*12
 assert m.ground_classes(((7,()),),())==(0,)


def test_phase_order_exact_types_and_hostile_subclasses():
 class T(tuple):
  def __iter__(self):raise AssertionError('hostile tuple iteration')
  def __len__(self):raise AssertionError('hostile tuple length')
 class I(int):
  def __le__(self,other):raise AssertionError('hostile int comparison')
 terms=((0,()),(1,()));eq=()
 badterms=([],T(terms),(),terms*7,([0,()],),((0,[]),),((True,()),),((I(0),()),),((0,T(())),),((0,(True,)),),((0,(I(0),)),),((0,),),((0,(),1),),((0,(0,0,0)),),((-1,()),),((8,()),),((0,(0,)),),((0,()),(0,(0,))))
 badpairs=([],T(()),((0,1),)*17,([0,1],),((0,),),((0,1,1),),((True,0),),((I(0),0),),((-1,0),),((0,2),))
 calls=((m.ground_classes,()),(m.ground_equal,(0,1)),(m.ground_entailed_pairs,()),(m.ground_conflicts,((),)),(m.ground_consistent,((),)),(m.ground_model,()),(m.ground_verify_model,((),(0,1))),(m.ground_merge_trace,()),(m.ground_verify_trace,((),)),(m.ground_redundant_equalities,()))
 for fn,tail in calls:
  for v in badterms:
   with pytest.raises(ValueError):fn(v,eq,*tail)
  for v in badpairs:
   with pytest.raises(ValueError):fn(terms,v,*tail)
 for fn in (m.ground_conflicts,m.ground_consistent):
  for v in badpairs:
   with pytest.raises(ValueError):fn(terms,eq,v)
 for v in badpairs:
  with pytest.raises(ValueError):m.ground_verify_model(terms,eq,v,(0,1))
 for labels in ([],T((0,1)),(0,),(0,1,2),(True,0),(I(0),0),(-1,0),(12,0)):
  with pytest.raises(ValueError):m.ground_verify_model(terms,eq,(),labels)
 for trace in ([],T(()),((0,0,1),)*12,([0,0,1],),((0,0),),((True,0,1),),((0,I(0),1),),((-1,0,1),),((2,0,1),),((0,-1,1),),((0,2,1),),((0,0,2),)):
  with pytest.raises(ValueError):m.ground_verify_trace(terms,eq,trace)
 for left,right in ((-1,0),(2,0),(0,-1),(0,2),(True,0),(0,I(0))):
  with pytest.raises(ValueError):m.ground_equal(terms,eq,left,right)
 with pytest.raises(ValueError,match='bad_type:equalities'):m.ground_classes((),[])
 with pytest.raises(ValueError,match='bad_type:terms'):m.ground_classes(T(terms),[])
 with pytest.raises(ValueError,match='bad_type:labels'):m.ground_verify_model((),(),(),(True,))
 with pytest.raises(ValueError,match='bad_shape:labels'):m.ground_verify_model(((8,()),),(),(),())
 with pytest.raises(ValueError,match='bad_type:right'):m.ground_equal((),(),-1,True)
 assert m.SCOPE.startswith('PARTIAL:') and 'global novelty' in m.NOT_CLAIMED


def test_registry_fallback_does_not_mask_broken_registry():
    import builtins, pathlib, types
    source=pathlib.Path(m.__file__).read_text()
    real_import=builtins.__import__
    target='app.modules.instinct_doc.p235_concepts_registry'
    def load(error_name, present):
        def importing(name, *args, **kwargs):
            if name == target:
                raise ModuleNotFoundError('injected import failure', name=error_name)
            if name == 'importlib.util':
                return types.SimpleNamespace(find_spec=lambda name: object() if present else None)
            return real_import(name, *args, **kwargs)
        namespace={'__builtins__': dict(vars(builtins), __import__=importing)}
        exec(compile(source, '<fallback-test>', 'exec'), namespace)
        return namespace
    fallback=load(target, False)
    with pytest.raises(ValueError, match='P235:ground_classes:bad_type:terms'):
        fallback['ground_classes']([],())
    with pytest.raises(ModuleNotFoundError): load('dependency_inside_registry', False)
    with pytest.raises(ModuleNotFoundError): load(target, True)

@pytest.fixture(autouse=True)
def bounded_runtime():
 import signal
 def alarm(*_):raise AssertionError('kernel runtime limit')
 old=signal.signal(signal.SIGALRM,alarm);signal.alarm(3)
 try:yield
 finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)

def test_max_arity_shape_and_each_symbol_boundary():
 terms=((0,()),(7,(0,0)))
 assert m.ground_classes(terms,())==(0,1)
 with pytest.raises(ValueError,match='bad_shape:terms'):m.ground_classes(((0,()),(7,(0,0,0))),())
 # Same arity symbol codes remain distinct and congruence is one-way.
 terms=((0,()),(1,()),(6,(0,)),(7,(0,)),(6,(1,)),(7,(1,)))
 assert m.ground_classes(terms,((2,4),))==(0,1,2,3,2,5)
 assert m.ground_classes(terms,((0,1),))==(0,0,2,3,2,3)
