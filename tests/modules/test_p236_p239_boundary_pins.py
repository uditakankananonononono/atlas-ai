"""Boundary and exact result-shape pins for supplied record mechanisms."""
import copy
import pytest
from app.modules.instinct_doc import agi_aspiration_register_p236 as a
from app.modules.instinct_doc import superlative_claim_p239 as c


def attempt(i=0):
    return {'id': f'a{i}', 'target_capability': 'arithmetic', 'approach': 'exact tests',
            'status': 'proposed'}


def comparison(i=0):
    return {'id': f'c{i}', 'subject': 's', 'competitor': 'r', 'metric': 'm', 'evidence_ref': 'e'}


@pytest.mark.parametrize('module,func,factory,prefix,list_name,fields', [
    (a, a.register, attempt, 'P236', 'attempts', ['id', 'target_capability', 'approach']),
    (c, c.audit, comparison, 'P239', 'comparisons', ['id', 'subject', 'competitor', 'metric']),
])
def test_text_empty_missing_and_exact_length(module, func, factory, prefix, list_name, fields):
    for field in fields:
        row = factory(); row[field] = '   '
        with pytest.raises(ValueError, match=f'^{prefix}:empty_field:'):
            func([row])
        row = factory(); del row[field]
        with pytest.raises(ValueError, match=f'^{prefix}:missing_field:'):
            func([row])
        row = factory(); row[field] = 'x' * module.TEXT_LIMITS[field]
        func([row])
        row[field] += 'x'
        with pytest.raises(ValueError, match=f'^{prefix}:text_too_long:'):
            func([row])


@pytest.mark.parametrize('module,func,factory,prefix,name', [
    (a, a.register, attempt, 'P236', 'attempts'),
    (c, c.audit, comparison, 'P239', 'comparisons'),
])
def test_exact_record_cap(module, func, factory, prefix, name):
    rows = [factory(i) for i in range(1024)]
    func(rows)
    with pytest.raises(ValueError, match=f'^{prefix}:too_many:{name}$'):
        func(rows + [factory(1024)])


@pytest.mark.parametrize('module,func,factory', [(a, a.register, attempt), (c, c.audit, comparison)])
def test_verify_exact_shape_and_counter_types(module, func, factory):
    rows = [factory()]
    checks = ['structure', 'exact_keys', 'field_equality']
    for value in [None, [], 0, 'x']:
        assert module.verify(rows, value) == {'verified': False, 'failed': ['structure'], 'checks': checks}
    result = func(rows)
    for value in [{}, dict(result, extra=0)]:
        assert module.verify(rows, value) == {'verified': False, 'failed': ['exact_keys'], 'checks': checks}
    for value in [0.0, False]:
        changed = copy.deepcopy(result); changed['issues'] = value
        assert module.verify(rows, changed) == {'verified': False, 'failed': ['issues'], 'checks': checks}


def test_p236_premature_evidence_exact_flag():
    row = attempt(); row['evidence_ref'] = 'e'
    result = a.register([row])
    assert result['attempt_rows'] == [{'id': 'a0', 'status': 'proposed',
                                     'flags': ['proposed_with_premature_evidence'], 'verdict': 'REVIEW'}]
    assert result['issues'] == 1


def test_p239_issue_count_and_subject_normalization():
    rows = [comparison(), comparison(1), comparison(2)]
    del rows[0]['evidence_ref']; del rows[1]['evidence_ref']
    rows[1]['subject'] = ' s '
    result = c.audit(rows)
    assert result['issues'] == 2 and result['comparisons'] == 3
    assert result['subjects_covered'] == ['s']
    assert [r['subject'] for r in result['comparison_rows']] == ['s', 's', 's']
