import pytest
from fractions import Fraction as Fr
import sys;sys.path.insert(0,'backend')
from app.modules.instinct_doc import p235_concepts_batch639 as m

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
    with pytest.raises(ValueError,match='^P235:harmonic_number:bad_type:n$'):ns['harmonic_number']('4')
 fake=types.ModuleType(name);sentinel=object();fake.make_fail=lambda _:sentinel
 with patch.dict(sys.modules,{name:fake}):assert runpy.run_path(m.__file__)['make_fail']('x') is sentinel

def test_known_values():
 assert m.greedy_egyptian(5,6)==(2,3) and m.greedy_egyptian_length(5,6)==2 and m.greedy_egyptian(3,7)==(3,11,231)
 assert m.engel_expansion(5,6)==(2,2,3) and m.engel_expansion(1,5)==(5,)
 assert m.sylvester_sequence(0)==() and m.sylvester_sequence(6)==(2,3,7,43,1807,3263443)
 assert m.harmonic_number(0)==0 and m.harmonic_number(4)==Fr(25,12)
 assert m.harmonic_range_sum(2,4)==Fr(13,12) and m.harmonic_range_sum(5,5)==Fr(1,5)
 assert m.unit_sum(())==0 and m.unit_sum((2,3,10,15))==1
 assert m.is_egyptian_decomposition(5,6,(2,3)) is True and m.is_egyptian_decomposition(5,6,(2,3,10,15)) is False
 assert m.sylvester_partial_sum(3)==Fr(41,42)
 assert m.egyptian_remainder(5,6,(2,))==Fr(1,3) and m.egyptian_remainder(5,6,(2,3))==0

def _greedy_oracle(p,q):
 # independent oracle: ceiling via divmod, denominator arithmetic on ints
 out=[]
 from math import gcd
 num,den=p,q
 while num:
  d=(den+num-1)//num
  out.append(d)
  num,den=num*d-den,den*d
  g=gcd(num,den);num//=g;den//=g
 return tuple(out)

def test_greedy_vs_oracle_and_roundtrip():
 for p in range(1,60):
  for q in range(p+1,60):
   if max(_greedy_oracle(p,q))>10**12:continue
   g=m.greedy_egyptian(p,q)
   assert g==_greedy_oracle(p,q)
   assert m.unit_sum(g)==Fr(p,q) and list(g)==sorted(set(g)) and m.greedy_egyptian_length(p,q)==len(g)
   assert m.is_egyptian_decomposition(p,q,g) is True

def test_engel_product_oracle():
 for p in range(1,40):
  for q in range(p+1,40):
   e=m.engel_expansion(p,q)
   acc=Fr(0)
   prod=Fr(1)
   for d in e:prod*=d;acc+=1/prod
   assert acc==Fr(p,q) and list(e)==sorted(e)

def test_harmonic_oracle_and_relations():
 from math import lcm
 for n in range(0,60):
  L=1
  for k in range(1,n+1):L=lcm(L,k)
  assert m.harmonic_number(n)==Fr(sum(L//k for k in range(1,n+1)),L)
 for lo in range(1,30):
  for hi in range(lo,30):assert m.harmonic_range_sum(lo,hi)==m.harmonic_number(hi)-m.harmonic_number(lo-1)
 assert m.harmonic_number(400).denominator.bit_length()>0

def test_sylvester_telescoping_identity():
 # sum of reciprocals of the first n Sylvester terms is 1 - 1/(a_n - 1)
 a=2
 for n in range(1,7):
  assert m.sylvester_sequence(n)[-1]==a
  a=a*(a-1)+1
  assert m.sylvester_partial_sum(n)==1-Fr(1,a-1)
 assert m.sylvester_sequence(6)[-1]<10**12

def test_caps_at_cap_and_cap_plus_one():
 assert m.sylvester_sequence(6)[-1]==3263443
 bad('sylvester_sequence',(7,),'bad_value:n_range');bad('sylvester_sequence',(-1,),'bad_value:n_range')
 bad('sylvester_sequence',(10**12+1,),'bad_value:n_abs')
 m.harmonic_number(400);bad('harmonic_number',(401,),'bad_value:n_range');bad('harmonic_number',(0-1,),'bad_value:n_range')
 m.harmonic_range_sum(1,400);bad('harmonic_range_sum',(0,400),'bad_value:lo_range');bad('harmonic_range_sum',(1,401),'bad_value:hi_range')
 assert m.greedy_egyptian(1,1000000)==(1000000,);bad('greedy_egyptian',(1000001,1000002),'bad_value:p_range');bad('greedy_egyptian',(1,1000001),'bad_value:q_range')
 bad('greedy_egyptian',(0,7),'bad_value:p_range');bad('greedy_egyptian',(7,0),'bad_value:q_range')
 m.unit_sum(tuple([10**12]*20));bad('unit_sum',(tuple([10**12]*21),),'bad_value:terms_length')
 bad('unit_sum',(((10**12+1,),)),'bad_value:terms_0_abs');bad('unit_sum',(((1,),)),'bad_value:terms_0_range');m.unit_sum((2,))
 # denominator cap refusal: greedy for 5/121 needs 873865157713; for 1806/1807 the 7th term is 1807*1806*... > 10**12
 bad('greedy_egyptian',(5,121),'bad_value:denominator_cap')
 assert m.greedy_egyptian(1805,1806)==(2,3,7,43)

def test_type_refusals():
 for fn,args in ((m.harmonic_number,(4,)),(m.sylvester_sequence,(3,))):
  with pytest.raises(ValueError,match='bad_type:bool_n$'):fn(True)
  with pytest.raises(ValueError,match='bad_type:n$'):fn(I(4));fn(Fr(4));fn('4');fn(None)
 bad('greedy_egyptian',(True,6),'bad_type:bool_p');bad('greedy_egyptian',(5,True),'bad_type:bool_q')
 bad('greedy_egyptian',(I(5),6),'bad_type:p');bad('greedy_egyptian',(5,'6'),'bad_type:q')
 bad('harmonic_range_sum',(1.5,4),'bad_type:lo');bad('harmonic_range_sum',(1,None),'bad_type:hi')
 bad('unit_sum',([2,3],),'bad_type:terms');bad('unit_sum',(True,),'bad_type:bool_terms')
 bad('unit_sum',(((I(2),),)),'bad_type:terms_0');bad('unit_sum',(((2,True),)),'bad_type:bool_terms_1')
 bad('is_egyptian_decomposition',(5,6,[2,3]),'bad_type:terms');bad('is_egyptian_decomposition',(5,6,(2,Fr(3))),'bad_type:terms_1')

def test_relations():
 bad('greedy_egyptian',(6,6),'bad_relation:not_proper');bad('greedy_egyptian',(7,6),'bad_relation:not_proper')
 bad('harmonic_range_sum',(5,4),'bad_relation:range_order')
 bad('is_egyptian_decomposition',(1,2,(2,2)),'bad_relation:dup_terms')
 bad('is_egyptian_decomposition',(6,6,(2,)),'bad_relation:not_proper')
 assert m.is_egyptian_decomposition(1,2,(2,)) is True

def test_mixed_invalid_phase_order():
 # every argument type precedes every argument value
 bad('greedy_egyptian',(0,True),'bad_type:bool_q');bad('greedy_egyptian',(0,7),'bad_value:p_range')
 bad('harmonic_range_sum',(0,'x'),'bad_type:hi');bad('harmonic_range_sum',(5,4),'bad_relation:range_order')
 bad('is_egyptian_decomposition',(0,7,'x'),'bad_type:terms');bad('is_egyptian_decomposition',(0,7,(2,)),'bad_value:p_range')
 # within terms: all element types precede all element values
 bad('unit_sum',(((1,'x'),)),'bad_type:terms_1');bad('unit_sum',(((1,2),)),'bad_value:terms_0_range')
 # relation after all values
 bad('is_egyptian_decomposition',(1,2,(2,2)),'bad_relation:dup_terms')
 bad('is_egyptian_decomposition',(7,7,(2,2)),'bad_relation:not_proper')

def test_output_freshness():
 a=m.greedy_egyptian(5,6);b=m.greedy_egyptian(5,6)
 assert a==b and a is not b
 c=m.sylvester_sequence(6);d=m.sylvester_sequence(6)
 assert c==d and c is not d
 e=m.engel_expansion(5,6);f=m.engel_expansion(5,6)
 assert e==f and e is not f

def test_survivor_pins_second_pass():
 # scalar just under the abs cap hits range, not abs: kills the abs-cmp boundary in _vals
 bad('harmonic_number',(10**12,),'bad_value:n_range')
 # sylvester_partial_sum value refusals mirror sylvester_sequence
 bad('sylvester_partial_sum',(7,),'bad_value:n_range');bad('sylvester_partial_sum',(-1,),'bad_value:n_range');bad('sylvester_partial_sum',(True,),'bad_type:bool_n')
 # is_egyptian_decomposition full terms refusal ladder
 bad('is_egyptian_decomposition',(5,6,(2,)*21),'bad_value:terms_length')
 bad('is_egyptian_decomposition',(5,6,(2,True)),'bad_type:bool_terms_1')
 bad('is_egyptian_decomposition',(5,6,(2,I(3))),'bad_type:terms_1')
 bad('is_egyptian_decomposition',(5,6,((10**12+1),)),'bad_value:terms_0_abs')
 bad('is_egyptian_decomposition',(5,6,(1,)),'bad_value:terms_0_range')
 assert m.is_egyptian_decomposition(1,10**6,(10**6,)) is True
 # egyptian_remainder refusal ladder
 bad('egyptian_remainder',(True,6,()),'bad_type:bool_p');bad('egyptian_remainder',(5,'6',()),'bad_type:q')
 bad('egyptian_remainder',(5,6,[2]),'bad_type:terms');bad('egyptian_remainder',(5,6,True),'bad_type:bool_terms')
 bad('egyptian_remainder',(0,6,()),'bad_value:p_range');bad('egyptian_remainder',(5,0,()),'bad_value:q_range')
 bad('egyptian_remainder',(6,6,()),'bad_relation:not_proper')
 bad('egyptian_remainder',(5,6,(2,)*21),'bad_value:terms_length')
 bad('egyptian_remainder',(5,6,(2,True)),'bad_type:bool_terms_1');bad('egyptian_remainder',(5,6,(2,I(3))),'bad_type:terms_1')
 bad('egyptian_remainder',(5,6,((10**12+1),)),'bad_value:terms_0_abs');bad('egyptian_remainder',(5,6,(1,)),'bad_value:terms_0_range')
 assert m.egyptian_remainder(5,6,(10**12,))==Fr(5,6)-Fr(1,10**12)
 # element types before element values in the inline validators
 bad('is_egyptian_decomposition',(5,6,(1,'x')),'bad_type:terms_1')
 bad('egyptian_remainder',(5,6,(1,'x')),'bad_type:terms_1')
 bad('is_egyptian_decomposition',(5,6,(1,2)),'bad_value:terms_0_range')

def test_survivor_pins_third_pass():
 # empty and exactly-20 terms stay valid: kills lower-bound and upper-bound length mutants
 assert m.is_egyptian_decomposition(1,2,()) is False and m.egyptian_remainder(1,2,())==Fr(1,2)
 assert m.is_egyptian_decomposition(1,2,tuple(range(2,22))) is False and len(tuple(range(2,22)))==20
 assert m.egyptian_remainder(1,2,tuple(range(2,22)))==Fr(1,2)-m.unit_sum(tuple(range(2,22)))
 # denominator exactly 10**12 accepted: kills the abs-cmp boundary in the inline validators
 assert m.is_egyptian_decomposition(1,2,(10**12,)) is False
 # sylvester_partial_sum and egyptian_remainder lower bounds
 assert m.sylvester_partial_sum(0)==0
 assert m.egyptian_remainder(1,2,(3,))==Fr(1,6)

def test_rev1_auditor32_pins():
 # refusal attribution: the length function owns its expansion refusals
 bad('greedy_egyptian_length',(5,121),'bad_value:denominator_cap')
 bad('greedy_egyptian',(5,121),'bad_value:denominator_cap')
 # live Engel length guard
 bad('engel_expansion',(999999,1000000),'bad_value:expansion_long')
 # all entry types precede scalar values and relations in the three-argument functions
 for fn in ('is_egyptian_decomposition','egyptian_remainder'):
  bad(fn,(0,7,('bad',)),'bad_type:terms_0')
  bad(fn,(7,7,('bad',)),'bad_type:terms_0')
  bad(fn,(0,7,(2,)),'bad_value:p_range')
  bad(fn,(7,7,(2,)),'bad_relation:not_proper')
 # unit_sum is a plain sum: duplicates accepted, only is_egyptian_decomposition enforces distinctness
 assert m.unit_sum((2,2))==1
