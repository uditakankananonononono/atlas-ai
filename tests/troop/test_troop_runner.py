"""Troop runner tests: planner / worker / reviewer roles over fixture tasks.
Stdlib only; run with PYTHONPATH=backend."""
import threading
import time

import pytest

from app.troop.roles import ActionWorker, Plan, RuleReviewer, Step, TemplatePlanner, WorkerError
from app.troop.runner import PlanError, TroopRunner


def runner(**kw):
    return TroopRunner(TemplatePlanner(), ActionWorker(), RuleReviewer(), **kw)


TEXT = {"id": "t1", "kind": "text_stats", "text": "the cat and the dog and the bird", "top_n": 2}


def test_text_stats_fixture_completes_with_real_counts():
    r = runner().run(TEXT)
    assert r.status == "completed"
    assert r.outputs["report"] == [("the", 3), ("and", 2)]
    assert r.outputs["count"]["the"] == 3 and r.outputs["count"]["bird"] == 1


def test_sum_table_fixture():
    r = runner().run({"id": "t2", "kind": "sum_table", "rows": [{"a": 1, "b": 2}, {"a": 3, "b": 4.5}]})
    assert r.status == "completed" and r.outputs["totals"] == {"a": 4, "b": 6.5}


def test_unknown_kind_rejected_by_planner():
    with pytest.raises(PlanError, match="unknown task kind"):
        runner().run({"id": "x", "kind": "nope"})


def test_transcript_order_and_roles():
    r = runner().run(TEXT)
    roles = [e["role"] for e in r.transcript]
    assert roles[0] == "planner" and "worker" in roles and "reviewer" in roles
    ws = [e["step"] for e in r.transcript if e["role"] == "worker"]
    assert ws == ["tokenize", "count", "report"]
    for e in r.transcript:
        if e["role"] == "reviewer":
            assert e["ok"] is True


def test_reviewer_rejection_triggers_retry_with_feedback():
    seen = []
    w = ActionWorker()

    def flaky(args, inputs, attempt, feedback):
        seen.append((attempt, feedback))
        return [] if attempt == 1 else ["ok"]

    w.register("flaky", flaky)

    class P:
        def plan(self, task):
            return Plan(task["id"], (Step("s", "flaky", {}, (), {"type": "non_empty"}),))

    r = TroopRunner(P(), w, RuleReviewer(), max_attempts=3).run({"id": "f"})
    assert r.status == "completed" and r.attempts["s"] == 2
    assert seen[0] == (1, None) and seen[1][0] == 2 and "non_empty" in seen[1][1]


def test_exhausted_attempts_fail_and_block_dependents():
    w = ActionWorker()
    w.register("bad", lambda a, i, n, f: [])
    w.register("never", lambda a, i, n, f: (_ for _ in ()).throw(AssertionError("must not run")))

    class P:
        def plan(self, task):
            return Plan("p", (Step("a", "bad", {}, (), {"type": "non_empty"}),
                              Step("b", "never", {}, ("a",), {})))

    r = TroopRunner(P(), w, RuleReviewer(), max_attempts=2).run({"id": "p"})
    assert r.status == "failed" and r.step_status == {"a": "failed", "b": "blocked"}
    assert r.attempts["a"] == 2 and "b" not in r.attempts


def test_worker_exception_is_captured_and_retried():
    w = ActionWorker()
    calls = []

    def boom(a, i, n, f):
        calls.append(n)
        if n == 1:
            raise WorkerError("transient")
        return 5

    w.register("boom", boom)

    class P:
        def plan(self, task):
            return Plan("p", (Step("a", "boom", {}, (), {"type": "equals", "value": 5}),))

    r = TroopRunner(P(), w, RuleReviewer(), max_attempts=2).run({"id": "p"})
    assert r.status == "completed" and calls == [1, 2]
    assert any(e["role"] == "worker" and e.get("error") == "transient" for e in r.transcript)


def test_partial_status_when_independent_branch_succeeds():
    w = ActionWorker()
    w.register("ok", lambda a, i, n, f: 1)
    w.register("bad", lambda a, i, n, f: None)

    class P:
        def plan(self, task):
            return Plan("p", (Step("a", "ok", {}, (), {"type": "equals", "value": 1}),
                              Step("b", "bad", {}, (), {"type": "equals", "value": 1})))

    r = TroopRunner(P(), w, RuleReviewer(), max_attempts=1).run({"id": "p"})
    assert r.status == "partial" and r.step_status == {"a": "completed", "b": "failed"}


def test_unknown_action_fails_step_not_runner():
    class P:
        def plan(self, task):
            return Plan("p", (Step("a", "missing", {}, (), {}),))

    r = TroopRunner(P(), ActionWorker(), RuleReviewer(), max_attempts=1).run({"id": "p"})
    assert r.status == "failed" and r.step_status == {"a": "failed"}


@pytest.mark.parametrize("steps,msg", [
    ((Step("a", "x", {}, (), {}), Step("a", "x", {}, (), {})), "duplicate step id"),
    ((Step("a", "x", {}, ("zz",), {}),), "unknown dependency"),
    ((Step("a", "x", {}, ("b",), {}), Step("b", "x", {}, ("a",), {})), "cycle"),
    ((), "no steps"),
])
def test_invalid_plans_rejected_before_any_work(steps, msg):
    ran = []
    w = ActionWorker()
    w.register("x", lambda a, i, n, f: ran.append(1))

    class P:
        def plan(self, task):
            return Plan("p", steps)

    with pytest.raises(PlanError, match=msg):
        TroopRunner(P(), w, RuleReviewer()).run({"id": "p"})
    assert ran == []


def test_max_steps_guard():
    class P:
        def plan(self, task):
            return Plan("p", tuple(Step(f"s{i}", "x", {}, (), {}) for i in range(5)))

    with pytest.raises(PlanError, match="too many steps"):
        TroopRunner(P(), ActionWorker(), RuleReviewer(), max_steps=4).run({"id": "p"})


def test_independent_steps_run_in_parallel():
    w = ActionWorker()
    barrier = threading.Barrier(3, timeout=5)

    def meet(a, i, n, f):
        barrier.wait()
        return 1

    w.register("meet", meet)

    class P:
        def plan(self, task):
            return Plan("p", tuple(Step(f"s{k}", "meet", {}, (), {"type": "equals", "value": 1}) for k in range(3)))

    r = TroopRunner(P(), w, RuleReviewer(), max_workers=3).run({"id": "p"})
    assert r.status == "completed"


def test_max_workers_one_is_sequential():
    w = ActionWorker()
    active, peak, lock = [0], [0], threading.Lock()

    def work(a, i, n, f):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.02)
        with lock:
            active[0] -= 1
        return 1

    w.register("w", work)

    class P:
        def plan(self, task):
            return Plan("p", tuple(Step(f"s{k}", "w", {}, (), {}) for k in range(3)))

    TroopRunner(P(), w, RuleReviewer(), max_workers=1).run({"id": "p"})
    assert peak[0] == 1


def test_dependency_outputs_passed_to_dependents():
    w = ActionWorker()
    w.register("one", lambda a, i, n, f: 10)
    w.register("add", lambda a, i, n, f: i["a"] + a["k"])

    class P:
        def plan(self, task):
            return Plan("p", (Step("a", "one", {}, (), {}), Step("b", "add", {"k": 5}, ("a",), {"type": "equals", "value": 15})))

    r = TroopRunner(P(), w, RuleReviewer()).run({"id": "p"})
    assert r.outputs["b"] == 15 and r.status == "completed"


@pytest.mark.parametrize("check,val,ok", [
    ({"type": "non_empty"}, [1], True), ({"type": "non_empty"}, "", False),
    ({"type": "equals", "value": 3}, 3, True), ({"type": "equals", "value": 3}, 4, False),
    ({"type": "keys", "keys": ["a"]}, {"a": 1}, True), ({"type": "keys", "keys": ["a"]}, {"b": 1}, False),
    ({"type": "min_len", "n": 2}, [1, 2], True), ({"type": "min_len", "n": 2}, [1], False),
    ({}, None, True),
])
def test_reviewer_checks(check, val, ok):
    assert RuleReviewer().review(Step("s", "a", {}, (), check), val).ok is ok


def test_reviewer_unknown_check_type_rejects():
    v = RuleReviewer().review(Step("s", "a", {}, (), {"type": "wat"}), 1)
    assert v.ok is False and "unknown check" in v.reasons[0]


def test_run_is_repeatable_and_input_not_mutated():
    t = dict(TEXT)
    a = runner().run(t)
    b = runner().run(t)
    assert a.outputs == b.outputs and a.transcript == b.transcript and t == TEXT


def test_task_without_id_rejected():
    with pytest.raises(PlanError, match="task id"):
        runner().run({"kind": "text_stats", "text": "a"})


def test_top_n_ties_broken_alphabetically():
    r = runner().run({"id": "t", "kind": "text_stats", "text": "zeta alpha mid zeta alpha mid", "top_n": 3})
    assert r.outputs["report"] == [("alpha", 2), ("mid", 2), ("zeta", 2)]


def test_sum_table_rejects_bool_and_text_cells():
    for bad in (True, "7"):
        r = runner(max_attempts=1).run({"id": "s", "kind": "sum_table", "rows": [{"a": bad}]})
        assert r.status == "failed" and r.step_status == {"totals": "failed"}


def test_keys_check_requires_all_keys():
    st = Step("s", "a", {}, (), {"type": "keys", "keys": ["a", "b"]})
    assert RuleReviewer().review(st, {"a": 1}).ok is False
    assert RuleReviewer().review(st, {"a": 1, "b": 2}).ok is True


def test_worker_called_exactly_max_attempts_times():
    w = ActionWorker()
    calls = []
    w.register("bad", lambda a, i, n, f: calls.append(n))

    class P:
        def plan(self, task):
            return Plan("p", (Step("a", "bad", {}, (), {"type": "equals", "value": 1}),))

    r = TroopRunner(P(), w, RuleReviewer(), max_attempts=3).run({"id": "p"})
    assert calls == [1, 2, 3] and r.attempts["a"] == 3


def test_any_worker_exception_type_is_captured():
    w = ActionWorker()
    w.register("bad", lambda a, i, n, f: 1 / 0)

    class P:
        def plan(self, task):
            return Plan("p", (Step("a", "bad", {}, (), {}),))

    r = TroopRunner(P(), w, RuleReviewer(), max_attempts=1).run({"id": "p"})
    assert r.status == "failed"
    assert [e for e in r.transcript if e["role"] == "worker"][0]["error"] == "division by zero"


def test_plan_exactly_at_max_steps_is_allowed():
    class P:
        def plan(self, task):
            return Plan("p", tuple(Step(f"s{i}", "x", {}, (), {}) for i in range(4)))

    w = ActionWorker()
    w.register("x", lambda a, i, n, f: 1)
    assert TroopRunner(P(), w, RuleReviewer(), max_steps=4).run({"id": "p"}).status == "completed"


def test_retry_events_in_attempt_order():
    w = ActionWorker()
    w.register("f", lambda a, i, n, f: [] if n == 1 else [1])

    class P:
        def plan(self, task):
            return Plan("p", (Step("a", "f", {}, (), {"type": "non_empty"}),))

    r = TroopRunner(P(), w, RuleReviewer(), max_attempts=2).run({"id": "p"})
    assert [(e["role"], e["attempt"]) for e in r.transcript[1:]] == [
        ("worker", 1), ("reviewer", 1), ("worker", 2), ("reviewer", 2)]
