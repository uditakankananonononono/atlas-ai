import copy
import math
import pytest
from app.modules.m12_ai_research_lab.scaled_attention152 import attend


def test_scaled_reference_asymmetric_dimensions_nonuniform_weights_and_no_mutation():
    q=[[2,0],[0,1]];k=[[1,0],[0,2],[-1,0]];v=[[1,10,2],[3,-2,5],[-4,0,7]]
    before=copy.deepcopy((q,k,v));r=attend(q,k,v)
    for i,scores in enumerate(([math.sqrt(2),0,-math.sqrt(2)],[0,math.sqrt(2),0])):
        z=sum(math.exp(x) for x in scores);w=[math.exp(x)/z for x in scores]
        assert r['weights'][i]==pytest.approx(w,abs=1e-14)
        expected=[sum(w[j]*v[j][c] for j in range(3)) for c in range(3)]
        assert r['outputs'][i]==pytest.approx(expected,abs=1e-14)
    assert r['scale_dimension']==2 and (q,k,v)==before
    assert not r['learned_projection_performed'] and not r['semantic_relevance_verified']
    assert not r['attention_is_causal_explanation'] and r['external_effects']==[]


def test_masked_largest_score_excluded_exact_zero_and_mask_not_mutated():
    mask=[[True,False,True],[False,True,False]];before=copy.deepcopy(mask)
    r=attend([[1],[2]],[[0],[1000],[1]],[[2],[999],[8]],mask)
    p=math.e/(1+math.e)
    assert r['weights'][0]==pytest.approx([1-p,0,p])
    assert r['weights'][0][1]==0 and r['outputs'][0][0]==pytest.approx(2*(1-p)+8*p)
    assert r['weights'][1]==[0,1,0] and r['outputs'][1]==[999]
    assert mask==before


def test_extreme_softmax_stability_and_uniform_mean():
    assert attend([[1000]],[[1000],[-1000]],[[1],[2]])['weights']==[[1,0]]
    r=attend([[0]],[[4],[9],[-3]],[[2,1],[5,2],[-1,9]])
    assert r['weights'][0]==pytest.approx([1/3]*3)
    assert r['outputs'][0]==pytest.approx([2,4])


@pytest.mark.parametrize('n',[1,31,32,33])
def test_row_caps_each_matrix(n):
    for which in range(3):
        arrays=[[[0]],[[0]],[[0]]];arrays[which]=[[0] for _ in range(n)]
        if which in (1,2):arrays[3-which]=[[0] for _ in range(n)]
        if n<=32:
            r=attend(*arrays);assert len(r['outputs'])==(n if which==0 else 1)
        else:
            with pytest.raises(ValueError,match='^1..32 matrix rows before scan$'):attend(*arrays)


@pytest.mark.parametrize('n',[1,15,16,17])
def test_width_caps_each_matrix(n):
    for which in range(3):
        arrays=[[[0]],[[0]],[[0]]];arrays[which]=[[0]*n]
        if which<2:arrays[1-which]=[[0]*n]
        if n<=16:assert len(attend(*arrays)['outputs'][0])==(n if which==2 else 1)
        else:
            with pytest.raises(ValueError,match='^1..16 matrix columns before scan$'):attend(*arrays)


@pytest.mark.parametrize('value',[-1000,1000,-1000.0,1000.0,.1])
def test_cell_edges_each_matrix(value):
    for which in range(3):
        arrays=[[[0]],[[0]],[[0]]];arrays[which][0][0]=value;attend(*arrays)


@pytest.mark.parametrize('value',[True,'1',None,1001,-1001,float('nan'),float('inf')])
def test_cell_refusals_each_matrix(value):
    for which in range(3):
        arrays=[[[0]],[[0]],[[0]]];arrays[which][0][0]=value
        with pytest.raises(ValueError,match='^strict finite matrix values within -1000..1000$'):attend(*arrays)


def test_matrix_shape_and_dimension_refusals():
    for which in range(3):
        for bad in ([],(),None,True):
            arrays=[[[0]],[[0]],[[0]]];arrays[which]=bad
            with pytest.raises(ValueError,match='^1..32 matrix rows before scan$'):attend(*arrays)
        for bad in ([],(),None,True):
            arrays=[[[0]],[[0]],[[0]]];arrays[which]=[bad]
            with pytest.raises(ValueError,match='^1..16 matrix columns before scan$'):attend(*arrays)
        arrays=[[[0]],[[0]],[[0]]];arrays[which]=[[0],[0,1]]
        with pytest.raises(ValueError,match='^rectangular matrix required$'):attend(*arrays)
    with pytest.raises(ValueError,match='^query/key dimensions must match$'):attend([[0,1]],[[0]],[[0]])
    with pytest.raises(ValueError,match='^key/value row counts must match$'):attend([[0]],[[0],[1]],[[0]])


def test_mask_shape_type_and_fully_masked_refusals():
    for mask in ([],(),True,[[True,True]],[True],[[True],[True]]):
        with pytest.raises(ValueError,match='^mask shape must match query/key rows$'):attend([[0]],[[0]],[[0]],mask)
    for bad in (0,1,'True',None):
        with pytest.raises(ValueError,match='^strict boolean mask cells$'):attend([[0]],[[0]],[[0]],[[bad]])
    with pytest.raises(ValueError,match='^at least one allowed key per query$'):attend([[0]],[[0]],[[0]],[[False]])
