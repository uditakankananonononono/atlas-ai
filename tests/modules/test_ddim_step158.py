import copy
import math
import pytest
from app.modules.m12_ai_research_lab.ddim_step158 import step


def test_asymmetric_image_hand_reference_no_clipping_and_no_mutation():
    image=[[1,-2],[.5,4]];noise=[[2,-1],[0,3]];before=copy.deepcopy((image,noise))
    r=step(image,noise,.25,.81)
    expected=[[2-2*math.sqrt(3),-4+math.sqrt(3)],[1,8-3*math.sqrt(3)]]
    for actual,want in zip(r['predicted_clean_image'],expected):assert actual==pytest.approx(want,abs=1e-14)
    for actual,x0,eps in zip(r['previous_image'],expected,noise):
        assert actual==pytest.approx([.9*x+math.sqrt(.19)*e for x,e in zip(x0,eps)],abs=1e-14)
    assert (image,noise)==before and not r['clipping_performed']
    assert not r['denoiser_execution_performed'] and not r['high_quality_image_verified']
    assert not r['trained_diffusion_model_used'] and r['external_effects']==[] and r['eta']==0


def test_forward_synthetic_noise_recovers_declared_clean_image_and_final_step():
    x0=[[2,-3,.2]];eps=[[1,4,-2]];alpha=.36
    xt=[[.6*x+.8*e for x,e in zip(x0[0],eps[0])]]
    r=step(xt,eps,alpha,1)
    assert r['predicted_clean_image'][0]==pytest.approx(x0[0])
    assert r['previous_image'][0]==pytest.approx(x0[0])
    r=step(xt,eps,alpha,alpha)
    assert r['previous_image'][0]==pytest.approx(xt[0])
    assert step([[5]],[[999]],1,1)['previous_image']==[[5]]


@pytest.mark.parametrize('alpha',[.000001,.999999,1,1.0])
def test_alpha_acceptance_boundaries(alpha):
    r=step([[1]],[[.1]],alpha,1)
    assert math.isfinite(r['previous_image'][0][0])


@pytest.mark.parametrize('bad',[True,'1',None,0,.0000009,1.000001,float('nan'),float('inf')])
def test_bad_alphas_each_argument(bad):
    for a,b in ((bad,1),(.000001,bad)):
        with pytest.raises(ValueError,match='^strict finite cumulative alpha within 1e-6..1$'):step([[0]],[[0]],a,b)
    with pytest.raises(ValueError,match='^previous cumulative alpha must be at least current$'):step([[0]],[[0]],.8,.7)


@pytest.mark.parametrize('n',[1,31,32,33])
@pytest.mark.parametrize('axis',[0,1])
def test_image_noise_dimensions_caps(n,axis):
    g=([[0] for _ in range(n)] if axis==0 else [[0]*n])
    if n<=32:assert step(g,g,.5,1)['previous_image']==g
    else:
        for arrays in ((g,[[0]]),([[0]],g)):
            with pytest.raises(ValueError,match='^1..32 image '+('rows' if axis==0 else 'columns')+' before scan$'):step(*arrays,.5,1)


@pytest.mark.parametrize('value',[-1000,1000,-1000.0,1000.0,.1])
def test_grid_values_edges(value):
    for arrays in (([[value]],[[0]]),([[0]],[[value]])):
        assert math.isfinite(step(*arrays,.5,1)['previous_image'][0][0])


@pytest.mark.parametrize('bad',[True,'1',None,-1001,1001,float('nan'),float('inf')])
def test_grid_bad_values(bad):
    for arrays in (([[bad]],[[0]]),([[0]],[[bad]])):
        with pytest.raises(ValueError,match='^strict finite grid value within -1000..1000$'):step(*arrays,.5,1)


def test_grid_shapes_empty_and_mismatches():
    for which in (0,1):
        for bad in ([],(),None,True):
            arrays=[[[0]],[[0]]];arrays[which]=bad
            with pytest.raises(ValueError,match='^1..32 image rows before scan$'):step(*arrays,.5,1)
            arrays=[[[0]],[[0]]];arrays[which]=[bad]
            with pytest.raises(ValueError,match='^1..32 image columns before scan$'):step(*arrays,.5,1)
        arrays=[[[0]],[[0]]];arrays[which]=[[0],[0,1]]
        with pytest.raises(ValueError,match='^rectangular image required$'):step(*arrays,.5,1)
    for image,noise in (([[0],[1]],[[0]]),([[0,1]],[[0]])):
        with pytest.raises(ValueError,match='^identical image/noise shape required$'):step(image,noise,.5,1)


@pytest.mark.parametrize('current,previous,expected_clean,expected_previous',[
    (.4,.7,math.sqrt(2.5),math.sqrt(1.75)),
    (.25,.81,2,1.8),
])
def test_distinct_cumulative_alphas_echoed_in_correct_fields_and_zero_noise_reference(current,previous,expected_clean,expected_previous):
    r=step([[1]],[[0]],current,previous)
    assert r['alpha_current']==current and r['alpha_previous']==previous
    assert r['predicted_clean_image'][0][0]==pytest.approx(expected_clean,abs=1e-14)
    assert r['previous_image'][0][0]==pytest.approx(expected_previous,abs=1e-14)
