import pytest
from app.modules.m12_ai_research_lab.lane_workflows import StepContext
from app.modules.m12_ai_research_lab.lane_models import ModelProfile
def C(): return StepContext("r","s",None,{},{})
BAD=[(float("nan"),1),(1,float("nan")),(float("inf"),0),(0,float("inf")),(True,1),(1,False),(1.5,2),(2,1.5),(-1,0),(0,-1),("3",1),(None,1)]
@pytest.mark.parametrize("a",BAD)
def test_bad_usage_rejected_and_state_unchanged(a):
    c=C()
    with pytest.raises((ValueError,TypeError)): c.record_usage(*a)
    assert (c.input_tokens,c.output_tokens)==(0,0)
def test_second_bad_arg_does_not_partially_apply():
    c=C(); c.record_usage(5,7)
    with pytest.raises((ValueError,TypeError)): c.record_usage(3,float("nan"))
    assert (c.input_tokens,c.output_tokens)==(5,7)
def test_valid_and_zero_usage_accumulates():
    c=C(); c.record_usage(0,0); c.record_usage(10,20); c.record_usage(1,2)
    assert (c.input_tokens,c.output_tokens)==(11,22)
