"""Test-only pins for improvement_gate (child of 2928df8b). Targets the peer auditor's 36 survivors."""
import dataclasses
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from app.self_improve import improvement_gate as ig
from app.self_improve.improvement_gate import (
    Authorization, ChangePlan, GateEvidence, ImprovementGate, MutationRun, PlanRefused, run_mutations)
from app.self_improve.self_eval import PytestResult

ROOTS = ("backend/app/self_improve/", "tests/self_improve/")
F1 = "backend/app/self_improve/x.py"


def plan(**kw):
    d = dict(module_slug="mod-a", feature="kw filter", branch="selfimprove/mod-a-kw",
             files=(F1, "tests/self_improve/test_x.py"))
    d.update(kw)
    return ChangePlan(**d)


def ok_t(passed=10):
    return PytestResult(0, passed, 0, 0, 0.1, "")


def mut(total=5, killed=5, survived=0, nomatch=0, timeouts=0):
    return MutationRun(total, killed, survived, nomatch, timeouts, ())


def evid(p, tests=None, mutation=None, **kw):
    return GateEvidence(plan_digest=p.digest(), tests=tests or ok_t(), mutation=mutation or mut(), **kw)


class T:
    def __init__(self, t=1000.0): self.t = t
    def __call__(self): return self.t


def g(tmp_path, roots=ROOTS, now=None, **kw):
    return ImprovementGate("mod-a", tmp_path / "g", sandbox_roots=roots, now=now or T(), **kw)


def refused(fn, code, detail=None):
    with pytest.raises(PlanRefused) as e:
        fn()
    assert e.value.code == code
    if detail is not None:
        assert e.value.detail == detail
    return e.value


# ---- frozen dataclasses (L38 ChangePlan, L52 MutationRun, L62 GateEvidence, L71 Authorization)
@pytest.mark.parametrize("make,field", [
    (lambda: plan(), "feature"), (lambda: mut(), "total"),
    (lambda: GateEvidence("d", None, None), "plan_digest"),
    (lambda: Authorization(plan(), "d", 1.0), "digest")])
def test_dataclasses_are_frozen(make, field):
    obj = make()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, field, "changed")


# ---- digest pin (L48 sort_keys)
def test_digest_exact_value_over_sorted_key_json():
    p = plan(files=("b/two.py", "a/one.py"))
    literal = ('{"branch": "selfimprove/mod-a-kw", "feature": "kw filter", "files": ["a/one.py", "b/two.py"], '
               '"module": "mod-a", "target": "branch"}')
    assert p.digest() == hashlib.sha256(literal.encode("utf-8")).hexdigest()


# ---- keyword-only markers and defaults (L87, L88, L218, L219)
def test_gate_constructor_signature_pins(tmp_path):
    sig = inspect.signature(ImprovementGate.__init__).parameters
    assert sig["sandbox_roots"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig["state_dir"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert (sig["max_changes_per_window"].default, sig["window_s"].default,
            sig["max_files_per_change"].default) == (3, 86400, 10)
    with pytest.raises(TypeError):
        ImprovementGate("mod-a", tmp_path, ROOTS)
    ImprovementGate(module_slug="mod-a", state_dir=tmp_path, sandbox_roots=ROOTS)


def test_default_budget_is_three_changes(tmp_path):
    gate = g(tmp_path)
    p = plan()
    for _ in range(3):
        gate.authorize(p, evid(p))
    refused(lambda: gate.authorize(p, evid(p)), "PLAN_REFUSED_BUDGET")


def test_default_window_is_86400_seconds(tmp_path):
    clock = T(1000.0)
    gate = g(tmp_path, now=clock, max_changes_per_window=1)
    p = plan()
    gate.authorize(p, evid(p))
    clock.t = 1000.0 + 86399
    refused(lambda: gate.authorize(p, evid(p)), "PLAN_REFUSED_BUDGET")
    clock.t = 1000.0 + 86400
    gate.authorize(p, evid(p))


def test_default_max_files_is_ten(tmp_path):
    ten = tuple(f"backend/app/self_improve/f{i}.py" for i in range(10))
    p = plan(files=ten)
    g(tmp_path).authorize(p, evid(p))
    eleven = tuple(f"backend/app/self_improve/f{i}.py" for i in range(11))
    p = plan(files=eleven)
    refused(lambda: g(tmp_path / "o").authorize(p, evid(p)), "PLAN_REFUSED_BUDGET")


def test_run_mutations_signature_pins():
    sig = inspect.signature(run_mutations).parameters
    assert sig["cwd"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig["target_rel"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert sig["timeout"].default == 120


# ---- constructor budget validation (L95)
def test_constructor_boundaries(tmp_path):
    g(tmp_path / "a", max_changes_per_window=1, window_s=1, max_files_per_change=1)
    g(tmp_path / "b", window_s=0.5)
    for kw in ({"max_changes_per_window": 0}, {"window_s": 0}, {"max_files_per_change": 0},
               {"max_changes_per_window": -1}, {"window_s": -1}, {"max_files_per_change": -1}):
        with pytest.raises(ValueError):
            g(tmp_path / "c", **kw)


# ---- ledger (L112 line numbers, L126 sorted keys)
def test_corrupt_ledger_names_the_right_line(tmp_path):
    gate = g(tmp_path)
    p = plan()
    gate.authorize(p, evid(p))
    with open(tmp_path / "g" / "mod-a.improvement-ledger.jsonl", "a") as fh:
        fh.write("{bad\n")
    with pytest.raises(ig.GateLedgerError) as e:
        gate.ledger()
    assert "corrupt ledger line 2:" in str(e.value)


def test_ledger_lines_are_written_with_sorted_keys(tmp_path):
    gate = g(tmp_path)
    p = plan()
    gate.authorize(p, evid(p))
    refused(lambda: gate.authorize(p, None), "PLAN_REFUSED_UNGATED")
    for line in (tmp_path / "g" / "mod-a.improvement-ledger.jsonl").read_text().splitlines():
        keys = list(json.loads(line).keys())
        assert keys == sorted(keys)


# ---- plan validation (L131) : the first-check detail must be the one raised
BLANK_DETAIL = "feature, module, branch and files must be non-empty"


@pytest.mark.parametrize("kw", [{"feature": ""}, {"module_slug": ""}, {"branch": ""}, {"files": ()},
                                {"files": ("",)}, {"feature": " "}, {"branch": "  "}])
def test_blank_fields_raise_the_blank_check_detail(tmp_path, kw):
    p = plan(**kw)
    refused(lambda: g(tmp_path).authorize(p, None), "PLAN_REFUSED_BAD_PLAN", BLANK_DETAIL)


# ---- sandbox (L146): each clause alone, with files inside a configured root
def test_each_unsafe_path_clause_alone_refuses(tmp_path):
    cases = [
        (ROOTS, "backend/app/self_improve/a\\b.py"),
        (ROOTS, "backend/app/self_improve/../x.py"),
        (ROOTS, "backend/app/self_improve/./x.py"),
        (("~/x/",), "~/x/f.py"),
        (("a~/x/",), "a~/x/f.py"),
    ]
    for roots, f in cases[:4]:
        p = plan(files=(f,))
        refused(lambda: g(tmp_path / "s", roots=roots).authorize(p, evid(p)), "PLAN_REFUSED_OUTSIDE_SANDBOX")
    p = plan(files=("a~/x/f.py",))
    g(tmp_path / "ok", roots=("a~/x/",)).authorize(p, evid(p))


# ---- mutation counts (L158 total<=0, L160 sum terms)
def test_one_mutant_run_is_enough(tmp_path):
    p = plan()
    g(tmp_path).authorize(p, evid(p, mutation=mut(1, 1, 0)))


def test_nomatch_has_its_own_detail_and_sum_terms_each_count(tmp_path):
    p = plan()
    refused(lambda: g(tmp_path).authorize(p, evid(p, mutation=mut(5, 4, 0, 1))),
            "PLAN_REFUSED_UNGATED", "some mutants did not apply")
    refused(lambda: g(tmp_path).authorize(p, evid(p, mutation=mut(5, 4, 0, 0, 0))),
            "PLAN_REFUSED_UNGATED", "mutation counts do not add up")
    g(tmp_path).authorize(p, evid(p, mutation=mut(6, 2, 2, 0, 2), equivalent_declared=2))


# ---- changelog digest width (L198)
def test_changelog_digest_is_exactly_twelve_chars(tmp_path):
    gate = g(tmp_path)
    p = plan()
    gate.authorize(p, evid(p))
    assert f"(digest {p.digest()[:12]}):" in gate.changelog()


# ---- run_mutations input checks (L221, L225)
def _proj(tmp_path, name="proj"):
    d = tmp_path / name
    d.mkdir()
    (d / "mod.py").write_text("def f():\n    return 1\n\ndef g():\n    return 1\n")
    (d / "test_mod.py").write_text("from mod import g\ndef test_g():\n    assert g() == 1\n")
    return d


@pytest.mark.parametrize("bad", [[["a", "b"]], [("a",)], [("a", "b", "c")], [(1, "b")], [("a", 2)],
                                 [("", "b")], [("a", "b"), ("", "z")], [None], ["ab"]])
def test_mutant_pairs_must_be_exact_string_tuples(tmp_path, bad):
    d = _proj(tmp_path)
    with pytest.raises(ValueError):
        run_mutations("mod.py", bad, ["test_mod.py"], cwd=d)


def test_empty_new_text_is_a_valid_mutant(tmp_path):
    d = _proj(tmp_path)
    r = run_mutations("mod.py", [("return 1", "")], ["test_mod.py"], cwd=d)
    assert r.total == 1 and r.nomatch == 0


@pytest.mark.parametrize("bad", [None, 5, "/abs.py", "sub/../mod.py", "missing.py", "../mod.py"])
def test_target_must_be_a_relative_existing_file(tmp_path, bad):
    d = _proj(tmp_path)
    (d / "sub").mkdir()
    if bad == "/abs.py":
        bad = str(d / "mod.py")
    with pytest.raises(ValueError):
        run_mutations(bad, [("return 1", "return 2")], ["test_mod.py"], cwd=d)


# ---- only the first occurrence is mutated (L241)
def test_only_first_occurrence_is_replaced(tmp_path):
    d = _proj(tmp_path)
    r = run_mutations("mod.py", [("return 1", "return 2")], ["test_mod.py"], cwd=d)
    assert (r.killed, r.survived) == (0, 1)


# ---- result text is truncated at 60 chars (L250)
def test_result_old_new_truncated_to_sixty(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    long_old = "return " + "x" * 80
    (d / "mod.py").write_text(f"def f():\n    {long_old}\n")
    (d / "test_mod.py").write_text("def test_ok():\n    assert True\n")
    new = "return " + "y" * 80
    r = run_mutations("mod.py", [(long_old, new)], ["test_mod.py"], cwd=d)
    row = r.results[0]
    assert row["old"] == long_old[:60] and len(row["old"]) == 60
    assert row["new"] == new[:60] and len(row["new"]) == 60
