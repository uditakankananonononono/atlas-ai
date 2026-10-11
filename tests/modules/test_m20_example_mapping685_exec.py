"""Finite, source-retaining example-mapping contract. No real provider calls."""
from copy import deepcopy
from itertools import product
import math
import pytest
from app.modules.m20_general_cognitive_worker.example_mapping_executor import evaluate_example_mapping


def packet():
    return {'story':'Finite eligibility rule', 'fields':[{'id':'age','type':'integer'}],
            'rules':[{'id':'r','predicate':{'op':'ge','field':'age','value':18},'source_ids':['spec:r']}],
            'examples':[{'id':'e','inputs':{'age':18},'expected':{'r':True},'source_ids':['spec:e']}],
            'questions':[]}


def test_computed_and_no_certification():
    p=packet(); original=deepcopy(p); out=evaluate_example_mapping(p)
    assert p==original
    assert out['examples'][0]['actual']=={'r':True}
    assert out['mapping_satisfied'] and out['mismatches']==[] and out['uncovered_rule_ids']==[]
    assert out['repository_behavior_verified'] is False and out['release_authorized'] is False
    assert out['rules'][0]['source_ids']==['spec:r'] and out['examples'][0]['source_ids']==['spec:e']


@pytest.mark.parametrize('op', ['eq','ne','lt','le','gt','ge'])
@pytest.mark.parametrize('a,b',product([-1,0,1],repeat=2))
def test_comparator_truth_table(op,a,b):
    p=packet();p['rules'][0]['predicate']={'op':op,'field':'age','value':b};p['examples'][0]['inputs']['age']=a
    expected={'eq':a==b,'ne':a!=b,'lt':a<b,'le':a<=b,'gt':a>b,'ge':a>=b}[op]
    p['examples'][0]['expected']['r']=expected
    assert evaluate_example_mapping(p)['mapping_satisfied']


@pytest.mark.parametrize('op',['and','or','not'])
@pytest.mark.parametrize('a,b',product([False,True],repeat=2))
def test_boolean_truth_table(op,a,b):
    p=packet();p['fields']=[{'id':'a','type':'boolean'},{'id':'b','type':'boolean'}]
    x={'op':'eq','field':'a','value':True};y={'op':'eq','field':'b','value':True}
    pred={'op':op,'args':[x,y]} if op!='not' else {'op':'not','arg':x}
    p['rules'][0]['predicate']=pred;p['examples'][0]['inputs']={'a':a,'b':b}
    p['examples'][0]['expected']['r']={'and':a and b,'or':a or b,'not':not a}[op]
    assert evaluate_example_mapping(p)['mapping_satisfied']


def test_mismatch_uncovered_questions_and_sources():
    p=packet();p['examples'][0]['expected']['r']=False
    p['rules'].append({'id':'z','predicate':{'op':'eq','field':'age','value':18},'source_ids':['spec:z']})
    p['questions']=[{'id':'q','text':'Clarify age threshold','source_ids':['spec:q']}]
    o=evaluate_example_mapping(p)
    assert not o['mapping_satisfied'] and o['status']=='needs_resolution'
    assert o['uncovered_rule_ids']==['z'] and o['unresolved_questions']==p['questions']
    assert o['mismatches']==[{'example_id':'e','rule_id':'r','expected':False,'actual':True,'source_ids':['spec:e','spec:r']}]


def test_unsorted_deterministic_outputs():
    p=packet();p['rules'] += [{'id':'a','predicate':{'op':'lt','field':'age','value':21},'source_ids':['z','a']}]
    p['examples'] += [{'id':'a','inputs':{'age':1},'expected':{'r':False},'source_ids':['z','a']}]
    p['questions']=[{'id':'z','text':'z','source_ids':['z']},{'id':'a','text':'a','source_ids':['a']}]
    q=deepcopy(p)
    for k in ['fields','rules','examples','questions']:q[k].reverse()
    q['rules'][1]['source_ids'].reverse()
    assert evaluate_example_mapping(p)==evaluate_example_mapping(q)


@pytest.mark.parametrize('mutate',[
    lambda p:p.update(extra=True),lambda p:p.pop('fields'),lambda p:p.update(story=''),
    lambda p:p['fields'].append(deepcopy(p['fields'][0])),
    lambda p:p['rules'].append(deepcopy(p['rules'][0])),lambda p:p['examples'].append(deepcopy(p['examples'][0])),
    lambda p:p['rules'][0]['predicate'].update(op='eval'),
    lambda p:p['rules'][0]['predicate'].update(field='missing'),
    lambda p:p['rules'][0]['predicate'].update(value=True),
    lambda p:p['rules'][0]['predicate'].update(extra='x'),
    lambda p:p['examples'][0]['expected'].update(missing=True),
    lambda p:p['examples'][0]['expected'].update(r='true'),
    lambda p:p['examples'][0]['inputs'].update(age='18'),
    lambda p:p['examples'][0]['inputs'].update(other=1),lambda p:p['examples'][0]['inputs'].clear(),
    lambda p:p['rules'][0].update(source_ids=[]),lambda p:p['rules'][0].update(source_ids=['x','x']),
    lambda p:p['fields'][0].update(type='object'),lambda p:p['rules'][0].update(predicate={'op':'and','args':[]}),
    lambda p:p['rules'][0].update(predicate={'op':'not','args':[]}),
    lambda p:p.update(questions=[{'id':'q','text':'x','source_ids':['x']}]*2),
])
def test_refuses_schema_and_refs(mutate):
    p=packet();mutate(p)
    with pytest.raises(ValueError):evaluate_example_mapping(p)


@pytest.mark.parametrize('kind,value',[('integer',True),('integer',1.0),('number',math.inf),('number',math.nan),('number',True),('string',1),('boolean',0),('integer',2**53+1)])
def test_strict_scalar_inputs(kind,value):
    p=packet();p['fields'][0]['type']=kind;p['rules'][0]['predicate']={'op':'eq','field':'age','value':{'integer':1,'number':1.,'string':'x','boolean':True}[kind]};p['examples'][0]['inputs']['age']=value
    with pytest.raises(ValueError):evaluate_example_mapping(p)


@pytest.mark.parametrize('key,n',[('fields',32),('rules',64),('examples',128),('questions',64)])
def test_exact_collection_bounds(key,n):
    p=packet()
    if key=='fields':p[key]=[{'id':f'f{i}','type':'integer'} for i in range(n)];p['rules'][0]['predicate']['field']='f0';p['examples'][0]['inputs']={f'f{i}':18 for i in range(n)}
    elif key=='rules':p[key]=[{**deepcopy(p['rules'][0]),'id':f'r{i}'} for i in range(n)];p['examples'][0]['expected']={'r0':True}
    elif key=='examples':p[key]=[{**deepcopy(p['examples'][0]),'id':f'e{i}'} for i in range(n)]
    else:p[key]=[{'id':f'q{i}','text':'x','source_ids':['x']} for i in range(n)]
    evaluate_example_mapping(p)
    p[key].append({**deepcopy(p[key][0]),'id':'overflow'})
    if key=='fields':p['examples'][0]['inputs']['overflow']=18
    with pytest.raises(ValueError):evaluate_example_mapping(p)


def test_depth_node_and_text_bounds():
    p=packet();p['story']='x'*2000;evaluate_example_mapping(p);p['story']+='x'
    with pytest.raises(ValueError):evaluate_example_mapping(p)
    p=packet();leaf=p['rules'][0]['predicate'];pred=leaf
    for _ in range(8-1):pred={'op':'not','arg':pred}
    p['rules'][0]['predicate']=pred;evaluate_example_mapping(p)
    p['rules'][0]['predicate']={'op':'not','arg':pred}
    with pytest.raises(ValueError):evaluate_example_mapping(p)
    p=packet();p['rules'][0]['predicate']={'op':'and','args':[leaf]*(64-1)};evaluate_example_mapping(p)
    p['rules'][0]['predicate']['args'].append(leaf)
    with pytest.raises(ValueError):evaluate_example_mapping(p)


def test_no_examples_no_false_success():
    p=packet();p['examples']=[];o=evaluate_example_mapping(p)
    assert not o['mapping_satisfied'] and o['uncovered_rule_ids']==['r']


@pytest.mark.parametrize('kind,values',[('string',['','a','b']),('boolean',[False,True]),('number',[-1.5,0,1.5]),('integer',[-2**53,0,2**53])])
@pytest.mark.parametrize('op',['eq','ne'])
def test_all_scalar_equality_truth_tables(kind,values,op):
    for a,b in product(values,repeat=2):
        p=packet();p['fields'][0]['type']=kind;p['rules'][0]['predicate']={'op':op,'field':'age','value':b}
        p['examples'][0]['inputs']['age']=a;p['examples'][0]['expected']['r']=(a==b) if op=='eq' else (a!=b)
        assert evaluate_example_mapping(p)['mapping_satisfied']


@pytest.mark.parametrize('kind',['boolean','string'])
@pytest.mark.parametrize('op',['lt','le','gt','ge'])
def test_non_numeric_ordering_refused(kind,op):
    p=packet();p['fields'][0]['type']=kind;p['rules'][0]['predicate']={'op':op,'field':'age','value':True if kind=='boolean' else 'a'}
    with pytest.raises(ValueError):evaluate_example_mapping(p)


@pytest.mark.parametrize('place',['input','literal'])
@pytest.mark.parametrize('value',[10**1000,2**53+1,-2**53-1,float('inf'),float('-inf'),float('nan'),None,True,[],{}])
def test_number_bounds_and_non_scalars(place,value):
    p=packet();p['fields'][0]['type']='number'
    if place=='input':p['examples'][0]['inputs']['age']=value
    else:p['rules'][0]['predicate']['value']=value
    with pytest.raises(ValueError):evaluate_example_mapping(p)


def test_source_and_id_exact_bounds():
    p=packet();p['rules'][0]['source_ids']=[str(i) for i in range(16)]
    p['examples'][0]['id']='x'*128;evaluate_example_mapping(p)
    p['rules'][0]['source_ids'].append('overflow')
    with pytest.raises(ValueError):evaluate_example_mapping(p)
    p=packet();p['examples'][0]['id']='x'*(128+1)
    with pytest.raises(ValueError):evaluate_example_mapping(p)
    p=packet();p['rules'][0]['source_ids']=['x'*128];evaluate_example_mapping(p)
    p['rules'][0]['source_ids'][0]+='x'
    with pytest.raises(ValueError):evaluate_example_mapping(p)


@pytest.mark.parametrize('mutation',[
    lambda p:p.update(fields=[]),lambda p:p.update(rules=[]),lambda p:p.update(fields={}),
    lambda p:p['fields'][0].update(type=[]),lambda p:p['fields'][0].update(id=1),
    lambda p:p['rules'][0].update(predicate={'op':[]}),lambda p:p['rules'][0].update(predicate=None),
    lambda p:p['rules'][0].update(source_ids=[' ']),lambda p:p['examples'][0].update(expected={}),
    lambda p:p['examples'][0].update(expected=[]),lambda p:p['examples'][0].update(source_ids=['x']*17),
    lambda p:p.update(questions=[{'id':'q','text':'','source_ids':['q']}]),
    lambda p:p['rules'][0].update(predicate={'op':'or','args':[{'op':'eq','field':'age','value':18},{'op':'eval','field':'age','value':18}]}),
])
def test_additional_malformed_refused(mutation):
    p=packet();mutation(p)
    with pytest.raises(ValueError):evaluate_example_mapping(p)


def test_output_mutation_does_not_touch_input():
    p=packet();o=evaluate_example_mapping(p);o['fields'][0]['id']='mutated';o['rules'][0]['predicate']['value']=0
    o['examples'][0]['inputs']['age']=0;o['rules'][0]['source_ids'].append('mutated')
    assert p==packet()


def test_mismatch_is_the_only_resolution_factor():
    p=packet();p['examples'][0]['expected']['r']=False
    o=evaluate_example_mapping(p)
    assert o['mismatches'] and not o['uncovered_rule_ids'] and not o['unresolved_questions']
    assert o['mapping_satisfied'] is False and o['status']=='needs_resolution'


def test_uncovered_is_the_only_resolution_factor():
    p=packet();p['rules'].append({'id':'z','predicate':{'op':'eq','field':'age','value':18},'source_ids':['z']})
    o=evaluate_example_mapping(p)
    assert not o['mismatches'] and o['uncovered_rule_ids']==['z'] and not o['unresolved_questions']
    assert o['mapping_satisfied'] is False and o['status']=='needs_resolution'


def test_question_is_the_only_resolution_factor():
    p=packet();p['questions']=[{'id':'q','text':'Why 18?','source_ids':['q']}]
    o=evaluate_example_mapping(p)
    assert not o['mismatches'] and not o['uncovered_rule_ids'] and o['unresolved_questions']
    assert o['mapping_satisfied'] is False and o['status']=='needs_resolution'


def test_empty_examples_without_mismatch_or_questions():
    p=packet();p['examples']=[];o=evaluate_example_mapping(p)
    assert o['examples']==[] and not o['mismatches'] and not o['unresolved_questions']
    assert o['uncovered_rule_ids']==['r'] and o['mapping_satisfied'] is False
    # Empty examples necessarily leave nonempty rules uncovered under this schema.


class DictSubclass(dict):
    pass


@pytest.mark.parametrize('place',['packet','field','rule','predicate','example','inputs','expected','question'])
def test_dict_subclasses_refused(place):
    p=packet()
    if place=='packet':p=DictSubclass(p)
    elif place=='field':p['fields'][0]=DictSubclass(p['fields'][0])
    elif place=='rule':p['rules'][0]=DictSubclass(p['rules'][0])
    elif place=='predicate':p['rules'][0]['predicate']=DictSubclass(p['rules'][0]['predicate'])
    elif place=='example':p['examples'][0]=DictSubclass(p['examples'][0])
    elif place=='inputs':p['examples'][0]['inputs']=DictSubclass(p['examples'][0]['inputs'])
    elif place=='expected':p['examples'][0]['expected']=DictSubclass(p['examples'][0]['expected'])
    else:p['questions']=[DictSubclass(id='q',text='why',source_ids=['q'])]
    with pytest.raises(ValueError):evaluate_example_mapping(p)


def test_source_union_and_expected_order_are_canonical():
    p=packet();p['rules'][0]['source_ids']=['z','shared','a']
    p['rules'].append({'id':'a','predicate':{'op':'eq','field':'age','value':18},'source_ids':['z','shared','a']})
    p['examples'][0]['source_ids']=['z','shared','b']
    p['examples'][0]['expected']={'r':False,'a':False}
    p['questions']=[{'id':'q','text':'why','source_ids':['z','a']}]
    o=evaluate_example_mapping(p)
    assert list(o['examples'][0]['expected'])==['a','r']
    assert list(o['examples'][0]['actual'])==['a','r']
    assert [m['rule_id'] for m in o['mismatches']]==['a','r']
    for m in o['mismatches']:assert m['source_ids']==['a','b','shared','z']
    assert o['rules'][0]['source_ids']==['a','shared','z']
    assert o['examples'][0]['source_ids']==['b','shared','z']
    assert o['unresolved_questions'][0]['source_ids']==['a','z']
    q=deepcopy(p);q['rules'].reverse();q['examples'][0]['expected']={'a':False,'r':False}
    for r in q['rules']:r['source_ids'].reverse()
    q['examples'][0]['source_ids'].reverse();q['questions'][0]['source_ids'].reverse()
    other=evaluate_example_mapping(q)
    assert o==other and list(other['examples'][0]['expected'])==['a','r']


@pytest.mark.parametrize('place',['input','literal','question'])
def test_fixed_2000_character_string_cap(place):
    p=packet();p['fields'][0]['type']='string';p['rules'][0]['predicate']={'op':'eq','field':'age','value':'x'}
    p['examples'][0]['inputs']['age']='x'
    if place=='input':p['examples'][0]['inputs']['age']='x'*2000
    elif place=='literal':p['rules'][0]['predicate']['value']='x'*2000
    else:p['questions']=[{'id':'q','text':'x'*2000,'source_ids':['q']}]
    evaluate_example_mapping(p)
    if place=='input':p['examples'][0]['inputs']['age']+='x'
    elif place=='literal':p['rules'][0]['predicate']['value']+='x'
    else:p['questions'][0]['text']+='x'
    with pytest.raises(ValueError):evaluate_example_mapping(p)


@pytest.mark.parametrize('op',['and','or'])
def test_fixed_depth_8_and_9_through_boolean_args(op):
    p=packet();pred=p['rules'][0]['predicate']
    for _ in range(7):pred={'op':op,'args':[pred]}
    p['rules'][0]['predicate']=pred;evaluate_example_mapping(p)
    p['rules'][0]['predicate']={'op':op,'args':[pred]}
    with pytest.raises(ValueError):evaluate_example_mapping(p)


@pytest.mark.parametrize('op',['and','or'])
def test_boolean_args_65_refused_without_short_circuit(op):
    p=packet();leaf=p['rules'][0]['predicate']
    # At most 63 leaves plus a root fits the 64-node rule budget.
    p['rules'][0]['predicate']={'op':op,'args':[deepcopy(leaf) for _ in range(63)]}
    evaluate_example_mapping(p)
    for n in [64,65]:
        p['rules'][0]['predicate']={'op':op,'args':[deepcopy(leaf) for _ in range(n)]}
        with pytest.raises(ValueError):evaluate_example_mapping(p)


@pytest.mark.parametrize('collection',['fields','rules'])
def test_nonempty_declarations_independently_refused(collection):
    p=packet();p[collection]=[]
    with pytest.raises(ValueError,match='collection bound'):evaluate_example_mapping(p)


@pytest.mark.parametrize('kind,value',[('string','a'),('boolean',True)])
@pytest.mark.parametrize('op',['lt','le','gt','ge'])
def test_well_typed_non_numeric_ordering_is_still_refused(kind,value,op):
    p=packet();p['fields'][0]['type']=kind;p['rules'][0]['predicate']={'op':op,'field':'age','value':value}
    p['examples'][0]['inputs']['age']=value
    with pytest.raises(ValueError,match='ordering requires numeric'):evaluate_example_mapping(p)


def test_number_scalar_exact_float_bound_r3pin():
    for place in ['input','literal']:
        p=packet();p['fields'][0]['type']='number'
        if place=='input':
            p['examples'][0]['inputs']['age']=float(2**53);evaluate_example_mapping(p)
            p['examples'][0]['inputs']['age']=float(2**53+2)
        else:
            p['rules'][0]['predicate']={'op':'eq','field':'age','value':float(2**53)};evaluate_example_mapping(p)
            p['rules'][0]['predicate']['value']=float(2**53+2)
        with pytest.raises(ValueError,match='scalar type or bound mismatch'):evaluate_example_mapping(p)


def test_number_scalar_lower_region_accepted_r3pin():
    for place in ['input','literal']:
        p=packet();p['fields'][0]['type']='number'
        if place=='input':
            p['examples'][0]['inputs']['age']=float(2**52+2)
        else:
            p['rules'][0]['predicate']={'op':'eq','field':'age','value':float(2**52+2)}
        evaluate_example_mapping(p)


def test_and_predicate_arg_count_exact_messages_r3pin():
    p=packet();leaf=p['rules'][0]['predicate']
    p['rules'][0]['predicate']={'op':'and','args':[deepcopy(leaf) for _ in range(63)]}
    evaluate_example_mapping(p)
    p['rules'][0]['predicate']={'op':'and','args':[deepcopy(leaf) for _ in range(64)]}
    with pytest.raises(ValueError,match='predicate depth or node bound'):evaluate_example_mapping(p)
    p['rules'][0]['predicate']={'op':'and','args':[deepcopy(leaf) for _ in range(65)]}
    with pytest.raises(ValueError,match='bounded nonempty boolean operands required'):evaluate_example_mapping(p)
