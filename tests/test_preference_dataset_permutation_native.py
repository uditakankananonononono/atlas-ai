"""Native package tests. Dataset preparation only, not model training."""
from itertools import permutations
import pytest
from app.modules.m21_claire.training import TrainingService

@pytest.fixture
def service(): return TrainingService(None)


def rows(options=None, ranking=None, count=20, context=''):
    return [{'options': options if options is not None else ['a','b'],
             'ranking': ranking if ranking is not None else ['a','b'], 'context':context} for _ in range(count)]


@pytest.mark.parametrize('options,ranking', [
    (['a','b'],['a','a','b']), (['a','b','c'], ['a','a','b']),
    (['a','b'], ['a']), (['a','b'],['a','z']), (['a','b'],['a','b','z']),
    (['a','a','b'],['a','b']), (['a','a'],['a','a']), ([],[]), (['a'],['a']),
    (['','b'],['','b']), (['  ','b'],['  ','b']), (['a','b'],['a','']),
    (['a',None],['a',None]), ([1,2],[1,2]), ([{'id':'a'},'b'], ['a','b']),
    ('ab',['a','b']), (['a','b'],'ab'), (None,None),
])
def test_invalid_ranking_rejected(service, options, ranking):
    invalid=[{'options':options,'ranking':ranking} for _ in range(20)]
    with pytest.raises(ValueError): service.preference_dataset(invalid)


def test_negative_fixture(service):
    import json
    from pathlib import Path
    fixture = json.loads((Path(__file__).parent/'fixtures/preference_duplicate_ranking.json').read_text())
    with pytest.raises(ValueError): service.preference_dataset([fixture]*20)


@pytest.mark.parametrize('count',[0,1,19])
def test_below_minimum_rejected(service,count):
    with pytest.raises(ValueError,match='at least 20'):service.preference_dataset(rows(count=count))


@pytest.mark.parametrize('count',[20,21,2001])
def test_at_and_above_minimum(service,count):
    assert len(service.preference_dataset(rows(count=count)).examples)==count


def test_generated_permutations(service):
    for n in range(2,7):
        opts=[f'option-{i}' for i in range(n)]
        for permutation in permutations(opts):
            order=list(permutation)
            ds=service.preference_dataset(rows(opts,order))
            assert ds.examples[0]['ranking']==order
            duplicate=order[:-1]+[order[0]]
            with pytest.raises(ValueError):service.preference_dataset(rows(opts,duplicate))


def test_unicode_and_optional_empty_context(service):
    opts=['অসমীয়া','café','☕','你好','e\u0301','é']
    ds=service.preference_dataset(rows(opts,list(reversed(opts)),context=''))
    assert ds.examples[0]['context']=='' and ds.examples[0]['options']==opts
    assert ds.sha256==service.preference_dataset(rows(opts,list(reversed(opts)),context='')).sha256
    assert ds.sha256!=service.preference_dataset(rows(opts,opts,context='')).sha256
    with pytest.raises(ValueError):service.preference_dataset(rows(context=None))


def test_dataset_does_not_alias_input_lists(service):
    input_rows=rows(); ds=service.preference_dataset(input_rows)
    input_rows[0]['ranking'].append('injected');input_rows[0]['options'].append('injected')
    assert ds.examples[0]['ranking']==['a','b'] and ds.examples[0]['options']==['a','b']


def test_malformed_records_and_collection_rejected(service):
    for invalid in [None, 'rankings', [None]*20, [42]*20]:
        with pytest.raises(ValueError):service.preference_dataset(invalid)
