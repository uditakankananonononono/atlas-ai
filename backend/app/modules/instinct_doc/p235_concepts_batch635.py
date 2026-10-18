"""P235 b635 exact binary halftoning of supplied integer rasters, PARTIAL.
Images exact tuple1..8 rows, exact tuple1..8 columns, rectangular, exact
ints0..255. Binary rasters same shape with ints0/1. Threshold exact0..255;
comparison is >=. Bayer order exact0..3 produces square side2**order,
ranks0..side**2-1. Ordered screen exact rectangular tuple<=8x8, a permutation
of ranks0..cell_count-1; tiles from top-left. Ordered comparison uses
2*cell_count*pixel >= 255*(2*rank+1), exact midpoint thresholds.
Diffusion kernel exact nonempty tuple<=8 of (dx,dy,numerator,denominator),
all exact ints, offsets dx -2..2, dy0..2, strictly future (dy>0 or dx>0),
weights positive numerator1..16/denominator1..16, sum<=1, unique offsets.
Kernel tuple order preserved, not sorted. Serpentine exact bool; odd rows
reverse traversal and mirror dx. Pixel work is exact Fraction, unclipped.
Quantization >=255/2 chooses255 else0, even outside input range. Error is
work-output; missing/off-image weight escapes. Trace rows (x,y,work_pair,
bit,error_pair), in traversal order. Trace verifier requires exact replay.
Trace exact tuple<=64, row exact tuple5; rational fields exact tuple2 of
exact ints with denominator1..720720**64 and numerator magnitude
<=510*2**64*720720**64. Every generated trace fits these derived bounds.
720720 is lcm(1..16); a contribution traverses at most63 future edges.
Each error magnitude is <=510 plus the sum of preceding error magnitudes,
so <=510*2**63; work is bounded by510*2**64. No clipping is introduced.
Validation globally all types positional, then shapes/caps positional,
then values positional. Verify checks both raster/kernel and whole trace.
Block coverage returns occupied/count rational per nonoverlapping block,
including partial edges, block width/height1..8. Error APIs measure
original pixel minus255*bit, not accumulated diffusion work.
Adjacent raster/compositing b475, morphology b379, and PCM: none claimed.
No audio, color, morphology, compositing, image-quality or perceptual claim.
"""
from fractions import Fraction as F
from importlib.util import find_spec
try:
 from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
 if exc.name!='app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
 def make_fail(name):
  def fail(code):raise ValueError('P235:%s:%s'%(name,code))
  return fail
SCOPE='PARTIAL: bounded exact binary raster halftoning'
NOT_CLAIMED=('raster compositing b475','morphology b379','PCM audio','perceptual quality','global novelty','production readiness')

_TRACE_DEN_CAP=720720**64
_TRACE_NUM_CAP=510*2**64*_TRACE_DEN_CAP

def _types(n,label,obj,kind):
 f=make_fail(n)
 if kind=='bool':
  if type(obj) is not bool:f('bad_type:'+label)
 elif kind=='int':
  if type(obj) is not int:f('bad_type:'+label)
 else:
  if type(obj) is not tuple:f('bad_type:'+label)
  for row in obj:
   if type(row) is not tuple:f('bad_type:'+label)
   for index,value in enumerate(row):
    if kind=='trace' and index in (2,4):
     if type(value) is not tuple:f('bad_type:'+label)
     if any(type(v) is not int for v in value):f('bad_type:'+label)
    elif type(value) is not int:f('bad_type:'+label)

def _shape(n,label,obj,kind):
 f=make_fail(n)
 if kind in ('image','binary','screen'):
  if not 1<=len(obj)<=8 or not 1<=len(obj[0])<=8:f('bad_shape:'+label)
  if any(len(row)!=len(obj[0]) for row in obj):f('bad_shape:'+label)
 elif kind=='kernel':
  if not 1<=len(obj)<=8 or any(len(r)!=4 for r in obj):f('bad_shape:'+label)
 elif kind=='trace':
  if len(obj)>64 or any(len(r)!=5 for r in obj):f('bad_shape:'+label)
  for x,y,work,bit,error in obj:
   if len(work)!=2 or len(error)!=2:f('bad_shape:'+label)

def _values(n,label,obj,kind,lo=0,hi=255):
 f=make_fail(n)
 if kind=='int':
  if not lo<=obj<=hi:f('bad_value:'+label)
 elif kind in ('image','binary'):
  top=255 if kind=='image' else 1
  if any(not 0<=v<=top for row in obj for v in row):f('bad_value:'+label)
 elif kind=='screen':
  vals=[v for row in obj for v in row]
  if sorted(vals)!=list(range(len(vals))):f('bad_value:'+label)
 elif kind=='kernel':
  for dx,dy,a,b in obj:
   if not -2<=dx<=2 or not 0<=dy<=2 or not (dy>0 or dx>0) or not 1<=a<=16 or not 1<=b<=16:f('bad_value:'+label)
  if len({(dx,dy) for dx,dy,_,_ in obj})!=len(obj) or sum(F(a,b) for _,_,a,b in obj)>1:f('bad_value:'+label)
 elif kind=='trace':
  for x,y,w,bit,e in obj:
   if not 0<=x<=7 or not 0<=y<=7 or bit not in (0,1):f('bad_value:'+label)
   for a,b in (w,e):
    if not -_TRACE_NUM_CAP<=a<=_TRACE_NUM_CAP or not 1<=b<=_TRACE_DEN_CAP:f('bad_value:'+label)

def _check(n,args):
 for label,obj,kind,*_ in args:_types(n,label,obj,kind)
 for label,obj,kind,*_ in args:_shape(n,label,obj,kind)
 if len(args)==2 and args[0][0]=='image' and args[1][0]=='bits':
  image,bits=args[0][1],args[1][1]
  if len(image)!=len(bits) or len(image[0])!=len(bits[0]):make_fail(n)('bad_shape:alignment')
 for label,obj,kind,*limits in args:_values(n,label,obj,kind,*limits)

def bayer_screen(order):
 n='bayer_screen';_check(n,(('order',order,'int',0,3),));r=((0,),)
 for _ in range(order):
  r=tuple(tuple(4*r[y%len(r)][x%len(r)]+((0,2),(3,1))[y//len(r)][x//len(r)] for x in range(2*len(r))) for y in range(2*len(r)))
 return r

def threshold_halftone(image,threshold):
 _check('threshold_halftone',(('image',image,'image'),('threshold',threshold,'int')))
 return tuple(tuple(int(v>=threshold) for v in row) for row in image)

def ordered_halftone(image,screen):
 _check('ordered_halftone',(('image',image,'image'),('screen',screen,'screen')));h=len(screen);w=len(screen[0]);count=h*w
 return tuple(tuple(int(2*count*v>=255*(2*screen[y%h][x%w]+1)) for x,v in enumerate(row)) for y,row in enumerate(image))

def _pair(v):return v.numerator,v.denominator

def _diffuse(image,kernel,serpentine):
 h=len(image);w=len(image[0]);work=[[F(v) for v in row] for row in image];bits=[[0]*w for _ in image];trace=[];escaped=F(0)
 for y in range(h):
  direction=-1 if serpentine and y%2 else 1
  for x in (range(w) if direction==1 else range(w-1,-1,-1)):
   value=work[y][x];bit=int(value>=F(255,2));error=value-255*bit;bits[y][x]=bit;trace.append((x,y,_pair(value),bit,_pair(error)));used=F(0)
   for dx,dy,a,b in kernel:
    xx=x+direction*dx;yy=y+dy;weight=F(a,b)
    if 0<=xx<w and 0<=yy<h:work[yy][xx]+=error*weight;used+=weight
   escaped+=error*(1-used)
 return tuple(tuple(row) for row in bits),tuple(trace),_pair(escaped)

def _diff_args(image,kernel,serpentine):return (('image',image,'image'),('kernel',kernel,'kernel'),('serpentine',serpentine,'bool'))

def diffusion_halftone(image,kernel,serpentine):
 _check('diffusion_halftone',_diff_args(image,kernel,serpentine));return _diffuse(image,kernel,serpentine)[0]

def diffusion_trace(image,kernel,serpentine):
 _check('diffusion_trace',_diff_args(image,kernel,serpentine));return _diffuse(image,kernel,serpentine)

def verify_diffusion_trace(image,kernel,serpentine,trace):
 _check('verify_diffusion_trace',_diff_args(image,kernel,serpentine)+(('trace',trace,'trace'),));return trace==_diffuse(image,kernel,serpentine)[1]

def _two(n,image,bits):
 _check(n,(('image',image,'image'),('bits',bits,'binary')))

def halftone_pixel_errors(image,bits):
 _two('halftone_pixel_errors',image,bits);return tuple(tuple(v-255*b for v,b in zip(row,br)) for row,br in zip(image,bits))

def halftone_total_error(image,bits):
 _two('halftone_total_error',image,bits);return sum(v-255*b for row,br in zip(image,bits) for v,b in zip(row,br))

def binary_block_coverage(bits,width,height):
 _check('binary_block_coverage',(('bits',bits,'binary'),('width',width,'int',1,8),('height',height,'int',1,8)))
 return tuple(tuple(_pair(F(sum(bits[y][x] for y in range(yy,min(yy+height,len(bits))) for x in range(xx,min(xx+width,len(bits[0])))),min(height,len(bits)-yy)*min(width,len(bits[0])-xx))) for xx in range(0,len(bits[0]),width)) for yy in range(0,len(bits),height))

def binary_expand(bits):
 _check('binary_expand',(('bits',bits,'binary'),));return tuple(tuple(255*v for v in row) for row in bits)
