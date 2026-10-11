import json
import sys
from pathlib import Path

import pytest

from app.self_improve import improvement_gate as ig
from app.self_improve.improvement_gate import (
    ChangePlan, GateEvidence, ImprovementGate, MutationRun, PlanRefused, run_mutations)
from app.self_improve.self_eval import PytestResult

ROOTS = ("backend/app/self_improve/", "tests/self_improve/")


def plan(**kw):
    d = dict(module_slug="mod-a", feature="kw filter", branch="selfimprove/mod-a-kw",
             files=("backend/app/self_improve/x.py", "tests/self_improve/test_x.py"))
    d.update(kw)
    return ChangePlan(**d)


def ok_tests(passed=10):
    return PytestResult(0, passed, 0, 0, 0.1, "")


def mut(total=5, killed=5, survived=0, nomatch=0, timeouts=0):
    return MutationRun(total, killed, survived, nomatch, timeouts, ())


def evid(p, tests=None, mutation=None, **kw):
    return GateEvidence(plan_digest=p.digest(), tests=tests or ok_tests(), mutation=mutation or mut(), **kw)


class T:
    def __init__(self, t=1000.0): self.t = t
    def __call__(self): return self.t


def gate(tmp_path, now=None, **kw):
    return ImprovementGate("mod-a", tmp_path / "g", sandbox_roots=ROOTS, now=now or T(), **kw)


def refused(fn, code):
    with pytest.raises(PlanRefused) as e:
        fn()
    assert e.value.code == code and str(e.value).startswith(code + ": ")
    return e.value


def test_happy_path_authorizes_branch_only(tmp_path):
    g = gate(tmp_path); p = plan()
    a = g.authorize(p, evid(p))
    assert a.digest == p.digest() and a.merge_allowed is False and a.at == 1000.0
    assert a.plan == p


def test_digest_is_stable_and_sensitive():
    p = plan()
    assert p.digest() == plan().digest() and len(p.digest()) == 64
    assert plan(files=tuple(reversed(p.files))).digest() == p.digest()
    for kw in ({"feature": "other"}, {"branch": "selfimprove/z"}, {"module_slug": "mod-b"},
               {"files": ("backend/app/self_improve/y.py",)}):
        assert plan(**kw).digest() != p.digest()


def test_exception_codes_are_exact():
    assert ig.CODES == ("PLAN_REFUSED_UNGATED", "PLAN_REFUSED_REGRESSION", "PLAN_REFUSED_BUDGET",
                        "PLAN_REFUSED_BAD_PLAN", "PLAN_REFUSED_SELF_MERGE", "PLAN_REFUSED_OUTSIDE_SANDBOX")
    assert issubclass(PlanRefused, ValueError)


@pytest.mark.parametrize("kw", [{"feature": ""}, {"feature": "  "}, {"module_slug": ""}, {"files": ()},
                                {"files": ("",)}, {"branch": ""}])
def test_bad_plan_fields(tmp_path, kw):
    p = plan(**kw)
    refused(lambda: gate(tmp_path).authorize(p, GateEvidence(p.digest(), ok_tests(), mut())), "PLAN_REFUSED_BAD_PLAN")


def test_module_slug_must_match_gate(tmp_path):
    p = plan(module_slug="mod-b")
    refused(lambda: gate(tmp_path).authorize(p, evid(p)), "PLAN_REFUSED_BAD_PLAN")


@pytest.mark.parametrize("branch", ["main", "master", "origin/main", "refs/heads/main", "HEAD"])
def test_branch_main_is_self_merge(tmp_path, branch):
    p = plan(branch=branch)
    refused(lambda: gate(tmp_path).authorize(p, evid(p)), "PLAN_REFUSED_SELF_MERGE")


def test_target_main_is_self_merge(tmp_path):
    p = plan(target="main")
    refused(lambda: gate(tmp_path).authorize(p, evid(p)), "PLAN_REFUSED_SELF_MERGE")
    p = plan(target="anything")
    refused(lambda: gate(tmp_path).authorize(p, evid(p)), "PLAN_REFUSED_BAD_PLAN")


def test_branch_prefix_must_be_selfimprove(tmp_path):
    p = plan(branch="feature/x")
    refused(lambda: gate(tmp_path).authorize(p, evid(p)), "PLAN_REFUSED_BAD_PLAN")


@pytest.mark.parametrize("f", ["/etc/passwd", "../x.py", "backend/app/self_improve/../../m.py",
                               "backend/app/other/x.py", "backend\\app\\self_improve\\x.py",
                               "backend/app/self_improve", "~/x.py"])
def test_outside_sandbox(tmp_path, f):
    p = plan(files=(f,))
    refused(lambda: gate(tmp_path).authorize(p, evid(p)), "PLAN_REFUSED_OUTSIDE_SANDBOX")


def test_inside_sandbox_prefix_boundary(tmp_path):
    p = plan(files=("backend/app/self_improve_evil/x.py",))
    refused(lambda: gate(tmp_path).authorize(p, evid(p)), "PLAN_REFUSED_OUTSIDE_SANDBOX")
    p = plan(files=("tests/self_improve/sub/test_y.py",))
    gate(tmp_path).authorize(p, evid(p))


def test_too_many_files_is_budget(tmp_path):
    fs = tuple(f"backend/app/self_improve/f{i}.py" for i in range(4))
    p = plan(files=fs)
    refused(lambda: gate(tmp_path, max_files_per_change=3).authorize(p, evid(p)), "PLAN_REFUSED_BUDGET")
    gate(tmp_path, max_files_per_change=4).authorize(p, evid(p))


def test_missing_evidence_is_ungated(tmp_path):
    p = plan()
    refused(lambda: gate(tmp_path).authorize(p, None), "PLAN_REFUSED_UNGATED")
    refused(lambda: gate(tmp_path).authorize(p, GateEvidence(p.digest(), None, mut())), "PLAN_REFUSED_UNGATED")
    refused(lambda: gate(tmp_path).authorize(p, GateEvidence(p.digest(), ok_tests(), None)), "PLAN_REFUSED_UNGATED")


def test_digest_mismatch_is_ungated(tmp_path):
    p = plan(); q = plan(feature="different")
    refused(lambda: gate(tmp_path).authorize(p, evid(q)), "PLAN_REFUSED_UNGATED")


def test_zero_or_unknown_tests_are_ungated(tmp_path):
    p = plan()
    for t in (PytestResult(0, 0, 0, 0, 0.1, ""), PytestResult(0, None, None, None, 0.1, "")):
        refused(lambda: gate(tmp_path).authorize(p, evid(p, tests=t)), "PLAN_REFUSED_UNGATED")


def test_mutation_must_have_run_and_be_consistent(tmp_path):
    p = plan()
    refused(lambda: gate(tmp_path).authorize(p, evid(p, mutation=mut(0, 0, 0))), "PLAN_REFUSED_UNGATED")
    refused(lambda: gate(tmp_path).authorize(p, evid(p, mutation=mut(5, 4, 0))), "PLAN_REFUSED_UNGATED")
    refused(lambda: gate(tmp_path).authorize(p, evid(p, mutation=mut(5, 4, 0, 1))), "PLAN_REFUSED_UNGATED")
    refused(lambda: gate(tmp_path).authorize(p, evid(p, mutation=mut(5, 5, 0), equivalent_declared=1)),
            "PLAN_REFUSED_UNGATED")


def test_failing_tests_are_regression(tmp_path):
    p = plan()
    for t in (PytestResult(1, 9, 1, 0, 0.1, ""), PytestResult(1, 9, 0, 1, 0.1, ""), PytestResult(1, 10, 0, 0, 0.1, ""),
              PytestResult(2, 10, 0, 0, 0.1, "")):
        refused(lambda: gate(tmp_path).authorize(p, evid(p, tests=t)), "PLAN_REFUSED_REGRESSION")


def test_test_count_drop_vs_baseline_is_regression(tmp_path):
    p = plan()
    refused(lambda: gate(tmp_path).authorize(p, evid(p, tests=ok_tests(9), baseline_passed=10)),
            "PLAN_REFUSED_REGRESSION")
    gate(tmp_path).authorize(p, evid(p, tests=ok_tests(10), baseline_passed=10))


def test_survivors_are_regression_unless_declared_equivalent(tmp_path):
    p = plan()
    refused(lambda: gate(tmp_path).authorize(p, evid(p, mutation=mut(5, 4, 1))), "PLAN_REFUSED_REGRESSION")
    refused(lambda: gate(tmp_path).authorize(p, evid(p, mutation=mut(5, 3, 2), equivalent_declared=1)),
            "PLAN_REFUSED_REGRESSION")
    gate(tmp_path).authorize(p, evid(p, mutation=mut(5, 3, 2), equivalent_declared=2))


def test_timeouts_count_as_detected(tmp_path):
    p = plan()
    gate(tmp_path).authorize(p, evid(p, mutation=mut(5, 3, 0, 0, 2)))


def test_budget_window(tmp_path):
    clock = T(1000.0)
    g = gate(tmp_path, now=clock, max_changes_per_window=2, window_s=100)
    p = plan()
    g.authorize(p, evid(p)); g.authorize(p, evid(p))
    refused(lambda: g.authorize(p, evid(p)), "PLAN_REFUSED_BUDGET")
    clock.t = 1099.0
    refused(lambda: g.authorize(p, evid(p)), "PLAN_REFUSED_BUDGET")
    clock.t = 1100.5
    g.authorize(p, evid(p))


def test_refusals_do_not_consume_budget(tmp_path):
    g = gate(tmp_path, max_changes_per_window=1)
    p = plan()
    refused(lambda: g.authorize(p, None), "PLAN_REFUSED_UNGATED")
    refused(lambda: g.authorize(p, evid(p, mutation=mut(5, 4, 1))), "PLAN_REFUSED_REGRESSION")
    g.authorize(p, evid(p))
    assert [e["event"] for e in g.ledger()] == ["refused", "refused", "authorized"]


def test_budget_checked_after_evidence(tmp_path):
    g = gate(tmp_path, max_changes_per_window=1)
    p = plan()
    g.authorize(p, evid(p))
    refused(lambda: g.authorize(p, None), "PLAN_REFUSED_UNGATED")


def test_ledger_and_changelog_content(tmp_path):
    g = gate(tmp_path)
    p = plan()
    g.authorize(p, evid(p, tests=ok_tests(12), mutation=mut(7, 6, 1), equivalent_declared=1))
    e = g.ledger()[0]
    assert e["event"] == "authorized" and e["digest"] == p.digest() and e["at"] == 1000.0
    assert e["tests_passed"] == 12 and e["mutants_total"] == 7 and e["mutants_survived"] == 1
    assert e["equivalent_declared"] == 1 and e["branch"] == p.branch and e["merge_allowed"] is False
    cl = g.changelog()
    assert "kw filter" in cl and p.branch in cl and p.digest()[:12] in cl and "mod-a" in cl
    assert "12 tests passed" in cl and "6/7 mutants killed" in cl


def test_refused_ledger_entry_has_code_and_changelog_untouched(tmp_path):
    g = gate(tmp_path)
    p = plan()
    refused(lambda: g.authorize(p, None), "PLAN_REFUSED_UNGATED")
    e = g.ledger()[0]
    assert e["event"] == "refused" and e["code"] == "PLAN_REFUSED_UNGATED" and e["digest"] == p.digest()
    assert g.changelog() == ""


def test_bad_plan_refusal_is_logged_without_digest_crash(tmp_path):
    g = gate(tmp_path)
    p = plan(files=())
    refused(lambda: g.authorize(p, None), "PLAN_REFUSED_BAD_PLAN")
    assert g.ledger()[0]["code"] == "PLAN_REFUSED_BAD_PLAN"


def test_ledger_survives_restart(tmp_path):
    p = plan()
    gate(tmp_path, max_changes_per_window=1).authorize(p, evid(p))
    g2 = gate(tmp_path, max_changes_per_window=1)
    refused(lambda: g2.authorize(p, evid(p)), "PLAN_REFUSED_BUDGET")


def test_corrupt_ledger_fails_loud(tmp_path):
    g = gate(tmp_path)
    (tmp_path / "g").mkdir(exist_ok=True)
    (tmp_path / "g" / "mod-a.improvement-ledger.jsonl").write_text("{bad\n")
    with pytest.raises(ig.GateLedgerError):
        g.ledger()
    with pytest.raises(ig.GateLedgerError):
        g.authorize(plan(), None)
    assert issubclass(ig.GateLedgerError, ValueError) and not issubclass(ig.GateLedgerError, PlanRefused)


def test_constructor_validation(tmp_path):
    for kw in ({"max_changes_per_window": 0}, {"window_s": 0}, {"max_files_per_change": 0}):
        with pytest.raises(ValueError):
            gate(tmp_path, **kw)
    with pytest.raises(ValueError):
        ImprovementGate("mod-a", tmp_path, sandbox_roots=())
    with pytest.raises(ValueError):
        ImprovementGate("a/b", tmp_path, sandbox_roots=ROOTS)
    with pytest.raises(ValueError):
        ImprovementGate("mod-a", tmp_path, sandbox_roots=("backend",))


def test_authorization_never_allows_merge():
    p = plan()
    a = ig.Authorization(p, p.digest(), 1.0)
    assert a.merge_allowed is False
    with pytest.raises(Exception):
        a.merge_allowed = True


def _proj(tmp_path, tests, name="proj"):
    d = tmp_path / name; d.mkdir()
    (d / "mod.py").write_text("def add(a, b):\n    return a + b\n\ndef neg(a):\n    return -a\n")
    (d / "test_mod.py").write_text(tests)
    return d


def test_run_mutations_real_kill_survive_nomatch(tmp_path):
    d = _proj(tmp_path, "from mod import add, neg\ndef test_add():\n    assert add(2, 3) == 5\n")
    r = run_mutations("mod.py", [("a + b", "a - b"), ("return -a", "return a"), ("zzz_missing", "q")],
                      ["test_mod.py"], cwd=d)
    assert (r.total, r.killed, r.survived, r.nomatch, r.timeouts) == (3, 1, 1, 1, 0)
    assert [o["outcome"] for o in r.results] == ["killed", "survived", "nomatch"]
    assert (d / "mod.py").read_text().count("a + b") == 1  # original untouched


def test_run_mutations_timeout_and_baseline_failure(tmp_path):
    d = _proj(tmp_path, "from mod import add\ndef test_add():\n    assert add(2, 3) == 5\n")
    (d / "mod.py").write_text("def add(a, b):\n    return a + b\n")
    r = run_mutations("mod.py", [("return a + b", "while True: pass")], ["test_mod.py"], cwd=d, timeout=2)
    assert (r.total, r.timeouts, r.killed, r.survived) == (1, 1, 0, 0)
    d2 = _proj(tmp_path, "def test_f():\n    assert 0\n", name="proj2")
    refused(lambda: run_mutations("mod.py", [("a + b", "a - b")], ["test_mod.py"], cwd=d2),
            "PLAN_REFUSED_UNGATED")


def test_same_size_same_second_mutant_is_not_masked_by_stale_bytecode(tmp_path):
    # "a + b" -> "a - b" keeps file size; a stale .pyc would hide it. Repeated 5 times in a row.
    d = _proj(tmp_path, "from mod import add\ndef test_add():\n    assert add(2, 3) == 5\n")
    for _ in range(5):
        r = run_mutations("mod.py", [("a + b", "a - b")], ["test_mod.py"], cwd=d)
        assert (r.killed, r.survived) == (1, 0)


def test_run_mutations_restores_environment_and_writes_no_bytecode(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)
    d = _proj(tmp_path, "from mod import add\ndef test_add():\n    assert add(2, 3) == 5\n")
    run_mutations("mod.py", [("a + b", "a - b")], ["test_mod.py"], cwd=d)
    import os
    assert "PYTHONDONTWRITEBYTECODE" not in os.environ
    assert not (d / "__pycache__").exists()
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "keep")
    run_mutations("mod.py", [("a + b", "a - b")], ["test_mod.py"], cwd=d)
    assert os.environ["PYTHONDONTWRITEBYTECODE"] == "keep"


def test_run_mutations_input_validation(tmp_path):
    d = _proj(tmp_path, "def test_f():\n    assert True\n")
    with pytest.raises(ValueError):
        run_mutations("mod.py", [], ["test_mod.py"], cwd=d)
    for bad in ("../mod.py", "/abs.py", "missing.py"):
        with pytest.raises(ValueError):
            run_mutations(bad, [("a", "b")], ["test_mod.py"], cwd=d)


def test_end_to_end_gate_with_real_runs(tmp_path):
    d = _proj(tmp_path, "from mod import add, neg\ndef test_add():\n    assert add(2, 3) == 5\ndef test_neg():\n    assert neg(2) == -2\n")
    from app.self_improve.self_eval import run_pytest
    p = plan()
    t = run_pytest(["test_mod.py"], cwd=d)
    m = run_mutations("mod.py", [("a + b", "a - b"), ("return -a", "return a")], ["test_mod.py"], cwd=d)
    a = gate(tmp_path).authorize(p, GateEvidence(p.digest(), t, m))
    assert a.merge_allowed is False
    weak = _proj(tmp_path, "from mod import add\ndef test_add():\n    assert add(2, 3) == 5\n", name="weak")
    t2 = run_pytest(["test_mod.py"], cwd=weak)
    m2 = run_mutations("mod.py", [("a + b", "a - b"), ("return -a", "return a")], ["test_mod.py"], cwd=weak)
    refused(lambda: gate(tmp_path / "other").authorize(p, GateEvidence(p.digest(), t2, m2)), "PLAN_REFUSED_REGRESSION")


def test_stdlib_only():
    import re
    src = Path(ig.__file__).read_text()
    mods = set(re.findall(r"^(?:from|import)\s+([A-Za-z_.]\w*)", src, re.M))
    assert mods <= {"__future__", "dataclasses", "hashlib", "json", "pathlib", "shutil", "tempfile",
                    "time", "typing", ".self_eval", "sys", "os"}


@pytest.mark.parametrize("branch", ["origin/master", "refs/heads/master"])
def test_more_main_names_are_self_merge(tmp_path, branch):
    p = plan(branch=branch)
    refused(lambda: gate(tmp_path).authorize(p, evid(p)), "PLAN_REFUSED_SELF_MERGE")


@pytest.mark.parametrize("f", ["backend/app/self_improve/a\\b.py", "backend/app/self_improve/./x.py",
                               "backend/app/self_improve/", "tests/self_improve/", "backend/app/self_improve/../x.py"])
def test_outside_sandbox_inside_prefix_forms(tmp_path, f):
    p = plan(files=(f,))
    refused(lambda: gate(tmp_path).authorize(p, evid(p)), "PLAN_REFUSED_OUTSIDE_SANDBOX")


def test_negative_declared_equivalents_are_ungated(tmp_path):
    p = plan()
    refused(lambda: gate(tmp_path).authorize(p, evid(p, equivalent_declared=-1)), "PLAN_REFUSED_UNGATED")


def test_inconsistent_green_returncode_with_failed_or_errors_is_regression(tmp_path):
    p = plan()
    refused(lambda: gate(tmp_path).authorize(p, evid(p, tests=PytestResult(0, 10, 1, 0, 0.1, ""))), "PLAN_REFUSED_REGRESSION")
    refused(lambda: gate(tmp_path).authorize(p, evid(p, tests=PytestResult(0, 10, 0, 1, 0.1, ""))), "PLAN_REFUSED_REGRESSION")


def test_budget_window_exact_boundary_is_outside(tmp_path):
    clock = T(1000.0)
    g = gate(tmp_path, now=clock, max_changes_per_window=1, window_s=100)
    p = plan()
    g.authorize(p, evid(p))
    clock.t = 1100.0
    g.authorize(p, evid(p))


def test_timeouts_appear_as_killed_in_changelog_and_ledger(tmp_path):
    g = gate(tmp_path)
    p = plan()
    g.authorize(p, evid(p, mutation=mut(5, 3, 0, 0, 2)))
    assert "5/5 mutants killed" in g.changelog()
    assert g.ledger()[0]["mutants_killed"] == 5


def test_ledger_files_are_sorted(tmp_path):
    g = gate(tmp_path)
    p = plan(files=("tests/self_improve/test_z.py", "backend/app/self_improve/a.py"))
    g.authorize(p, evid(p))
    assert g.ledger()[0]["files"] == ["backend/app/self_improve/a.py", "tests/self_improve/test_z.py"]


def test_target_with_dotdot_segment_rejected_even_if_it_exists(tmp_path):
    d = _proj(tmp_path, "def test_f():\n    assert True\n")
    (d / "sub").mkdir()
    with pytest.raises(ValueError):
        run_mutations("sub/../mod.py", [("a + b", "a - b")], ["test_mod.py"], cwd=d)
