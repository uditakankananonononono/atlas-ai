"""Error-coding repair pins for cognitive_learning_860_909.

Malformed inputs must surface as coded CognitiveLearningError naming the
problem, never raw KeyError/TypeError/ZeroDivisionError. Valid-input outputs
stay byte-identical (the pre-existing exact-transformation suite pins those;
this file re-pins one per repaired row as a witness).
"""
import pytest
from app.modules.m20_general_cognitive_worker.cognitive_learning_860_909 import execute, CognitiveLearningError

S = [{'source_id': 's', 'observed_at': '2026-10-18T00:00:00+00:00', 'kind': 'primary'}]

def payload(row, inputs):
    return {'tenant_id': 'tenant-a', 'actor_id': 'actor-a', 'sources': [dict(S[0])],
            'inputs': inputs, 'learner_goals': ['learn']}


def test_row_860_missing_year_is_coded():
    with pytest.raises(CognitiveLearningError, match="missing required input key: 'year'"):
        execute(860, payload(860, {'events': [{'event': 'x'}]}))


def test_row_860_missing_event_is_coded():
    with pytest.raises(CognitiveLearningError, match="missing required input key: 'event'"):
        execute(860, payload(860, {'events': [{'year': 1}]}))


def test_row_860_non_object_event_is_coded():
    with pytest.raises(CognitiveLearningError, match='invalid input structure'):
        execute(860, payload(860, {'events': [['x', 1]]}))


def test_row_865_missing_weighted_score_is_coded():
    inputs = {'options': [{'name': 'a', 'scores': {}}], 'weights': {'fit': 1}}
    with pytest.raises(CognitiveLearningError, match="missing required input key: 'fit'"):
        execute(865, payload(865, inputs))


def test_row_870_missing_attributes_is_coded():
    with pytest.raises(CognitiveLearningError, match="missing required input key: 'attributes'"):
        execute(870, payload(870, {'examples': [{}]}))


def test_row_887_missing_score_is_coded():
    with pytest.raises(CognitiveLearningError, match="missing required input key: 'score'"):
        execute(887, payload(887, {'attempts': [{'id': '1'}]}))


def test_row_900_missing_weight_is_coded():
    with pytest.raises(CognitiveLearningError, match="missing required input key: 'weight'"):
        execute(900, payload(900, {'hypothesis': 'h', 'evidence': [{}]}))


def test_row_881_empty_theory_scores_is_coded():
    with pytest.raises(CognitiveLearningError, match='theory_scores must be a non-empty object'):
        execute(881, payload(881, {'theory_scores': {}}))


def test_row_881_non_object_theory_scores_is_coded():
    with pytest.raises(CognitiveLearningError, match='theory_scores must be a non-empty object'):
        execute(881, payload(881, {'theory_scores': ['t1']}))


def test_row_881_non_list_scores_is_coded():
    with pytest.raises(CognitiveLearningError, match='invalid theory_scores'):
        execute(881, payload(881, {'theory_scores': {'t1': 'high'}}))


def test_row_881_empty_score_list_is_coded():
    with pytest.raises(CognitiveLearningError, match='invalid theory_scores'):
        execute(881, payload(881, {'theory_scores': {'t1': []}}))


def test_row_881_non_numeric_scores_is_coded():
    with pytest.raises(CognitiveLearningError, match='invalid theory_scores'):
        execute(881, payload(881, {'theory_scores': {'t1': ['high']}}))


def test_valid_input_outputs_unchanged_witnesses():
    assert execute(860, payload(860, {'events': [{'event': 'later', 'year': 2}, {'event': 'early', 'year': 1}]}))['result'] == \
        {'chronology': ['early', 'later'], 'continuities': [], 'changes': []}
    assert execute(865, payload(865, {'options': [{'name': 'a', 'scores': {'fit': .8}}, {'name': 'b', 'scores': {'fit': .4}}], 'weights': {'fit': 1}}))['result'] == \
        {'ranking': [{'option': 'a', 'score': 0.8}, {'option': 'b', 'score': 0.4}], 'selected': 'a'}
    assert execute(870, payload(870, {'examples': [{'attributes': ['living', 'moves']}, {'attributes': ['living', 'grows']}]}))['result'] == \
        {'defining_attributes': ['living'], 'category_rule': 'living'}
    assert execute(881, payload(881, {'theory_scores': {'t1': [.8, .9], 't2': [.2, .4]}}))['result'] == \
        {'comparative_fit': {'t1': 0.85, 't2': 0.3}, 'preferred_theory': 't1'}
    assert execute(887, payload(887, {'attempts': [{'id': '1', 'score': .2}, {'id': '2', 'score': .8}]}))['result'] == \
        {'best_attempt': '2', 'error_reduction': 0.6000000000000001, 'next_experiment': None}
    assert execute(900, payload(900, {'hypothesis': 'h', 'evidence': [{'weight': .8}, {'weight': -.2}]}))['result'] == \
        {'hypothesis': 'h', 'evidence_balance': 0.6000000000000001, 'new_questions': []}
