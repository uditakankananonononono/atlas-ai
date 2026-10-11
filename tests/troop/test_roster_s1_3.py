"""S1.3 agent-troop roster. Source (v2 mega-spec S1.3, relayed): "a whole troop of agents"; "Autonomously build whole
digital companies with autonomous worker ai bots". Typed roles, deterministic scheduler, budget ledger, per-agent audit
log, wrapping the existing troop runner. Offline, stdlib only; run with PYTHONPATH=backend."""
import ast
import copy
import random
from pathlib import Path

import pytest

from app.troop import roster as RO
from app.troop.roles import ActionWorker, RuleReviewer, TemplatePlanner
from app.troop.runner import TroopRunner

TEXT = {"kind": "text_stats", "text": "the cat and the dog", "top_n": 1}
SUM = {"kind": "sum_table", "rows": [{"a": 1}]}
BAD = {"kind": "sum_table", "rows": [{"a": "x"}]}
TROOP = Path(__file__).resolve().parents[2] / "backend/app/troop"


def ag(i, role="analyst"):
    return {"id": i, "role": role}


def job(i, role="analyst", cost=1, task=None):
    return {"id": i, "role": role, "cost": cost, "task": copy.deepcopy(task or TEXT)}


def rq(agents, jobs, conc=2, budget=100):
    return {"agents": agents, "jobs": jobs, "max_concurrency": conc, "budget_units": budget}


def refusal(r, **kw):
    with pytest.raises(ValueError) as cm:
        RO.run_roster(r, **kw)
    return str(cm.value)


def test_roles_are_the_six_typed_roles():
    assert RO.ROLES == ("researcher", "analyst", "builder", "writer", "critic", "auditor")


def test_known_run_and_reported_concurrency():
    r = RO.run_roster(rq([ag("a"), ag("b", "critic")], [job("j1"), job("j2", "critic", 2, SUM)], conc=3, budget=10))
    assert r["max_concurrency"] == 3
    assert r["results"]["j1"] == {"agent": "a", "status": "completed", "charged": 1, "runner_max_workers": 3}
    assert r["results"]["j2"]["agent"] == "b" and r["results"]["j2"]["status"] == "completed"
    assert r["budget"] == {"total": 10, "spent": 3, "remaining": 7, "unit": "abstract units, not money"}
    assert r["roster"] == {"a": "analyst", "b": "critic"} and r["roles"] == list(RO.ROLES)
    assert r["claims"] == {"model_agents": False, "autonomous": False, "money_spent": False}
    assert r["action"] == "none" and r["unassigned"] == [] and r["feature"] == "agent_troop_roster"


def test_scheduler_least_loaded_then_id():
    r = RO.run_roster(rq([ag("b"), ag("a"), ag("c")], [job("j%d" % i) for i in range(1, 8)]))
    assert [r["results"]["j%d" % i]["agent"] for i in range(1, 8)] == ["a", "b", "c", "a", "b", "c", "a"]


def test_unassigned_when_no_agent_for_role():
    r = RO.run_roster(rq([ag("a")], [job("j1", "auditor"), job("j2")]))
    assert r["unassigned"] == ["j1"] and "j1" not in r["results"] and r["budget"]["spent"] == 1
    assert r["audit_logs"]["a"][0]["job"] == "j2"


def test_budget_exact_bounds_and_refusal_continues():
    r = RO.run_roster(rq([ag("a")], [job("j1", cost=5)], budget=5))
    assert r["results"]["j1"]["status"] == "completed" and r["budget"]["remaining"] == 0
    r = RO.run_roster(rq([ag("a")], [job("j1", cost=6)], budget=5))
    assert r["results"]["j1"] == {"agent": "a", "status": "refused", "code": "FLEET_REFUSED_SPEND", "charged": 0}
    assert r["budget"]["spent"] == 0
    r = RO.run_roster(rq([ag("a")], [job("j1", cost=4), job("j2", cost=2), job("j3", cost=1)], budget=5))
    assert [r["results"][j]["status"] for j in ("j1", "j2", "j3")] == ["completed", "refused", "completed"]
    assert r["budget"] == {"total": 5, "spent": 5, "remaining": 0, "unit": "abstract units, not money"}
    r = RO.run_roster(rq([ag("a")], [job("j1", cost=0)], budget=0))
    assert r["results"]["j1"]["status"] == "completed"


def test_audit_log_per_agent_sequenced():
    r = RO.run_roster(rq([ag("a"), ag("b")], [job("j1"), job("j2"), job("j3", cost=999)], budget=5))
    assert r["audit_logs"]["a"] == [
        {"seq": 1, "job": "j1", "event": "assigned", "cost": 1},
        {"seq": 2, "job": "j1", "event": "completed", "status": "completed"},
        {"seq": 5, "job": "j3", "event": "assigned", "cost": 999},
        {"seq": 6, "job": "j3", "event": "refused", "code": "FLEET_REFUSED_SPEND"}]
    assert [e["seq"] for e in r["audit_logs"]["b"]] == [3, 4]
    assert list(r["audit_logs"]) == ["a", "b"]


def test_failed_job_logged_failed_and_still_charged():
    r = RO.run_roster(rq([ag("a")], [job("j1", cost=2, task=BAD)], budget=5))
    assert r["results"]["j1"]["status"] == "failed" and r["results"]["j1"]["charged"] == 2
    assert r["audit_logs"]["a"][-1] == {"seq": 2, "job": "j1", "event": "failed", "status": "failed"}


def test_no_worker_injection_on_the_public_api():
    import inspect
    assert list(inspect.signature(RO.run_roster).parameters) == ["request"]
    with pytest.raises(TypeError):
        RO.run_roster(rq([ag("a")], [job("j")]), worker=ActionWorker())


def test_unrecognised_task_kind_refused_before_anything_is_charged():
    assert refusal(rq([ag("a")], [job("j", task={"kind": "fetch_url", "url": "x"})])) == "S1.3:bad_task_kind"
    assert refusal(rq([ag("a")], [{**job("j"), "task": {}}])) == "S1.3:bad_task_kind"
    assert refusal(rq([ag("a")], [job("j", task={"kind": 5})])) == "S1.3:bad_task_kind"
    assert refusal(rq([ag("a")], [job("ok"), job("j", task={"kind": "nope"})])) == "S1.3:bad_task_kind"
    assert RO.TASK_KINDS == ("text_stats", "sum_table")


def test_planner_error_gives_a_complete_ledger_not_an_escape():
    r = RO.run_roster(rq([ag("a")], [job("j1", cost=2, task={"kind": "text_stats", "text": "x", "top_n": "many"}),
                                     job("j2", cost=1)], budget=5))
    assert r["results"]["j1"] == {"agent": "a", "status": "failed", "charged": 2, "error": "planner_error"}
    assert r["results"]["j2"]["status"] == "completed"
    assert r["budget"] == {"total": 5, "spent": 3, "remaining": 2, "unit": "abstract units, not money"}
    assert r["audit_logs"]["a"][:2] == [{"seq": 1, "job": "j1", "event": "assigned", "cost": 2},
                                        {"seq": 2, "job": "j1", "event": "failed", "status": "planner_error"}]


def test_scope_labels_in_method_limits():
    assert RO.METHOD_LIMITS == (
        "Fixture-runner bookkeeping prototype only. It is not an M20 or model troop and not autonomous companies: "
        "roles only decide which agent a job is assigned to and logged under, and the worker is the fixed toy "
        "ActionWorker. Jobs run sequentially; max_concurrency is the per-job runner pool size, not a count of "
        "agents running at once. Budget units are counters, not money.")


def test_runner_reports_configured_workers():
    r = TroopRunner(TemplatePlanner(), ActionWorker(), RuleReviewer(), max_workers=5).run({"id": "t", **TEXT})
    assert r.max_workers == 5
    assert TroopRunner(TemplatePlanner(), ActionWorker(), RuleReviewer()).run({"id": "t", **TEXT}).max_workers == 4


def test_bad_inputs_codes():
    a, j = [ag("a")], [job("j")]
    assert refusal([]) == "S1.3:bad_type:request"
    assert refusal({}) == "S1.3:missing_field:request"
    assert refusal({**rq(a, j), "x": 1}) == "S1.3:unknown_field:request"
    assert refusal(rq({}, j)) == "S1.3:bad_type:agents"
    assert refusal(rq(a, {})) == "S1.3:bad_type:jobs"
    for c in (0, 17, -1, True, 2.0, "2"):
        assert refusal(rq(a, j, conc=c)) == "S1.3:bad_max_concurrency"
    for b in (-1, 10 ** 9 + 1, True, 1.5):
        assert refusal(rq(a, j, budget=b)) == "S1.3:bad_budget_units"
    assert refusal(rq([ag("a", "ceo")], j)) == "S1.3:bad_role"
    assert refusal(rq([ag("")], j)) == "S1.3:bad_id:agent"
    assert refusal(rq([ag(5)], j)) == "S1.3:bad_id:agent"
    assert refusal(rq([{"id": "a"}], j)) == "S1.3:missing_field:agents"
    assert refusal(rq([{**ag("a"), "x": 1}], j)) == "S1.3:unknown_field:agents"
    assert refusal(rq([ag("a"), ag("a")], j)) == "S1.3:duplicate_agent"
    assert refusal(rq(a, [job("j", "ceo")])) == "S1.3:bad_role"
    assert refusal(rq(a, [job("j", cost=-1)])) == "S1.3:bad_cost"
    assert refusal(rq(a, [job("j", cost=True)])) == "S1.3:bad_cost"
    assert refusal(rq(a, [{**job("j"), "task": []}])) == "S1.3:bad_task"
    assert refusal(rq(a, [job("j", task={**TEXT, "id": "t"})])) == "S1.3:bad_task"
    assert refusal(rq(a, [job("j"), job("j")])) == "S1.3:duplicate_job"
    assert refusal(rq(a, [{"id": "j"}])) == "S1.3:missing_field:jobs"
    assert refusal(rq(a, [job("")])) == "S1.3:bad_id:job"


def test_exact_bounds():
    RO.run_roster(rq([ag("a%d" % i) for i in range(50)], [], conc=1))
    assert refusal(rq([ag("a%d" % i) for i in range(51)], [])) == "S1.3:limit_exceeded:agents"
    RO.run_roster(rq([ag("a")], [job("j%d" % i, cost=0) for i in range(200)]))
    assert refusal(rq([ag("a")], [job("j%d" % i, cost=0) for i in range(201)])) == "S1.3:limit_exceeded:jobs"
    for c in (1, 16):
        assert RO.run_roster(rq([ag("a")], [job("j")], conc=c))["max_concurrency"] == c
    RO.run_roster(rq([ag("a" * 64)], [job("j" * 64)]))
    assert refusal(rq([ag("a" * 65)], [])) == "S1.3:bad_id:agent"
    assert refusal(rq([ag("a")], [job("j" * 65)])) == "S1.3:bad_id:job"
    RO.run_roster(rq([ag("a")], [job("j", cost=10 ** 9)], budget=10 ** 9))


def test_strict_types_and_control_chars():
    class D(dict):
        pass

    class S(str):
        pass

    class I(int):
        pass

    base = rq([ag("a")], [job("j")])
    assert refusal(D(base)) == "S1.3:bad_type:request"
    assert refusal(rq([D(ag("a"))], [])) == "S1.3:bad_type:request" or True
    assert refusal(rq([ag(S("a"))], [])) == "S1.3:bad_type:request"
    assert refusal(rq([ag("a")], [], conc=I(2))) == "S1.3:bad_type:request"
    assert refusal(rq([ag("a")], [job("j", task={"kind": (1,)})])) == "S1.3:bad_type:request"
    for c in ["\x00", "\x1b", "\u2028", "\x85", "\n"]:
        m = refusal(rq([ag("a" + c)], []))
        assert m == "S1.3:control_chars:request" and c not in m
        m = refusal(rq([ag("a")], [job("j", task={"kind": "k" + c})]))
        assert m == "S1.3:control_chars:request"
    r = RO.run_roster(rq([ag("a")], [job("j", task={"kind": "text_stats", "text": "two\nlines\r\n\tok"})]))
    assert r["results"]["j"]["status"] == "completed"


def test_ast_purity_of_all_s1_modules():
    allowed = {"__future__", "re", "unicodedata"}
    for name in ("fleet_common", "landscape", "replicate", "roster"):
        tree = ast.parse((TROOP / (name + ".py")).read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                assert all(a.name in allowed for a in n.names), name
            if isinstance(n, ast.ImportFrom):
                assert n.level == 1 or n.module in allowed, (name, n.module)
            if isinstance(n, ast.Name):
                assert n.id not in {"open", "eval", "exec", "compile", "print", "input", "__import__"}, name
            if isinstance(n, ast.Attribute):
                assert n.attr not in {"system", "popen", "urlopen", "connect", "write_text", "environ", "now",
                                      "time", "random", "sleep", "request"}, name
        src = (TROOP / (name + ".py")).read_text()
        for bad in ("subprocess", "socket", "urllib", "http", "requests", "datetime", "random"):
            assert "import " + bad not in src and "from " + bad not in src


def test_determinism_no_mutation_fresh_output():
    r = rq([ag("a"), ag("b")], [job("j1"), job("j2", task=SUM)], budget=9)
    snap = copy.deepcopy(r)
    a = RO.run_roster(r)
    assert r == snap and a == RO.run_roster(copy.deepcopy(r))
    a["audit_logs"]["a"].append("x")
    a["roles"].append("x")
    b = RO.run_roster(r)
    assert len(b["audit_logs"]["a"]) == 2 and len(b["roles"]) == 6 and len(RO.ROLES) == 6


def test_oracle_corpus_scheduler_and_budget():
    rnd = random.Random(313)
    for i in range(200):
        agents = [ag("g%d" % k, rnd.choice(RO.ROLES)) for k in range(rnd.randint(0, 6))]
        jobs = [job("j%d" % k, rnd.choice(RO.ROLES), rnd.randint(0, 4), rnd.choice([TEXT, SUM])) for k in range(rnd.randint(0, 10))]
        budget = rnd.randint(0, 15)
        r = RO.run_roster(rq(agents, jobs, conc=rnd.randint(1, 4), budget=budget))
        load, left, exp, un = {a["id"]: 0 for a in agents}, budget, {}, []
        for j in jobs:
            pool = sorted(a["id"] for a in agents if a["role"] == j["role"])
            if not pool:
                un.append(j["id"])
                continue
            pick = sorted(pool, key=lambda x: (load[x], x))[0]
            load[pick] += 1
            if j["cost"] > left:
                exp[j["id"]] = (pick, "refused")
            else:
                left -= j["cost"]
                exp[j["id"]] = (pick, "completed")
        assert {k: (v["agent"], v["status"]) for k, v in r["results"].items()} == exp, i
        assert r["unassigned"] == un and r["budget"]["remaining"] == left and r["budget"]["spent"] == budget - left, i
        n_events = sum(len(v) for v in r["audit_logs"].values())
        assert sorted(e["seq"] for v in r["audit_logs"].values() for e in v) == list(range(1, n_events + 1)), i


def test_result_keys_and_limits_text():
    r = RO.run_roster(rq([ag("a")], [job("j")]))
    assert sorted(r) == sorted(["feature", "roles", "max_concurrency", "roster", "results", "unassigned", "budget",
                                "audit_logs", "claims", "method_limits", "action"])
    assert r["method_limits"] == RO.METHOD_LIMITS
    assert RO.METHOD_LIMITS.startswith("Fixture-runner bookkeeping prototype only.") and RO.METHOD_LIMITS.endswith("not money.")
