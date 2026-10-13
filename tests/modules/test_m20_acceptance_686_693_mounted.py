"""Acceptance pins for the mounted engines 686 to 693: hand-derived vectors, exact refusal text and input caps."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

BASE = '/api/v1/api/modules/20'
P686 = BASE + '/bdd-scenarios/686/execute'
P687 = BASE + '/test-driven-development/687/check'
P688 = BASE + '/acceptance-test-driven-development/688/bookkeeping'
P689 = BASE + '/refactoring/689/rename-local'
P690 = BASE + '/code-review/690/review'
P691 = BASE + '/pair-programming/691/diagnostics'
P692P = BASE + '/mob-programming/692/plan'
P692A = BASE + '/mob-programming/692/audit'
P693 = BASE + '/technical-debt/693/schedule'


@pytest.fixture
def call(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    counter = {'n': 0}

    def go(path, body, expect=200):
        counter['n'] += 1  # the app limits requests per tenant and actor, so every call uses its own tenant
        tenant = 'acc%s%d' % (path.rsplit('/', 2)[-2].replace('-', ''), counter['n'])
        r = client.post(path, headers=oidc_auth_headers(tenant, 'owner'), json=body)
        assert r.status_code == expect, r.text
        j = r.json()
        if expect == 200:
            assert j.pop('tenant_id') == tenant and j.pop('actor_id') == 'owner'
            return j
        return j['detail']
    return go


# ------------------------------------------------------------------ 686
def sc(name, given, when, then):
    return {'name': name, 'given': given, 'when': when, 'then': then}


A686 = {'scenarios': [
    sc('inc', [{'op': 'assign', 'var': 'n', 'value': 1}], [{'op': 'increment', 'var': 'n', 'by': 2}],
       [{'assert': 'equals', 'var': 'n', 'value': 3}]),
    sc('typed', [{'op': 'assign', 'var': 'f', 'value': True}], [], [{'assert': 'equals', 'var': 'f', 'value': 1}])]}


def test_686_vector_bool_is_not_int_and_flags(call):
    j = call(P686, {'data': A686})
    assert j['status'] == 'failures_present' and j['steps_executed'] == 5 and j['max_steps'] == 512
    inc, typed = j['scenarios']
    assert inc['status'] == 'passed' and inc['failure'] is None
    assert typed['status'] == 'failed'
    assert typed['failure'] == {'section': 'then', 'step_index': 0, 'step': {'assert': 'equals', 'var': 'f', 'value': 1},
                                'reason': 'assertion_failed', 'var': 'f', 'expected': 1, 'actual': True}
    assert j['semantics'] == {'ordering': 'sequential_in_listed_order', 'simultaneous': False,
                              'scenario_isolation': True, 'then_requires': 'all'}
    assert j['row'] == 686 and j['capability'] == 'Behavior-Driven Development'
    assert j['scope'] == 'bounded_declarative_given_when_then_dsl_execution'
    assert j['human_review_required'] is True
    for flag in ('repository_behavior_certified', 'natural_language_interpreted', 'arbitrary_code_executed',
                 'external_task_scheduled'):
        assert j['provenance'][flag] is False
    assert j['provenance']['input_sha256'] == 'a66f0aa3b8ffe9fd6af35bada86e30db779f20f1333ab7495f89d0fbd8be31bc'


def test_686_step_cap_is_inconclusive(call):
    j = call(P686, {'data': {**A686, 'max_steps': 3}})
    assert j['status'] == 'inconclusive_step_cap_exceeded' and j['steps_executed'] == 3
    assert [s['status'] for s in j['scenarios']] == ['passed', 'incomplete']
    assert j['scenarios'][1]['failure'] is None


def test_686_refusals_and_caps(call):
    dup = {'scenarios': [A686['scenarios'][0], A686['scenarios'][0]]}
    assert call(P686, {'data': dup}, 422) == 'duplicate scenario name: inc'
    bad = {'scenarios': [sc('x', [{'op': 'mul', 'var': 'n', 'value': 1}], [], [])]}
    assert call(P686, {'data': bad}, 422) == 'given[0] unsupported op (allowlist: assign, increment)'
    assert call(P686, {'data': {**A686, 'max_steps': 0}}, 422) == 'max_steps requires an integer 1..4096'
    assert call(P686, {'data': {**A686, 'max_steps': 4097}}, 422) == 'max_steps requires an integer 1..4096'
    assert call(P686, {'data': {'scenarios': []}}, 422) == 'scenarios require a list of 1..16 scenarios'
    one = A686['scenarios'][0]
    ok16 = {'scenarios': [dict(one, name='s%d' % i) for i in range(16)]}
    assert call(P686, {'data': ok16})['status'] == 'all_passed'
    assert call(P686, {'data': {'scenarios': ok16['scenarios'] + [dict(one, name='s16')]}}, 422) == \
        'scenarios require a list of 1..16 scenarios'
    assert call(P686, {'data': {**ok16, 'max_steps': 4096}})['max_steps'] == 4096


# ------------------------------------------------------------------ 687
def rc(stage, ordinal, rev, outcome, suite='s'):
    return {'stage': stage, 'ordinal': ordinal, 'revision_ref': rev, 'suite_ref': suite, 'evidence_ref': 'e' + str(ordinal),
            'results': [{'id': 't1', 'outcome': outcome}]}


def test_687_vector(call):
    c1 = {'id': 'c1', 'behavior': 'b1', 'receipts': [rc('red', 1, 'r1', 'FAIL'), rc('green', 2, 'r2', 'PASS'),
                                                      rc('refactor', 3, 'r3', 'PASS')]}
    c2 = {'id': 'c2', 'behavior': 'b2', 'receipts': [rc('red', 1, 'r1', 'PASS'), rc('green', 1, 'r1', 'PASS'),
                                                      rc('refactor', 2, 'r3', 'PASS')]}
    j = call(P687, {'data': {'as_of': 'now', 'cycles': [c1, c2]}})
    a, b = j['cycles']
    assert a['declaration_consistent'] is True and a['reasons'] == []
    assert a['result_counts'] == {'red': {'PASS': 0, 'FAIL': 1}, 'green': {'PASS': 1, 'FAIL': 0},
                                  'refactor': {'PASS': 1, 'FAIL': 0}}
    assert a['evidence_refs'] == ['e1', 'e2', 'e3']
    assert b['declaration_consistent'] is False
    assert b['reasons'] == ['stage_order_not_increasing', 'red_has_no_failure', 'red_green_revision_unchanged']
    assert j['consistent_cycles'] == 1 and j['status'] == 'supplied_receipt_consistency_only'
    for flag in ('tests_executed', 'evidence_verified', 'repository_behavior_verified', 'release_authority'):
        assert j[flag] is False


def test_687_refusals_and_caps(call):
    assert call(P687, {'data': {'as_of': 'now'}}, 422) == 'TESTDR687:fields:request'
    assert call(P687, {'data': {'as_of': 'now', 'cycles': []}}, 422) == 'TESTDR687:empty:cycles'
    cyc = {'id': 'c1', 'behavior': 'b', 'receipts': [rc('red', 1, 'r1', 'FAIL'), rc('green', 2, 'r2', 'PASS'),
                                                      rc('refactor', 3, 'r3', 'PASS')]}
    assert call(P687, {'data': {'as_of': 'now', 'cycles': [cyc, cyc]}}, 422) == 'TESTDR687:duplicate:cycle_id'
    many = [dict(cyc, id='c%d' % i) for i in range(64)]
    assert call(P687, {'data': {'as_of': 'now', 'cycles': many}})['consistent_cycles'] == 64
    assert call(P687, {'data': {'as_of': 'now', 'cycles': many + [dict(cyc, id='c64')]}}, 422) == 'TESTDR687:limit:cycles'


# ------------------------------------------------------------------ 688
def test_688_vector_and_constant(call):
    j = call(P688, {'data': {'feature': 'F', 'acceptance_criteria': [{'id': 'c1', 'text': 't1'}, {'id': 'c2', 'text': 't2'}],
                             'examples': [{'criterion_id': 'c1', 'text': 'e'}, {'criterion_id': 'c9', 'text': 'e2'}],
                             'stakeholders': ['po', 'qa'], 'agreed_by': ['po', 'dev']}})
    assert j['criteria_count'] == 2 and j['example_count'] == 2
    assert j['pending_agreement'] == ['qa'] and j['unlisted_agreements'] == ['dev']
    assert j['agreement_complete'] is False
    assert j['uncovered_criterion_ids'] == ['c2'] and j['orphan_example_criterion_ids'] == ['c9']
    assert j['tests_executed'] is False and j['caller_declared_agreement'] is True
    assert len(j['limits']) == 4
    # constant only: it is hard-coded true, whatever the input, and is not evidence of anything
    assert j['executable_before_implementation'] is True


def test_688_refusals(call):
    good = {'feature': 'F', 'acceptance_criteria': [{'id': 'c1', 'text': 't'}], 'examples': [],
            'stakeholders': ['po']}
    for key in ('run_tests', 'execute', 'deploy', 'release', 'certify'):
        assert call(P688, {'data': {**good, key: True}}, 422) == 'ACCEPT688:EXECUTION_REQUEST:' + key
    assert call(P688, {'data': {**good, 'zzz': 1}}, 422) == 'ACCEPT688:UNKNOWN_KEY'
    assert call(P688, {'data': {k: v for k, v in good.items() if k != 'feature'}}, 422) == 'ACCEPT688:MISSING:feature'
    dup = {**good, 'acceptance_criteria': [{'id': 'c1', 'text': 't'}, {'id': 'c1', 'text': 'u'}]}
    assert call(P688, {'data': dup}, 422) == 'ACCEPT688:DUPLICATE:criterion_id'
    assert call(P688, {'data': {**good, 'stakeholders': []}}, 422) == 'ACCEPT688:EMPTY:stakeholders'


# ------------------------------------------------------------------ 689
def test_689_vector(call):
    j = call(P689, {'source': 'def f(a):\n    t = a + 1\n    return t * 2\n', 'old': 't', 'new': 'u'})
    assert j['source'] == 'def f(a):\n    u = a + 1\n    return u * 2\n' and j['renamed_occurrences'] == 2
    assert j['before_sha256'].startswith('eb969d7dd82d1105') and j['after_sha256'].startswith('4a9264d7410079ed')
    assert j['ast_alpha_equivalence_checked'] is True and j['repository_behavior_verified'] is False
    assert j['boundary'] == 'Restricted single-function local rename; no execution, file write, merge or release.'


def test_689_refusals(call):
    src = 'def f(a):\n    t = a + 1\n    return t * 2\n'
    assert call(P689, {'source': src, 'old': 't', 'new': 't'}, 422) == 'distinct ASCII non-keyword identifiers required'
    for old, new in (('a', 'u'), ('t', 'a')):
        assert call(P689, {'source': src, 'old': old, 'new': new}, 422) == 'cannot rename or collide with a parameter'
    assert call(P689, {'source': src, 'old': 'zz', 'new': 'u'}, 422) == 'old identifier is not a local assignment target'
    for bad in (src + 'def g(a):\n    return a\n', 'import os\n'):
        assert call(P689, {'source': bad, 'old': 't', 'new': 'u'}, 422) == 'exactly one plain function required'


# ------------------------------------------------------------------ 690
D690 = '--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,2 @@\n+password = "hunter2hunter2"\n+print(x)  \n'
LIST690 = ['no debug output', 'no secrets', 'tests included', 'style', 'naming is clear']


def test_690_vector_findings_checklist_and_decision(call):
    j = call(P690, {'diff': D690, 'review_checklist': LIST690, 'author': 'ann'})
    assert j['input_sha256'].startswith('96f59e92dd214ef9') and j['files'] == ['app.py'] and j['added_lines'] == 2
    assert [(f['rule'], f['severity'], f['path'], f['line']) for f in j['findings']] == [
        ('hardcoded-secret', 'blocking', 'app.py', 1), ('debug-leftover', 'warning', 'app.py', 2),
        ('trailing-whitespace', 'nit', 'app.py', 2), ('missing-tests', 'warning', None, None)]
    assert [(c['status'], c['rules']) for c in j['checklist']][4] == ('needs_human', [])
    assert [c['status'] for c in j['checklist']][:4] == ['fail', 'fail', 'fail', 'fail']
    assert j['unresolved_blockers'] == [j['findings'][0]]
    assert j['decision'] == 'request_changes' and j['approval'] is None
    assert j['self_approval_forbidden'] is True and j['human_review_required'] is True


def test_690_approval_paths(call):
    clean = '--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,1 @@\n+x = 1\n'
    j = call(P690, {'diff': clean, 'review_checklist': [], 'author': 'ann', 'reviewer': 'bob',
                    'requested_decision': 'approve'})
    assert j['decision'] == 'approved_by_reviewer' and j['approval'] == {'reviewer': 'bob', 'author': 'ann'}
    j = call(P690, {'diff': D690, 'review_checklist': [], 'author': 'ann', 'reviewer': 'bob',
                    'requested_decision': 'approve'})
    assert j['decision'] == 'request_changes' and j['approval'] is None
    j = call(P690, {'diff': clean, 'review_checklist': [], 'author': 'ann', 'requested_decision': 'request_changes'})
    assert j['decision'] == 'request_changes'
    assert call(P690, {'diff': clean, 'review_checklist': [], 'author': 'ann', 'reviewer': ' ANN ',
                       'requested_decision': 'approve'}, 422) == 'reviewer must differ from author'
    assert call(P690, {'diff': clean, 'review_checklist': [], 'author': 'ann',
                       'requested_decision': 'approve'}, 422) == 'approval requires a reviewer'


def test_690_valid_context_diff_is_parsed_without_context_findings(call):
    with_context = '--- a/x\n+++ b/x\n@@ -1,1 +1,3 @@\n context\n+a\n+b\n'
    j = call(P690, {'diff': with_context, 'review_checklist': [], 'author': 'ann'})
    assert j['files'] == ['x'] and j['added_lines'] == 2
    assert j['findings'] == [] and j['unresolved_blockers'] == []
    assert j['decision'] == 'no_issues_found' and j['approval'] is None
    assert j['self_approval_forbidden'] and j['human_review_required']
    # Context consumes source positions but is not reviewed as added code.
    debug_context = '--- a/x\n+++ b/x\n@@ -1,1 +1,2 @@\n print("context")\n+print("added")\n'
    j = call(P690, {'diff': debug_context, 'review_checklist': [], 'author': 'ann'})
    assert j['added_lines'] == 1
    assert [(f['rule'], f['path'], f['line']) for f in j['findings']] == [('debug-leftover', 'x', 2)]


@pytest.mark.parametrize('diff', [
    '--- a/x\n+++ b/x\n@@ -1,2 +1,3 @@\n context\n+a\n+b\n',  # wrong old count
    '--- a/x\n+++ b/x\n@@ -1,1 +1,3 @@\n context\n+a\n',  # truncated new count
    '--- a/x\n+++ b/x\n@@ -1,1 +1,2 @@\n context\n+a\n+b\n',  # excess addition
    '--- a/x\n+++ b/x\n@@ -1,x +1,2 @@\n context\n+a\n',  # malformed header
])
def test_690_malformed_context_counts_refused(call, diff):
    detail = call(P690, {'diff': diff, 'review_checklist': [], 'author': 'ann'}, 422)
    assert detail in ('hunk line counts do not match its header', 'malformed hunk header')


def test_690_oversize_context_diff_refused_before_parse(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    diff = '--- a/x\n+++ b/x\n@@ -1,1 +1,2 @@\n context\n+' + 'a' * 1_000_001 + '\n'
    r = client.post(P690, headers=oidc_auth_headers('acc690oversize', 'owner'),
                    json={'diff': diff, 'review_checklist': [], 'author': 'ann'})
    assert r.status_code == 422
    assert any(e['loc'] == ['body', 'diff'] and e['type'] == 'string_too_long' for e in r.json()['detail'])


# ------------------------------------------------------------------ 691
def test_691_vector(call):
    j = call(P691, {'data': {'session_id': 's1', 'task': 't', 'participants': ['ann', 'bob'],
                             'rotations': [{'driver_id': 'ann', 'duration_minutes': 30},
                                           {'driver_id': 'bob', 'duration_minutes': 10, 'handoff_note': 'n'},
                                           {'driver_id': 'bob', 'duration_minutes': 20}],
                             'understanding_checks': [{'item': 'api', 'confirmed': True},
                                                      {'item': 'edge', 'confirmed': False}]}})
    assert j['rotation_count'] == 3 and j['total_minutes'] == 60
    assert j['drive_minutes'] == {'ann': 30, 'bob': 30} and j['drive_share'] == {'ann': 0.5, 'bob': 0.5}
    assert j['dominant_driver'] is None and j['never_drove'] == []
    assert j['consecutive_repeat_indexes'] == [2] and j['missing_handoff_indexes'] == []
    assert j['unconfirmed_understanding_items'] == ['edge']
    assert j['balanced_rotation'] is True and j['shared_understanding_aligned'] is False
    assert j['gaps'] == ['consecutive_driver_repeat', 'unconfirmed_understanding']
    assert j['status'] == 'session_rotation_gaps'
    for flag in ('collaboration_observed', 'code_changes_made', 'source_truth_verified'):
        assert j[flag] is False


def test_691_refusals(call):
    base = {'session_id': 's1', 'task': 't', 'participants': ['ann', 'bob'],
            'rotations': [{'driver_id': 'ann', 'duration_minutes': 30}],
            'understanding_checks': [{'item': 'x', 'confirmed': True}]}

    def with_(**kw):
        return {'data': {**base, **kw}}
    assert call(P691, with_(participants=['ann']), 422) == 'participants requires bounded text list'
    assert call(P691, with_(rotations=[{'driver_id': 'zed', 'duration_minutes': 5}]), 422) == \
        'rotation driver_id must be one of the participants'
    for minutes in (0, 181):
        assert call(P691, with_(rotations=[{'driver_id': 'ann', 'duration_minutes': minutes}]), 422) == \
            'duration_minutes requires 0 < minutes <= 180'
    assert call(P691, with_(rotations=[{'driver_id': 'ann', 'duration_minutes': 180}]))['total_minutes'] == 180
    assert call(P691, with_(understanding_checks=[{'item': 'x', 'confirmed': 1}]), 422) == 'confirmed requires a boolean'


# ------------------------------------------------------------------ 692
def test_692_plan_vector(call):
    j = call(P692P, {'participants': ['a', 'b', 'c'], 'task': 'task', 'session_minutes': 50, 'rotation_minutes': 20,
                     'break_every_minutes': 20, 'break_minutes': 5})
    assert [(t['kind'], t.get('driver'), t.get('navigator'), t.get('mob'), t['start_minute'], t['end_minute'])
            for t in j['turns']] == [
        ('turn', 'a', 'b', ['c'], 0, 20), ('break', None, None, None, 20, 25),
        ('turn', 'b', 'c', ['a'], 25, 45), ('break', None, None, None, 45, 50),
        ('turn', 'c', 'a', ['b'], 50, 60)]
    assert j['turns'][4]['minutes'] == 10
    assert j['driver_minutes'] == {'a': 20, 'b': 20, 'c': 10} and j['driver_minutes_spread'] == 10
    assert j['everyone_drives'] is True and j['work_minutes'] == 50 and j['total_wall_minutes'] == 60
    assert j['session_executed'] is False and j['evidence_independently_verified'] is False
    assert j['human_review_required'] is True


def test_692_audit_vector_and_empty_log(call):
    j = call(P692A, {'participants': ['a', 'b', 'c'],
                     'log': [{'driver': 'a', 'start_minute': 0, 'end_minute': 30},
                             {'driver': 'b', 'start_minute': 20, 'end_minute': 40},
                             {'driver': 'x', 'start_minute': 0, 'end_minute': 5}]})
    assert j['violations'] == [{'code': 'unknown_driver', 'index': 2, 'driver': 'x'},
                               {'code': 'overlap', 'index': 1, 'with_index': 0},
                               {'code': 'driver_share_exceeded', 'driver': 'a', 'share': 0.6},
                               {'code': 'never_drove', 'driver': 'c'}]
    assert j['ok'] is False and j['driver_minutes'] == {'a': 30, 'b': 20, 'c': 0} and j['never_drove'] == ['c']
    e = call(P692A, {'participants': ['a', 'b', 'c'], 'log': []})
    assert e['ok'] is False and e['violations'] == [{'code': 'empty_log'}]


def test_692_refusals(call):
    assert call(P692P, {'participants': ['a', 'b'], 'task': 't', 'session_minutes': 30, 'rotation_minutes': 10}, 422) == \
        'a mob needs at least 3 participants'
    assert call(P692P, {'participants': ['a', 'b', 'c'], 'task': 't', 'session_minutes': 10, 'rotation_minutes': 20},
                422) == 'rotation_minutes must not exceed session_minutes'
    assert call(P692P, {'participants': ['a', 'b', 'c'], 'task': 't', 'session_minutes': 30, 'rotation_minutes': 10,
                        'start_driver': 'z'}, 422) == 'start_driver must be one of the participants'
    assert call(P692A, {'participants': ['a', 'b', 'c'], 'log': [{'driver': 'a'}]}, 422) == 'log entry keys refused'


# ------------------------------------------------------------------ 693
def test_693_vector(call):
    j = call(P693, {'data': {'budget_hours': 6, 'items': [
        {'id': 'a', 'benefit': 5, 'cost': 4}, {'id': 'b', 'benefit': 6, 'cost': 3, 'depends_on': ['a']},
        {'id': 'c', 'benefit': 4, 'cost': 2}]}})
    assert j['selected_ids'] == ['a', 'c'] and j['total_benefit'] == 9 and j['total_cost'] == 6
    assert j['budget_hours'] == 6 and j['status'] == 'optimal_selection_certified'
    assert j['unselected'] == [{'id': 'b', 'reason': 'infeasible_within_budget', 'closure_cost_hours': 7}]
    cert = j['certificate']
    assert (cert['algorithm'], cert['items'], cert['subsets_enumerated'], cert['state_cap']) == \
        ('bounded_exhaustive_subset_search', 3, 8, 4096)
    assert cert['optimal_benefit'] == 9 and cert['optimal_cost'] == 6 and cert['prerequisite_closure_required'] is True
    assert cert['tie_break'] == 'lexicographically smallest sorted selected-id tuple among benefit-maximal feasible subsets'
    assert cert['independently_reproducible'] is True
    assert j['provenance']['input_sha256'] == 'e7fa255e659ce828180111d17625a7a6cf0f2241d63946cb7a56a226b4af3ef1'
    for flag in ('benefits_are_predicted_savings', 'repository_edits', 'learned_prioritization', 'external_task_scheduled'):
        assert j['provenance'][flag] is False


def test_693_refusals_and_cap(call):
    def d(**kw):
        return {'data': {'budget_hours': 6, 'items': [{'id': 'a', 'benefit': 5, 'cost': 4}], **kw}}
    cyc = [{'id': 'a', 'benefit': 1, 'cost': 1, 'depends_on': ['b']}, {'id': 'b', 'benefit': 1, 'cost': 1, 'depends_on': ['a']}]
    assert call(P693, d(items=cyc), 422) == 'dependency cycle detected involving: a, b'
    assert call(P693, d(items=[]), 422) == 'items require a list of 1..12 debt items'
    assert call(P693, d(items=[{'id': 'a', 'benefit': 1, 'cost': 1, 'depends_on': ['q']}]), 422) == \
        'unknown dependency reference: q'
    assert call(P693, d(items=[{'id': 'a', 'benefit': True, 'cost': 1}]), 422) == \
        'items[0].benefit requires a finite non-boolean number'
    assert call(P693, {'data': {'items': [{'id': 'a', 'benefit': 1, 'cost': 1}]}}, 422) == 'budget_hours is required'
    twelve = [{'id': 'i%02d' % i, 'benefit': 1, 'cost': 1} for i in range(12)]
    assert call(P693, d(items=twelve))['certificate']['subsets_enumerated'] == 4096
    assert call(P693, d(items=twelve + [{'id': 'i12', 'benefit': 1, 'cost': 1}]), 422) == \
        'items require a list of 1..12 debt items'


# ------------------------------------------------------------------ route-level validation (flat routes, caps)
def _is_model_error(detail):
    """Pydantic refusals carry a list of error objects; engine refusals carry the engine's text."""
    return isinstance(detail, list)


SRC689 = 'def f(a):\n    t = a + 1\n    return t * 2\n'


def test_flat_routes_validate_fields_before_the_engine(call):
    for path, body in ((P689, {'old': 't', 'new': 'u'}), (P689, {'source': SRC689, 'old': 't'}),
                       (P689, {'source': 5, 'old': 't', 'new': 'u'}),
                       (P690, {'review_checklist': [], 'author': 'a'}), (P690, {'diff': D690, 'author': 'a'}),
                       (P690, {'diff': 5, 'review_checklist': [], 'author': 'a'}),
                       (P692P, {'participants': ['a', 'b', 'c'], 'task': 't', 'session_minutes': 30}),
                       (P692A, {'participants': ['a', 'b', 'c']})):
        assert _is_model_error(call(path, body, 422)), path
    for path in (P686, P687, P688, P691, P693):
        assert _is_model_error(call(path, {}, 422)), path
        assert _is_model_error(call(path, {'data': 5}, 422)), path


def test_689_route_caps_exact(call):
    ok = SRC689 + '#' * (100000 - len(SRC689))
    assert len(ok) == 100000
    assert call(P689, {'source': ok, 'old': 't', 'new': 'u'})['renamed_occurrences'] == 2
    over = SRC689 + '#' * (100001 - len(SRC689))
    assert _is_model_error(call(P689, {'source': over, 'old': 't', 'new': 'u'}, 422))
    name = 'n' * 256
    assert call(P689, {'source': SRC689, 'old': 't', 'new': name})['renamed_occurrences'] == 2
    assert _is_model_error(call(P689, {'source': SRC689, 'old': 't', 'new': name + 'n'}, 422))
    assert _is_model_error(call(P689, {'source': SRC689, 'old': 'o' * 257, 'new': 'u'}, 422))


def test_690_route_caps_exact(call):
    # at the cap the request reaches the engine (text refusal); one over is refused by the route model (error list)
    at = call(P690, {'diff': 'x' * 1_000_000, 'review_checklist': [], 'author': 'a'}, 422)
    assert not _is_model_error(at)
    assert _is_model_error(call(P690, {'diff': 'x' * 1_000_001, 'review_checklist': [], 'author': 'a'}, 422))
    clean = '--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,1 @@\n+x = 1\n'
    assert len(call(P690, {'diff': clean, 'review_checklist': ['q'] * 64, 'author': 'a'})['checklist']) == 64
    assert _is_model_error(call(P690, {'diff': clean, 'review_checklist': ['q'] * 65, 'author': 'a'}, 422))


def test_resource_refs_cap_exact_on_three_representative_routes(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    bodies = {P686: {'data': A686}, P689: {'source': SRC689, 'old': 't', 'new': 'u'},
              P692P: {'participants': ['a', 'b', 'c'], 'task': 't', 'session_minutes': 30, 'rotation_minutes': 10}}
    for n, (path, body) in enumerate(bodies.items()):
        tenant = 'refs%d' % n
        headers = oidc_auth_headers(tenant, 'owner')
        refs = [{'tenant_id': tenant, 'actor_id': 'owner', 'id': str(i)} for i in range(64)]
        assert client.post(path, headers=headers, json={**body, 'resource_refs': refs}).status_code == 200
        refs.append({'tenant_id': tenant, 'actor_id': 'owner', 'id': '64'})
        assert client.post(path, headers=headers, json={**body, 'resource_refs': refs}).status_code == 422


# ------------------------------------------------------------------ boundaries found by the mutation check
def _pair(rotations):
    return {'data': {'session_id': 's', 'task': 't', 'participants': ['ann', 'bob'], 'rotations': rotations,
                     'understanding_checks': [{'item': 'x', 'confirmed': True}]}}


def test_691_dominant_driver_threshold_is_at_three_quarters(call):
    at = call(P691, _pair([{'driver_id': 'ann', 'duration_minutes': 30}, {'driver_id': 'bob', 'duration_minutes': 10,
                                                                          'handoff_note': 'n'}]))
    assert at['drive_share'] == {'ann': 0.75, 'bob': 0.25} and at['dominant_driver'] == 'ann'
    below = call(P691, _pair([{'driver_id': 'ann', 'duration_minutes': 149}, {'driver_id': 'bob', 'duration_minutes': 51,
                                                                              'handoff_note': 'n'}]))
    assert below['dominant_driver'] is None and below['drive_share']['ann'] == 0.745


def test_692_audit_share_rounding_and_limit_boundary(call):
    people = ['a', 'b', 'c']

    def entries(*spans):
        return [{'driver': d, 'start_minute': s, 'end_minute': e} for d, s, e in spans]
    j = call(P692A, {'participants': people, 'log': entries(('a', 0, 40), ('b', 40, 60))})
    assert {'code': 'driver_share_exceeded', 'driver': 'a', 'share': 0.6667} in j['violations']
    exact = call(P692A, {'participants': people, 'log': entries(('a', 0, 20), ('b', 20, 30), ('c', 30, 40))})
    assert exact['ok'] is True and exact['violations'] == []      # a holds exactly 0.5, not over the default limit
    tight = call(P692A, {'participants': people, 'max_driver_share': 0.4,
                         'log': entries(('a', 0, 20), ('b', 20, 30), ('c', 30, 40))})
    assert [v['code'] for v in tight['violations']] == ['driver_share_exceeded']


def test_692_plan_participant_cap_32_33(call):
    names = ['p%02d' % i for i in range(32)]
    ok = call(P692P, {'participants': names, 'task': 't', 'session_minutes': 32, 'rotation_minutes': 1})
    assert ok['everyone_drives'] is True and len(ok['participants']) == 32
    assert call(P692P, {'participants': names + ['p32'], 'task': 't', 'session_minutes': 33, 'rotation_minutes': 1},
                422) == 'participants exceeds count cap'


def test_688_list_caps_exact(call):
    def req(**kw):
        base = {'feature': 'F', 'acceptance_criteria': [{'id': 'c1', 'text': 't'}], 'examples': [], 'stakeholders': ['po']}
        return {'data': {**base, **kw}}
    for n, field, make in ((128, 'acceptance_criteria', lambda i: {'id': 'c%d' % i, 'text': 't'}),
                           (64, 'stakeholders', lambda i: 's%d' % i),
                           (64, 'agreed_by', lambda i: 'g%d' % i)):
        assert call(P688, req(**{field: [make(i) for i in range(n)]}))
        assert call(P688, req(**{field: [make(i) for i in range(n + 1)]}), 422) == 'ACCEPT688:OVERSIZE:' + field


def test_687_receipt_count_is_exactly_three(call):
    cyc = {'id': 'c1', 'behavior': 'b', 'receipts': [rc('red', 1, 'r1', 'FAIL'), rc('green', 2, 'r2', 'PASS')]}
    two = call(P687, {'data': {'as_of': 'now', 'cycles': [cyc]}}, 422)
    four = call(P687, {'data': {'as_of': 'now', 'cycles': [dict(cyc, receipts=cyc['receipts'] * 2)]}}, 422)
    assert two == 'TESTDR687:count:receipts'
    assert four == 'TESTDR687:limit:receipts'
