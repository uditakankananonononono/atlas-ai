"""P235 b644 supplied-prime Shamir-style arithmetic, PARTIAL only.
Four APIs, not ten independent ideas. No randomness or security claim.
Prime exact int2..251, primality checked by trial division. Coefficients
exact tuple1..8, exact residues0..prime-1, constant first, trailing zeros
allowed. Abscissas exact tuple1..16, exact distinct ints1..prime-1.
Shares exact tuple1..16 of exact (x,y) pairs with distinct x1..prime-1,
y0..prime-1. Degree limit exact int0..7. All types across arguments first
in positional order, then shapes/caps, then values positional. Prime is
validated before residue ranges. Bool/subclasses always refused.
share evaluates supplied coefficients; no secret or randomness generated.
reconstruct needs >=degree+1 shares and refuses if their interpolant has
larger degree. It is explicitly a thin interpolation-at-zero wrapper.
verify_consistency checks only interpolant degree<=limit; insufficient
shares can return True but do not uniquely determine a degree-limit secret.
degree_bound returns degree of the unique degree<count interpolant, zero
for the zero polynomial. No generic interpolation coefficients exposed.
Adjacent b447-new interpolation, b503 held Lagrange interpolation, b318
GF16, b485 GF2 LFSR; those purposes are not claimed as new. b541 lattice
name similarity has no arithmetic role. Not a deployable sharing scheme,
no randomness, authentication, secrecy, adversarial correction or IO.
"""
from importlib.util import find_spec
try:
 from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
 if exc.name!='app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
 def make_fail(name):
  def fail(code):raise ValueError('P235:%s:%s'%(name,code))
  return fail
SCOPE='PARTIAL: bounded supplied-prime secret-sharing arithmetic'
NOT_CLAIMED=('generic interpolation b447 b503','finite-field novelty b318 b485','randomness','security','deployable sharing scheme','global novelty','production readiness')

def _check(n,prime,args):
 f=make_fail(n)
 if type(prime) is not int:f('bad_type:prime')
 for label,obj,kind in args:
  if kind=='degree':
   if type(obj) is not int:f('bad_type:'+label)
  else:
   if type(obj) is not tuple:f('bad_type:'+label)
   for row in obj:
    if kind=='shares':
     if type(row) is not tuple:f('bad_type:'+label)
     if any(type(v) is not int for v in row):f('bad_type:'+label)
    elif type(row) is not int:f('bad_type:'+label)
 for label,obj,kind in args:
  if kind=='degree':continue
  cap=8 if kind=='coefficients' else 16
  if not 1<=len(obj)<=cap:f('bad_shape:'+label)
  if kind=='shares' and any(len(row)!=2 for row in obj):f('bad_shape:'+label)
 if not 2<=prime<=251 or any(prime%d==0 for d in range(2,int(prime**0.5)+1)):f('bad_value:prime')
 for label,obj,kind in args:
  if kind=='degree':
   if not 0<=obj<=7:f('bad_value:'+label)
  elif kind=='coefficients':
   if any(not 0<=v<prime for v in obj):f('bad_value:'+label)
  else:
   xs=tuple(x for x,_ in obj) if kind=='shares' else obj
   if any(not 1<=x<prime for x in xs) or len(set(xs))!=len(xs):f('bad_value:'+label)
   if kind=='shares' and any(not 0<=y<prime for _,y in obj):f('bad_value:'+label)

def _degree(prime,shares):
 # Newton divided differences, highest nonzero coefficient determines degree.
 values=[y for _,y in shares];degree=0
 for order in range(1,len(shares)):
  values=[(values[i+1]-values[i])*pow((shares[i+order][0]-shares[i][0])%prime,-1,prime)%prime for i in range(len(values)-1)]
  if values[0]!=0:degree=order
 return degree

def sharing_share(prime,coefficients,abscissas):
 n='sharing_share';_check(n,prime,(('coefficients',coefficients,'coefficients'),('abscissas',abscissas,'xs')));out=[]
 for x in abscissas:
  value=0
  for c in reversed(coefficients):value=(value*x+c)%prime
  out.append((x,value))
 return tuple(out)

def sharing_reconstruct(prime,shares,degree):
 n='sharing_reconstruct';_check(n,prime,(('shares',shares,'shares'),('degree',degree,'degree')))
 if len(shares)<degree+1:make_fail(n)('insufficient_shares')
 if _degree(prime,shares)>degree:make_fail(n)('inconsistent_shares')
 # Thin Lagrange-at-zero wrapper, only for the admitted share set.
 secret=0
 for i,(x,y) in enumerate(shares):
  weight=1
  for j,(other,_) in enumerate(shares):
   if i!=j:weight=weight*(-other)*pow((x-other)%prime,-1,prime)%prime
  secret=(secret+y*weight)%prime
 return secret

def sharing_verify_consistency(prime,shares,degree):
 _check('sharing_verify_consistency',prime,(('shares',shares,'shares'),('degree',degree,'degree')))
 return _degree(prime,shares)<=degree

def sharing_degree_bound(prime,shares):
 _check('sharing_degree_bound',prime,(('shares',shares,'shares'),));return _degree(prime,shares)
