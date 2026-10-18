"""P235 b495-origami: bounded exact single-vertex flat-fold checks.
angles is an exact list of 2..12 sector angles in integer degrees, each
1..359, summing to exactly 360. signs, where present, is an exact list of the
same length with entries 0 (valley) or 1 (mountain). Validation is argument
left-to-right: angles container type, count lower/upper, per-angle bool/type/
range, total sum, then signs container/length/entries. Kawasaki: alternating
sector sum is zero (requires even count). Maekawa: mountain minus valley
count has absolute value 2. Signing enumeration is capped at 4096 candidates
by the angle-count cap; results are sorted. Minimum-angle positions are the
indices of strictly locally-minimal angles (cyclic neighborhoods), the
big-little-big configuration. Outputs are fresh exact int lists, exact ints,
or bools. These are the classical necessary single-vertex conditions only;
no layer-ordering or global foldability is claimed. No metric geometry, no
rendering. All data is caller supplied; no retrieval or network.
"""
from importlib.util import find_spec
try:
 from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
 if exc.name!='app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
 def make_fail(name):
  def fail(code):raise ValueError('P235:%s:%s'%(name,code))
  return fail
SCOPE='PARTIAL: bounded exact Kawasaki/Maekawa single-vertex checks on supplied angles and signings'
NOT_CLAIMED=('layer-ordering or global flat-foldability','metric geometry','rendering','global novelty','production readiness')


def _angles(name,angles):
 f=make_fail(name)
 if type(angles) is not list:f('bad_type:angles')
 if len(angles)<2:f('bad_value:angles_size')
 if len(angles)>12:f('too_many:angles')
 for a in angles:
  if type(a) is bool:f('bad_type:angle')
  if type(a) is not int:f('bad_type:angle')
  if a<1:f('bad_value:angle')
  if a>359:f('too_many:angle')
 if sum(angles)!=360:f('bad_value:angle_sum')
 return f

def _signs(f,angles,signs):
 if type(signs) is not list:f('bad_type:signs')
 if len(signs)!=len(angles):f('bad_value:signs_size')
 for s in signs:
  if type(s) is bool:f('bad_type:sign')
  if type(s) is not int:f('bad_type:sign')
  if s not in (0,1):f('bad_value:sign')

def _alt(angles):
 return sum(angles[::2]),sum(angles[1::2])

def _kawasaki(angles):
 return len(angles)%2==0 and _alt(angles)[0]==_alt(angles)[1]

def _imbalance(signs):
 return sum(1 for s in signs if s==1)-sum(1 for s in signs if s==0)


def origami_kawasaki(angles):
 """True iff the alternating sector sums are equal (even count required)."""
 _angles('origami_kawasaki',angles)
 return _kawasaki(angles)


def origami_alternating_sums(angles):
 """[sum of even-indexed angles, sum of odd-indexed angles]."""
 _angles('origami_alternating_sums',angles)
 return list(_alt(angles))


def origami_maekawa(angles,signs):
 """True iff |#mountain - #valley| equals 2."""
 f=_angles('origami_maekawa',angles);_signs(f,angles,signs)
 return abs(_imbalance(signs))==2


def origami_sign_imbalance(angles,signs):
 """#mountain - #valley as an exact int."""
 f=_angles('origami_sign_imbalance',angles);_signs(f,angles,signs)
 return _imbalance(signs)


def origami_flat_foldable(angles,signs):
 """Kawasaki AND Maekawa for the supplied assignment (single-vertex
 necessary conditions only)."""
 f=_angles('origami_flat_foldable',angles);_signs(f,angles,signs)
 return _kawasaki(angles)and abs(_imbalance(signs))==2


def origami_valid_signings(angles):
 """Sorted sign vectors satisfying Maekawa; refuses bad_value:not_kawasaki
 when the angles fail Kawasaki."""
 f=_angles('origami_valid_signings',angles)
 if not _kawasaki(angles):f('bad_value:not_kawasaki')
 n=len(angles);out=[]
 for mask in range(1<<n):
  signs=[(mask>>i)&1 for i in range(n)]
  if abs(_imbalance(signs))==2:out.append(signs)
 return sorted(out)


def origami_signing_count(angles):
 """Number of Maekawa-satisfying sign vectors; refuses
 bad_value:not_kawasaki when angles fail Kawasaki."""
 f=_angles('origami_signing_count',angles)
 if not _kawasaki(angles):f('bad_value:not_kawasaki')
 n=len(angles)
 return sum(1 for mask in range(1<<n)if abs(sum(1 for i in range(n)if(mask>>i)&1)-sum(1 for i in range(n)if not(mask>>i)&1))==2)


def origami_min_angle_positions(angles):
 """Sorted indices of strictly locally-minimal angles (cyclic
 neighborhoods)."""
 _angles('origami_min_angle_positions',angles)
 n=len(angles)
 return[i for i in range(n)if angles[i]<angles[(i-1)%n]and angles[i]<angles[(i+1)%n]]


def origami_cyclic_equivalent(a1,a2):
 """True iff the two validated angle lists are cyclic rotations."""
 _angles('origami_cyclic_equivalent',a1)
 _angles('origami_cyclic_equivalent',a2)
 if len(a1)!=len(a2):return False
 n=len(a1)
 return any(a1==a2[k:]+a2[:k]for k in range(n))


def origami_angle_sum(angles):
 """Total of the supplied angles (validated to be 360)."""
 _angles('origami_angle_sum',angles)
 return sum(angles)
