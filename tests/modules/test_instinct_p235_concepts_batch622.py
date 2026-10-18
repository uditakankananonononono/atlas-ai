import itertools as it,random,pytest
from app.modules.instinct_doc import p235_concepts_batch622 as m

def allowed(c,i,j,a,b):
 table={(x,y):set(p) for x,y,p in c}
 return ((a,b) in table[i,j]) if i<j and (i,j) in table else ((b,a) in table[j,i]) if j<i and (j,i) in table else True

def ac(d,c):
 while True:
  new=tuple(tuple(a for a in r if all(any(allowed(c,i,j,a,b) for b in d[j]) for j in range(len(d)) if j!=i)) for i,r in enumerate(d))
  if new==d:return d
  d=new

def trace_oracle(d,c):
 t=[]
 while True:
  candidates=sorted((i,j,a) for i in range(len(d)) for j in range(len(d)) if i!=j for a in d[i] if not any(allowed(c,i,j,a,b) for b in d[j]))
  if not candidates:return d,tuple(t)
  i,j,a=candidates[0];t.append((i,j,a));d=d[:i]+(tuple(v for v in d[i] if v!=a),)+d[i+1:]

def path_oracle(d,c):
 n=len(d);rels={(i,j):set((a,b) for a in d[i] for b in d[j] if (a==b if i==j else allowed(c,i,j,a,b))) for i in range(n) for j in range(n)}
 while True:
  new={key:set(value) for key,value in rels.items()}
  for i,j in rels:
   for k in range(n):
    composed={(a,b) for a,t in rels[i,k] for u,b in rels[k,j] if t==u}
    new[i,j]&=composed
  if new==rels:break
  rels=new
 return tuple(tuple(a for a in r if (a,a) in rels[i,i]) for i,r in enumerate(d)),tuple((i,j,tuple(sorted(rels[i,j]))) for i in range(n) for j in range(i+1,n))

def singleton(d,c):
 d=ac(d,c)
 while True:
  new=tuple(tuple(a for a in r if all(ac(d[:i]+((a,),)+d[i+1:],c))) for i,r in enumerate(d))
  new=ac(new,c)
  if new==d:return d
  d=new

def instances():
 r=random.Random(622)
 yield ((0,1),)*3,tuple((i,j,((0,1),(1,0))) for i,j in ((0,1),(0,2),(1,2)))
 yield ((0,1),(0,1)),((0,1,()),)
 yield ((),),()
 yield ((0,1,2,3),),()
 yield ((0,1,2,3),)*4,()
 for n in range(1,5):
  for _ in range(35):
   d=tuple(tuple(a for a in range(3) if r.randrange(4)) for _ in range(n))
   c=tuple((i,j,tuple((a,b) for a in range(3) for b in range(3) if r.randrange(2))) for i in range(n) for j in range(i+1,n) if r.randrange(2))
   yield d,c

def test_independent_consistency_oracles():
 for d,c in instances():
  original=repr((d,c));closed=ac(d,c);tr=trace_oracle(d,c)
  assert m.csp_arc_close(d,c)==closed
  assert m.csp_arc_trace(d,c)==tr
  assert tr[0]==closed
  assert m.csp_verify_arc_trace(d,c,tr[1])
  assert m.csp_is_arc_consistent(d,c)==(closed==d)
  assert m.csp_path_close(d,c)==path_oracle(d,c)
  assert m.csp_singleton_close(d,c)==singleton(d,c)
  for i in range(len(d)):
   for j in range(len(d)):
    if i==j:continue
    gone=tuple(a for a in d[i] if not any(allowed(c,i,j,a,b) for b in d[j]))
    assert m.csp_revise(d,c,i,j)==(d[:i]+(tuple(a for a in d[i] if a not in gone),)+d[i+1:],gone)
    for a in d[i]:assert m.csp_supports(d,c,i,j,a)==tuple(b for b in d[j] if allowed(c,i,j,a,b))
  assert repr((d,c))==original


def test_assignments_and_solution_preservation():
 for d,c in instances():
  closed=m.csp_arc_close(d,c);sd=m.csp_singleton_close(d,c);pd,pc=m.csp_path_close(d,c)
  for values in it.product(range(3),repeat=len(d)):
   bad=tuple((-1,i) for i,r in enumerate(d) if values[i] not in r)+tuple((i,j) for i,j,p in c if (values[i],values[j]) not in p)
   assert m.csp_violations(d,c,values)==bad
   assert m.csp_assignment_ok(d,c,values)==(not bad)
   if not bad:
    assert all(v in row for v,row in zip(values,closed))
    assert all(v in row for v,row in zip(values,sd))
    assert all(v in row for v,row in zip(values,pd))
    assert all((values[i],values[j]) in p for i,j,p in pc)


def test_trace_tampering_and_local_incompleteness():
 d=((0,1),)*3;c=tuple((i,j,((0,1),(1,0))) for i,j in ((0,1),(0,2),(1,2)))
 assert m.csp_is_arc_consistent(d,c)
 assert m.csp_singleton_close(d,c)==((),(),())
 assert m.csp_path_close(d,c)[0]==((),(),())
 d=((0,1),(0,1));c=((0,1,()),);closed,t=m.csp_arc_trace(d,c)
 assert len(t)==4
 for wrong in (t[:-1],t+((0,1,0),),tuple(reversed(t)),((0,1,1),)+t[1:]):assert not m.csp_verify_arc_trace(d,c,wrong)
 # Universal missing relation still propagates an empty domain.
 assert m.csp_arc_close(((),(0,1)),())==((),())
 # Unsupported pairs outside domains ignored.
 assert m.csp_revise(((0,),(1,)),((0,1,((0,1),(2,3))),),0,1)==(((0,),(1,)),())


def test_validation_every_api():
 class T(tuple):pass
 class I(int):pass
 d=((0,1),(0,1));c=()
 bad_d=[[],T(d),(),((),)*5,([0],),(tuple(range(5)),),((True,),),((I(0),),),((0.0,),),((-1,),),((4,),),((1,0),),((0,0),)]
 bad_c=[[],T(()),((0,1,()),)*7,([],),((0,1),),((0,1,[]),),((0,1,((0,),)),),((0,1,([0,1],)),),((True,1,()),),((0,I(1),()),),((0,1,((False,0),)),),((0,1,((0,0.0),)),),((-1,1,()),),((1,0,()),),((0,2,()),),((0,1,((-1,0),)),),((0,1,((0,4),)),),((0,1,((1,1),(0,0))),),((0,1,((0,0),(0,0))),),((0,1,()),(0,1,()))]
 calls=[(m.csp_supports,(0,1,0)),(m.csp_revise,(0,1)),(m.csp_arc_close,()),(m.csp_arc_trace,()),(m.csp_verify_arc_trace,((),)),(m.csp_is_arc_consistent,()),(m.csp_path_close,()),(m.csp_singleton_close,()),(m.csp_violations,((0,0),)),(m.csp_assignment_ok,((0,0),))]
 for fn,tail in calls:
  for bad in bad_d:
   with pytest.raises(ValueError):fn(bad,c,*tail)
  for bad in bad_c:
   with pytest.raises(ValueError):fn(d,bad,*tail)
 for fn in (m.csp_supports,m.csp_revise):
  for a,b in ((-1,1),(2,1),(0,-1),(0,2),(0,0),(True,1),(0,I(1))):
   with pytest.raises(ValueError):fn(d,c,a,b,*((0,) if fn==m.csp_supports else ()))
 for v in (-1,4,True,I(0),0.0):
  with pytest.raises(ValueError):m.csp_supports(d,c,0,1,v)
 with pytest.raises(ValueError):m.csp_supports(((0,),(0,)),(),0,1,1)
 for tr in ([],T(()),((0,1,0),)*17,([],),((0,1),),((0,True,0),),((-1,1,0),),((0,2,0),),((0,0,0),),((0,1,4),)):
  with pytest.raises(ValueError):m.csp_verify_arc_trace(d,c,tr)
 for fn in (m.csp_violations,m.csp_assignment_ok):
  for v in ([],T((0,0)),(),(0,),(0,0,0),(True,0),(I(0),0),(-1,0),(4,0)):
   with pytest.raises(ValueError):fn(d,c,v)
 full=((0,1,2,3),)*4;rel=tuple(it.product(range(4),repeat=2));cons=tuple((i,j,rel) for i in range(4) for j in range(i+1,4))
 assert m.csp_arc_close(full,cons)==full
 with pytest.raises(ValueError):m.csp_arc_close(full,((0,1,rel+((3,3),)),))
 with pytest.raises(ValueError):m.csp_arc_close(full,((1,2,()),(0,1,())))
 assert m.csp_supports(full,cons,3,2,3)==(0,1,2,3)
 assert m.csp_assignment_ok(full,cons,(3,3,3,3))
 assert m.SCOPE.startswith('PARTIAL:') and 'global novelty' in m.NOT_CLAIMED


def test_validation_order():
 with pytest.raises(ValueError,match='bad_type:constraints'):m.csp_arc_close((),[])
 with pytest.raises(ValueError,match='bad_shape:constraints'):m.csp_arc_close(((True,),),((0,1),))
 with pytest.raises(ValueError,match='bad_type:pairs'):m.csp_arc_close(((4,),),((0,1,((True,0),)),))
 with pytest.raises(ValueError,match='bad_value:i'):m.csp_revise(((0,),(0,)),(),2,True)
 with pytest.raises(ValueError,match='bad_type:values'):m.csp_assignment_ok(((0,),(0,)),(),(4,True))


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
    with pytest.raises(ValueError, match='P235:csp_arc_close:bad_type:domains'):
        fallback['csp_arc_close']([],())
    with pytest.raises(ModuleNotFoundError): load('dependency_inside_registry', False)
    with pytest.raises(ModuleNotFoundError): load(target, True)

@pytest.fixture(autouse=True)
def bounded_runtime():
 import signal
 def alarm(*_):raise AssertionError('kernel runtime limit')
 old=signal.signal(signal.SIGALRM,alarm);signal.alarm(3)
 try:yield
 finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)

def test_singleton_shaving_retains_supported_solution():
 pairs=((0,1),(1,0),(2,2))
 c=tuple((i,j,pairs) for i,j in ((0,1),(0,2),(1,2)))
 d=((0,1,2),)*3
 assert m.csp_singleton_close(d,c)==((2,),)*3
 assert m.csp_path_close(d,c)[0]==((2,),)*3
 c=tuple((i,j,((0,1),(1,0))) for i,j in ((1,2),(1,3),(2,3)))
 assert m.csp_singleton_close(((0,),)+((0,1),)*3,c)==((),)*4


def test_trace_envelope_and_self_constraint():
 d=((0,1,2,3),)*4;c=((0,1,()),)
 final,trace=m.csp_arc_trace(d,c)
 assert len(trace)==16 and final==((),)*4
 assert m.csp_verify_arc_trace(d,c,trace)
 assert not m.csp_verify_arc_trace(d,c,((0,1,3),))
 for t in (((4,1,0),),((0,4,0),)):
  with pytest.raises(ValueError,match='bad_value:trace'):m.csp_verify_arc_trace(d,c,t)
 with pytest.raises(ValueError,match='bad_value:indices'):m.csp_arc_close(((0,),),((0,0,((0,0),)),))
 # Caps are checked before entry ranges and uniqueness, not just eventually.
 with pytest.raises(ValueError,match='bad_shape:domains'):m.csp_arc_close(((0,1,2,3,4),),())
 pairs=tuple(it.product(range(4),repeat=2))+((3,3),)
 with pytest.raises(ValueError,match='bad_shape:pairs'):m.csp_arc_close(d,((0,1,pairs),))
