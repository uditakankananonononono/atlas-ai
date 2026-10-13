import copy
import math
import pytest
from app.modules.m12_ai_research_lab.policy_step161 import update


def test_asymmetric_nonuniform_hand_reference_all_gradient_terms_and_no_mutation():
    logits=[0,math.log(2),math.log(3)];samples=[dict(action=0,advantage=3),dict(action=2,advantage=-1)]
    before=copy.deepcopy((logits,samples));r=update(logits,samples,.2)
    assert r['old_probabilities']==pytest.approx([1/6,1/3,1/2])
    assert r['gradient']==pytest.approx([4/3,-1/3,-1])
    expected=[4/15,math.log(2)-1/15,math.log(3)-1/5]
    assert r['updated_logits']==pytest.approx(expected)
    masses=[math.exp(x) for x in expected];total=sum(masses)
    assert r['new_probabilities']==pytest.approx([x/total for x in masses])
    assert r['sample_surrogate_before']==pytest.approx((3*math.log(1/6)-math.log(1/2))/2)
    assert r['sample_surrogate_after']==pytest.approx((3*(expected[0]-math.log(total))-(expected[2]-math.log(total)))/2)
    assert (logits,samples)==before and abs(sum(r['gradient']))<1e-14
    assert not r['environment_return_improvement_verified'] and not r['on_policy_sampling_verified']
    assert not r['environment_execution_performed'] and r['external_effects']==[]


def test_zero_advantage_no_update_and_positive_negative_action_direction():
    assert update([0,0],[dict(action=0,advantage=0)],1)['updated_logits']==[0,0]
    positive=update([0,0],[dict(action=0,advantage=2)],.1)
    negative=update([0,0],[dict(action=0,advantage=-2)],.1)
    assert positive['updated_logits']==pytest.approx([.1,-.1])
    assert negative['updated_logits']==pytest.approx([-.1,.1])
    assert positive['new_probabilities'][0]>.5 and negative['new_probabilities'][0]<.5


def test_shift_invariance_repeated_samples_and_extreme_log_softmax():
    samples=[dict(action=0,advantage=-1000),dict(action=1,advantage=1000)]
    r=update([-100,100],samples,1)
    assert all(math.isfinite(r[k]) for k in ('sample_surrogate_before','sample_surrogate_after'))
    a=update([1,2],samples,.01);b=update([4,5],samples*3,.01)
    assert a['gradient']==pytest.approx(b['gradient'])
    assert a['new_probabilities']==pytest.approx(b['new_probabilities'])


@pytest.mark.parametrize('n',[1,2,19,20,21])
def test_action_count_caps(n):
    if 2<=n<=20:assert len(update([0]*n,[dict(action=n-1,advantage=1)],.1)['gradient'])==n
    else:
        with pytest.raises(ValueError,match='^2..20 action logits before scan$'):update([0]*n,[dict(action=0,advantage=1)],.1)


@pytest.mark.parametrize('n',[0,1,999,1000,1001])
def test_sample_count_caps(n):
    samples=[dict(action=0,advantage=1)]*n
    if 1<=n<=1000:assert update([0,0],samples,.1)['gradient']==pytest.approx([.5,-.5])
    else:
        with pytest.raises(ValueError,match='^1..1000 action samples before scan$'):update([0,0],samples,.1)


@pytest.mark.parametrize('value',[-100,100,-100.0,100.0])
def test_logits_edges(value):assert update([value,0],[dict(action=0,advantage=1)],1)['gradient']
@pytest.mark.parametrize('value',[-1000,1000,-1000.0,1000.0])
def test_advantage_edges(value):assert update([0,0],[dict(action=0,advantage=value)],1)['gradient']==pytest.approx([value/2,-value/2])
@pytest.mark.parametrize('rate',[1,1.0,1e-12])
def test_rate_acceptance(rate):assert update([0,0],[dict(action=0,advantage=2)],rate)['updated_logits']==pytest.approx([rate,-rate])


def test_strict_numerics_and_schema_refusals():
    for bad in (True,'1',None,-101,101,float('nan'),float('inf')):
        with pytest.raises(ValueError,match='^strict finite logits within -100..100$'):update([bad,0],[dict(action=0,advantage=1)],.1)
    for bad in (True,'1',None,-1001,1001,float('nan'),float('inf')):
        with pytest.raises(ValueError,match='^strict finite advantage within -1000..1000$'):update([0,0],[dict(action=0,advantage=bad)],.1)
    for bad in (True,'1',None,0,-1,1.01,float('nan')):
        with pytest.raises(ValueError,match='^strict finite learning rate inside zero through one$'):update([0,0],[dict(action=0,advantage=1)],bad)
    for bad in (True,0.0,'0',None,-1,2):
        with pytest.raises(ValueError,match='^strict action index in policy$'):update([0,0],[dict(action=bad,advantage=1)],.1)
    for bad in ({'action':0,'wrong':1},{},[],None):
        with pytest.raises(ValueError,match='^exact action/advantage fields$'):update([0,0],[bad],.1)
    for bad in ((),None,True):
        with pytest.raises(ValueError,match='^2..20 action logits before scan$'):update(bad,[dict(action=0,advantage=1)],.1)
        with pytest.raises(ValueError,match='^1..1000 action samples before scan$'):update([0,0],bad,.1)
