"""Decoded JSON traversal budget must precede child materialization."""
import json
import pytest
from app.modules.m20_general_cognitive_worker import model_adapters as adapter

BOUND = 'model JSON exceeds depth64/node20000 boundary'

@pytest.mark.parametrize('kind', [list, dict])
def test_oversized_decoded_container_no_traversal(monkeypatch, kind):
    value = [0]*20000 if kind is list else {str(i):0 for i in range(20000)}
    monkeypatch.setattr(adapter.json, 'loads', lambda *a, **kw: value)
    visits=[]
    def children(node):
        visits.append(node)
        raise AssertionError('children materialized before admission')
    monkeypatch.setattr(adapter, '_json_children', children, raising=False)
    with pytest.raises(ValueError, match=BOUND):
        adapter.extract_json('[]')
    assert visits == []

@pytest.mark.parametrize('kind', [list, dict])
def test_decoded_nodes_20000_20001(kind):
    value = [0]*19999 if kind is list else {str(i):0 for i in range(19999)}
    # Large dict is injected because the existing text limit is independent.
    if kind is dict:
        from unittest.mock import patch
        with patch.object(adapter.json, 'loads', return_value=value):
            assert adapter.extract_json('{}') is value
        value['extra']=0
        with patch.object(adapter.json, 'loads', return_value=value), pytest.raises(ValueError, match=BOUND):
            adapter.extract_json('{}')
    else:
        assert adapter.extract_json(json.dumps(value)) == value
        with pytest.raises(ValueError, match=BOUND):
            adapter.extract_json(json.dumps(value+[0]))

def test_pending_siblings_budget_before_iteration(monkeypatch):
    child=[0]*19998
    monkeypatch.setattr(adapter.json, 'loads', lambda *a, **kw: [0,child])
    visits=[]
    original=adapter._json_children
    def children(node):
        if node is child:
            visits.append(node)
            raise AssertionError('pending budget ignored')
        return original(node)
    monkeypatch.setattr(adapter, '_json_children', children)
    with pytest.raises(ValueError, match=BOUND):
        adapter.extract_json('[]')
    assert visits == []

def test_depth_64_65():
    assert adapter.extract_json('['*64+'0'+']'*64) is not None
    with pytest.raises(ValueError, match=BOUND):
        adapter.extract_json('['*65+'0'+']'*65)

def test_depth_refuses_before_child_iteration(monkeypatch):
    child=[0];value=child
    for _ in range(64):value=[value]
    monkeypatch.setattr(adapter.json, 'loads', lambda *a, **kw: value)
    visits=[]
    original=adapter._json_children
    def children(node):
        if node is child:
            visits.append(node)
            raise AssertionError('depth child iterated')
        return original(node)
    monkeypatch.setattr(adapter, '_json_children', children)
    with pytest.raises(ValueError, match=BOUND):
        adapter.extract_json('[]')
    assert visits == []

def test_text_100000_100001():
    body='"'+'x'*99998+'"'
    assert len(body)==100000
    assert len(adapter.extract_json(body))==99998
    with pytest.raises(ValueError, match='model output must be bounded text'):
        adapter.extract_json(body+' ')

def test_empty_container_at_depth64():
    assert adapter.extract_json('['*64+'[]'+']'*64) is not None


def test_final_deferred_scalar_nodes_20000_20001(monkeypatch):
    admitted=[[0]*19997,0]
    monkeypatch.setattr(adapter.json,'loads',lambda *a,**kw:admitted)
    assert adapter.extract_json('[]') is admitted
    rejected=[[0]*19998,0]
    monkeypatch.setattr(adapter.json,'loads',lambda *a,**kw:rejected)
    with pytest.raises(ValueError,match=BOUND):adapter.extract_json('[]')

@pytest.mark.parametrize('body,message',[
    ('{"a":1,"a":2}','duplicate JSON key'),
    ('{"a":NaN}','nonfinite JSON constant: NaN'),
    ('{"a":1e999}','JSON numeric exponent exceeds finite range'),
])
def test_parser_refusal_exact_messages(body,message):
    with pytest.raises(ValueError) as exc:adapter.extract_json(body)
    assert str(exc.value)==message

def test_fenced_json_boundary():
    assert adapter.extract_json('prose ```json\n{"a":1}\n``` suffix')=={'a':1}
    assert adapter.extract_json('```\n[1]\n```')==[1]

def test_decoder_refusal_exact_message(monkeypatch):
    def fail(*a,**kw):raise RecursionError('decoder')
    monkeypatch.setattr(adapter.json,'loads',fail)
    with pytest.raises(ValueError) as exc:adapter.extract_json('{}')
    assert str(exc.value)=='model JSON nesting exceeds decoder boundary'

def test_text_refusal_exact_message():
    with pytest.raises(ValueError) as exc:adapter.extract_json(' '*100001)
    assert str(exc.value)=='model output must be bounded text'

def test_resource_refusal_exact_message():
    with pytest.raises(ValueError) as exc:adapter.extract_json('['*65+'0'+']'*65)
    assert str(exc.value)==BOUND
