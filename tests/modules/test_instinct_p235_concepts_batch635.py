from fractions import Fraction as F
import random,itertools as it,pytest
from app.modules.instinct_doc import p235_concepts_batch635 as m
K=((1,0,7,16),(-1,1,3,16),(0,1,5,16),(1,1,1,16))
def pair(v):return v.numerator,v.denominator

def oracle(image,kernel,snake):
 h,w=len(image),len(image[0]);positions=[(x,y) for y in range(h) for x in (list(range(w))[::-1] if snake and y%2 else range(w))]
 values={p:F(image[p[1]][p[0]]) for p in positions};outputs={};records=[];escape=F(0)
 for index,(x,y) in enumerate(positions):
  value=values[x,y];b=1 if value*2>=255 else 0;e=value-255*b;outputs[x,y]=b;records.append((x,y,pair(value),b,pair(e)));sent=F(0)
  for dx,dy,a,den in kernel:
   dest=(x-dx if snake and y%2 else x+dx,y+dy)
   if dest in positions[index+1:]:values[dest]+=e*F(a,den);sent+=e*F(a,den)
  escape+=e-sent
 return tuple(tuple(outputs[x,y] for x in range(w)) for y in range(h)),tuple(records),pair(escape)

def test_bayer_by_bit_digits_and_ordered():
 for order in range(4):
  side=2**order;table=m.bayer_screen(order)
  expected=tuple(tuple(sum(((0,2),(3,1))[(y>>k)&1][(x>>k)&1]*4**(order-1-k) for k in range(order)) for x in range(side)) for y in range(side))
  assert table==expected
  assert sorted(v for row in table for v in row)==list(range(side*side))
  image=tuple(tuple((17*y+31*x)%256 for x in range(8)) for y in range(8))
  got=m.ordered_halftone(image,table)
  assert got==tuple(tuple(int(F(v,255)>=F(2*table[y%side][x%side]+1,2*side*side)) for x,v in enumerate(row)) for y,row in enumerate(image))
 for v in (0,127,128,255):assert m.ordered_halftone(((v,),),((0,),))==((int(v>=128),),)
 assert m.bayer_screen(1)==((0,2),(3,1))


def test_diffusion_independent_schedule_and_conservation():
 r=random.Random(635)
 kernels=(K,((1,0,1,1),),((0,1,1,2),),((-2,1,1,4),(2,0,1,4),(0,2,1,4)),((2,2,1,16),))
 for h,w in ((1,1),(1,8),(8,1),(3,4),(8,8)):
  for _ in range(3):
   image=tuple(tuple(r.randrange(256) for _ in range(w)) for _ in range(h));original=repr(image)
   for kernel in kernels:
    for snake in (False,True):
     expected=oracle(image,kernel,snake);got=m.diffusion_trace(image,kernel,snake)
     assert got==expected
     assert m.diffusion_halftone(image,kernel,snake)==expected[0]
     assert m.verify_diffusion_trace(image,kernel,snake,got[1])
     assert F(*got[2])==sum(v for row in image for v in row)-255*sum(v for row in got[0] for v in row)
   assert repr(image)==original
 image=((128,127),(255,0));bits,trace,_=m.diffusion_trace(image,K,True)
 assert not m.verify_diffusion_trace(image,K,True,trace[:-1])
 assert not m.verify_diffusion_trace(image,K,True,tuple(reversed(trace)))
 row=trace[0];bad=(row[0],row[1],row[2],1-row[3],row[4])
 assert not m.verify_diffusion_trace(image,K,True,(bad,)+trace[1:])


def test_threshold_errors_and_block_coverage():
 image=((0,127,128,255),(40,100,200,240),(1,2,3,4))
 for threshold in (0,1,127,128,254,255):
  bits=m.threshold_halftone(image,threshold)
  assert bits==tuple(tuple(int(v>=threshold) for v in row) for row in image)
  errors=m.halftone_pixel_errors(image,bits)
  assert errors==tuple(tuple(v-255*bits[y][x] for x,v in enumerate(row)) for y,row in enumerate(image))
  assert m.halftone_total_error(image,bits)==sum(map(sum,errors))
  assert m.binary_expand(bits)==tuple(tuple(255*b for b in row) for row in bits)
  for width,height in it.product(range(1,9),repeat=2):
   got=m.binary_block_coverage(bits,width,height);expected=[]
   for yy in range(0,len(bits),height):
    row=[]
    for xx in range(0,len(bits[0]),width):
     cells=[b for y,r in enumerate(bits) for x,b in enumerate(r) if yy<=y<yy+height and xx<=x<xx+width];row.append(pair(F(sum(cells),len(cells))))
    expected.append(tuple(row))
   assert got==tuple(expected)
 assert m.binary_expand(((1,),))==((255,),)


def test_types_shapes_values_and_caps():
 class T(tuple):
  def __iter__(self):raise AssertionError('hostile tuple iteration')
  def __len__(self):raise AssertionError('hostile tuple length')
 class I(int):
  def __le__(self,o):raise AssertionError('hostile int compare')
 image=((0,),);kernel=((1,0,1,1),);trace=()
 bad_images=([],T(image),([0],),(T((0,)),),((True,),),((I(0),),),((0.0,),),(),((),),((0,),)*9,(tuple([0]*9),),((0,),(0,0)),((-1,),),((256,),))
 for bad in bad_images:
  for fn,tail in ((m.threshold_halftone,(1,)),(m.ordered_halftone,(((0,),),)),(m.diffusion_halftone,(kernel,False)),(m.diffusion_trace,(kernel,True)),(m.verify_diffusion_trace,(kernel,False,trace))):
   with pytest.raises(ValueError):fn(bad,*tail)
  for fn in (m.halftone_pixel_errors,m.halftone_total_error):
   with pytest.raises(ValueError):fn(bad,((0,),))
 for bad in bad_images+(((2,),),):
  for fn in (m.halftone_pixel_errors,m.halftone_total_error):
   with pytest.raises(ValueError):fn(image,bad)
  with pytest.raises(ValueError):m.binary_expand(bad)
  with pytest.raises(ValueError):m.binary_block_coverage(bad,1,1)
 for fn in (m.halftone_pixel_errors,m.halftone_total_error):
  with pytest.raises(ValueError,match='bad_shape:alignment'):fn(((256,),),((0,0),))
 for val in (-1,256,True,I(1),1.0):
  with pytest.raises(ValueError):m.threshold_halftone(image,val)
 for val in (-1,4,True,I(1)):
  with pytest.raises(ValueError):m.bayer_screen(val)
 for bad in ([],T(((0,),)),([0],),((True,),),(),((),),((0,),)*9,((0,0),),((1,),),((-1,),),((0,),(1,2))):
  with pytest.raises(ValueError):m.ordered_halftone(image,bad)
 badkernels=([],T(kernel),([1,0,1,1],),((1,0,1),),((1,0,True,1),),((I(1),0,1,1),),(),kernel*9,((3,0,1,1),),((-3,1,1,1),),((0,-1,1,1),),((0,3,1,1),),((0,0,1,1),),((-1,0,1,1),),((1,0,0,1),),((1,0,17,16),),((1,0,1,0),),((1,0,1,17),),((1,0,2,1),),kernel*2)
 for bad in badkernels:
  for fn,tail in ((m.diffusion_halftone,(False,)),(m.diffusion_trace,(True,)),(m.verify_diffusion_trace,(False,trace))):
   with pytest.raises(ValueError):fn(image,bad,*tail)
 for snake in (0,1,None,'yes'):
  with pytest.raises(ValueError):m.diffusion_trace(image,kernel,snake)
 for width,height in ((0,1),(9,1),(1,0),(1,9),(True,1),(1,I(1))):
  with pytest.raises(ValueError):m.binary_block_coverage(((0,),),width,height)
 full=tuple(tuple(0 for _ in range(8)) for _ in range(8));assert m.diffusion_halftone(full,K,True)==full
 capkernel=tuple((dx,dy,1,16) for dx,dy in ((1,0),(2,0),(-2,1),(-1,1),(0,1),(1,1),(2,1),(0,2)))
 assert m.diffusion_halftone(image,capkernel,False)==((0,),)
 assert m.diffusion_halftone(image,((1,0,16,16),),False)==((0,),)
 assert m.SCOPE.startswith('PARTIAL:') and 'morphology b379' in m.NOT_CLAIMED

def test_trace_validation_and_phase_order():
 class T(tuple):
  def __iter__(self):raise AssertionError('hostile iteration')
 class I(int):pass
 image=((0,),);kernel=((1,0,1,1),);row=(0,0,(0,1),0,(0,1))
 bad=([],T(()),([],),((0,0,(0,1),0),),((True,0,(0,1),0,(0,1)),),((0,0,[0,1],0,(0,1)),),((0,0,T((0,1)),0,(0,1)),),((0,0,(I(0),1),0,(0,1)),),(row,)*65,((0,0,(0,),0,(0,1)),),((0,0,(0,1,1),0,(0,1)),),((-1,0,(0,1),0,(0,1)),),((8,0,(0,1),0,(0,1)),),((0,8,(0,1),0,(0,1)),),((0,0,(0,1),2,(0,1)),),((0,0,(m._TRACE_NUM_CAP+1,1),0,(0,1)),),((0,0,(-m._TRACE_NUM_CAP-1,1),0,(0,1)),),((0,0,(0,0),0,(0,1)),),((0,0,(0,m._TRACE_DEN_CAP+1),0,(0,1)),))
 for trace in bad:
  with pytest.raises(ValueError):m.verify_diffusion_trace(image,kernel,False,trace)
 assert m.verify_diffusion_trace(image,kernel,False,(row,))
 assert not m.verify_diffusion_trace(image,kernel,False,(row,)*64)
 for numerator in (-m._TRACE_NUM_CAP,m._TRACE_NUM_CAP):
  assert not m.verify_diffusion_trace(image,kernel,False,((7,7,(numerator,m._TRACE_DEN_CAP),1,(numerator,m._TRACE_DEN_CAP)),))
 # All later-argument types precede any earlier shapes or values.
 with pytest.raises(ValueError,match='bad_type:threshold'):m.threshold_halftone((),True)
 with pytest.raises(ValueError,match='bad_type:kernel'):m.diffusion_trace((),[],False)
 with pytest.raises(ValueError,match='bad_type:serpentine'):m.diffusion_trace(((-1,),),kernel,0)
 with pytest.raises(ValueError,match='bad_type:trace'):m.verify_diffusion_trace((),kernel,False,[])
 with pytest.raises(ValueError,match='bad_shape:kernel'):m.diffusion_trace(((-1,),),(),False)
 with pytest.raises(ValueError,match='bad_shape:trace'):m.verify_diffusion_trace(((-1,),),kernel,False,(row,)*65)
 with pytest.raises(ValueError,match='bad_type:width'):m.binary_block_coverage((),True,True)
 with pytest.raises(ValueError,match='bad_type:height'):m.binary_block_coverage((),0,True)


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
    with pytest.raises(ValueError, match='P235:binary_expand:bad_type:bits'):
        fallback['binary_expand']([])
    with pytest.raises(ModuleNotFoundError): load('dependency_inside_registry', False)
    with pytest.raises(ModuleNotFoundError): load(target, True)

@pytest.fixture(autouse=True)
def bounded_runtime():
 import signal
 def alarm(*_):raise AssertionError('kernel runtime limit')
 old=signal.signal(signal.SIGALRM,alarm);signal.alarm(3)
 try:yield
 finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)

def test_diffusion_tie_caps_and_nonzero_block_origins():
 assert m.diffusion_halftone(((127,64),),((1,0,1,2),),False)==((0,1),)
 image=((0,),);kernel=((1,0,1,1),)
 with pytest.raises(ValueError,match='bad_value:kernel'):m.diffusion_trace(image,((1,0,1,17),),False)
 with pytest.raises(ValueError,match='bad_value:kernel'):m.diffusion_trace(image,((1,0,17,16),),False)
 cap=tuple((dx,dy,1,16) for dx,dy in ((1,0),(2,0),(-2,1),(-1,1),(0,1),(1,1),(2,1),(0,2)))
 with pytest.raises(ValueError,match='bad_shape:kernel'):m.diffusion_trace(image,cap+((1,2,1,16),),False)
 with pytest.raises(ValueError,match='bad_shape:trace'):m.verify_diffusion_trace(image,kernel,False,((0,0,(0,1),0,(0,1,1)),))
 for bits in (((1,),),((1,0,1),(1,1,0),(0,1,1))):
  for width,height in it.product((1,2,8),repeat=2):
   got=m.binary_block_coverage(bits,width,height)
   want=[]
   for yy in range(0,len(bits),height):
    row=[]
    for xx in range(0,len(bits[0]),width):
     block=[v for y,r in enumerate(bits) for x,v in enumerate(r) if yy<=y<yy+height and xx<=x<xx+width];row.append(pair(F(sum(block),len(block))))
    want.append(tuple(row))
   assert got==tuple(want)

def test_generated_trace_bound_stress_roundtrip():
 import math
 assert m._TRACE_DEN_CAP==math.lcm(*range(1,17))**64
 assert m._TRACE_NUM_CAP==510*2**64*m._TRACE_DEN_CAP
 IMAGE=((236,22,5,68,233,98,10,131),(180,139,222,215,0,55,32,181),(45,42,221,4,193,37,206,14),(165,134,241,16,171,212,178,12),(83,214,32,73,190,120,40,29),(198,156,74,149,199,188,64,172),(61,85,197,221,31,69,232,10),(178,230,230,155,219,14,81,166))
 KERNEL=((1,0,1,12),(2,0,1,13),(-2,1,1,16),(-1,1,1,10),(0,1,1,15),(1,1,1,11),(2,1,1,14),(0,2,1,9))
 rng=random.Random(635109)
 fixtures=(IMAGE,tuple((0,)*8 for _ in range(8)),tuple((255,)*8 for _ in range(8)),tuple(tuple(255*((x+y)%2) for x in range(8)) for y in range(8)))+tuple(tuple(tuple(rng.randrange(256) for _ in range(8)) for _ in range(8)) for _ in range(8))
 for image in fixtures:
  for snake in (False,True):
   bits,trace,escaped=m.diffusion_trace(image,KERNEL,snake)
   assert m.verify_diffusion_trace(image,KERNEL,snake,trace)
   assert (bits,trace,escaped)==oracle(image,KERNEL,snake)
   assert F(*escaped)==m.halftone_total_error(image,bits)
   for _,_,work,_,error in trace:
    for a,b in (work,error):
     assert abs(a)<=m._TRACE_NUM_CAP and 1<=b<=m._TRACE_DEN_CAP
 assert max(len(str(abs(v))) for row in m.diffusion_trace(IMAGE,KERNEL,True)[1] for p in (row[2],row[4]) for v in p)>100
