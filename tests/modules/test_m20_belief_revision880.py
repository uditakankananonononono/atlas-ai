"""Row 880 bounded belief revision over declared beliefs and evidence.

Hermetic, stdlib-only; loads the module by file path.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

P = Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/belief_revision880.py'
s = importlib.util.spec_from_file_location('belief880', P)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)


def req(**over):
    base = {
        'beliefs': [
            {'id': 'b1', 'statement': 'the launch is on time', 'prior': 600},
            {'id': 'b2', 'statement': 'the vendor is reliable', 'prior': 150},
        ],
        'evidence': [
            {'id': 'e1', 'belief_id': 'b1', 'direction': 'refutes', 'strength': 100},
            {'id': 'e2', 'belief_id': 'b1', 'direction': 'supports', 'strength': 50},
            {'id': 'e3', 'belief_id': 'b2', 'direction': 'refutes', 'strength': 100},
        ],
    }
    base.update(over)
    return base


def test_exact_revision_and_statuses():
    out = m.revise(req())
    b1, b2 = out['beliefs']
    assert (b1['prior'], b1['signed_evidence'], b1['revised']) == (600, -50, 550)
    assert b1['revised_share'] == '11/20' and b1['status'] == 'weakened' and b1['clamped'] is False
    assert (b2['prior'], b2['signed_evidence'], b2['revised']) == (150, -100, 50)
    assert b2['revised_share'] == '1/20' and b2['status'] == 'retracted'
    assert out['retracted_ids'] == ['b2']
    assert out['evidence_count'] == 3 and out['evidence_truth_verified'] is False
    assert len(out['limits']) == 3


def test_clamping_at_scale_bounds():
    d = req(evidence=[{'id': 'e1', 'belief_id': 'b1', 'direction': 'supports', 'strength': 100}])
    d['beliefs'][0]['prior'] = 990
    out = m.revise(d)
    assert out['beliefs'][0]['revised'] == 1000 and out['beliefs'][0]['clamped'] is True
    assert out['beliefs'][0]['status'] == 'strengthened'
    d = req(evidence=[{'id': 'e1', 'belief_id': 'b1', 'direction': 'refutes', 'strength': 100}])
    d['beliefs'][0]['prior'] = 50
    out = m.revise(d)
    assert out['beliefs'][0]['revised'] == 0 and out['beliefs'][0]['clamped'] is True
    assert out['beliefs'][0]['status'] == 'below_threshold'
    assert out['retracted_ids'] == []


def test_upward_crossing_is_strengthened():
    d = req(evidence=[{'id': 'e1', 'belief_id': 'b2', 'direction': 'supports', 'strength': 60}])
    out = m.revise(d)
    assert out['beliefs'][1]['revised'] == 210 and out['beliefs'][1]['status'] == 'strengthened'
    assert out['retracted_ids'] == []


def test_retraction_threshold_boundary():
    d = req(evidence=[{'id': 'e1', 'belief_id': 'b1', 'direction': 'refutes', 'strength': 100}])
    d['beliefs'][0]['prior'] = 200
    out = m.revise(d)
    assert out['beliefs'][0]['revised'] == 100 and out['beliefs'][0]['status'] == 'weakened'
    d['beliefs'][0]['prior'] = 199
    out = m.revise(d)
    assert out['beliefs'][0]['revised'] == 99 and out['beliefs'][0]['status'] == 'retracted'


def test_deterministic_under_evidence_permutation():
    a = m.revise(req())
    d = req()
    d['evidence'] = list(reversed(d['evidence']))
    assert a == m.revise(d)


def refuse(x):
    with pytest.raises(ValueError, match='^BELIEF880:'):
        m.revise(x)


def test_schema_and_field_validation():
    for bad in [None, [], {}, {'beliefs': []}, dict(req(), extra=1)]:
        refuse(bad)
    refuse(req(beliefs=[]))
    d = req(); d['beliefs'][1]['id'] = 'b1'; refuse(d)          # duplicate belief id
    d = req(); d['evidence'][0]['id'] = 'e3'; refuse(d)         # duplicate evidence id
    d = req(); d['evidence'][0]['belief_id'] = 'nope'; refuse(d)
    d = req(); d['evidence'][0]['direction'] = 'maybe'; refuse(d)
    d = req(); d['evidence'][0]['strength'] = 101; refuse(d)
    d = req(); d['evidence'][0]['strength'] = True; refuse(d)
    d = req(); d['beliefs'][0]['prior'] = 1001; refuse(d)
    d = req(); d['beliefs'][0]['prior'] = -1; refuse(d)
    d = req(); d['beliefs'][0]['statement'] = ' '; refuse(d)
    d = req(); d['beliefs'][0].pop('prior'); refuse(d)
    d = req(); d['evidence'][0]['extra'] = 1; refuse(d)


def test_no_evidence_is_unchanged():
    out = m.revise(req(evidence=[]))
    assert [b['status'] for b in out['beliefs']] == ['unchanged', 'unchanged']
    assert out['beliefs'][1]['revised'] == 150
    d = req(evidence=[])
    d['beliefs'][1]['prior'] = 50
    out = m.revise(d)
    assert out['beliefs'][1]['status'] == 'below_threshold'
    assert out['retracted_ids'] == []


def test_v3_prior_exactly_at_threshold_can_retract():
    out = m.revise({'beliefs': [{'id': 'b', 'statement': 'declared', 'prior': 100}],
                    'evidence': [{'id': 'e', 'belief_id': 'b', 'direction': 'refutes', 'strength': 5}]})
    assert out['beliefs'][0]['revised'] == 95
    assert out['beliefs'][0]['status'] == 'retracted'
    assert out['retracted_ids'] == ['b']


def test_v3_duplicate_belief_id_has_own_refusal():
    with pytest.raises(ValueError, match='duplicate belief id'):
        m.revise({'beliefs': [{'id': 'b', 'statement': 'first', 'prior': 100},
                             {'id': 'b', 'statement': 'second', 'prior': 200}],
                  'evidence': []})


def test_v3_evidence_cap_includes_256_but_refuses_257():
    evidence = [{'id': 'e%d' % i, 'belief_id': 'b', 'direction': 'supports', 'strength': 0}
                for i in range(256)]
    d = {'beliefs': [{'id': 'b', 'statement': 'declared', 'prior': 100}], 'evidence': evidence}
    out = m.revise(d)
    assert out['evidence_count'] == 256
    assert out['beliefs'][0]['revised'] == 100
    d['evidence'] = evidence + [{'id': 'last', 'belief_id': 'b', 'direction': 'supports', 'strength': 0}]
    with pytest.raises(ValueError, match='at most 256'):
        m.revise(d)


def test_v4_exact_output_declarations():
    out = m.revise(req())
    assert out['limits'] == ['Revised weights are deterministic arithmetic over declared numbers on a declared 0..1000 scale, not probabilities or degrees of real belief.', 'Evidence is accepted as declared; its truth, provenance and sufficiency are never verified by this unit.', 'A retraction flag marks the declared weight crossing the declared threshold; no mind is changed and no action is taken.']
    assert out['interpretation'] == 'caller-declared beliefs and evidence only; exact additive revision on a declared scale'


def test_v4_exact_module_corpus_hash():
    import hashlib
    assert hashlib.sha256(m.__doc__.encode()).hexdigest() == 'c4ee9a28b1480abeb0dce7cadeacf032607ad3fd11c73934702862896e297f19'


def test_v5_belief_count_exact_cap():
    beliefs = [{'id': 'b%d' % i, 'statement': 'declared', 'prior': 100} for i in range(64)]
    assert m.revise({'beliefs': beliefs, 'evidence': []})['belief_count'] == 64
    beliefs.append({'id': 'last', 'statement': 'declared', 'prior': 100})
    with pytest.raises(ValueError, match='^BELIEF880:beliefs must be a list of 1[.][.]64 records$'):
        m.revise({'beliefs': beliefs, 'evidence': []})


def test_v5_text_exact_cap_at_every_public_field():
    for field, label in [('belief_id', 'belief id'), ('statement', 'belief statement'),
                         ('evidence_id', 'evidence id'), ('reference', 'evidence belief_id')]:
        for size in (200, 201):
            text = 'x' * size
            d = {'beliefs': [{'id': 'b', 'statement': 'declared', 'prior': 100}],
                 'evidence': [{'id': 'e', 'belief_id': 'b', 'direction': 'supports', 'strength': 0}]}
            if field == 'belief_id':
                d['beliefs'][0]['id'] = text; d['evidence'][0]['belief_id'] = text
            elif field == 'statement': d['beliefs'][0]['statement'] = text
            elif field == 'evidence_id': d['evidence'][0]['id'] = text
            else:
                d['beliefs'][0]['id'] = 'x' * 200
                d['evidence'][0]['belief_id'] = text
            if size == 200:
                assert m.revise(d)['evidence_count'] == 1
            else:
                with pytest.raises(ValueError, match='^BELIEF880:' + label + ' must be nonblank text up to 200 characters$'):
                    m.revise(d)


def test_v5_zero_prior_strength_and_output_contract():
    d = {'beliefs': [{'id': 'b', 'statement': 'declared', 'prior': 0}],
         'evidence': [{'id': 'e', 'belief_id': 'b', 'direction': 'supports', 'strength': 0}]}
    out = m.revise(d)
    assert out['belief_count'] == 1 and out['evidence_count'] == 1
    assert out['scale'] == 1000 and out['retraction_threshold'] == 100
    assert out['beliefs'][0]['revised'] == 0
    d['evidence'][0]['strength'] = -1
    import re
    with pytest.raises(ValueError, match='^' + re.escape('BELIEF880:evidence strength must be an integer 0..100') + '$'):
        m.revise(d)


def test_v5_every_refusal_full_message():
    import copy
    import re
    cases = []
    def case(value, message):
        cases.append((value, 'BELIEF880:' + message))
    case(None, 'request must be a mapping')
    case({}, 'request must have exactly beliefs and evidence')
    case(dict(req(), extra=1), 'request must have exactly beliefs and evidence')
    case(req(beliefs=tuple(req()['beliefs'])), 'beliefs must be a list of 1..64 records')
    case(req(beliefs=None), 'beliefs must be a list of 1..64 records')
    case(req(beliefs=[]), 'beliefs must be a list of 1..64 records')
    case(req(evidence=tuple(req()['evidence'])), 'evidence must be a list of at most 256 records')
    case(req(evidence=None), 'evidence must be a list of at most 256 records')
    for index in (0, 1):
        d=req();d['beliefs'][index].pop('prior')
        case(d, 'belief %d must have exactly id, statement, prior' % index)
        d=req();d['evidence'][index].pop('strength')
        case(d, 'evidence %d must have exactly id, belief_id, direction, strength' % index)
    d=req();d['beliefs'][1]['id']='b1';case(d,'duplicate belief id')
    d=req();d['evidence'][1]['id']='e1';case(d,'duplicate evidence id')
    d=req();d['evidence'][0]['belief_id']='unknown';case(d,'evidence references unknown belief')
    d=req();d['evidence'][0]['direction']='maybe';case(d,'evidence direction must be supports or refutes')
    for field, label in [('id','belief id'),('statement','belief statement')]:
        for value in (None, ' ', 'x'*201):
            d=req();d['beliefs'][0][field]=value
            case(d,label+' must be nonblank text up to 200 characters')
    for field, label in [('id','evidence id'),('belief_id','evidence belief_id')]:
        for value in (None, ' ', 'x'*201):
            d=req();d['evidence'][0][field]=value
            case(d,label+' must be nonblank text up to 200 characters')
    for value in (True,-1,1001):
        d=req();d['beliefs'][0]['prior']=value
        case(d,'belief prior must be an integer 0..1000')
    for value in (True,-1,101):
        d=req();d['evidence'][0]['strength']=value
        case(d,'evidence strength must be an integer 0..100')
    for value, message in cases:
        with pytest.raises(ValueError, match='^' + re.escape(message) + '$'):
            m.revise(copy.deepcopy(value))


def test_v6_nondict_records_have_exact_schema_refusals():
    import re
    for d, message in [
        (req(beliefs=[5]), 'BELIEF880:belief 0 must have exactly id, statement, prior'),
        (req(evidence=[5]), 'BELIEF880:evidence 0 must have exactly id, belief_id, direction, strength'),
    ]:
        with pytest.raises(ValueError, match='^' + re.escape(message) + '$'):
            m.revise(d)


def test_v6_unit_net_evidence_status_and_statement_values():
    for direction, expected, revised in [('supports', 'strengthened', 501), ('refutes', 'weakened', 499)]:
        d = {'beliefs': [{'id': 'b', 'statement': '  caller-declared statement  ', 'prior': 500}],
             'evidence': [{'id': 'e', 'belief_id': 'b', 'direction': direction, 'strength': 1}]}
        belief = m.revise(d)['beliefs'][0]
        assert belief['status'] == expected
        assert belief['revised'] == revised
        assert belief['statement'] == 'caller-declared statement'
    out = m.revise(req())
    assert [b['statement'] for b in out['beliefs']] == ['the launch is on time', 'the vendor is reliable']
