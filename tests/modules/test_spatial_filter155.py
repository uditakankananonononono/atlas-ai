import copy
from fractions import Fraction
import pytest
from app.modules.m12_ai_research_lab.spatial_filter155 import extract


@pytest.mark.parametrize('activation,expected',[('identity',[['0','6'],['7','-2']]),('relu',[['0','6'],['7','0']])])
def test_asymmetric_kernel_hand_reference_not_flipped_and_activation_menu(activation,expected):
    image=[[1,2,0],[3,1,4],[2,5,1]];kernel=[[1,-1],[0,1]];before=copy.deepcopy((image,kernel))
    r=extract(image,kernel,activation=activation)
    assert r['features_fraction']==expected and r['shape']==[2,2]
    assert r['padding_top_left']==[0,0] and (image,kernel)==before
    assert not r['kernel_learning_performed'] and not r['network_training_performed']
    assert not r['semantic_features_verified'] and r['external_effects']==[]
    assert r['units']=='image units times supplied kernel units'


def test_same_padding_even_kernel_odd_excess_bottom_right_and_stride():
    image=[[1,2,3],[4,5,6]];kernel=[[1,2],[3,4]]
    r=extract(image,kernel,padding='same')
    assert r['features_fraction']==[['37','47','21'],['14','17','6']]
    assert r['shape']==[2,3] and r['padding_top_left']==[0,0]
    r=extract(image,kernel,stride=2,padding='same')
    assert r['features_fraction']==[['37','21']] and r['shape']==[1,2]
    r=extract([[1]],[[1,2,3],[4,5,6],[7,8,9]],padding='same')
    assert r['features_fraction']==[['5']] and r['padding_top_left']==[1,1]


@pytest.mark.parametrize('stride',[1,2,3,4])
@pytest.mark.parametrize('padding',['valid','same'])
def test_complete_stride_padding_menu_exact_shape_and_decimal_units(stride,padding):
    r=extract([[.1]*7 for _ in range(6)],[[.2]],stride,padding)
    assert r['shape']==[(6+stride-1)//stride,(7+stride-1)//stride]
    assert all(Fraction(v)==Fraction(1,50) for row in r['features_fraction'] for v in row)


@pytest.mark.parametrize('which,cap',[(0,32),(1,5)])
@pytest.mark.parametrize('axis',[0,1])
def test_matrix_cap_edges_each_axis(which,cap,axis):
    for n in (1,cap-1,cap,cap+1):
        arrays=[[[0]],[[0]]];arrays[which]=([[0] for _ in range(n)] if axis==0 else [[0]*n])
        if n<=cap:extract(*arrays,padding='same')
        else:
            with pytest.raises(ValueError,match='^bounded nonempty matrix '+('rows' if axis==0 else 'columns')+' before scan$'):extract(*arrays,padding='same')


@pytest.mark.parametrize('value',[-1000,1000,-1000.0,1000.0])
def test_signed_value_boundaries(value):
    assert extract([[value]],[[value]])['features_fraction']==[['1000000']]


@pytest.mark.parametrize('value',[True,'1',None,1001,-1001,float('nan'),float('inf')])
def test_bad_values_each_matrix(value):
    for arrays in ([[[value]],[[0]]],[[[0]],[[value]]]):
        with pytest.raises(ValueError,match='^strict finite bounded image/kernel value$'):extract(*arrays)


def test_options_shapes_and_kernel_fit_refusals():
    for bad in (True,1.0,'1',0,5):
        with pytest.raises(ValueError,match='^strict stride 1..4$'):extract([[0]],[[0]],bad)
    for bad in ('',True,None,'bad'):
        with pytest.raises(ValueError,match='^padding valid or same$'):extract([[0]],[[0]],padding=bad)
        with pytest.raises(ValueError,match='^activation identity or relu$'):extract([[0]],[[0]],activation=bad)
    for which in (0,1):
        for bad in ([],(),None,True):
            arrays=[[[0]],[[0]]];arrays[which]=bad
            with pytest.raises(ValueError,match='^bounded nonempty matrix rows before scan$'):extract(*arrays)
            arrays=[[[0]],[[0]]];arrays[which]=[bad]
            with pytest.raises(ValueError,match='^bounded nonempty matrix columns before scan$'):extract(*arrays)
        arrays=[[[0]],[[0]]];arrays[which]=[[0],[0,1]]
        with pytest.raises(ValueError,match='^rectangular matrix required$'):extract(*arrays)
    with pytest.raises(ValueError,match='^valid kernel must fit image$'):extract([[1]],[[1,2]])
    with pytest.raises(ValueError,match='^valid kernel must fit image$'):extract([[1]],[[1],[2]])


@pytest.mark.parametrize('transpose,stride,shape,pads',[
    (False,2,[3,4],[1,1,1,1]),(False,3,[2,3],[0,1,1,1]),
    (False,4,[2,2],[1,1,0,0]),(True,2,[4,3],[1,1,1,1]),
    (True,3,[3,2],[1,1,0,1]),(True,4,[2,2],[0,0,1,1]),
])
def test_nonsquare_same_padding_stride_with_explicit_zero_padded_reference(transpose,stride,shape,pads):
    image=[[10*r+c+1 for c in range(8)] for r in range(5)]
    kernel=[[1,2,-1,3],[0,-2,4,1],[3,1,0,-1]]
    if transpose:
        image=[list(row) for row in zip(*image)]
        kernel=[list(row) for row in zip(*kernel)]
    top,bottom,left,right=pads
    # Pads above are hand-derived: output ceil(image/stride); total padding
    # (output-1)*stride+kernel-image, top/left=floor(total/2).
    # The explicit grid places any odd excess on bottom/right.
    width=len(image[0])+left+right
    padded=[[0]*width for _ in range(top)]
    padded += [[0]*left+row+[0]*right for row in image]
    padded += [[0]*width for _ in range(bottom)]
    expected=[]
    for row_start in range(0,len(padded)-len(kernel)+1,stride):
        line=[]
        for col_start in range(0,width-len(kernel[0])+1,stride):
            window=[row[col_start:col_start+len(kernel[0])] for row in padded[row_start:row_start+len(kernel)]]
            line.append(str(sum(a*b for wr,kr in zip(window,kernel) for a,b in zip(wr,kr))))
        expected.append(line)
    assert [len(expected),len(expected[0])]==shape
    result=extract(image,kernel,stride,padding='same')
    assert result['shape']==shape
    assert result['padding_top_left']==[top,left]
    assert result['features_fraction']==expected


@pytest.mark.parametrize('transpose,stride,shape',[
    (False,1,[3,5]),(False,2,[2,3]),(False,3,[1,2]),
    (True,1,[5,3]),(True,2,[3,2]),(True,3,[2,1]),
])
def test_nonsquare_valid_stride_shape_and_explicit_unpadded_windows(transpose,stride,shape):
    image=[[10*r+c+1 for c in range(8)] for r in range(5)]
    kernel=[[1,2,-1,3],[0,-2,4,1],[3,1,0,-1]]
    if transpose:
        image=[list(row) for row in zip(*image)]
        kernel=[list(row) for row in zip(*kernel)]
    expected=[]
    for row_start in range(0,len(image)-len(kernel)+1,stride):
        line=[]
        for col_start in range(0,len(image[0])-len(kernel[0])+1,stride):
            window=[row[col_start:col_start+len(kernel[0])] for row in image[row_start:row_start+len(kernel)]]
            line.append(str(sum(a*b for wr,kr in zip(window,kernel) for a,b in zip(wr,kr))))
        expected.append(line)
    assert [len(expected),len(expected[0])]==shape
    r=extract(image,kernel,stride,padding='valid')
    assert r['shape']==shape and r['features_fraction']==expected
    assert r['padding_top_left']==[0,0]


@pytest.mark.parametrize('image,kernel',[
    ([[1,2],[3,4],[5,6]],[[1,2,3],[4,5,6]]),
    ([[1,2,3],[4,5,6]],[[1,2],[3,4],[5,6]]),
])
def test_valid_kernel_fits_only_one_axis_refused(image,kernel):
    with pytest.raises(ValueError,match='^valid kernel must fit image$'):extract(image,kernel,padding='valid')


@pytest.mark.parametrize('image,kernel,stride,expected',[
    ([[1,2,3],[4,5,6]],[[2]],1,[['2','4','6'],['8','10','12']]),
    ([[1,2,3,4],[5,6,7,8]],[[1,0],[0,1]],2,[['7','11']]),
])
def test_same_zero_total_padding_pins_zero_not_negative(image,kernel,stride,expected):
    r=extract(image,kernel,stride,padding='same')
    assert r['padding_top_left']==[0,0] and r['features_fraction']==expected


@pytest.mark.parametrize('image,kernel,expected',[
    ([[10*r+c+1 for c in range(6)] for r in range(6)],[[2]],[['2','10'],['82','90']]),
    ([[10*r+c+1 for c in range(7)] for r in range(7)],[[1,2],[3,4]],[['86','126'],['486','526']]),
])
def test_same_stride_larger_than_kernel_negative_needed_padding_clamped_to_zero(image,kernel,expected):
    # 6: ceil(6/4)=2; needed=(2-1)*4+1-6=-1.
    # 7: ceil(7/4)=2; needed=(2-1)*4+2-7=-1.
    # Correct zero top/left samples unpadded windows at offsets0 and4.
    r=extract(image,kernel,4,padding='same')
    assert r['shape']==[2,2] and r['padding_top_left']==[0,0]
    assert r['features_fraction']==expected
