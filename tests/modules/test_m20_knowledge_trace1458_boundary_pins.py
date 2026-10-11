"""Literal row1458 contract pins; synthetic inputs test validation only.

These tests do not claim actual learner mastery, fitted parameters, mounted
integration, efficacy, or whole-suite acceptance. Runtime source stays frozen.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from app.modules.m20_general_cognitive_worker.knowledge_trace1458 import (
    KnowledgeTraceError, trace,
)


def payload():
    return {
        'source': {'title': 'Declared boundary fixture', 'url': 'https://example.org/scored'},
        'sources': {'ref': 'Synthetic caller citation'},
        'parameters': {'skill': {'prior': .2, 'learn': .1, 'guess': .2,
                                 'slip': .1, 'source_id': 'ref'}},
        'attempts': [{'attempt_id': 'attempt', 'tenant_id': 'tenant',
                      'learner_id': 'learner', 'skill': 'skill', 'correct': True,
                      'occurred_at': '2026-10-01T00:00:00Z', 'source_id': 'ref'}],
    }


def call(p):
    return trace(p, tenant_id='tenant', actor_id='actor')


def accepted(p, *, tenant='tenant', actor='actor'):
    try:
        return trace(p, tenant_id=tenant, actor_id=actor)
    except KnowledgeTraceError as error:
        pytest.fail(f'Valid literal-boundary fixture was refused: {error}')


def test_exact_row_id_and_copy_isolation():
    p = payload()
    result = accepted(p)
    assert result['row_id'] == 1458
    result['sources']['ref'] = 'changed'
    result['parameters']['skill']['prior'] = .9
    assert p['sources']['ref'] == 'Synthetic caller citation'
    assert p['parameters']['skill']['prior'] == .2


@pytest.mark.parametrize('count', [511, 512, 513])
def test_literal_attempt_count_boundary(count):
    p = payload()
    first = p['attempts'][0]
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    p['attempts'] = [dict(first, attempt_id=f'a{i}',
        occurred_at=(start + timedelta(seconds=i)).isoformat()) for i in range(count)]
    if count <= 512:
        assert accepted(p)['histories'][0]['observation_count'] == count
    else:
        with pytest.raises(KnowledgeTraceError) as error:
            call(p)
        assert str(error.value) == 'attempts requires a list of at most 512'


@pytest.mark.parametrize('count', [0, 1, 63, 64, 65])
def test_literal_declared_skill_min_and_max(count):
    p = payload()
    par = p['parameters']['skill']
    p['parameters'] = {f's{i}': dict(par) for i in range(count)}
    p['attempts'] = []
    if 1 <= count <= 64:
        result = accepted(p)
        assert len(result['parameters']) == count
        assert result['status'] == 'abstained'
    else:
        with pytest.raises(KnowledgeTraceError) as error:
            call(p)
        assert str(error.value) == 'parameters requires 1..64 per-skill declarations'


@pytest.mark.parametrize('count', [0, 1, 127, 128, 129])
def test_literal_source_min_and_max(count):
    p = payload()
    p['sources'] = {f'r{i}': 'Synthetic citation' for i in range(count)}
    p['parameters']['skill']['source_id'] = 'r0'
    p['attempts'][0]['source_id'] = 'r0'
    if 1 <= count <= 128:
        assert len(accepted(p)['sources']) == count
    else:
        with pytest.raises(KnowledgeTraceError) as error:
            call(p)
        assert str(error.value) == 'sources requires 1..128 declared references'


@pytest.mark.parametrize('field', ['attempt_id', 'learner_id', 'actor_id', 'tenant_id',
                                  'skill', 'source_id'])
@pytest.mark.parametrize('length', [255, 256, 257])
def test_literal_identifier_boundary(field, length):
    p = payload()
    text = 'x' * length
    tenant, actor = 'tenant', 'actor'
    if field == 'actor_id':
        actor = text
    elif field == 'tenant_id':
        tenant = text
        p['attempts'][0]['tenant_id'] = text
    elif field == 'skill':
        p['parameters'] = {text: p['parameters']['skill']}
        p['attempts'][0]['skill'] = text
    elif field == 'source_id':
        p['sources'] = {text: 'Synthetic citation'}
        p['parameters']['skill']['source_id'] = text
        p['attempts'][0]['source_id'] = text
    else:
        p['attempts'][0][field] = text
    if length <= 256:
        assert accepted(p, tenant=tenant, actor=actor)['row_id'] == 1458
    else:
        with pytest.raises(KnowledgeTraceError) as error:
            trace(p, tenant_id=tenant, actor_id=actor)
        assert str(error.value) == f'{field} requires non-empty text <= 256 characters'


@pytest.mark.parametrize('field', ['source.title', 'source.url', 'source citation'])
@pytest.mark.parametrize('length', [2047, 2048, 2049])
def test_literal_text_boundary(field, length):
    p = payload()
    if field == 'source.title':
        p['source']['title'] = 't' * length
    elif field == 'source.url':
        prefix = 'https://example.org/'
        p['source']['url'] = prefix + 'p' * (length - len(prefix))
    else:
        p['sources']['ref'] = 'c' * length
    if length <= 2048:
        assert accepted(p)['row_id'] == 1458
    else:
        with pytest.raises(KnowledgeTraceError) as error:
            call(p)
        assert str(error.value) == f'{field} requires non-empty text <= 2048 characters'


@pytest.mark.parametrize('value', ['', '   ', 7, None])
def test_nonempty_and_string_type_arms_independent(value):
    p = payload()
    p['attempts'][0]['attempt_id'] = value
    with pytest.raises(KnowledgeTraceError) as error:
        call(p)
    assert str(error.value) == 'attempt_id requires non-empty text <= 256 characters'


@pytest.mark.parametrize('value', [' padded', 'padded ', 'internal\x00control',
                                 'internal\x1fcontrol'])
def test_whitespace_and_control_arms_independent(value):
    p = payload()
    p['attempts'][0]['attempt_id'] = value
    with pytest.raises(KnowledgeTraceError) as error:
        call(p)
    assert str(error.value) == 'attempt_id has whitespace or control characters'


def test_ascii_space_inside_identifier_is_allowed():
    p = payload()
    p['attempts'][0]['attempt_id'] = 'internal space'
    assert accepted(p)['histories'][0]['steps'][0]['attempt_id'] == 'internal space'


@pytest.mark.parametrize('value', [[], '', None, 1])
def test_sources_type_arm_independent(value):
    p = payload()
    p['sources'] = value
    with pytest.raises(KnowledgeTraceError) as error:
        call(p)
    assert str(error.value) == 'sources requires 1..128 declared references'


def test_authenticated_identity_is_keyword_only():
    with pytest.raises(TypeError):
        trace(payload(), 'tenant', 'actor')
