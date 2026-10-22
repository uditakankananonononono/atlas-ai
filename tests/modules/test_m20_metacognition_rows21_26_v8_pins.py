"""v8 pin for row 22 (L870 markers.get(value, [])): a terminal value OUTSIDE the marker table has no
markers, so it never conflicts, whatever the plan text says. A value IN the table is the control. Tests only."""
import pytest
from app.modules.m20_general_cognitive_worker.metacognition import GoalHierarchyManager
from app.modules.m20_general_cognitive_worker.schemas import PlanNode


@pytest.mark.parametrize('value,title', [('kindness', 'harm plan'), ('unknown_value', 'cause harm to user'),
                                         ('kindness', 'deceive and steal'), ('Kindness', 'harm plan')])
def test_value_outside_marker_table_never_conflicts(value, title):
    g = GoalHierarchyManager(terminal_values=[value])
    plan = [PlanNode(id='a', title=title)]
    assert g.check(plan) == []
    r = g.restructure(plan)
    assert r['conflicts'] == [] and r['cancelled'] == [] and plan[0].state.name == 'PENDING'


def test_control_in_table_value_still_conflicts_and_mixed_list_only_reports_table_value():
    plan = [PlanNode(id='a', title='harm plan')]
    c = GoalHierarchyManager(terminal_values=['safety']).check(plan)
    assert [(x.node_id, x.violated_value, x.marker) for x in c] == [('a', 'safety', 'harm')]
    c2 = GoalHierarchyManager(terminal_values=['kindness', 'safety']).check(plan)
    assert [(x.node_id, x.violated_value, x.marker) for x in c2] == [('a', 'safety', 'harm')]
