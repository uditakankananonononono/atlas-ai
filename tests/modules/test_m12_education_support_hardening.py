# Helper hardening for m12 education_support (rows 1460-1509 helper). Standalone: imports only the helper module,
# no app.main / FastAPI (the older education test files import app.main, which needs Python 3.11+).
# This is NOT a completion claim for the parked row 46 (Class 11 CBSE app).
import math
import pytest
from app.modules.m12_ai_research_lab.education_support import FEATURES, education_support

S = [{'source_id': 'teacher-1', 'observed_at': '2026-10-12T00:00:00+00:00'}]


def run(i, d):
    return education_support(i, {**d, 'sources': S})


def res(i, d):
    return run(i, d)['result']


# ---- 1460 engagement
def test_1460_weighted_mean_and_bands():
    assert res(1460, {'signals': [{'value': 1, 'weight': 1}, {'value': 0, 'weight': 3}]})['engagement_score'] == .25
    assert res(1460, {'signals': [{'value': .7}]})['band'] == 'high'
    assert res(1460, {'signals': [{'value': .69}]})['band'] == 'medium'
    assert res(1460, {'signals': [{'value': .4}]})['band'] == 'medium'
    assert res(1460, {'signals': [{'value': .39}]})['band'] == 'low'


def test_1460_rejects_bad_signals():
    for bad in ({'value': 1.5}, {'value': -.1}, {'value': True}, {'value': .5, 'weight': 0}, {'value': .5, 'weight': -1}, {'value': 'x'}):
        with pytest.raises(ValueError):
            res(1460, {'signals': [bad]})


# ---- 1461/1462
def test_1461_logistic_value_and_human_review():
    r = res(1461, {'features': {'a': 2}, 'coefficients': {'intercept': 0, 'a': 1}, 'model_version': 'v1'})
    assert r['dropout_risk_probability'] == round(1 / (1 + math.exp(-2)), 4) == .8808
    assert r['intervention_decision'] == 'human_review_required' and r['model_version'] == 'v1'
    assert res(1461, {'features': {'a': 2}, 'coefficients': {'intercept': -1, 'a': .5}})['dropout_risk_probability'] == .5
    assert res(1461, {'features': {'a': 2}, 'coefficients': {'a': -1}})['dropout_risk_probability'] == round(1 / (1 + math.exp(2)), 4)


def test_1461_missing_feature_named_and_intercept_not_a_feature():
    with pytest.raises(ValueError, match='missing model features: b, c'):
        res(1461, {'features': {'a': 1}, 'coefficients': {'a': 1, 'c': 1, 'b': 1}})
    assert res(1461, {'features': {}, 'coefficients': {'intercept': 0, 'a': 0}} | {'features': {'a': 5}})


def test_1462_linear_prediction():
    assert res(1462, {'features': {'practice': 3}, 'coefficients': {'intercept': 4, 'practice': 2}})['predicted_performance'] == 10
    assert res(1462, {'features': {'p': 3, 'q': 1}, 'coefficients': {'p': 2, 'q': -5}})['predicted_performance'] == 1


# ---- 1463 recommendation
def test_1463_cosine_ranking_ties_and_zero():
    r = res(1463, {'learner_vector': [1, 0], 'candidates': [
        {'id': 'b', 'vector': [0, 1]}, {'id': 'a', 'vector': [1, 0]}, {'id': 'z', 'vector': [1, 1]},
        {'id': 'c', 'vector': [1, 1]}, {'id': 'zero', 'vector': [0, 0]}]})
    assert [(x['id'], x['score']) for x in r['ranked_recommendations']] == [
        ('a', 1.0), ('c', .7071), ('z', .7071), ('b', 0.0), ('zero', 0)]
    assert r['selected'] is False


def test_1463_misaligned_vectors_rejected():
    with pytest.raises(ValueError, match='vectors must align'):
        res(1463, {'learner_vector': [1, 0], 'candidates': [{'id': 'a', 'vector': [1]}]})


# ---- 1464/1465/1466
def test_1464_score_is_fraction_of_learner_tags():
    r = res(1464, {'learner_tags': ['a', 'b'], 'content': [{'id': 'x', 'tags': ['a']}, {'id': 'y', 'tags': ['a', 'b']}, {'id': 'z'}]})
    assert [(c['id'], c['score'], c['matched_tags']) for c in r['ranked_content']] == [
        ('y', 1.0, ['a', 'b']), ('x', .5, ['a']), ('z', 0.0, [])]


def test_1465_peer_score_weights_complementary_twice_and_never_contacts():
    r = res(1465, {'learner': {'interests': ['bio', 'ml'], 'seeking': ['py']}, 'peers': [
        {'id': 'p2', 'interests': ['bio'], 'can_help_with': []},
        {'id': 'p1', 'interests': ['ml', 'bio'], 'can_help_with': ['py']},
        {'id': 'p0', 'interests': ['bio'], 'can_help_with': []}]})
    assert [(p['id'], p['score']) for p in r['ranked_peers']] == [('p1', 4), ('p0', 1), ('p2', 1)]
    assert r['contacted'] is False and r['consent_required'] is True


def test_1466_prerequisites_done_nodes_and_priority():
    r = res(1466, {'completed': ['a'], 'nodes': [
        {'id': 'b', 'prerequisites': ['a'], 'priority': 1}, {'id': 'c', 'prerequisites': ['a', 'x']},
        {'id': 'a'}, {'id': 'd', 'priority': 5}]})
    assert r['next_nodes'] == [{'id': 'd', 'priority': 5}, {'id': 'b', 'priority': 1}]


# ---- 1467/1468 writing
def test_1467_weighted_normalized_score_no_grade():
    r = res(1467, {'rubric': [{'id': 'x', 'max_score': 4, 'weight': 3}, {'id': 'y', 'max_score': 10}], 'ratings': {'x': 3, 'y': 10}})
    assert r['normalized_score'] == 81.25 and r['final_grade_awarded'] is False and r['human_moderation_required'] is True
    assert [(x['criterion_id'], x['score'], x['max_score']) for x in r['rubric_results']] == [('x', 3, 4), ('y', 10, 10)]
    assert res(1467, {'rubric': [{'id': 'x', 'max_score': 4}], 'ratings': {'x': 4}})['normalized_score'] == 100
    assert res(1467, {'rubric': [{'id': 'x', 'max_score': 4}], 'ratings': {'x': 0}})['normalized_score'] == 0


def test_1467_rejects_invalid_ratings():
    base = {'rubric': [{'id': 'x', 'max_score': 4}], 'ratings': {'x': 3}}
    for bad in ({'ratings': {'x': 5}}, {'ratings': {'x': -1}}, {'ratings': {}, 'rubric': [{'id': 'x', 'max_score': 4}, {'id': 'y', 'max_score': 4}]},
                {'rubric': [{'id': 'x', 'max_score': 0}]}, {'rubric': [{'id': 'x', 'max_score': 4, 'weight': 0}]},
                {'ratings': {'x': float('nan')}}, {'ratings': {'x': float('inf')}}, {'ratings': {'x': 'abc'}}):
        with pytest.raises(ValueError):
            res(1467, {**base, **bad})


def test_1468_feedback_only_below_target_sorted_by_gap():
    r = res(1468, {'rubric_results': [{'criterion_id': 'x', 'score': 1, 'target': 4}, {'criterion_id': 'y', 'score': 2, 'target': 3},
                                       {'criterion_id': 'z', 'score': 5, 'target': 5}, {'criterion_id': 'w', 'score': 0, 'target': 6, 'feedback': 'custom'}]})
    assert [(f['criterion_id'], f['gap'], f['feedback']) for f in r['prioritized_feedback']] == [
        ('w', 6, 'custom'), ('x', 3, 'Revise evidence for x'), ('y', 1, 'Revise evidence for y')]
    assert r['revision_owned_by_learner'] is True


# ---- assessment 1469-1479
OBJ = {'objectives': [{'id': 'o1'}, {'id': 'o2'}, {'id': 'o3'}], 'evidence': [{'id': 'e1', 'objective_ids': ['o1']}]}


def test_assessment_types_timing_and_unassessed():
    r = res(1470, OBJ)
    assert (r['assessment_type'], r['timing'], r['purpose']) == ('summative', 'end of learning', 'judge attainment')
    assert r['unassessed_objectives'] == ['o2', 'o3'] and r['score_or_grade_finalized'] is False
    assert r['attainment_summary'] == {'objectives_with_evidence': 1, 'total_objectives': 3}
    f = res(1469, OBJ)
    assert f['instructional_adjustments'] == [{'objective_id': x, 'action': 'collect evidence and reteach'} for x in ('o2', 'o3')]
    assert res(1471, OBJ)['prerequisite_gaps'] == [{'objective_id': x, 'diagnostic_follow_up': True} for x in ('o2', 'o3')]
    assert res(1477, OBJ)['next_teaching_moves'] == [{'objective_id': x, 'move': 'elicit new evidence'} for x in ('o2', 'o3')]


def test_assessment_rejects_unknown_objective_and_requires_inputs():
    with pytest.raises(ValueError, match='unknown objective ids'):
        res(1470, {'objectives': [{'id': 'o1'}], 'evidence': [{'id': 'e', 'objective_ids': ['nope']}]})
    with pytest.raises(ValueError, match='missing required inputs'):
        res(1470, {'objectives': [{'id': 'o1'}]})


def test_1473_1476_1479_computed_fields():
    d = {'objectives': [{'id': 'o1'}], 'evidence': [{'id': 'e1', 'objective_ids': ['o1'], 'rubric': ['r']}, {'id': 'e2', 'objective_ids': []}]}
    assert res(1473, d)['performance_observations'] == [{'evidence_id': 'e1', 'observable': True}, {'evidence_id': 'e2', 'observable': False}]
    assert res(1479, d)['reporting_summary'] == {'attained_evidence_count': 1, 'teacher_signoff_required': True}
    assert res(1476, d)['peer_moderation'] == {'anonymous': True, 'teacher_moderation_required': True}
    assert res(1476, {**d, 'anonymous': False})['peer_moderation']['anonymous'] is False


# ---- progress 1480-1483
def test_1480_standard_levels_and_status_boundary():
    r = res(1480, {'standards': [{'id': 'a', 'threshold': 70}, {'id': 'b', 'threshold': 50}, {'id': 'c', 'threshold': 50}, {'id': 'd', 'threshold': 50}],
                   'evidence': [{'standard_id': 'a', 'score': 60}, {'standard_id': 'a', 'score': 90}, {'standard_id': 'b', 'score': 40},
                                {'standard_id': 'c', 'score': 50}]})
    got = {s['standard_id']: (s['level'], s['status']) for s in r['standards']}
    assert got == {'a': (75.0, 'meets'), 'b': (40.0, 'developing'), 'c': (50.0, 'meets'), 'd': (None, 'insufficient_evidence')}
    assert r['averaged_into_single_grade'] is False


def test_1480_range_validation():
    for bad in ({'standards': [{'id': 'a', 'threshold': 101}], 'evidence': [{'standard_id': 'a', 'score': 1}]},
                {'standards': [{'id': 'a', 'threshold': 50}], 'evidence': [{'standard_id': 'a', 'score': 101}]},
                {'standards': [{'id': 'a', 'threshold': 50}], 'evidence': [{'standard_id': 'a', 'score': -1}]}):
        with pytest.raises(ValueError):
            res(1480, bad)


PROG = {'competencies': [{'id': 'c1', 'mastery_threshold': .5}, {'id': 'c2', 'mastery_threshold': .8}, {'id': 'c3', 'mastery_threshold': .1}],
        'evidence': [{'competency_id': 'c1', 'score': .5}, {'competency_id': 'c2', 'score': .79}]}


def test_1481_1482_mastery_boundary_and_unevidenced_default():
    r = res(1481, PROG)
    assert [(x['competency_id'], x['score'], x['mastered']) for x in r['competency_progress']] == [('c1', .5, True), ('c2', .79, False), ('c3', 0, False)]
    assert r['advancement_candidates'] == ['c1'] and r['advancement_requires_review'] is True
    m = res(1482, PROG)
    assert m['reteach'] == ['c2', 'c3'] and m['reassessment_required'] is True


def test_1481_score_range_validation():
    with pytest.raises(ValueError):
        res(1481, {**PROG, 'evidence': [{'competency_id': 'c1', 'score': 1.5}]})


def test_1483_precision_teaching_rates_celeration_and_decision():
    r = res(1483, {**PROG, 'timed_probes': [{'correct': 10, 'minutes': 2}, {'correct': 9, 'minutes': 3}]})
    assert r['frequency_per_minute'] == [5.0, 3.0] and r['celeration_ratio'] == .6 and r['decision'] == 'continue and monitor'
    assert res(1483, {**PROG, 'timed_probes': [{'correct': 10, 'minutes': 2}, {'correct': 9, 'minutes': 3}], 'aim': 4})['decision'] == 'review teaching'
    assert res(1483, {**PROG, 'timed_probes': [{'correct': 10, 'minutes': 2}, {'correct': 12, 'minutes': 3}], 'aim': 4})['decision'] == 'continue and monitor'
    with pytest.raises(ValueError):
        res(1483, {**PROG, 'timed_probes': [{'correct': 1, 'minutes': 0}]})


# ---- instruction/tutor
def test_1484_accuracy_and_release_flag():
    base = {'objective': 'o', 'examples': ['e']}
    r = res(1484, {**base, 'response_checks': [True, True, False, True]})
    assert r['guided_practice_accuracy'] == .75 and r['release_to_independent'] is False and r['delivered'] is False
    assert [p['order'] for p in r['sequence']] == [1, 2, 3, 4, 5]
    assert res(1484, {**base, 'response_checks': [True] * 5})['release_to_independent'] is True
    assert res(1484, base)['guided_practice_accuracy'] is None and res(1484, base)['release_to_independent'] is False


def test_1486_cumulative_progression_and_1489_weakest_item_tiebreak():
    r = res(1486, {'objective': 'o', 'examples': ['e'], 'skill_steps': ['s1', 's2', 's3']})
    assert r['cumulative_progression'] == [{'step': 's1', 'review': ['s1']}, {'step': 's2', 'review': ['s1', 's2']}, {'step': 's3', 'review': ['s1', 's2', 's3']}]
    a = res(1489, {'objective': 'o', 'examples': ['e'], 'attempts': [{'item_id': 'b', 'score': .5}, {'item_id': 'a', 'score': .5}, {'item_id': 'c', 'score': .9}]})
    assert a['adaptive_next_item'] == 'a' and a['attempt_summary'] == {'count': 3, 'mean_score': .633}


def test_1490_targets_weakest_component_with_id_tiebreak_and_threshold():
    kc = lambda *m: {'objective': 'o', 'learner_state': {'g': 1}, 'knowledge_components': [{'id': i, 'mastery': v} for i, v in m]}
    r = res(1490, kc(('k2', .3), ('k1', .3), ('k3', .9)))
    assert r['next_action'] == {'type': 'worked_example', 'knowledge_component_id': 'k1'} and r['automatic_high_stakes_action'] is False
    assert res(1490, kc(('k1', .5)))['next_action']['type'] == 'practice'
    assert res(1490, kc(('k1', .49)))['next_action']['type'] == 'worked_example'


# ---- boundary / privacy / provenance
def test_direct_identifiers_rejected_at_depth_in_dicts_and_lists_case_insensitive():
    base = {'signals': [{'value': .5}]}
    for bad in ({'email': 'a@b'}, {'Full_Name': 'x'}, {'nested': {'student_id': 1}}, {'rows': [{'phone': '1'}]}, {'rows': [[{'pupil_id': 3}]]}, {'learner_id': 'x'}):
        with pytest.raises(ValueError, match='direct learner identifier prohibited'):
            run(1460, {**base, **bad})
    assert run(1460, {**base, 'cohort': 'A'})['feature_id'] == 1460


def test_sources_required_with_both_fields():
    for bad in ([], [{'source_id': 'x'}], [{'observed_at': 'y'}], [{'source_id': '', 'observed_at': 'y'}], [S[0], {'source_id': 'x'}]):
        with pytest.raises(ValueError, match='source_id and observed_at required'):
            education_support(1460, {'signals': [{'value': .5}], 'sources': bad})
    with pytest.raises(ValueError, match='source_id and observed_at required'):
        education_support(1460, {'signals': [{'value': .5}]})


def test_unsupported_feature_rejected():
    for i in (1459, 1510, 0):
        with pytest.raises(ValueError, match='unsupported education feature'):
            run(i, {})


def test_envelope_flags_and_prediction_range():
    r = run(1462, {'features': {'a': 1}, 'coefficients': {'a': 1}})
    assert r['feature'] == FEATURES[1462] and r['mechanism_key'] == 'performance_prediction'
    assert r['side_effects'] == [] and r['qualified_teacher_review_required'] is True
    assert r['status'] == 'draft_for_learner_and_qualified_teacher_review'
    assert r['sources'] == S and r['evaluation']['observed_outputs'] == sorted(r['evaluation']['observed_outputs']) and 'predicted_performance' in r['evaluation']['observed_outputs']
    assert run(1466, {'completed': ['q'], 'nodes': [{'id': 'a'}]})['uncertainty']['prediction_is_not_fact'] is True
    assert run(1467, {'rubric': [{'id': 'x', 'max_score': 2}], 'ratings': {'x': 1}})['uncertainty']['prediction_is_not_fact'] is False
    assert run(1460, {'signals': [{'value': .5}]})['uncertainty']['prediction_is_not_fact'] is True


def test_open_questions_passthrough_and_observed_outputs_skip_empty():
    r = run(1466, {'completed': ['q'], 'nodes': [{'id': 'a', 'prerequisites': ['zz']}], 'open_questions': ['q1']})
    assert r['evaluation']['open_questions'] == ['q1']
    assert r['result']['next_nodes'] == [] and 'next_nodes' not in r['evaluation']['observed_outputs']


def test_feature_registry_keys_are_exactly_1460_through_1509():
    assert set(FEATURES) == set(range(1460, 1510))


def test_need_rejects_none_empty_list_and_empty_dict():
    for i, d in ((1460, {'signals': []}), (1460, {}), (1461, {'features': {'a': 1}, 'coefficients': {}}),
                 (1461, {'features': {}, 'coefficients': {'a': 1}}), (1466, {'completed': ['x'], 'nodes': []})):
        with pytest.raises(ValueError, match='missing required inputs'):
            res(i, d)
