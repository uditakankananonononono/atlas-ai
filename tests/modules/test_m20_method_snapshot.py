"""Focused tests for HTNPlanner learned-method snapshot export/import.

The GCW package __init__ fans out into routes/services, so these tests load
schemas, embeddings and htn_planner as an isolated package directly from
source files. Importing this test module never bootstraps the full app.
Set GCW_MODULE_DIR to the directory containing schemas.py, embeddings.py
and htn_planner.py (default: ./m20_general_cognitive_worker next to this
file). Requires pytest and pydantic; stdlib otherwise. No network, no DB,
no model calls: the only planner model used is the in-test stub below.

Scope: these tests cover the portable BASE-planner snapshot contract only.
Durable restore (repository write-through, review-gate status) is out of
scope by design; import_methods refuses subclasses (tested below).
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

MODULE_DIR = Path(
    os.environ.get(
        "GCW_MODULE_DIR",
        Path(__file__).resolve().parent / "m20_general_cognitive_worker",
    )
)
PKG = "gcw_snapshot_isolated"


def _load_isolated():
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [str(MODULE_DIR)]
    sys.modules[PKG] = pkg
    loaded = {}
    for name in ("schemas", "embeddings", "htn_planner"):
        fullname = f"{PKG}.{name}"
        spec = importlib.util.spec_from_file_location(fullname, MODULE_DIR / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded


_mod = _load_isolated()
schemas = _mod["schemas"]
htn = _mod["htn_planner"]

HTNMethod = schemas.HTNMethod
MethodSource = schemas.MethodSource
PlanNode = schemas.PlanNode
Risk = schemas.Risk
TaskState = schemas.TaskState
HTNPlanner = htn.HTNPlanner
PlanError = htn.PlanError


class StubPlannerModel:
    """Deterministic stand-in for the LLM decomposer."""

    def __init__(self, steps):
        self.steps = steps
        self.calls = 0

    def decompose(self, goal, *, context=""):
        self.calls += 1
        return self.steps


def library_method():
    return HTNMethod(
        name="market-entry",
        goal_pattern="prepare market entry strategy analysis",
        subtasks=[
            PlanNode(title="research market", tool="web_search", risk=Risk.READ),
            PlanNode(
                title="draft report",
                tool="write_document",
                risk=Risk.REVERSIBLE,
                depends_on=["research market"],
            ),
        ],
    )


def planner_with_learned():
    """Planner holding one library method and one learned method with counters."""
    planner = HTNPlanner(model=StubPlannerModel([
        {"id": "a", "title": "gather data", "tool": "web_search", "risk": "read"},
        {"id": "b", "title": "analyze", "tool": "python_sandbox", "risk": "reversible", "depends_on": ["a"]},
    ]))
    planner.register_method(library_method())
    planner.decompose("analyze competitor pricing for textbooks", context="q3")
    learned_name = next(n for n, m in planner.methods.items() if m.source == MethodSource.LEARNED)
    planner.record_outcome(learned_name, True)
    planner.record_outcome(learned_name, False)
    return planner, learned_name


def _entry(**overrides):
    """Full-field HTNMethod JSON entry (as export_methods emits) with overrides."""
    data = library_method().model_dump(mode="json")
    data.update(overrides)
    return data


def _node(**overrides):
    """Full-field PlanNode JSON dict (as export emits) with overrides."""
    data = PlanNode(title="a").model_dump(mode="json")
    data.update(overrides)
    return data


def _snapshot(*entries):
    return {"kind": "htn-method-snapshot", "version": 1, "methods": list(entries)}


def _learned_entry(**overrides):
    base = _entry(
        name="learned:scoped",
        source="learned",
        generated_goal="analyze competitor pricing for textbooks",
        generated_context_sha256=hashlib.sha256(b"q3").hexdigest(),
    )
    base.update(overrides)
    return base


def test_round_trip_preserves_provenance_templates_and_counters():
    source, learned_name = planner_with_learned()
    snapshot = source.export_methods()
    assert snapshot["kind"] == htn.METHOD_SNAPSHOT_KIND
    assert snapshot["version"] == htn.METHOD_SNAPSHOT_VERSION
    target = HTNPlanner()
    imported = target.import_methods(snapshot)
    assert set(imported) == set(source.methods)
    for name in imported:
        before = source.methods[name].model_dump(mode="json")
        after = target.methods[name].model_dump(mode="json")
        assert after == before  # full fidelity for cleanly-built methods
    lib = target.methods["market-entry"]
    assert (lib.outcomes_recorded, lib.successes_recorded, lib.success_rate) == (0, 0, 0.0)
    learned = target.methods[learned_name]
    assert (learned.outcomes_recorded, learned.successes_recorded) == (2, 1)
    assert learned.success_rate == 0.5
    assert learned.source == MethodSource.LEARNED
    assert learned.generated_goal == "analyze competitor pricing for textbooks"
    assert learned.generated_context_sha256 == hashlib.sha256(b"q3").hexdigest()
    assert learned.times_used == source.methods[learned_name].times_used


def test_export_sanitizes_authority_and_execution_without_mutating_store():
    dirty = HTNMethod(
        name="dirty",
        goal_pattern="dirty fixture",
        activation_review={"reviewer": "someone", "approved": True},
        proposer_actor_id="actor-1",
        subtasks=[PlanNode(
            title="compute",
            state=TaskState.SUCCEEDED,
            attempts=3,
            approval_id="approval-live",
            result_summary="actually executed",
            output={"answer": 42},
            outcome_unknown=True,
        )],
    )
    planner = HTNPlanner()
    planner.register_method(dirty)
    (entry,) = planner.export_methods()["methods"]
    assert entry["activation_review"] is None
    assert entry["proposer_actor_id"] is None
    (node,) = entry["subtasks"]
    assert node["state"] == "pending"
    assert node["attempts"] == 0
    assert node["approval_id"] is None
    assert node["result_summary"] == ""
    assert node["output"] is None
    assert node["outcome_unknown"] is False
    stored = planner.methods["dirty"]  # export must not mutate the live store
    assert stored.activation_review == {"reviewer": "someone", "approved": True}
    assert stored.proposer_actor_id == "actor-1"
    assert stored.subtasks[0].state == TaskState.SUCCEEDED
    assert stored.subtasks[0].approval_id == "approval-live"


def test_import_strips_authority_and_execution_state():
    entry = _entry(
        activation_review={"reviewer": "someone", "approved": True},
        proposer_actor_id="actor-claiming-prior-approval",
        subtasks=[_node(
            title="compute",
            state="succeeded",
            attempts=3,
            approval_id="approval-smuggled",
            result_summary="claimed executed elsewhere",
            output={"answer": 42},
            outcome_unknown=True,
        )],
    )
    planner = HTNPlanner()
    planner.import_methods(_snapshot(entry))
    method = planner.methods["market-entry"]
    assert method.activation_review is None
    assert method.proposer_actor_id is None
    node = method.subtasks[0]
    assert node.state == TaskState.PENDING
    assert node.attempts == 0
    assert node.approval_id is None
    assert node.result_summary == ""
    assert node.output is None
    assert node.outcome_unknown is False


def test_snapshot_is_deep_copied_both_directions():
    source, _ = planner_with_learned()
    snapshot = source.export_methods()
    snapshot["methods"][0]["subtasks"][0]["title"] = "tampered"
    original = source.methods[snapshot["methods"][0]["name"]].subtasks[0].title
    assert original != "tampered"
    target = HTNPlanner()
    target.import_methods(source.export_methods())
    exported_again = source.export_methods()
    exported_again["methods"][0]["subtasks"][0]["title"] = "tampered again"
    name = exported_again["methods"][0]["name"]
    assert target.methods[name].subtasks[0].title == original


@pytest.mark.parametrize("snapshot", [
    "not a dict",
    {"kind": "htn-method-snapshot", "version": 1, "methods": [], "extra": 1},
    {"kind": "wrong-kind", "version": 1, "methods": []},
    {"kind": "htn-method-snapshot", "version": 1, "methods": "not a list"},
])
def test_import_rejects_bad_envelope(snapshot):
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.import_methods(snapshot)
    assert not planner.methods


@pytest.mark.parametrize("version", [True, 1.0, "1", None, 2])
def test_import_rejects_non_integer_version(version):
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.import_methods({"kind": "htn-method-snapshot", "version": version, "methods": []})
    assert not planner.methods


@pytest.mark.parametrize("entry", [
    "not a dict",
    _entry(unknown_field=True),
    _entry(successes_recorded=3, outcomes_recorded=1, success_rate=1.0),
    _entry(successes_recorded=-1),
    _entry(successes_recorded=1.5, outcomes_recorded=2, success_rate=0.75),
    _entry(subtasks=[]),
    _entry(source="LEARNED"),
    _entry(source=1),
    _entry(source=True),
])
def test_import_rejects_malformed_entries(entry):
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(entry))
    assert not planner.methods


def test_import_rejects_missing_entry_and_subtask_fields():
    planner = HTNPlanner()
    entry = _entry()
    del entry["source"]  # must not silently default to LIBRARY
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(entry))
    entry = _entry()
    del entry["generated_goal"]
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(entry))
    entry = _entry(subtasks=[_node()])
    del entry["subtasks"][0]["kind"]
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(entry))
    assert not planner.methods


@pytest.mark.parametrize("value", [True, -1, 1.5, "3"])
def test_import_rejects_non_raw_int_times_used(value):
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(_entry(times_used=value)))
    assert not planner.methods


@pytest.mark.parametrize("value", [True, 1.5, -0.1, "0.5"])
def test_import_rejects_bad_success_rate(value):
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(_entry(success_rate=value)))
    assert not planner.methods


def test_import_rejects_rate_inconsistent_with_counters():
    planner = HTNPlanner()
    with pytest.raises(PlanError):  # zero outcomes but a nonzero claimed rate
        planner.import_methods(_snapshot(_entry(success_rate=0.5)))
    with pytest.raises(PlanError):  # 1/2 outcomes but a 0.9 claimed rate
        planner.import_methods(_snapshot(_entry(
            outcomes_recorded=2, successes_recorded=1, success_rate=0.9,
        )))
    assert not planner.methods


@pytest.mark.parametrize("value", [True, 1.0, 0, 101, "3"])
def test_import_rejects_coerced_or_unbounded_subtask_max_attempts(value):
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(_entry(subtasks=[_node(max_attempts=value)])))
    assert not planner.methods


@pytest.mark.parametrize("subtasks", [
    [_node(id="same", title="a"), _node(id="same", title="b")],
    [_node(title="a", depends_on=["missing"])],
    [_node(id="a", title="a", depends_on=["b"]), _node(id="b", title="b", depends_on=["a"])],
    [_node(title="same"), _node(title="same"), _node(title="c", depends_on=["same"])],
    [_node(id="a", title="a"), _node(title="b", depends_on=["a"], arguments={"x": {"$step": "ghost", "path": []}})],
])
def test_import_rejects_invalid_or_ambiguous_dag(subtasks):
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(_entry(subtasks=subtasks)))
    assert not planner.methods


@pytest.mark.parametrize("override", [
    {"generated_goal": None},
    {"generated_goal": ""},
    {"generated_context_sha256": None},
    {"generated_context_sha256": "tooshort"},
    {"generated_context_sha256": hashlib.sha256(b"q3").hexdigest().upper()},
    {"generated_context_sha256": "z" * 64},
])
def test_import_rejects_learned_without_valid_scope_binding(override):
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(_learned_entry(**override)))
    assert not planner.methods


def test_import_accepts_validly_scoped_learned_method():
    planner = HTNPlanner()
    planner.import_methods(_snapshot(_learned_entry()))
    method = planner.methods["learned:scoped"]
    assert method.source == MethodSource.LEARNED
    assert method.generated_goal == "analyze competitor pricing for textbooks"
    assert method.generated_context_sha256 == hashlib.sha256(b"q3").hexdigest()


def test_import_is_atomic_on_mid_list_failure():
    planner = HTNPlanner()
    bad = _entry(name="bad", subtasks=[_node(title="x", depends_on=["ghost"])])
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(_entry(), bad))
    assert not planner.methods  # the valid first entry was not committed


def test_import_rejects_name_collisions():
    planner = HTNPlanner()
    planner.register_method(library_method())
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(_entry()))
    dup_a = _entry(name="dup")
    dup_b = _entry(name="dup", goal_pattern="other pattern entirely")
    with pytest.raises(PlanError):
        HTNPlanner().import_methods(_snapshot(dup_a, dup_b))
    assert set(planner.methods) == {"market-entry"}


def test_import_refused_on_subclasses_without_durable_hooks():
    class AnySubclass(HTNPlanner):
        pass

    planner = AnySubclass()
    with pytest.raises(PlanError):
        planner.import_methods(_snapshot(_entry()))
    assert not planner.methods
    # Export stays available read-only on subclasses.
    assert planner.export_methods()["methods"] == []


def test_imported_learned_method_matches_only_exact_goal_and_context():
    source, learned_name = planner_with_learned()
    snapshot = source.export_methods()
    model = StubPlannerModel([{"title": "fresh", "tool": "web_search"}])
    target = HTNPlanner(model=model)
    target.import_methods(snapshot)
    plan = target.decompose("analyze competitor pricing for textbooks", context="q3")
    assert model.calls == 0  # imported learned method matched
    assert [n.title for n in plan] == ["gather data", "analyze"]
    no_model = HTNPlanner()
    no_model.import_methods(snapshot)
    with pytest.raises(PlanError):
        no_model.decompose("analyze competitor pricing for textbooks", context="q4")  # context sha mismatch: no learned match, no model bound
    target2 = HTNPlanner(model=model)
    target2.import_methods(snapshot)
    target2.decompose("analyze competitor pricing for textbooks", context="q4")
    assert model.calls == 1  # wrong context sha: no match, model used
    method = target2.methods[learned_name]
    assert method.generated_context_sha256 == hashlib.sha256(b"q3").hexdigest()


def test_preserved_counters_extend_not_reset():
    source, learned_name = planner_with_learned()
    target = HTNPlanner()
    target.import_methods(source.export_methods())
    target.record_outcome(learned_name, True)
    method = target.methods[learned_name]
    assert method.outcomes_recorded == 3
    assert method.successes_recorded == 2
    assert abs(method.success_rate - 2 / 3) < 1e-9
