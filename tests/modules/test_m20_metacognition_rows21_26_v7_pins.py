"""v7 pins for rows 21-26 (+ row 22 surface): daily-cap overflow state, identity-vs-equality operators
(equal but non-identical strings/ints), and row 22 state transitions. Tests only."""
import pytest
from app.modules.m20_general_cognitive_worker import metacognition as mc
from app.modules.m20_general_cognitive_worker.metacognition import (
    DecisionFatigueGuard, GoalHierarchyManager, RoutinePolicy, sunk_cost_choice)
from app.modules.m20_general_cognitive_worker.schemas import PlanNode, TaskState


def _dyn(*parts):
    s = ''.join(parts)  # fresh, non-interned, equal-but-not-identical string
    return s


# ---- row 23: L940 used_today >= max_auto_per_day (public dataclass field set directly) ----
@pytest.mark.parametrize('used,cap,automated', [
    (5, 3, False), (4, 3, False), (3, 3, False), (2, 3, True), (0, 1, True), (1, 1, False), (0, 0, False), (0, -1, False), (7, 0, False)])
def test_daily_cap_is_greater_or_equal_including_overshoot(used, cap, automated):
    g = DecisionFatigueGuard()
    g.add_policy(RoutinePolicy('t', 'a', max_auto_per_day=cap, used_today=used))
    r = g.decide('t', options=['a', 'b'])
    assert r['automated'] is automated
    if automated:
        assert g.policies['t'].used_today == used + 1 and g.automated_total == 1
    else:
        assert g.policies['t'].used_today == used and g.automated_total == 0
        assert r['chosen'] is None and r['escalated_options'] == ['a', 'b']


def test_decide_stakes_compared_by_value_not_identity():
    g = DecisionFatigueGuard()
    g.add_policy(RoutinePolicy('t', 'a'))
    low = _dyn('lo', 'w')
    assert low == 'low' and low is not 'low'  # noqa: F632  (equal, not identical)
    assert g.decide('t', options=['a'], stakes=low)['automated'] is True
    assert g.decide('t', options=['a'], stakes=_dyn('hi', 'gh'))['automated'] is False
    assert g.decide('t', options=['a'], stakes=_dyn('LO', 'W'))['automated'] is False


# ---- row 22: identity vs equality, dependency/identifier validation ----
def test_self_dependency_detected_by_equality_not_identity():
    a1, a2 = _dyn('a', 'b'), _dyn('a', 'b')
    assert a1 == a2 and a1 is not a2
    node = PlanNode(id=a1, title='t', depends_on=[a2])
    with pytest.raises(ValueError) as ei:
        GoalHierarchyManager().restructure([node])
    assert str(ei.value) == 'unique plan ids and existing dependency references required'


def test_duplicate_id_count_compared_by_value_on_large_plans():
    # len() results above the small-int cache are distinct objects: '!=' must compare by value.
    plan = [PlanNode(id='n%d' % i, title='step %d' % i) for i in range(1000)]
    out = GoalHierarchyManager().restructure(plan)
    assert out['restructured'] is False and len(out['remaining_steps']) == 1000
    dup = plan + [PlanNode(id='n0', title='dup')]
    with pytest.raises(ValueError) as ei:
        GoalHierarchyManager().restructure(dup)
    assert str(ei.value) == 'unique plan ids and existing dependency references required'


def test_restructure_state_transitions_exact():
    g = GoalHierarchyManager()
    bad = PlanNode(id='b', title='deceive the user')
    pending_dep = PlanNode(id='d1', title='send', depends_on=['b'])
    done_dep = PlanNode(id='d2', title='logged', depends_on=['b'], state=TaskState.SUCCEEDED)
    failed_dep = PlanNode(id='d3', title='failed step', depends_on=['b'], state=TaskState.FAILED)
    free_pending = PlanNode(id='f1', title='read docs')
    free_done = PlanNode(id='f2', title='archived', state=TaskState.SUCCEEDED)
    out = g.restructure([bad, pending_dep, done_dep, failed_dep, free_pending, free_done])
    assert bad.state == TaskState.CANCELLED and pending_dep.state == TaskState.CANCELLED
    assert done_dep.state == TaskState.SUCCEEDED and failed_dep.state == TaskState.FAILED
    assert free_pending.state == TaskState.PENDING, 'unblocked non-terminal node must not be cancelled'
    assert free_done.state == TaskState.SUCCEEDED
    assert out['already_executed_dependents'] == ['d2', 'd3']
    assert out['blocked_by_cancelled_prerequisite'] == ['d1', 'd2', 'd3']
    assert out['remaining_steps'] == ['read docs', 'archived']
    assert out['cancelled'] == ['deceive the user', 'send', 'logged', 'failed step']


def test_blocked_already_cancelled_node_is_left_cancelled():
    bad = PlanNode(id='b', title='fake it', state=TaskState.CANCELLED)
    GoalHierarchyManager().restructure([bad])
    assert bad.state == TaskState.CANCELLED


# ---- row 26: L1048 name comparison by value (duplicate display names, different options) ----
def test_sunk_cost_influence_compares_names_by_value():
    n1, n2 = _dyn('o', 'pt'), _dyn('o', 'pt')
    assert n1 == n2 and n1 is not n2
    opts = [{'name': n1, 'forward_value': 5, 'past_investment': 0},
            {'name': n2, 'forward_value': 3, 'past_investment': 10}]
    r = sunk_cost_choice(opts)
    assert r['recommended'] == 'opt'
    assert r['sunk_cost_influenced'] is False


def test_sunk_cost_influence_true_when_names_differ():
    r = sunk_cost_choice([{'name': 'a', 'forward_value': 5}, {'name': 'b', 'forward_value': 3, 'past_investment': 10}])
    assert r['recommended'] == 'a' and r['sunk_cost_influenced'] is True


# ---- executed equivalence witnesses for the row 22 f-string text (L868), NOT kill pins ----
def test_check_text_boundaries_cannot_create_markers_with_typed_nodes():
    # PlanNode.arguments is a dict, so f'{title} {arguments}' always ends with '}' and the mutants that
    # prepend/append a letter ('X') could only change matches for a marker starting with 'x' or containing '}'.
    allm = [m for ms in mc._VALUE_CONFLICT_MARKERS.values() for m in ms]
    assert not any(m.startswith('x') or '}' in m for m in allm)
    n = PlanNode(id='a', title='do', arguments={})
    assert n.arguments == {} and str(n.arguments).endswith('}')
