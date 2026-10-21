"""Extra doc rows 46-50 (attention residue, flow, reframing, bias, intuition):
non-duplicate pins. Existing coverage lives in test_m20_working_memory.py,
test_m20_metacognition.py, test_m20_flow_structure_row17_validation.py and
test_m20_atomic_concepts_70_92.py; this file adds only what those miss.
Row 50 weight-robustness is a NEW build: RED-first against the old 20.2
result (no uniform-weight rescore / Pareto channels; the old key
'choice_independently_validated' was hardcoded False and is renamed
'choice_uniform_pareto_confirmed' because the channels rescore the same caller-provided
scores - they are NOT independent validation). Builder self-report.

Enumeration note (mutant-domain counts cited in review): the 729/0/0 and
5832/324/540 counts are on the len==1-PROJECTED domain (cases projected to a
unique dominant). At the RAW dominant-list level, before that projection,
the counts are 81/90 and 1782/918. The projection is what makes the
dominance-weakening mutants indistinguishable there; raw dominant-list
membership is a strictly finer discriminator."""
import pytest

from app.modules.m20_general_cognitive_worker.atomic_concepts_70_92 import run
from app.modules.m20_general_cognitive_worker.metacognition import FlowStateManager

OPTS = {'options': [
    {'id': 'a', 'salience': 3, 'scores': {'quality': 1, 'cost': 1}},
    {'id': 'b', 'salience': 2, 'scores': {'quality': 5, 'cost': 4}}],
    'criteria': [{'id': 'quality', 'weight': 3}, {'id': 'cost', 'weight': 1}]}


def test_row50_uniform_pareto_channels_exist_and_confirm():
    # RED on old code: no uniform_weight_choice / pareto_dominant keys.
    r = run('20.2', OPTS)['result']
    assert r['caller_weight_ranked_choice'] == 'b'
    assert r['uniform_weight_choice'] == 'b'
    assert r['uniform_tie'] is False
    assert r['pareto_dominant'] == 'b'  # b beats a on every criterion
    assert r['weight_sensitive'] is False
    assert r['choice_uniform_pareto_confirmed'] is True
    assert r['channels_independent_of_caller_weights'] is True


def test_row50_weight_sensitive_choice_is_not_confirmed():
    # RED on old code: keys absent.
    d = {'options': [
        {'id': 'a', 'salience': 9, 'scores': {'q': 10, 'c': 0}},
        {'id': 'b', 'salience': 1, 'scores': {'q': 0, 'c': 11}}],
        'criteria': [{'id': 'q', 'weight': 10}, {'id': 'c', 'weight': 1}]}
    r = run('20.2', d)['result']
    assert r['caller_weight_ranked_choice'] == 'a'  # caller weights rule
    assert r['uniform_weight_choice'] == 'b'  # weight-free channel disagrees
    assert r['pareto_dominant'] is None  # no dominance either way
    assert r['weight_sensitive'] is True
    assert r['choice_uniform_pareto_confirmed'] is False


def test_row50_uniform_tie_makes_rescore_channel_inconclusive():
    # RED on old code: uniform_tie key absent; robust required rescore only.
    d = {'options': [
        {'id': 'a', 'salience': 1, 'scores': {'q': 2, 'c': 2}},
        {'id': 'b', 'salience': 2, 'scores': {'q': 2, 'c': 2}}],
        'criteria': [{'id': 'q', 'weight': 5}, {'id': 'c', 'weight': 1}]}
    r = run('20.2', d)['result']
    assert r['uniform_tie'] is True
    assert r['uniform_weight_choice'] == 'a'  # first-tied: deterministic but arbitrary
    assert r['caller_weight_ranked_choice'] == 'a'
    assert r['pareto_dominant'] is None  # identical scores: no strict dominance
    assert r['choice_uniform_pareto_confirmed'] is False  # tie means rescore cannot confirm


def test_row50_duplicate_ids_no_vacuous_pareto_dominance():
    # Legacy accepts duplicate ids (collapse, last wins). All-identical ids
    # leave every option with an empty competitor set, so dominant collects
    # len(opts) entries and dom stays None (no unique dominant). RED on
    # pristine ce19b328: pareto_dominant key absent. This is a
    # legacy-semantics pin; given the len==1 selection rule no dominance-loop
    # mutant distinguishes it.
    d = {'options': [
        {'id': 'a', 'salience': 1, 'scores': {'q': 1}},
        {'id': 'a', 'salience': 2, 'scores': {'q': 9}}],
        'criteria': [{'id': 'q', 'weight': 1}]}
    r = run('20.2', d)['result']
    assert r['analytic_scores'] == {'a': 9.0}  # legacy collapse, last wins
    assert r['caller_weight_ranked_choice'] == 'a'
    assert r['pareto_dominant'] is None  # no competitor set, not vacuous dominance
    assert r['uniform_weight_choice'] == 'a'
    assert r['choice_uniform_pareto_confirmed'] is True  # rescore channel: no tie, same id


def test_row50_pareto_requires_strict_dominance_over_each_competitor():
    # x weakly beats everyone but only TIES z (identical vectors): textbook
    # pairwise Pareto dominance fails, so no dominant. RED on pristine
    # ce19b328: keys absent. Broken by M5 (tie-detection dropped) via
    # uniform_tie; the dominance-weakening mutant provably cannot change dom
    # (a tied competitor mirrors x into dominant, breaking len==1 either way).
    d = {'options': [
        {'id': 'x', 'salience': 1, 'scores': {'q': 3, 'c': 3}},
        {'id': 'y', 'salience': 2, 'scores': {'q': 1, 'c': 1}},
        {'id': 'z', 'salience': 3, 'scores': {'q': 3, 'c': 3}}],
        'criteria': [{'id': 'q', 'weight': 1}, {'id': 'c', 'weight': 1}]}
    r = run('20.2', d)['result']
    assert r['pareto_dominant'] is None  # x ties z everywhere: not dominant
    assert r['uniform_tie'] is True  # x and z tie at 6
    assert r['choice_uniform_pareto_confirmed'] is False


def test_row50_duplicate_id_mixed_vectors_no_unique_dominant():
    # Distinguishing case for the textbook Pareto rule: b ties a2 elementwise
    # but strictly beats a1; because _others excludes by id, a2 cannot see a1,
    # so the weakened "strict over any" rule would wrongly crown b. Textbook
    # rule: no unique dominant. RED on pristine ce19b328: keys absent.
    # Broken by M6 (dominance weakened to strict-over-any).
    d = {'options': [
        {'id': 'a', 'salience': 1, 'scores': {'q': 0, 'c': 0}},
        {'id': 'a', 'salience': 2, 'scores': {'q': 0, 'c': 1}},
        {'id': 'b', 'salience': 3, 'scores': {'q': 0, 'c': 1}}],
        'criteria': [{'id': 'q', 'weight': 1}, {'id': 'c', 'weight': 1}]}
    r = run('20.2', d)['result']
    assert r['pareto_dominant'] is None  # NOT 'b' (weakened-rule answer)
    assert r['analytic_scores'] == {'a': 1.0, 'b': 1.0}  # duplicate a collapsed, last wins
    assert r['uniform_tie'] is True  # collapsed a and b tie at 1
    assert r['choice_uniform_pareto_confirmed'] is False


def test_row50_negative_weights_legacy_accepted_uniform_channel_ignores_them():
    # Negative criterion weights are legacy-accepted; they skew analytic_scores
    # but the uniform channel must ignore caller weights entirely.
    # RED on old code: uniform keys absent.
    d = {'options': [
        {'id': 'a', 'salience': 1, 'scores': {'q': 1, 'c': 5}},
        {'id': 'b', 'salience': 2, 'scores': {'q': 4, 'c': 1}}],
        'criteria': [{'id': 'q', 'weight': 1}, {'id': 'c', 'weight': -2}]}
    r = run('20.2', d)['result']
    assert r['analytic_scores'] == {'a': -9.0, 'b': 2.0}  # negative weight applied
    assert r['caller_weight_ranked_choice'] == 'b'
    assert r['uniform_weight_choice'] == 'a'  # 6 > 5 ignoring weights
    assert r['weight_sensitive'] is True
    assert r['choice_uniform_pareto_confirmed'] is False


def test_row47_flow_zone_off_edge_deltas_and_binary_float_boundary():
    # Pin of EXISTING behavior (GREEN pre-patch; not a row-50 build pin).
    # Mostly tests off-edge deltas and the binary-float boundary: 0.65-0.5 is
    # 0.15000...02 in binary, so the nominal 0.15 line lands in anxiety.
    f = FlowStateManager()
    assert f.assess(challenge=0.625, skill=0.5)['zone'] == 'flow'  # delta 0.125 < 0.15
    assert f.assess(challenge=0.75, skill=0.5)['zone'] == 'anxiety'  # delta 0.25 > 0.15
    assert f.assess(challenge=0.65, skill=0.5)['zone'] == 'anxiety'  # binary-float line
    assert f.assess(challenge=0.2, skill=0.2)['zone'] == 'flow'  # not < 0.2
    assert f.assess(challenge=0.19, skill=0.19)['zone'] == 'apathy'


def test_row50_duplicate_id_weak_only_dominance_is_not_enough():
    # Auditor survivor pin (full-drop mutant: strict clause removed, weak
    # Pareto only). a1=(q0,c1) TIES b=(q0,c1) elementwise; a2=(q1,c0) shares
    # a1's id, so by-id exclusion hides the mirror that would otherwise break
    # len==1 under the weak-only rule. Weak-only crowns 'a'; textbook: none.
    d = {'options': [
        {'id': 'a', 'salience': 1, 'scores': {'q': 0, 'c': 1}},
        {'id': 'a', 'salience': 2, 'scores': {'q': 1, 'c': 0}},
        {'id': 'b', 'salience': 3, 'scores': {'q': 0, 'c': 1}}],
        'criteria': [{'id': 'q', 'weight': 1}, {'id': 'c', 'weight': 1}]}
    r = run('20.2', d)['result']
    assert r['pareto_dominant'] is None  # NOT 'a' (weak-only answer)


def test_row50_pareto_partial_equality_still_dominant():
    # Reviewer-found survivor pin (M04: weak clause >= mutated to strict >).
    # b strictly beats a on q, TIES on c: textbook dominance holds (weak-all
    # plus strict on at least one criterion); the strict-everywhere mutant
    # would wrongly return None.
    d = {'options': [
        {'id': 'a', 'salience': 1, 'scores': {'q': 1, 'c': 1}},
        {'id': 'b', 'salience': 2, 'scores': {'q': 5, 'c': 1}}],
        'criteria': [{'id': 'q', 'weight': 1}, {'id': 'c', 'weight': 1}]}
    r = run('20.2', d)['result']
    assert r['pareto_dominant'] == 'b'  # NOT None (strict-everywhere answer)


def test_row50_pareto_dominant_other_than_caller_choice_does_not_confirm():
    # Peer-survivor pin (second FINAL PARTIAL): production is
    # confirmed = rescore_confirms or (dom == best). Here 'a' is Pareto
    # dominant but the caller-weighted choice is 'b', so dominance of an
    # option OTHER than the caller's choice must NOT confirm; the surviving
    # mutant confirmed = rescore_confirms or (dom is not None) yields True.
    d = {'options': [
        {'id': 'a', 'salience': 1, 'scores': {'q': 5, 'c': 5}},
        {'id': 'b', 'salience': 2, 'scores': {'q': 4, 'c': 5}}],
        'criteria': [{'id': 'q', 'weight': -1}, {'id': 'c', 'weight': 1}]}
    r = run('20.2', d)['result']
    assert r['pareto_dominant'] == 'a'
    assert r['caller_weight_ranked_choice'] == 'b'
    assert r['choice_uniform_pareto_confirmed'] is False
