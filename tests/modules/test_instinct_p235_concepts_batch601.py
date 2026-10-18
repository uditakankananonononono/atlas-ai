import random,sys
from fractions import Fraction
import pytest
sys.path.insert(0,'backend')
from app.modules.instinct_doc import p235_concepts_batch601 as m

class I(int):pass
class S(str):pass
def naive_lru(refs,cap):
 st=[];h=0
 for x in refs:
  if x in st:h+=1;st.remove(x);st.insert(0,x)
  else:
   st.insert(0,x)
   if len(st)>cap:st.pop()
 return h,tuple(st)
def naive_fifo(refs,cap):
 st=[];h=0
 for x in refs:
  if x in st:h+=1
  else:
   st.append(x)
   if len(st)>cap:st.pop(0)
 return h,tuple(st)
def naive_lru_log(refs,cap):
 st=[];out=[]
 for x in refs:
  if x in st:st.remove(x);st.insert(0,x)
  else:
   st.insert(0,x)
   if len(st)>cap:out.append(st.pop())
 return tuple(out)
def naive_fifo_log(refs,cap):
 st=[];out=[]
 for x in refs:
  if x not in st:
   st.append(x)
   if len(st)>cap:out.append(st.pop(0))
 return tuple(out)
def naive_lfu_log(refs,cap):
 fr={};us={};out=[]
 for t,x in enumerate(refs):
  if x in fr:fr[x]+=1;us[x]=t
  else:
   if len(fr)==cap:
    v=min(fr,key=lambda k:(fr[k],us[k]));out.append(v);del fr[v];del us[v]
   fr[x]=1;us[x]=t
 return tuple(out)
def naive_min(refs,cap):
 cache=[];h=0;ev=[]
 for t,x in enumerate(refs):
  if x in cache:h+=1;continue
  if len(cache)==cap:
   def nxt(k):
    try:return refs.index(k,t+1)
    except ValueError:return len(refs)+1
   v=max(cache,key=lambda k:(nxt(k),k));cache.remove(v);ev.append(v)
  cache.append(x)
 return h,tuple(ev)
def raises(pat,fn,*a):
 with pytest.raises(ValueError,match=pat):fn(*a)

def test_scope_and_not_claimed_exact_text():
 assert m.SCOPE=='PARTIAL exact deterministic cache replacement simulation over supplied bounded reference strings with recount certificates'
 assert m.NOT_CLAIMED==('AGI-like intelligence','hardware cache fidelity','optimality beyond exact Belady recomputation','production readiness')

def test_registry_guard_both_branches():
 src=open('backend/app/modules/instinct_doc/p235_concepts_batch601.py').read()
 assert "except ModuleNotFoundError as exc:" in src
 assert "exc.name != 'app.modules.instinct_doc.p235_concepts_registry'" in src
 assert "find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None" in src
 with pytest.raises(ValueError,match=r'^P235:zzz:qqq$'):m.make_fail('zzz')('qqq')

def test_refs_type_cap_and_element_rules():
 for bad in ([1,2],'12',1,None,{1:1}):
  raises(r'^P235:lru_simulate:bad_type:refs$',m.lru_simulate,bad,1)
 assert m.lru_simulate(tuple([0]*256),1)==(255,(0,)) # cap OK
 raises(r'^P235:lru_simulate:bad_value:refs$',m.lru_simulate,tuple([0]*257),1)
 for bad in (True,Fraction(1),I(1),'1',S('1'),None,1.5):
  raises(r'^P235:lru_simulate:bad_type:refs element$',m.lru_simulate,(1,bad),1)
 raises(r'^P235:lru_simulate:bad_value:refs element$',m.lru_simulate,(1,64),1)
 raises(r'^P235:lru_simulate:bad_value:refs element$',m.lru_simulate,(1,-1),1)
 assert m.lru_simulate((0,63),2)==(0,(63,0))

def test_cap_rules_and_argument_order():
 for bad in (True,Fraction(1),I(1),'1',None,1.0):
  raises(r'^P235:lru_simulate:bad_type:cap$',m.lru_simulate,(1,),bad)
 raises(r'^P235:lru_simulate:bad_value:cap$',m.lru_simulate,(1,),0)
 raises(r'^P235:lru_simulate:bad_value:cap$',m.lru_simulate,(1,),9)
 assert m.lru_simulate((1,2),8)==(0,(2,1)) # cap max OK
 raises(r'^P235:lru_simulate:bad_type:refs$',m.lru_simulate,'ab','x') # container phase beats scalar
 raises(r'^P235:lru_simulate:bad_value:refs element$',m.lru_simulate,(99,),-1) # element range beats cap value

def test_lru_fifo_simulate_values_and_checks():
 assert m.lru_simulate((),1)==(0,())
 assert m.lru_simulate((1,2,3,1,2,4,1),2)==(0,(1,4))
 assert m.lru_simulate((1,2,1,3,1),2)==(2,(1,3))
 assert m.fifo_simulate((1,2,3,1,2,4,1),2)==(0,(4,1))
 assert m.fifo_simulate((1,2,1,3,1),2)==(1,(3,1)) # fifo does not reorder on hit
 r=m.lru_simulate((1,2,1,3,1),2)
 assert r==(2,(1,3))
 assert type(r[0]) is int and type(r[1]) is tuple and all(type(x) is int for x in r[1])
 assert m.lru_check((1,2,1,3,1),2,(2,(1,3))) is True
 assert m.lru_check((1,2,1,3,1),2,(3,(3,1))) is False
 assert m.lru_check((1,2,1,3,1),2,(3,(1,3))) is False
 assert m.fifo_check((1,2,1,3,1),2,(1,(3,1))) is True
 assert m.fifo_check((1,2,1,3,1),2,(1,(1,3))) is False
 raises(r'^P235:lru_check:bad_shape:cert$',m.lru_check,(1,),1,(1,2,3))
 raises(r'^P235:lru_check:bad_type:cert$',m.lru_check,(1,),1,[3,(1,)])
 raises(r'^P235:lru_check:bad_type:cert hits$',m.lru_check,(1,),1,(True,(1,)))
 raises(r'^P235:lru_check:bad_value:cert hits$',m.lru_check,(1,),1,(-1,(1,)))
 raises(r'^P235:lru_check:bad_type:cert state$',m.lru_check,(1,),1,(1,[1]))
 raises(r'^P235:lru_check:bad_value:cert state$',m.lru_check,(1,2),1,(0,(1,2))) # state longer than cap
 raises(r'^P235:lru_check:bad_type:cert state element$',m.lru_check,(1,),1,(0,(True,)))
 raises(r'^P235:lru_check:bad_value:cert state element$',m.lru_check,(1,),1,(0,(64,)))

def test_lfu_simulate_and_check_tiebreaks():
 assert m.lfu_simulate((),1)==(0,())
 assert m.lfu_simulate((1,2,1,3,1,2,4),2)==(2,((1,3),(4,1)))
 assert m.lfu_simulate((1,2,3),1)==(0,((3,1),)) # every miss evicts
 assert m.lfu_simulate((1,1,2,2,3),2)==(2,((2,2),(3,1))) # freq tie: least-recently-used 1 evicted
 st=m.lfu_simulate((1,1,2,2,3),2)
 assert m.lfu_check((1,1,2,2,3),2,st) is True
 assert m.lfu_check((1,2,1,3,1,2,4),2,(2,((1,3),(4,1)))) is True
 raises(r'^P235:lfu_check:bad_value:cert state order$',m.lfu_check,(1,2),2,(0,((2,1),(1,1))))
 raises(r'^P235:lfu_check:bad_value:cert state duplicate$',m.lfu_check,(1,2),2,(0,((1,1),(1,2))))
 raises(r'^P235:lfu_check:bad_shape:cert state entry$',m.lfu_check,(1,),1,(0,((1,1,1),)))
 raises(r'^P235:lfu_check:bad_type:cert state entry$',m.lfu_check,(1,),1,(0,((True,1),)))
 raises(r'^P235:lfu_check:bad_value:cert state entry$',m.lfu_check,(1,),1,(0,((1,0),)))
 raises(r'^P235:lfu_check:bad_value:cert state entry$',m.lfu_check,(1,),1,(0,((64,1),)))

def test_belady_min_and_check_optimality_witness():
 refs=(1,2,3,4,1,2,5,1,2,3,4,5)
 assert m.belady_min(refs,3)==(5,(3,4,2,3)) # classic OPT hit count, tie-break larger key
 assert m.belady_min((),2)==(0,())
 assert m.belady_min((1,2,1,3,1,2,4),2)==(2,(2,3,2)) # furthest-next-use, ties to larger key
 assert m.belady_min((1,2,3,4),2)==(0,(2,3)) # no reuse: larger resident key evicted each time
 assert m.belady_check(refs,3,(5,(3,4,2,3))) is True
 assert m.belady_check(refs,3,(5,(3,4,2))) is False # truncated eviction log
 assert m.belady_check(refs,3,(6,(3,4,2,3))) is False # hit count beyond optimal
 assert m.belady_check(refs,3,(5,(3,4,2,9))) is False
 raises(r'^P235:belady_check:bad_shape:cert$',m.belady_check,refs,3,(5,))
 raises(r'^P235:belady_check:bad_type:cert hits$',m.belady_check,refs,3,(True,(3,)))
 assert m.belady_check(refs,3,(5,(3,4,1,2))) is False # wrong victims though classic textbook log
 raises(r'^P235:belady_check:bad_value:cert hits$',m.belady_check,refs,3,(-1,(3,)))
 raises(r'^P235:belady_check:bad_type:cert state element$',m.belady_check,refs,3,(5,(3,True)))
 raises(r'^P235:belady_check:bad_value:cert state element$',m.belady_check,refs,3,(5,(3,64)))
 raises(r'^P235:belady_check:bad_value:cert state$',m.belady_check,(1,2),1,(0,(1,2,3))) # evictions longer than refs

def test_eviction_log_and_log_check_policies():
 assert m.eviction_log((1,2,3,1,2,4,1),2,'lru')==(1,2,3,1,2)
 assert m.eviction_log((1,2,3,1,2,4,1),2,'fifo')==(1,2,3,1,2)
 assert m.eviction_log((1,2,1,3,1,2,4),2,'lfu')==(2,3,2)
 assert m.eviction_log((),1,'lru')==()
 assert m.eviction_log((1,1,1),1,'lru')==()
 assert m.log_check((1,2,3,1,2,4,1),2,'lru',(1,2,3,1,2)) is True
 assert m.log_check((1,2,3,1,2,4,1),2,'lru',(1,2,3,2,1)) is False
 assert m.log_check((1,2,1,3,1,2,4),2,'lfu',(2,3,2)) is True
 assert m.log_check((1,2,1,3,1,2,4),2,'lfu',(3,2)) is False
 for bad in (True,1,None,['lru'],I(1)):
  raises(r'^P235:eviction_log:bad_type:policy$',m.eviction_log,(1,),1,bad)
 raises(r'^P235:eviction_log:bad_type:policy$',m.eviction_log,(1,),1,S('lru'))
 raises(r'^P235:eviction_log:bad_value:policy$',m.eviction_log,(1,),1,'clock')
 raises(r'^P235:eviction_log:bad_value:policy$',m.eviction_log,(1,),1,'LRU')
 raises(r'^P235:eviction_log:bad_type:refs$',m.eviction_log,'ab',0,'x') # container phase beats scalars
 raises(r'^P235:eviction_log:bad_type:cap$',m.eviction_log,(1,),'x','clock') # cap type beats policy
 raises(r'^P235:log_check:bad_type:log$',m.log_check,(1,),1,'lru',[1])
 raises(r'^P235:log_check:bad_value:log$',m.log_check,(1,2),1,'lru',(1,2,3))

def test_junk_fuzz_and_cross_identities():
 rng=random.Random(601)
 for _ in range(300):
  n=rng.randint(0,40);refs=tuple(rng.randint(0,5) for _ in range(n));cap=rng.randint(1,4)
  lh,ls=m.lru_simulate(refs,cap);fh,fs=m.fifo_simulate(refs,cap);uh,us=m.lfu_simulate(refs,cap)
  assert (lh,ls)==naive_lru(refs,cap) and (fh,fs)==naive_fifo(refs,cap)
  bh,ev=m.belady_min(refs,cap)
  assert (bh,ev)==naive_min(refs,cap)
  assert bh>=lh and bh>=fh and bh>=uh # MIN dominates every online policy
  assert lh<=n and fh<=n and uh<=n and bh<=n
  assert m.belady_check(refs,cap,(bh,ev)) is True
  for pol,oracle in (('lru',naive_lru_log),('fifo',naive_fifo_log),('lfu',naive_lfu_log)):
   log=m.eviction_log(refs,cap,pol)
   assert m.log_check(refs,cap,pol,log) is True
   assert log==oracle(refs,cap) # independent oracle, not the module's own recompute
   assert len(log)<=n
  assert m.lru_check(refs,cap,(lh,ls)) is True and m.fifo_check(refs,cap,(fh,fs)) is True and m.lfu_check(refs,cap,(uh,us)) is True
 for bad in (True,1.5,'x',None,[1],(1,'a'),(1,64),(1,True)):
  try:m.lru_simulate(bad,1);assert False
  except ValueError:pass
 for badc in (True,'1',None,Fraction(1),0,9,-2):
  try:m.fifo_simulate((1,2),badc);assert False
  except ValueError:pass


def test_boundary63_and_lru_hit_recency_pins():
 assert m.lru_check((63,),1,(0,(63,))) is True # boundary key in cert state
 assert m.lfu_check((63,),1,(0,((63,1),))) is True # boundary key in lfu cert entry
 assert m.eviction_log((63,1,2),2,'fifo')==(63,) # boundary key evicted
 assert m.log_check((63,1,2),2,'fifo',(63,)) is True # boundary key in log
 assert m.fifo_check((63,),1,(0,(63,))) is True # boundary key in fifo cert state
 assert m.eviction_log((1,2,1,3),2,'lru')==(2,) # hit fronts the key: 2 is the next victim
 assert m.log_check((1,2,1,3),2,'lru',(2,)) is True
 assert m.log_check((1,2,1,3),2,'lru',(1,)) is False


def test_cross_argument_global_phase_order():
    # auditor-flagged deviation fixed in rev1: containers in global phases
    # across ALL container args, then scalars positional, then cross-argument
    # constraints; the docstring promises exactly this order.
    raises(r'^P235:log_check:bad_type:log$',m.log_check,(1,2),'x','lru','bad') # the audit example
    raises(r'^P235:log_check:bad_type:log element$',m.log_check,(1,2),1,'nope',(True,)) # log element types beat scalar policy
    raises(r'^P235:log_check:bad_value:log element$',m.log_check,(1,),0,'nope',(99,)) # log element ranges beat scalars
    raises(r'^P235:lru_check:bad_type:cert$',m.lru_check,(1,),0,[0,(1,)]) # cert type beats scalar cap
    raises(r'^P235:lru_check:bad_type:cert hits$',m.lru_check,(1,),0,(True,(1,))) # cert element types beat cap
    raises(r'^P235:lru_check:bad_value:cert hits$',m.lru_check,(1,),0,(-1,(1,))) # cert element ranges beat cap
    raises(r'^P235:lru_check:bad_type:refs element$',m.lru_check,(1,True),0,(0,(1,))) # refs element types beat cap
    raises(r'^P235:log_check:bad_type:refs$',m.log_check,[1],0,'nope','bad') # refs type first across all args
    raises(r'^P235:belady_check:bad_value:cap$',m.belady_check,(1,),0,(0,(1,2,3))) # scalars beat cross-argument constraints
    raises(r'^P235:lfu_check:bad_value:cap$',m.lfu_check,(1,2),0,(0,((1,1),(1,2)))) # scalars beat uniqueness/order constraints
    raises(r'^P235:lru_check:bad_value:refs element$',m.lru_check,(99,),0,(0,(64,))) # refs ranges positional before cert state ranges
    assert m.lru_check((0,)*256,1,(0,())) is False # REF_MAX boundary accepted
    raises(r'^P235:lru_check:bad_value:refs$',m.lru_check,(0,)*257,1,(0,())) # REF_MAX+1 refused
    assert m.log_check((0,)*256,1,'lru',()) is True # REF_MAX boundary accepted
    raises(r'^P235:log_check:bad_value:refs$',m.log_check,(0,)*257,1,'lru',()) # REF_MAX+1 refused
