import pytest
from fractions import Fraction as Fr
from math import comb
import sys;sys.path.insert(0,'backend')
from app.modules.instinct_doc import p235_concepts_batch634 as m

def bad(name,args,code):
 with pytest.raises(ValueError,match='^P235:%s:%s$'%(name,__import__('re').escape(code))):getattr(m,name)(*args)

class I(int):pass

def test_registry_import_guard_matrix():
 import builtins,runpy,sys,types
 from unittest.mock import patch
 name='app.modules.instinct_doc.p235_concepts_registry';orig=builtins.__import__
 for claimed,present in ((name,False),(name,True),('other_dependency',False)):
  def fake_import(n,*a,**k):
   if n==name:raise ModuleNotFoundError('synthetic',name=claimed)
   return orig(n,*a,**k)
  with patch('builtins.__import__',fake_import),patch('importlib.util.find_spec',lambda _:object() if present else None):
   if present or claimed!=name:
    with pytest.raises(ModuleNotFoundError):runpy.run_path(m.__file__)
   else:
    ns=runpy.run_path(m.__file__)
    with pytest.raises(ValueError,match='^P235:partition_count:bad_type:n$'):ns['partition_count']('5')
 fake=types.ModuleType(name);sentinel=object();fake.make_fail=lambda _:sentinel
 with patch.dict(sys.modules,{name:fake}):assert runpy.run_path(m.__file__)['make_fail']('x') is sentinel

def test_known_values():
 assert m.partition_count(0)==1 and m.partition_count(5)==7 and m.partition_count(10)==42 and m.partition_count(60)==966467
 assert m.partition_count_parts(0,0)==1 and m.partition_count_parts(0,1)==0 and m.partition_count_parts(5,2)==2 and m.partition_count_parts(5,9)==0
 assert m.partition_count_max_part(0,0)==1 and m.partition_count_max_part(5,0)==0 and m.partition_count_max_part(5,2)==3 and m.partition_count_max_part(5,60)==7
 assert m.partition_count_distinct(5)==3 and m.partition_count_odd(5)==3 and m.partition_count_distinct(10)==10
 assert m.partition_list(4)==((4,),(3,1),(2,2),(2,1,1),(1,1,1,1)) and m.partition_list(0)==((),)
 assert m.partition_conjugate(())==() and m.partition_conjugate((3,2))==(2,2,1) and m.partition_conjugate((1,))==(1,)
 assert m.composition_count_bounded(5,2,3)==2 and m.composition_count_bounded(0,0,5)==1 and m.composition_count_bounded(5,0,5)==0 and m.composition_count_bounded(5,2,0)==0
 assert m.composition_count_weak(0,0)==1 and m.composition_count_weak(5,0)==0 and m.composition_count_weak(3,2)==4
 assert m.composition_list_bounded(4,2,3)==((1,3),(2,2),(3,1)) and m.composition_list_bounded(0,0,9)==((),) and m.composition_list_bounded(3,0,9)==() and m.composition_list_bounded(3,2,1)==()

def _penta_oracle(n):
 # independent oracle: Euler's pentagonal-number recurrence
 p=[1]
 for i in range(1,n+1):
  s=0;j=1
  while True:
   for g in (j*(3*j-1)//2,j*(3*j+1)//2):
    if g>i:break
    s+=p[i-g] if j%2 else -p[i-g]
   if j*(3*j+1)//2>i and j*(3*j-1)//2>i:break
   j+=1
  p.append(s)
 return p[n]

def _brute_parts(n,exact_k=None,distinct=False,odd=False):
 # independent oracle: direct recursive generation, filter by construction
 if n==0:return 1 if exact_k in (None,0) else 0
 out=[0]
 def rec(rem,hi,depth):
  if rem==0:
   if exact_k is None or depth==exact_k:out[0]+=1
   return
  lo=min(hi,rem)
  if odd:lo-= (lo%2==0)
  step=2 if odd else 1
  for p in range(lo,0,-step):
   if exact_k is not None and depth+1>exact_k:break
   rec(rem-p,p-1 if distinct else p,depth+1)
 rec(n,n,0)
 return out[0]

def test_partition_count_vs_pentagonal_oracle():
 for n in range(61):assert m.partition_count(n)==_penta_oracle(n)

def test_restricted_counts_vs_brute_force():
 for n in range(26):
  assert m.partition_count_odd(n)==_brute_parts(n,odd=True)
  assert m.partition_count_distinct(n)==_brute_parts(n,distinct=True)
  for k in range(0,27):assert m.partition_count_parts(n,k)==_brute_parts(n,exact_k=k)
  
def _max_part_brute(n,mm):
 out=[0]
 def rec(rem,hi):
  if rem==0:out[0]+=1;return
  for p in range(min(hi,rem,mm),0,-1):rec(rem-p,p)
 if mm==0:return 1 if n==0 else 0
 rec(n,mm)
 return out[0]

def test_max_part_vs_brute_and_distinct_odd_identity():
 for n in range(26):
  for mm in range(0,26):assert m.partition_count_max_part(n,mm)==_max_part_brute(n,mm)
 for n in range(61):assert m.partition_count_distinct(n)==m.partition_count_odd(n)

def _inclex(n,k,b):
 # independent oracle: inclusion-exclusion over the upper bound
 if k==0:return 1 if n==0 else 0
 s=0
 for j in range(0,k+1):
  top=n-j*b-1
  if top>=k-1:s+=(-1)**j*comb(k,j)*comb(top,k-1)
 return s

def test_composition_counts_vs_oracles():
 for n in range(0,31):
  for k in range(0,8):
   for b in range(1,12):assert m.composition_count_bounded(n,k,b)==_inclex(n,k,b)
   assert m.composition_count_weak(n,k)==(1 if (n,k)==(0,0) else (0 if k==0 else comb(n+k-1,k-1)))

def test_lists_match_counts_and_ordering():
 for n in range(13):
  rows=m.partition_list(n)
  assert len(rows)==m.partition_count(n) and rows==tuple(sorted(rows,reverse=True))
  for p in rows:assert list(p)==sorted(p,reverse=True) and sum(p)==n and all(1<=x<=n for x in p)
 assert len(m.partition_list(12))==77
 for n,k,b in ((5,3,3),(6,3,4),(22,3,17),(4,2,3)):
  rows=m.composition_list_bounded(n,k,b)
  assert len(rows)==m.composition_count_bounded(n,k,b) and rows==tuple(sorted(rows))
  for c in rows:assert sum(c)==n and len(c)==k and all(1<=x<=b for x in c)
 assert len(m.composition_list_bounded(22,3,17))==192

def test_conjugate_involution_and_sum():
 import random
 rng=random.Random(631)
 for _ in range(200):
  n=rng.randrange(0,13);p=rng.choice(m.partition_list(n))
  assert m.partition_conjugate(m.partition_conjugate(p))==p and sum(m.partition_conjugate(p))==n

def test_output_freshness():
 a=m.partition_list(5);b=m.partition_list(5)
 assert a==b and a is not b and a[0] is not b[0]
 c=m.composition_list_bounded(5,3,3);d=m.composition_list_bounded(5,3,3)
 assert c==d and c is not d

def test_type_refusals():
 for fn,args in ((m.partition_count,(5,)),(m.partition_count_distinct,(5,)),(m.partition_count_odd,(5,)),(m.partition_list,(5,))):
  with pytest.raises(ValueError,match='bad_type:bool_n$'):fn(True)
  with pytest.raises(ValueError,match='bad_type:n$'):fn(I(5));fn(Fr(5,1));fn('5');fn(None)
 bad('partition_count_parts',(True,1),'bad_type:bool_n');bad('partition_count_parts',(5,True),'bad_type:bool_k')
 bad('partition_count_parts',(I(5),1),'bad_type:n');bad('partition_count_parts',(5,Fr(1)),'bad_type:k')
 bad('partition_count_max_part',(5,I(2)),'bad_type:m');bad('composition_count_bounded',(5,2,True),'bad_type:bool_b')
 bad('composition_count_bounded',(5,'2',3),'bad_type:k');bad('composition_count_weak',(None,2),'bad_type:n')
 bad('partition_conjugate',(True,),'bad_type:bool_partition');bad('partition_conjugate',([],),'bad_type:partition');bad('partition_conjugate',(I(3),),'bad_type:partition')

def test_value_caps_at_cap_and_cap_plus_one():
 assert m.partition_count(60)==966467
 bad('partition_count',(61,),'bad_value:n_range');bad('partition_count',(-1,),'bad_value:n_range')
 bad('partition_count',(10**12+1,),'bad_value:n_abs');assert m.partition_count(0)==1
 bad('partition_count',(-10**12-1,),'bad_value:n_abs')
 bad('partition_count_parts',(60,61),'bad_value:k_range');assert m.partition_count_parts(60,60)==1
 bad('partition_count_max_part',(0,61),'bad_value:m_range');assert m.partition_count_max_part(0,60)==1
 bad('composition_count_bounded',(5,2,61),'bad_value:b_range');assert m.composition_count_bounded(60,60,60)==1
 bad('composition_count_weak',(61,1),'bad_value:n_range');assert m.composition_count_weak(60,1)==1
 bad('partition_list',(13,),'bad_value:n_range');bad('partition_list',(12,),'none') if False else None
 assert len(m.partition_list(12))==77
 bad('partition_conjugate',(tuple([61]),),'bad_value:partition_0_range');bad('partition_conjugate',((0,),),'bad_value:partition_0_range')
 bad('partition_conjugate',(tuple([10**12+1]),),'bad_value:partition_0_abs')
 assert m.partition_conjugate(tuple([1]*12))==(12,)
 assert m.partition_conjugate(tuple([5]*12))==(12,)*5
 bad('partition_conjugate',(tuple([1]*13),),'bad_value:partition_length')
 bad('partition_conjugate',(((5,)*13),),'bad_value:partition_length')
 bad('partition_conjugate',((12,12,12,12,12,1),),'bad_value:partition_sum')

def test_output_row_cap_boundary():
 # 192 rows (22,3,17) succeeds; no (n,k,b) in caps yields exactly 193..200 rows; 201 (22,3,18) refuses
 assert len(m.composition_list_bounded(22,3,17))==192
 bad('composition_list_bounded',(22,3,18),'bad_value:too_many')
 bad('composition_list_bounded',(60,3,60),'bad_value:too_many')
 assert m.composition_count_bounded(22,3,18)==201

def test_relations():
 bad('partition_conjugate',((2,3),),'bad_relation:not_partition')
 bad('partition_conjugate',((1,3,2),),'bad_relation:not_partition')
 assert m.partition_conjugate((3,3,2))==(3,3,2)

def test_mixed_invalid_phase_order():
 # every argument type precedes every argument value
 bad('partition_count_parts',(61,True),'bad_type:bool_k')
 bad('partition_count_parts',(I(1),61),'bad_type:n')
 bad('composition_count_bounded',(61,62,True),'bad_type:bool_b')
 bad('composition_count_bounded',(61,62,63),'bad_value:n_range')
 bad('composition_count_bounded',(5,62,63),'bad_value:k_range')
 bad('composition_count_bounded',(5,2,63),'bad_value:b_range')
 bad('partition_count_max_part',(True,10**12+1),'bad_type:bool_n')
 bad('partition_count_max_part',(5,10**12+1),'bad_value:m_abs')
 # same-phase positional order preserved
 bad('partition_count_parts',(61,62),'bad_value:n_range')
 bad('partition_count_parts',(10**12+1,10**12+1),'bad_value:n_abs')
 # conjugate: tuple type/length, then all entry types, then all entry values, then relation
 bad('partition_conjugate',(((10**12+1),'x'),),'bad_type:partition_1')
 bad('partition_conjugate',(((10**12+1),2),),'bad_value:partition_0_abs')
 bad('partition_conjugate',((2,1,'x'),),'bad_type:partition_2')
 bad('partition_conjugate',((2,1,True),),'bad_type:bool_partition_2')
 bad('partition_conjugate',((0,'x'),),'bad_type:partition_1')
 bad('partition_conjugate',((0,1),),'bad_value:partition_0_range')

def test_survivor_pins():
 # values just under the abs cap must hit the range check, not the abs check: kills ABS shrink/bin/cmp mutants
 bad('partition_count',(10**12,),'bad_value:n_range')
 bad('partition_conjugate',((10**12,),),'bad_value:partition_0_range')
 # entry exactly 60 stays valid: kills the upper range-cmp boundary
 assert m.partition_conjugate((60,))==(1,)*60
 # nonempty b=1 composition list: kills the b==0 guard shifted to b==1
 assert m.composition_list_bounded(2,2,1)==((1,1),)
