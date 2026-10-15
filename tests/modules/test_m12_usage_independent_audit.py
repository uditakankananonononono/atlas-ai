import itertools
import pytest
from app.modules.m12_ai_research_lab.lane_workflows import StepContext

def ctx():return StepContext('r','s',None,{}, {})
def test_validation_grid_and_atomicity():
 vals=[0,1,7,10**50,-1,-10,True,False,1.0,.5,float('nan'),float('inf'),float('-inf'),'1',None,[],{}]
 count=0
 for a,b in itertools.product(vals,repeat=2):
  c=ctx();c.record_usage(5,9)
  if type(a) is int and type(b) is int and a>=0 and b>=0:
   c.record_usage(a,b);assert (c.input_tokens,c.output_tokens)==(5+a,9+b)
  else:
   with pytest.raises(ValueError):c.record_usage(a,b)
   assert (c.input_tokens,c.output_tokens)==(5,9)
  count+=1
 assert count==289

def test_exact_integer_types_and_addition_not_assignment():
 class I(int):pass
 c=ctx()
 with pytest.raises(ValueError):c.record_usage(I(1),0)
 c.record_usage(3,7);c.record_usage(2,8);assert (c.input_tokens,c.output_tokens)==(5,15)
