import copy
import pytest
from app.modules.m12_ai_research_lab.structural_labels146 import build


@pytest.mark.parametrize('mode',['next_token','masked_token'])
def test_full_mode_menu_exact_order_reference_and_no_input_mutation(mode):
    sequences=[['a','b','a'],['x','Y']];before=copy.deepcopy(sequences);r=build(sequences,mode)
    expected=[]
    if mode=='next_token':
        expected=[(0,1,['a'],'b'),(0,2,['a','b'],'a'),(1,1,['x'],'Y')]
    else:
        expected=[(0,0,['[MASK]','b','a'],'a'),(0,1,['a','[MASK]','a'],'b'),
                  (0,2,['a','b','[MASK]'],'a'),(1,0,['[MASK]','Y'],'x'),(1,1,['x','[MASK]'],'Y')]
    assert r['examples']==[dict(sequence_index=s,label_position=p,input_tokens=c,label=y) for s,p,c,y in expected]
    assert r['example_count']==len(expected) and r['mode']==mode
    assert not r['model_training_performed'] and not r['semantic_label_truth_verified']
    assert not r['split_independence_verified'] and r['external_effects']==[]
    assert sequences==before
    r['examples'][0]['input_tokens'][0]='changed'
    assert sequences==before


def test_custom_mask_unicode_and_future_exclusion():
    r=build([['tea','ß','茶']], 'masked_token','???')
    assert r['examples'][1]==dict(sequence_index=0,label_position=1,input_tokens=['tea','???','茶'],label='ß')
    a=build([['a','b','c']],'next_token');b=build([['a','b','z']],'next_token')
    assert a['examples'][0]==b['examples'][0]
    assert a['examples'][1]['input_tokens']==b['examples'][1]['input_tokens']==['a','b']


@pytest.mark.parametrize('mode',['next_token','masked_token'])
@pytest.mark.parametrize('n',[1,2,99,100,101])
def test_sequence_count_caps(mode,n):
    inputs=[['a','b'] for _ in range(n)]
    if n<=100:assert build(inputs,mode)['example_count']==n*(1 if mode=='next_token' else 2)
    else:
        with pytest.raises(ValueError,match='^1..100 sequences before scan$'):build(inputs,mode)


@pytest.mark.parametrize('mode',['next_token','masked_token'])
@pytest.mark.parametrize('n',[1,2,99,100,101])
def test_token_count_caps(mode,n):
    inputs=[['x']*n]
    if 2<=n<=100:assert build(inputs,mode)['example_count']==(n-1 if mode=='next_token' else n)
    else:
        with pytest.raises(ValueError,match='^2..100 tokens per sequence before scan$'):build(inputs,mode)


@pytest.mark.parametrize('mode',['next_token','masked_token'])
def test_maximum_allocations_have_exact_order_and_count(mode):
    r=build([['x']*100 for _ in range(100)],mode)
    assert r['example_count']==(9900 if mode=='next_token' else 10000)
    assert r['examples'][-1]['sequence_index']==99 and r['examples'][-1]['label_position']==99
    assert len(r['examples'][-1]['input_tokens'])==(99 if mode=='next_token' else 100)


@pytest.mark.parametrize('length',[119,120,121])
def test_label_and_mask_length_boundaries(length):
    if length<=120:
        assert build([['x'*length,'b']],'next_token')['examples'][0]['input_tokens']==['x'*length]
        assert build([['a','b']],'masked_token','m'*length)['examples'][0]['input_tokens'][0]=='m'*length
    else:
        with pytest.raises(ValueError,match='^bounded nonblank string token$'):build([['x'*length,'b']],'next_token')
        with pytest.raises(ValueError,match='^bounded nonblank mask token$'):build([['a','b']],'masked_token','m'*length)


@pytest.mark.parametrize('bad',['',' ','\t\n',True,None,1,{}])
def test_strict_tokens_and_mask_type_nonblank_refusals(bad):
    for mode in ('next_token','masked_token'):
        for position in (0,1):
            sequence=['a','b'];sequence[position]=bad
            with pytest.raises(ValueError,match='^bounded nonblank string token$'):build([sequence],mode)
        with pytest.raises(ValueError,match='^bounded nonblank mask token$'):build([['a','b']],mode,bad)


def test_modes_shapes_empty_and_mask_collision_precise_refusals():
    for bad in ('bad','',True,None,1):
        with pytest.raises(ValueError,match='^mode must be next_token or masked_token$'):build([['a','b']],bad)
    for bad in ([],(),None,True,{}):
        with pytest.raises(ValueError,match='^1..100 sequences before scan$'):build(bad,'next_token')
    for bad in ([],(),None,True,{}):
        with pytest.raises(ValueError,match='^2..100 tokens per sequence before scan$'):build([bad],'next_token')
    for mode in ('next_token','masked_token'):
        with pytest.raises(ValueError,match='^mask token must not occur in inputs$'):build([['a','[MASK]']],mode)


@pytest.mark.parametrize('mode',['next_token','masked_token'])
@pytest.mark.parametrize('mask',['m','茶'])
def test_one_character_mask_tokens_accepted_in_both_modes(mode,mask):
    r=build([['a','b']],mode,mask)
    assert r['example_count']==(1 if mode=='next_token' else 2)
    if mode=='masked_token':
        assert r['examples'][0]['input_tokens']==[mask,'b']
        assert r['examples'][1]['input_tokens']==['a',mask]
    else:assert r['examples'][0]['input_tokens']==['a']
    with pytest.raises(ValueError,match='^mask token must not occur in inputs$'):
        build([['a',mask]],mode,mask)
