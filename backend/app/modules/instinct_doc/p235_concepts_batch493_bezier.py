"""P235 b493-bezier: bounded exact rational Bezier arithmetic.
points is an exact list of 2..9 control points; every point is an exact list
of the same dimension 1..4, each coordinate an exact int or Fraction with
absolute numerator <=4096 and positive denominator <=4096. t is an exact int
or Fraction with the same component caps; evaluation is not clamped to [0,1].
r (repeated elevation count) is an exact int 0..4. Bool and subclasses refuse
before type checks. Validation is argument left-to-right: points container
type, count lower/upper, per point type, consistent dimension and dimension
bounds, per component type/numerator/denominator; then scalar arguments.
Outputs are fresh lists of exact Fractions (lists of points as lists of
Fractions) or bools. Degree elevation keeps the curve exact; subdivision at t
uses de Casteljau. The blossom takes exactly degree scalar arguments. No
rendering, rasterization, approximation, arc-length or intersection claims.
All data is caller supplied; no retrieval or network.
"""
from fractions import Fraction
from importlib.util import find_spec
try:
 from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
 if exc.name!='app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
 def make_fail(name):
  def fail(code):raise ValueError('P235:%s:%s'%(name,code))
  return fail
SCOPE='PARTIAL: bounded exact rational Bezier evaluation and manipulation on supplied control points'
NOT_CLAIMED=('rendering or rasterization','approximation or arc length','curve intersection','global novelty','production readiness')


def _component(f,x):
 if type(x) is bool:f('bad_type:component')
 if type(x) is not int and type(x) is not Fraction:f('bad_type:component')
 if abs(x.numerator)>4096:f('too_many:numerator')
 if x.denominator>4096:f('too_many:denominator')
 return Fraction(x)

def _scalar(f,x,label='t'):
 if type(x) is bool:f('bad_type:'+label)
 if type(x) is not int and type(x) is not Fraction:f('bad_type:'+label)
 if abs(x.numerator)>4096:f('too_many:'+label+'_numerator')
 if x.denominator>4096:f('too_many:'+label+'_denominator')
 return Fraction(x)

def _points(name,points):
 f=make_fail(name)
 if type(points) is not list:f('bad_type:points')
 if len(points)<2:f('bad_value:points_size')
 if len(points)>9:f('too_many:points')
 d=None
 for p in points:
  if type(p) is not list:f('bad_type:point')
  if d is None:
   d=len(p)
   if d<1:f('bad_value:dimension')
   if d>4:f('too_many:dimension')
  elif len(p)!=d:f('bad_value:dimension')
  for x in p:_component(f,x)
 return f,[[Fraction(x)for x in p]for p in points]

def _casteljau(pts,t):
 layer=pts
 while len(layer)>1:layer=[[ (Fraction(1)-t)*x+t*y for x,y in zip(a,b)]for a,b in zip(layer,layer[1:])]
 return layer[0]

def _deriv(pts,scale):
 return [[Fraction(scale)*(b-a)for a,b in zip(p,q)]for p,q in zip(pts,pts[1:])]

def _elevate(pts):
 n=len(pts)
 out=[pts[0]]
 for i in range(1,n):out.append([Fraction(i,n)*a+Fraction(n-i,n)*b for a,b in zip(pts[i-1],pts[i])])
 out.append(pts[-1])
 return out


def bezier_evaluate(points,t):
 """Exact de Casteljau point at t (t may lie outside [0,1])."""
 f,pts=_points('bezier_evaluate',points);tv=_scalar(f,t)
 return _casteljau(pts,tv)


def bezier_subdivide(points,t):
 """[left control points, right control points] splitting the curve at t."""
 f,pts=_points('bezier_subdivide',points);tv=_scalar(f,t)
 layer=pts;left=[pts[0]];right=[pts[-1]]
 while len(layer)>1:
  layer=[[(Fraction(1)-tv)*x+tv*y for x,y in zip(a,b)]for a,b in zip(layer,layer[1:])]
  left.append(layer[0]);right.append(layer[-1])
 right.reverse()
 return[left,right]


def bezier_blossom(points,args):
 """Polar value: args must be exactly degree many scalar values."""
 f,pts=_points('bezier_blossom',points)
 if type(args) is not list:f('bad_type:args')
 if len(args)!=len(pts)-1:f('bad_value:args_size')
 vals=[_scalar(f,x,'arg')for x in args]
 layer=pts
 for tv in vals:
  layer=[[(Fraction(1)-tv)*x+tv*y for x,y in zip(a,b)]for a,b in zip(layer,layer[1:])]
 return layer[0]


def bezier_degree_elevate(points):
 """One exact degree elevation; point count grows by one."""
 f,pts=_points('bezier_degree_elevate',points)
 return _elevate(pts)


def bezier_elevate_n(points,r):
 """r repeated exact degree elevations; r is 0..4."""
 f,pts=_points('bezier_elevate_n',points)
 if type(r) is bool:f('bad_type:r')
 if type(r) is not int:f('bad_type:r')
 if r<0:f('bad_value:r')
 if r>4:f('too_many:r')
 for _ in range(r):pts=_elevate(pts)
 return pts


def bezier_derivative_control(points):
 """Control points of the first derivative (scaled by the degree)."""
 f,pts=_points('bezier_derivative_control',points)
 return _deriv(pts,len(pts)-1)


def bezier_second_derivative_control(points):
 """Control points of the second derivative; degree must be at least 2."""
 f,pts=_points('bezier_second_derivative_control',points)
 if len(pts)<3:f('bad_value:degree')
 return _deriv(_deriv(pts,len(pts)-1),len(pts)-2)


def bezier_derivative_evaluate(points,t):
 """Exact first derivative vector at t."""
 f,pts=_points('bezier_derivative_evaluate',points);tv=_scalar(f,t)
 return _casteljau(_deriv(pts,len(pts)-1),tv)


def bezier_endpoints(points):
 """[first control point, last control point] as exact Fractions."""
 f,pts=_points('bezier_endpoints',points)
 return[pts[0],pts[-1]]


def bezier_is_collinear(points):
 """True iff every control point lies on the line through the first two
 distinct control points (or all points coincide)."""
 f,pts=_points('bezier_is_collinear',points)
 base=None
 for p in pts:
  if p!=pts[0]:base=p;break
 if base is None:return True
 d=len(pts[0]);v=[b-a for a,b in zip(pts[0],base)]
 for p in pts:
  w=[b-a for a,b in zip(pts[0],p)]
  for i in range(d):
   for j in range(i+1,d):
    if v[i]*w[j]!=v[j]*w[i]:return False
 return True
