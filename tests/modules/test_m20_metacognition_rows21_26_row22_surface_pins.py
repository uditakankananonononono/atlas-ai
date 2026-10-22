"""OPTIONAL row 22 surface (GoalHierarchyManager marker table and restructure payload), outside the row 21/23-26 unit.
The marker table below is an independent literal copy. Tests only."""
import pytest
from app.modules.m20_general_cognitive_worker.metacognition import GoalHierarchyManager
from app.modules.m20_general_cognitive_worker.schemas import PlanNode

TABLE = {
    "honesty": ["deceive", "lie", "fake", "mislead", "fabricate"],
    "privacy": ["share personal", "leak", "expose private", "sell data", "dox"],
    "safety": ["harm", "weapon", "dangerous", "injure"],
    "legality": ["pirate", "steal", "bypass paywall", "crack", "launder"],
    "budget": ["unlimited spend", "ignore cost", "money is no object"],
}
PAIRS = [(v, m) for v, ms in TABLE.items() for m in ms]


@pytest.mark.parametrize("value,marker", PAIRS)
def test_every_marker_flags_exactly_its_value_via_title(value, marker):
    node = PlanNode(id="n", title=marker.upper())
    got = [(c.violated_value, c.marker) for c in GoalHierarchyManager([value]).check([node])]
    assert got == [(value, m) for m in TABLE[value] if m in marker]
    assert (value, marker) in got


@pytest.mark.parametrize("value,marker", PAIRS)
def test_every_marker_flags_via_arguments_and_reports_node_fields(value, marker):
    node = PlanNode(id="n1", title="Step", arguments={"note": marker})
    cs = GoalHierarchyManager([value]).check([node])
    hit = [c for c in cs if c.marker == marker]
    assert len(hit) == 1
    assert hit[0].__dict__ == {"node_id": "n1", "node_title": "Step", "violated_value": value, "marker": marker}


def test_default_terminal_values_exclude_safety_and_budget():
    g = GoalHierarchyManager()
    assert g.terminal_values == ["honesty", "privacy", "legality"]
    assert g.check([PlanNode(id="a", title="harm")]) == []
    assert g.check([PlanNode(id="a", title="ignore cost")]) == []
    assert [c.violated_value for c in g.check([PlanNode(id="a", title="steal")])] == ["legality"]


def test_restructure_payload_keys_status_and_flags():
    g = GoalHierarchyManager()
    bad = PlanNode(id="b", title="deceive user")
    dep = PlanNode(id="d", title="send", depends_on=["b"])
    free = PlanNode(id="f", title="read")
    out = g.restructure([bad, dep, free])
    assert out == {
        "status": "marker_conflict_pruning_only", "capability_executed": False,
        "cancelled": ["deceive user", "send"],
        "already_executed_dependents": [],
        "blocked_by_cancelled_prerequisite": ["d"],
        "conflicts": [{"node_id": "b", "node_title": "deceive user", "violated_value": "honesty", "marker": "deceive"}],
        "remaining_steps": ["read"],
        "restructured": True,
    }
    clean = g.restructure([PlanNode(id="x", title="read")])
    assert clean["restructured"] is False and clean["conflicts"] == [] and clean["remaining_steps"] == ["read"]


def test_restructure_validation_message_is_exact():
    with pytest.raises(ValueError) as ei:
        GoalHierarchyManager().restructure([PlanNode(id="a", title="x", depends_on=["zz"])])
    assert str(ei.value) == "unique plan ids and existing dependency references required"
