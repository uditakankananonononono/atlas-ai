"""Tests for the SQLite lab store (both seams + manifests + eval reports)."""

import pytest

from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger
from app.modules.m12_ai_research_lab.lane_models import BudgetPolicy, usd_to_micro
from app.modules.m12_ai_research_lab.lane_runs import build_manifest, manifest_file_payload
from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore
from app.modules.m12_ai_research_lab.lane_workflows import Workflow, WorkflowEngine, WorkflowStep


def test_spend_store_seam_roundtrip(tmp_path):
    store = SQLiteLabStore(str(tmp_path / "lab.db"))
    store.add_spend("e1", "run-1", 100, "2026-09-20T10:00:00+00:00")
    store.add_spend("e2", "run-2", 250, "2026-09-20T12:00:00+00:00")
    store.add_spend("e3", "run-1", 50, "2026-09-21T00:00:00+00:00")
    assert store.spend_between("2026-09-20T00:00:00+00:00", "2026-09-21T00:00:00+00:00") == 350
    assert store.spend_by_run("run-1") == 150
    store.close()


def test_ledger_works_against_sqlite_store(tmp_path):
    store = SQLiteLabStore(str(tmp_path / "lab.db"))
    ledger = BudgetLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(1)), store=store)
    ledger.reserve("run-1", usd_to_micro(0.5))
    ledger.commit("run-1", usd_to_micro(0.4))
    assert store.spend_by_run("run-1") == usd_to_micro(0.4)
    store.close()


def test_ledger_survives_store_reopen(tmp_path):
    path = str(tmp_path / "lab.db")
    store = SQLiteLabStore(path)
    BudgetLedger(BudgetPolicy(), store=store).commit("run-1", 123)
    store.close()
    store2 = SQLiteLabStore(path)
    assert store2.spend_by_run("run-1") == 123
    store2.close()


def test_step_state_seam_roundtrip(tmp_path):
    store = SQLiteLabStore(str(tmp_path / "lab.db"))
    store.save_completed("r1", "a", {"out": [1, 2, 3]})
    store.save_completed("r1", "b", "text")
    store.save_completed("r2", "a", None)
    assert store.load_completed("r1") == {"a": {"out": [1, 2, 3]}, "b": "text"}
    assert store.load_completed("r2") == {"a": None}
    store.clear_run("r1")
    assert store.load_completed("r1") == {}
    store.close()


def test_engine_resumes_from_sqlite_checkpoint(tmp_path):
    store = SQLiteLabStore(str(tmp_path / "lab.db"))
    calls = {"a": 0}

    def a(params, ctx):
        calls["a"] += 1
        return "done"

    wf = Workflow("w", (
        WorkflowStep("a", "a", max_retries=0),
        WorkflowStep("b", "b", depends_on=("a",), max_retries=0),
    ))
    eng = WorkflowEngine({"a": a, "b": lambda p, c: (_ for _ in ()).throw(RuntimeError("x"))},
                         state_store=store)
    assert eng.run(wf, run_id="r").status == "failed"
    eng2 = WorkflowEngine({"a": a, "b": lambda p, c: "ok"}, state_store=store)
    assert eng2.run(wf, run_id="r").status == "completed"
    assert calls["a"] == 1  # not re-executed across engines
    store.close()


def test_manifest_persistence_roundtrip(tmp_path):
    store = SQLiteLabStore(str(tmp_path / "lab.db"))
    m = build_manifest("run-9", "wf", {"k": "v"}, "input", seed=1,
                       created_at_utc="2026-09-20T00:00:00+00:00")
    store.save_manifest("run-9", manifest_file_payload(m))
    payload = store.load_manifest("run-9")
    assert payload["digest"] == m.digest()
    assert "run-9" in store.list_manifests()
    assert store.load_manifest("nope") is None
    store.close()
