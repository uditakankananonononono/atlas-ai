import copy
import math
from fractions import Fraction
import pytest
from app.modules.m12_ai_research_lab.inverse_bandit164 import infer


def test_nonuniform_hand_reference_rewards_probability_reconstruction_and_no_mutation():
    counts=[1,3,0];before=copy.deepcopy(counts);r=infer(counts,2,1)
    assert r['smoothed_probabilities_fraction']==['2/7','4/7','1/7']
    assert r['relative_rewards']==pytest.approx([0,2*math.log(2),-2*math.log(2)])
    assert r['reconstructed_action_probabilities']==pytest.approx([2/7,4/7,1/7])
    assert r['reference_action']==0 and r['reference_reward']==0
    assert r['temperature']==2 and r['pseudocount']==1
    assert not r['true_objective_identified'] and not r['sequential_dynamics_modeled']
    assert not r['demonstration_provenance_verified'] and r['external_effects']==[] and counts==before


def test_fractional_smoothing_temperature_scale_and_permutation_reference():
    r=infer([0,1,4],.5,.25)
    assert r['smoothed_probabilities_fraction']==['1/23','5/23','17/23']
    assert r['relative_rewards']==pytest.approx([0,.5*math.log(5),.5*math.log(17)])
    scaled=infer([0,1,4],1,.25)
    assert scaled['relative_rewards']==pytest.approx([2*v for v in r['relative_rewards']])
    assert scaled['reconstructed_action_probabilities']==pytest.approx(r['reconstructed_action_probabilities'])
    permuted=infer([4,1,0],.5,.25)
    assert permuted['relative_rewards']==pytest.approx([0,.5*math.log(5/17),.5*math.log(1/17)])


@pytest.mark.parametrize('n',[1,2,19,20,21])
def test_action_caps(n):
    if 2<=n<=20:
        r=infer([1]*n,1,1);assert r['relative_rewards']==[0]*n
        assert r['smoothed_probabilities_fraction']==[str(Fraction(1,n))]*n
    else:
        with pytest.raises(ValueError,match='^2..20 action counts before scan$'):infer([1]*n,1,1)


@pytest.mark.parametrize('count',[0,999999,1000000])
def test_count_boundaries(count):
    r=infer([1,count],1,1);assert r['smoothed_probabilities_fraction']==[str(Fraction(2,count+3)),str(Fraction(count+1,count+3))]


@pytest.mark.parametrize('value',[.000001,999,1000,1000.0])
def test_temperature_pseudocount_edges(value):
    for t,p in ((value,1),(1,value)):
        r=infer([0,1000000],t,p)
        assert all(math.isfinite(v) for v in r['relative_rewards'])
        assert r['reconstructed_action_probabilities']==pytest.approx([float(Fraction(x)) for x in r['smoothed_probabilities_fraction']],abs=1e-12)
        assert r['temperature']==t and r['pseudocount']==p


def test_strict_bounds_types_shapes_and_empty_demonstrations():
    for bad in (True,1.0,'1',None,-1,1000001):
        with pytest.raises(ValueError,match='^strict integer action count 0..1000000$'):infer([1,bad],1,1)
    for bad in (True,'1',None,0,.0000009,1001,float('nan'),float('inf')):
        with pytest.raises(ValueError,match='^strict finite temperature 1e-6..1000$'):infer([0,1],bad,1)
        with pytest.raises(ValueError,match='^strict finite pseudocount 1e-6..1000$'):infer([0,1],1,bad)
    with pytest.raises(ValueError,match='^at least one demonstrated action$'):infer([0,0],1,1)
    for bad in ([],(),None,True):
        with pytest.raises(ValueError,match='^2..20 action counts before scan$'):infer(bad,1,1)
