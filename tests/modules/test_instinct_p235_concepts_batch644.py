import itertools as it,random,pytest
from app.modules.instinct_doc import p235_concepts_batch644 as m

def evaluate(p,co,x):return sum(c*pow(x,i,p) for i,c in enumerate(co))%p

def brute_degree(p,shares):
 for degree in range(len(shares)):
  for co in it.product(range(p),repeat=degree+1):
   if all(evaluate(p,co,x)==y for x,y in shares):return degree
 raise AssertionError('no interpolant')

def test_shares_and_reconstruction_independent_power_sums():
 r=random.Random(644)
 for p in (2,3,5,7,11,251):
  for degree in range(min(8,p-1)):
   for _ in range(8):
    co=tuple(r.randrange(p) for _ in range(degree+1));xs=tuple(range(1,min(17,p)));shares=m.sharing_share(p,co,xs)
    assert shares==tuple((x,evaluate(p,co,x)) for x in xs)
    expected=max((i for i,c in enumerate(co) if c),default=0)
    assert m.sharing_degree_bound(p,shares)==expected
    assert m.sharing_verify_consistency(p,shares,degree)
    assert m.sharing_reconstruct(p,shares,degree)==co[0]
    shuffled=list(shares);r.shuffle(shuffled)
    assert m.sharing_reconstruct(p,tuple(shuffled),degree)==co[0]
    if len(shares)>=degree+1:
     subset=shares[-(degree+1):]
     assert m.sharing_reconstruct(p,subset,degree)==co[0]
 for co in ((0,)*8,(250,)*8):
  xs=tuple(range(1,17));shares=m.sharing_share(251,co,xs)
  assert m.sharing_reconstruct(251,shares,7)==co[0]
 assert m.sharing_share(251,(250,),(250,))==((250,250),)
 assert m.sharing_share(2,(0,),(1,))==((1,0),)


def test_exhaustive_small_field_degree_oracle():
 for p in (2,3,5):
  for count in range(1,min(4,p)):
   xs=tuple(range(1,count+1))
   for ys in it.product(range(p),repeat=count):
    shares=tuple(zip(xs,ys));degree=brute_degree(p,shares)
    assert m.sharing_degree_bound(p,shares)==degree
    for bound in range(4):
     assert m.sharing_verify_consistency(p,shares,bound)==(degree<=bound)
     if count<bound+1:
      with pytest.raises(ValueError,match='insufficient_shares'):m.sharing_reconstruct(p,shares,bound)
     elif degree>bound:
      with pytest.raises(ValueError,match='inconsistent_shares'):m.sharing_reconstruct(p,shares,bound)
     else:
      # Enumerate admitted polynomial, including its constant, rather than interpolation.
      candidates=[co for co in it.product(range(p),repeat=bound+1) if all(evaluate(p,co,x)==y for x,y in shares)]
      assert len(candidates)==1
      assert m.sharing_reconstruct(p,shares,bound)==candidates[0][0]
 # Verify admits sparse evidence but reconstruction must still refuse.
 assert m.sharing_verify_consistency(251,((250,123),),7)
 with pytest.raises(ValueError,match='insufficient_shares'):m.sharing_reconstruct(251,((250,123),),7)


def test_validation_phase_order_hostile_and_caps():
 class T(tuple):
  def __iter__(self):raise AssertionError('hostile tuple iter')
  def __len__(self):raise AssertionError('hostile tuple len')
 class I(int):
  def __le__(self,o):raise AssertionError('hostile int comparison')
 good=((1,0),)
 for p in (True,I(5),5.0,1,252,4,9,121,169,247):
  for fn,tail in ((m.sharing_share,((0,),(1,))),(m.sharing_reconstruct,(good,0)),(m.sharing_verify_consistency,(good,0)),(m.sharing_degree_bound,(good,))):
   with pytest.raises(ValueError):fn(p,*tail)
 badco=([],T((0,)),(),(0,)*9,(True,),(I(0),),(0.0,),(-1,),(251,))
 for co in badco:
  with pytest.raises(ValueError):m.sharing_share(251,co,(1,))
 badxs=([],T((1,)),(),(1,)*17,(True,),(I(1),),(1.0,),(0,),(-1,),(251,),(1,1))
 for xs in badxs:
  with pytest.raises(ValueError):m.sharing_share(251,(0,),xs)
 badshares=([],T(good),(),good*17,([1,0],),(T((1,0)),),((1,),),((1,0,0),),((True,0),),((I(1),0),),((1,I(0)),),((1,0.0),),((0,0),),((251,0),),((1,-1),),((1,251),),good*2)
 for shares in badshares:
  for fn,tail in ((m.sharing_reconstruct,(0,)),(m.sharing_verify_consistency,(0,)),(m.sharing_degree_bound,())):
   with pytest.raises(ValueError):fn(251,shares,*tail)
 for d in (-1,8,True,I(0),0.0):
  for fn in (m.sharing_reconstruct,m.sharing_verify_consistency):
   with pytest.raises(ValueError):fn(251,good,d)
 with pytest.raises(ValueError,match='bad_type:abscissas'):m.sharing_share(4,(),[])
 with pytest.raises(ValueError,match='bad_type:prime'):m.sharing_share(True,[],[])
 with pytest.raises(ValueError,match='bad_type:degree'):m.sharing_reconstruct(4,(),True)
 with pytest.raises(ValueError,match='bad_shape:shares'):m.sharing_reconstruct(4,(),-1)
 with pytest.raises(ValueError,match='bad_value:prime'):m.sharing_share(4,(-1,),(0,))
 with pytest.raises(ValueError,match='bad_value:coefficients'):m.sharing_share(5,(-1,),(0,))
 with pytest.raises(ValueError,match='bad_type:shares'):m.sharing_degree_bound(4,((0,True),))
 assert m.sharing_share(251,(0,)*8,tuple(range(1,17)))==tuple((x,0) for x in range(1,17))
 assert m.SCOPE.startswith('PARTIAL:') and 'security' in m.NOT_CLAIMED


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
    with pytest.raises(ValueError, match='P235:sharing_share:bad_type:coefficients'):
        fallback['sharing_share'](5,[],(1,))
    with pytest.raises(ModuleNotFoundError): load('dependency_inside_registry', False)
    with pytest.raises(ModuleNotFoundError): load(target, True)

@pytest.fixture(autouse=True)
def bounded_runtime():
 import signal
 def alarm(*_):raise AssertionError('kernel runtime limit')
 old=signal.signal(signal.SIGALRM,alarm);signal.alarm(3)
 try:yield
 finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)

def test_unique_seventeenth_entry_hits_shape_cap():
 with pytest.raises(ValueError,match='bad_shape:abscissas'):m.sharing_share(251,(0,),tuple(range(1,18)))
 shares=tuple((x,0) for x in range(1,18))
 for fn,tail in ((m.sharing_reconstruct,(0,)),(m.sharing_verify_consistency,(0,)),(m.sharing_degree_bound,())):
  with pytest.raises(ValueError,match='bad_shape:shares'):fn(251,shares,*tail)
 assert m.sharing_degree_bound(251,shares[:16])==0
