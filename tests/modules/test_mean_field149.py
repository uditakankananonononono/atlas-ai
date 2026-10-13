import copy
import itertools
import math
import pytest
from app.modules.m12_ai_research_lab.mean_field149 import approximate


def reference_kl(weights,q):
    raw=[math.exp(w-max(weights)) for w in weights];z=sum(raw);kl=0
    for state,p in zip(itertools.product((0,1),repeat=len(q)),raw):
        v=math.prod(q[j] if bit else 1-q[j] for j,bit in enumerate(state))
        kl+=v*math.log(v/(p/z))
    return kl


def test_independent_joint_exact_posterior_probabilities_and_elbo_units():
    weights=[0,math.log(3),math.log(2),math.log(6)];initial=[.2,.8];before=copy.deepcopy((weights,initial))
    r=approximate(weights,initial)
    assert r['binary_probabilities']==pytest.approx([2/3,3/4],abs=1e-12)
    assert r['log_normalizer']==pytest.approx(math.log(12))
    assert r['elbo']==pytest.approx(math.log(12)) and r['reverse_kl']==pytest.approx(0,abs=1e-12)
    assert r['converged_by_probability_change'] and r['sweeps']==2
    assert (weights,initial)==before and r['units']=='natural-log probability units (nats)'
    assert not r['global_optimum_verified'] and not r['supplied_joint_truth_verified']
    assert not r['posterior_model_execution_performed'] and r['external_effects']==[]


def test_coupled_joint_one_sweep_sequential_coordinate_hand_reference():
    weights=[0,1,2,5];r=approximate(weights,[.25,.75],1,1e-12)
    first=1/(1+math.exp(-3.5));second=1/(1+math.exp(-(1+2*first)))
    assert r['binary_probabilities']==pytest.approx([first,second],abs=1e-14)
    assert r['reverse_kl']==pytest.approx(reference_kl(weights,[first,second]),abs=1e-12)
    assert len(r['elbo_history'])==2 and not r['converged_by_probability_change'] and r['sweeps']==1
    assert r['elbo_history'][1]>=r['elbo_history'][0]


def test_correlated_posterior_approximation_not_exact_and_weight_shift_invariance():
    weights=[1,-2,0,3];r=approximate(weights,[.4,.6]);shifted=approximate([v+5 for v in weights],[.4,.6])
    assert r['reverse_kl']>0 and r['reverse_kl']==pytest.approx(reference_kl(weights,r['binary_probabilities']))
    assert shifted['binary_probabilities']==pytest.approx(r['binary_probabilities'])
    assert shifted['reverse_kl']==pytest.approx(r['reverse_kl'])
    assert shifted['elbo']==pytest.approx(r['elbo']+5)
    assert all(b>=a-1e-12 for a,b in zip(r['elbo_history'],r['elbo_history'][1:]))


@pytest.mark.parametrize('n',[1,7,8,9])
def test_dimension_cap(n):
    if n<=8:assert approximate([0]*(2**n),[.4]*n)['binary_probabilities']==[.5]*n
    else:
        with pytest.raises(ValueError,match='^1..8 initial binary probabilities before scan$'):approximate([0]*(2**n),[.4]*n)


@pytest.mark.parametrize('value',[-100,100,-100.0,100.0])
def test_log_weight_edges_and_stable_extreme_sigmoid(value):
    r=approximate([value,-value],[.5]);assert all(math.isfinite(v) for v in (r['elbo'],r['reverse_kl'],r['log_normalizer']))
    assert r['binary_probabilities'][0]==pytest.approx(1-1e-15 if value<0 else 1e-15)


@pytest.mark.parametrize('bad',[True,'1',None,-100.01,100.01,float('nan'),float('inf')])
def test_bad_weights(bad):
    with pytest.raises(ValueError,match='^strict finite log weights within -100..100$'):approximate([0,bad],[.5])


@pytest.mark.parametrize('bad',[True,'1',None,0,1,-1,float('nan')])
def test_bad_initial_probabilities(bad):
    with pytest.raises(ValueError,match='^strict finite initial probabilities inside zero and one$'):approximate([0,1],[bad])


@pytest.mark.parametrize('cap',[1,999,1000,1001,0,True,1.0,'1'])
def test_sweep_cap_menu(cap):
    if type(cap) is int and 1<=cap<=1000:assert approximate([0,0],[.5],cap)['sweeps']==1
    else:
        with pytest.raises(ValueError,match='^strict 1..1000 sweep cap$'):approximate([0,0],[.5],cap)


@pytest.mark.parametrize('tolerance',[1e-12,1,1.0,0,1e-13,1.01,True,'1',float('nan')])
def test_tolerance_menu(tolerance):
    if type(tolerance) in (int,float) and 1e-12<=tolerance<=1:approximate([0,0],[.5],tolerance=tolerance)
    else:
        with pytest.raises(ValueError,match='^strict finite tolerance within 1e-12..1$'):approximate([0,0],[.5],tolerance=tolerance)


def test_shapes_and_empty_refusals():
    for bad in ([],(),None,True):
        with pytest.raises(ValueError,match='^1..8 initial binary probabilities before scan$'):approximate([0,0],bad)
    for bad in ([],[0],[0,0,0],(0,0),None):
        with pytest.raises(ValueError,match='^exact binary log weight table size$'):approximate(bad,[.5])


def test_negative_coordinate_update_unclamped_sigmoid_and_last_elbo_exact():
    # Lexicographic weights00=0,01=-1,10=-2,11=-4.
    # Starting q1=1/2 gives coordinate0 delta=-5/2.
    # Sequential coordinate1 delta=-1-q0, still moderately negative.
    weights=[0,-1,-2,-4]
    r=approximate(weights,[.4,.5],max_sweeps=1,tolerance=1e-12)
    first=math.exp(-2.5)/(1+math.exp(-2.5))
    second=math.exp(-1-first)/(1+math.exp(-1-first))
    assert r['binary_probabilities']==pytest.approx([first,second],abs=1e-14)
    assert all(1e-3<p<.5 for p in r['binary_probabilities'])
    assert r['elbo']==r['elbo_history'][-1]
    assert abs(r['elbo_history'][-1]-r['elbo_history'][-2])>0.1
    assert r['reverse_kl']==pytest.approx(reference_kl(weights,[first,second]),abs=1e-12)
