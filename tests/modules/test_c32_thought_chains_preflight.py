"""Owned S2.8 resource preflight regression pins."""
import importlib.util
import pathlib
from unittest.mock import patch

import pytest

_PATH = pathlib.Path(__file__).resolve().parents[2] / 'backend/app/modules/c32/thought_chains.py'
_SPEC = importlib.util.spec_from_file_location('s28_preflight', _PATH)
m = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(m)


def doc(text='loop', **extra):
    return {'id': 'd', 'medium': 'essay', 'text': text, **extra}


def run(d):
    return m.run({'docs': [d]})


@pytest.mark.parametrize('field,limit', [('id', 64), ('text', 200000), ('label', 64)])
def test_existing_raw_cap_precedes_shared_helper(field, limit):
    d = doc(**{field: 'x' * (limit + 1)}) if field != 'label' else doc(segments=[{'label': 'x' * (limit + 1), 'text': 'loop'}])
    original = m.policy.clean_text

    def bounded(value, prefix, name, cap, **kwargs):
        assert not (name == field and len(value) > cap), 'overcap reached shared scan'
        return original(value, prefix, name, cap, **kwargs)

    with patch.object(m.policy, 'clean_text', side_effect=bounded):
        with pytest.raises(ValueError, match='TREND_REFUSED_OVERSIZE:' + field + '$'):
            run(d)


@pytest.mark.parametrize('annotation,name', [('turns', 'speaker'), ('segments', 'label')])
def test_partition_refuses_oversized_piece_before_comparison(annotation, name):
    class Piece(str):
        def __len__(self):
            return 1000000

    with pytest.raises(ValueError, match='TREND_REFUSED_BAD_TYPE:' + ('turn_text' if annotation == 'turns' else 'segment_text') + '$'):
        run(doc(**{annotation: [{name: 'a', 'text': Piece('loop')}]}))


@pytest.mark.parametrize('annotation,name', [('turns', 'speaker'), ('segments', 'label')])
def test_partition_remains_byte_exact_with_empty_parts(annotation, name):
    parts = [{name: 'a', 'text': ''}, {name: 'b', 'text': 'lo'}, {name: 'c', 'text': 'op'}, {name: 'd', 'text': ''}]
    out = run(doc(**{annotation: parts}))['docs'][0]
    assert len(out[annotation]) == 4
    assert out[annotation][1]['moves'] == {'systems': 1}
    for text in ('Loop', ' loop', 'loo'):
        with pytest.raises(ValueError, match='TREND_REFUSED_BAD_SEGMENT$'):
            run(doc(text, **{annotation: parts}))


def refusal(request, code):
    with pytest.raises(ValueError) as caught:
        m.run(request)
    assert str(caught.value) == 'TREND_REFUSED_' + code


@pytest.mark.parametrize('field', ['speaker', 'id', 'label'])
@pytest.mark.parametrize('bad', ['\x00', '\u202e', '\u2028', '\u2029'])
def test_echoed_unicode_hygiene(field, bad):
    d = doc()
    if field == 'id':
        d[field] = 'a' + bad
    else:
        d['turns' if field == 'speaker' else 'segments'] = [{field: 'a' + bad, 'text': 'loop'}]
    refusal({'docs': [d]}, 'BAD_TYPE:' + field)


@pytest.mark.parametrize('speaker', ['a' * 10002, 'x' * 65])
def test_raw_speaker_size_before_strip_unicode_and_output(speaker):
    with patch.object(m.policy, 'clean_text', side_effect=AssertionError('scan before bounds')):
        refusal({'docs': [doc(turns=[{'speaker': speaker, 'text': 'loop'}])]}, 'OVERSIZE:speaker')


def test_speaker_exact_boundary_bidi_and_blank():
    assert run(doc(turns=[{'speaker': 'a' * 64, 'text': 'loop'}]))['docs'][0]['turns'][0]['speaker'] == 'a' * 64
    refusal({'docs': [doc(turns=[{'speaker': 'ab\u202ecd', 'text': 'loop'}])]}, 'BAD_TYPE:speaker')
    refusal({'docs': [doc(turns=[{'speaker': ' \u2002 ', 'text': 'loop'}])]}, 'NOSPEAKER')
    assert run(doc(turns=[{'speaker': '\u2002Ann\u2002', 'text': 'loop'}]))['docs'][0]['turns'][0]['speaker'] == 'Ann'


@pytest.mark.parametrize('where,container', [('request', 'request'), ('doc', 'docs'), ('turn', 'turns'), ('segment', 'segments')])
@pytest.mark.parametrize('key', ['private_key_do_not_echo', 99])
def test_unknown_and_nonstring_keys_refused_without_echo(where, container, key):
    part = {'speaker': 'a', 'text': 'loop'}
    seg = {'label': 'b', 'text': 'loop'}
    d = doc(turns=[part], segments=[seg])
    r = {'docs': [d]}
    {'request': r, 'doc': d, 'turn': part, 'segment': seg}[where][key] = 'private_value'
    refusal(r, 'BAD_TYPE:' + container)


@pytest.mark.parametrize('where,container', [('request', 'request'), ('doc', 'docs'), ('turn', 'turns'), ('segment', 'segments')])
def test_dict_count_gate_precedes_key_inspection(where, container):
    part = {'speaker': 'a', 'text': 'loop'}
    seg = {'label': 'b', 'text': 'loop'}
    d = doc(turns=[part], segments=[seg])
    r = {'docs': [d]}
    target = {'request': r, 'doc': d, 'turn': part, 'segment': seg}[where]
    target.update({i: None for i in range(17)})
    with patch.object(m.policy, 'clean_text', side_effect=AssertionError('scan')):
        refusal(r, 'OVERSIZE:' + container)


@pytest.mark.parametrize('annotation,field', [('turns', 'speaker'), ('segments', 'label')])
def test_per_doc_list_count_boundary_and_gate(annotation, field):
    parts = [{field: 'a', 'text': ''}] * 999 + [{field: 'a', 'text': 'loop'}]
    assert len(run(doc(**{annotation: parts}))['docs'][0][annotation]) == 1000
    with patch.object(m.policy, 'clean_text', side_effect=AssertionError('scan')):
        refusal({'docs': [doc(**{annotation: parts + [None]})]}, 'OVERSIZE:' + annotation)


@pytest.mark.parametrize('annotation,field', [('turns', 'speaker'), ('segments', 'label')])
def test_request_annotation_count_boundary_before_any_analysis(annotation, field):
    parts = [{field: 'a', 'text': ''}] * 999 + [{field: 'a', 'text': 'loop'}]
    docs = [doc(**{annotation: parts})] * 20
    assert len(m._preflight({'docs': docs})) == 20
    with patch.object(m, '_analyze_doc', side_effect=AssertionError('analysis before budget')):
        refusal({'docs': docs + [doc(**{annotation: [{field: 'a', 'text': 'loop'}]})]}, 'OVERSIZE:' + annotation)


def test_aggregate_raw_boundary_and_plus_one_before_scans():
    d = doc('a' * 200000)
    # Full public path at the exact boundary; duplicated refs count repeatedly.
    out = m.run({'docs': [d] * 25})
    assert out['doc_count'] == 25 and out['word_count'] == 25
    with patch.object(m, '_analyze_doc', side_effect=AssertionError('analysis before budget')), patch.object(m.policy, 'clean_text', side_effect=AssertionError('scan before budget')):
        refusal({'docs': [d] * 25 + [doc('a')]}, 'OVERSIZE:docs')


@pytest.mark.parametrize('annotation,field', [('turns', 'speaker'), ('segments', 'label')])
def test_incremental_partition_excess_stops_before_later_bad_entry(annotation, field):
    with patch.object(m.policy, 'clean_text', side_effect=AssertionError('scan')):
        refusal({'docs': [doc(**{annotation: [{field: 'a', 'text': 'loopx'}, None]})]}, 'BAD_SEGMENT')


@pytest.mark.parametrize('annotation', ['docs', 'turns', 'segments'])
def test_list_tuple_and_subclass_refused_before_iteration(annotation):
    class Hostile(list):
        def __iter__(self):
            raise AssertionError('subclass iteration')
        def __len__(self):
            raise AssertionError('subclass len')
    for bad in ((), Hostile()):
        r = {'docs': bad} if annotation == 'docs' else {'docs': [doc(**{annotation: bad})]}
        refusal(r, 'BAD_TYPE:' + annotation)


@pytest.mark.parametrize('field', ['id', 'kind', 'medium', 'text', 'speaker', 'label'])
def test_str_subclass_refused_before_length_or_strip(field):
    class Hostile(str):
        def __len__(self):
            raise AssertionError('subclass len')
        def strip(self):
            raise AssertionError('subclass strip')
    d = doc()
    if field in ('speaker', 'label'):
        d['turns' if field == 'speaker' else 'segments'] = [{field: Hostile('a'), 'text': 'loop'}]
    else:
        d[field] = Hostile('loop')
    refusal({'docs': [d]}, 'BAD_TYPE:' + field)


@pytest.mark.parametrize('where,container', [('request', 'request'), ('doc', 'docs'), ('turn', 'turns'), ('segment', 'segments')])
def test_dict_subclass_refused_before_access(where, container):
    class Hostile(dict):
        def get(self, *args):
            raise AssertionError('subclass access')
        def __len__(self):
            raise AssertionError('subclass len')
    part = {'speaker': 'a', 'text': 'loop'}
    seg = {'label': 'b', 'text': 'loop'}
    d = doc(turns=[part], segments=[seg])
    r = {'docs': [d]}
    if where == 'request':
        r = Hostile(r)
    elif where == 'doc':
        r['docs'] = [Hostile(d)]
    elif where == 'turn':
        d['turns'] = [Hostile(part)]
    else:
        d['segments'] = [Hostile(seg)]
    refusal(r, 'BAD_TYPE:' + container)


def test_timestamp_exact_types_and_unbounded_int_no_float_conversion():
    class Int(int):
        pass
    class Float(float):
        pass
    for bad in (True, Int(1), Float(1), float('inf'), float('nan'), -1):
        refusal({'docs': [doc(turns=[{'speaker': 'a', 'text': 'loop', 't_start': bad}])]}, 'BAD_TYPE:t_start')
    ts = 10 ** 500
    assert run(doc(turns=[{'speaker': 'a', 'text': 'loop', 't_start': ts}]))['docs'][0]['turns'][0]['t_start'] == ts


def test_text_whitespace_and_echoed_zs_preserved():
    out = run(doc('lo\nop\r\t', id='a\u2002', segments=[{'label': 'b\u2002', 'text': 'lo\nop\r\t'}]))['docs'][0]
    assert out['id'] == 'a\u2002' and out['segments'][0]['label'] == 'b\u2002'


@pytest.mark.parametrize('speaker', ['\n', '\r', '\t', ' \u2028 '])
def test_blank_control_speaker_is_bad_type_not_nospeaker(speaker):
    refusal({'docs': [doc(turns=[{'speaker': speaker, 'text': 'loop'}])]}, 'BAD_TYPE:speaker')


def test_full_request_overcap_late_doc_before_first_doc_scan():
    with patch.object(m.policy, 'clean_text', side_effect=AssertionError('scan')), patch.object(m, '_analyze_doc', side_effect=AssertionError('analysis')):
        refusal({'docs': [doc('loop'), doc('x' * 200001)]}, 'OVERSIZE:text')


def test_total_turn_and_segment_budgets_are_separate():
    turns = [{'speaker': 'a', 'text': ''}] * 999 + [{'speaker': 'a', 'text': 'loop'}]
    segments = [{'label': 'a', 'text': ''}] * 999 + [{'label': 'a', 'text': 'loop'}]
    assert len(m._preflight({'docs': [doc(turns=turns, segments=segments)] * 20})) == 20


def test_document_count_boundary_and_code():
    assert len(m._preflight({'docs': [doc()] * 10000})) == 10000
    with patch.object(m.policy, 'clean_text', side_effect=AssertionError('scan')):
        refusal({'docs': [doc()] * 10001}, 'OVERSIZE:docs')


def test_dictionary_exact_seventeen_keys_gate():
    refusal({str(i): None for i in range(17)}, 'OVERSIZE:request')
    refusal({str(i): None for i in range(16)}, 'BAD_TYPE:request')


@pytest.mark.parametrize('annotation,field', [('turns', 'speaker'), ('segments', 'label')])
def test_annotation_text_subclass_refused(annotation, field):
    class Text(str):
        pass
    refusal({'docs': [doc(**{annotation: [{field: 'a', 'text': Text('loop')}]})]}, 'BAD_TYPE:' + ('turn_text' if annotation == 'turns' else 'segment_text'))


def test_key_subclass_refused_even_when_equal_to_allowed_key():
    class Key(str):
        pass
    refusal({Key('docs'): [doc()]}, 'BAD_TYPE:request')
