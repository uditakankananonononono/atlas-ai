"""ProofCarryingGate: the improvement gate with sandboxed proof checking required (direction 6 wiring)."""
import pytest

from app.self_improve import proof_carrying as pc
from app.self_improve.improvement_gate import ChangePlan, GateEvidence, ImprovementGate, MutationRun, PlanRefused
from app.self_improve.proof_carrying import Conclusion, sha
from app.self_improve.proof_gate import CODE_UNPROVEN, ProofCarryingGate
from app.self_improve.self_eval import PytestResult

ROOTS = ("backend/app/self_improve/", "tests/self_improve/")


def plan(feature="f", **kw):
    d = dict(module_slug="mod-a", feature=feature, branch="selfimprove/mod-a-f",
             files=("backend/app/self_improve/x.py", "tests/self_improve/test_x.py"))
    d.update(kw)
    return ChangePlan(**d)


def evid(p, **kw):
    return GateEvidence(plan_digest=p.digest(), tests=PytestResult(0, 10, 0, 0, 0.1, ""),
                        mutation=MutationRun(5, 5, 0, 0, 0, ()), **kw)


class T:
    def __init__(self): self.t = 1000.0
    def __call__(self): self.t += 1; return self.t


def gate(tmp_path, **kw):
    return ProofCarryingGate("mod-a", tmp_path / "g", sandbox_roots=ROOTS, now=T(), **kw)


def fact(p, n=91, f=(7, 13), **kw):
    return Conclusion("n composite", "factorization", dict(n=n, factors=list(f)), plan_digest=p.digest(), **kw)


def events(g):
    return [(e["event"], e.get("code")) for e in g.ledger()]


def test_verified_conclusion_authorizes_and_ledger_records_proofs_then_authorization(tmp_path):
    p = plan(); g = gate(tmp_path)
    auth = g.authorize(p, evid(p), [fact(p, confidence=0.1)])
    assert auth.digest == p.digest() and auth.merge_allowed is False
    led = g.ledger()
    assert [e["event"] for e in led] == ["proofs_verified", "authorized"]
    pr = led[0]["proofs"][0]
    assert (pr["status"], pr["confidence"], pr["kind"]) == ("VERIFIED", 0.1, "factorization")
    assert led[1]["merge_allowed"] is False


@pytest.mark.parametrize("arg", [None, [], (), "x", 5])
def test_missing_or_empty_conclusions_are_refused(tmp_path, arg):
    p = plan(); g = gate(tmp_path)
    with pytest.raises(PlanRefused) as e:
        g.authorize(p, evid(p), arg)
    assert e.value.code == CODE_UNPROVEN
    assert events(g) == [("refused", CODE_UNPROVEN)]


def test_calling_without_conclusions_argument_is_refused(tmp_path):
    p = plan(); g = gate(tmp_path)
    with pytest.raises(PlanRefused) as e:
        g.authorize(p, evid(p))
    assert e.value.code == CODE_UNPROVEN


def test_unverified_conclusion_is_refused_whatever_its_confidence(tmp_path):
    p = plan(); g = gate(tmp_path)
    with pytest.raises(PlanRefused) as e:
        g.authorize(p, evid(p), [fact(p, f=(7, 11), confidence=0.999)])
    assert e.value.code == CODE_UNPROVEN and "UNVERIFIED" in e.value.detail
    rec = g.ledger()[-1]
    assert rec["event"] == "refused" and rec["proofs"][0]["confidence"] == 0.999 and rec["proofs"][0]["status"] == "UNVERIFIED"
    assert not any(e["event"] == "authorized" for e in g.ledger())


def test_one_bad_conclusion_among_good_ones_refuses_everything(tmp_path):
    p = plan(); g = gate(tmp_path)
    with pytest.raises(PlanRefused):
        g.authorize(p, evid(p), [fact(p), fact(p, f=(3, 5)), fact(p)])
    assert [e["event"] for e in g.ledger()] == ["refused"]


def test_verification_impossible_kind_cannot_gate(tmp_path):
    p = plan(); g = gate(tmp_path)
    op = Conclusion("this change is wise", "opinion", {}, confidence=1.0, plan_digest=p.digest())
    with pytest.raises(PlanRefused) as e:
        g.authorize(p, evid(p), [op])
    assert "VERIFICATION_IMPOSSIBLE" in e.value.detail
    with pytest.raises(PlanRefused):
        g.authorize(p, evid(p), [fact(p), op])


def test_advisory_impossible_conclusion_is_recorded_but_does_not_gate_or_count_as_verified(tmp_path):
    p = plan(); g = gate(tmp_path)
    op = Conclusion("this change is wise", "opinion", {}, confidence=1.0, plan_digest=p.digest())
    g.authorize(p, evid(p), [fact(p)], advisory=[op, "junk"])
    adv = [x for x in g.ledger()[0]["proofs"] if x.get("advisory")]
    assert len(adv) == 1 and adv[0]["status"] == "VERIFICATION_IMPOSSIBLE"


def test_conclusion_bound_to_another_plan_cannot_be_replayed(tmp_path):
    p, q = plan("f"), plan("g")
    g = gate(tmp_path)
    with pytest.raises(PlanRefused) as e:
        g.authorize(p, evid(p), [fact(q)])
    assert "not bound to this plan" in e.value.detail
    unbound = Conclusion("x", "factorization", dict(n=91, factors=[7, 13]))
    with pytest.raises(PlanRefused):
        g.authorize(p, evid(p), [unbound])


def test_non_conclusion_entries_are_refused(tmp_path):
    p = plan(); g = gate(tmp_path)
    with pytest.raises(PlanRefused) as e:
        g.authorize(p, evid(p), [{"status": "VERIFIED"}])
    assert "not a Conclusion" in e.value.detail


def test_base_gate_rules_still_apply_after_proofs_pass(tmp_path):
    p = plan(); g = gate(tmp_path)
    bad_ev = GateEvidence(plan_digest=p.digest(), tests=PytestResult(0, 10, 0, 0, 0.1, ""),
                          mutation=MutationRun(5, 4, 1, 0, 0, ()))
    with pytest.raises(PlanRefused) as e:
        g.authorize(p, bad_ev, [fact(p)])
    assert e.value.code == "PLAN_REFUSED_REGRESSION"
    assert [x["event"] for x in g.ledger()] == ["proofs_verified", "refused"]
    with pytest.raises(PlanRefused) as e:
        g.authorize(plan(target="main"), evid(p), [fact(p)])
    assert e.value.code == "PLAN_REFUSED_SELF_MERGE" or e.value.code == CODE_UNPROVEN


def test_non_changeplan_goes_to_base_refusal(tmp_path):
    g = gate(tmp_path)
    with pytest.raises(PlanRefused) as e:
        g.authorize("not a plan", None, [])
    assert e.value.code == "PLAN_REFUSED_BAD_PLAN"


def test_budget_still_enforced(tmp_path):
    g = gate(tmp_path, max_changes_per_window=1)
    p = plan(); g.authorize(p, evid(p), [fact(p)])
    with pytest.raises(PlanRefused) as e:
        g.authorize(p, evid(p), [fact(p)])
    assert e.value.code == "PLAN_REFUSED_BUDGET"


def test_gate_is_an_improvement_gate_and_plain_gate_is_unchanged(tmp_path):
    p = plan()
    assert isinstance(gate(tmp_path), ImprovementGate)
    plain = ImprovementGate("mod-a", tmp_path / "plain", sandbox_roots=ROOTS)
    plain.authorize(p, evid(p))           # the unmodified class still works without proofs (scope limit, stated)


@pytest.mark.skipif(not pc.sandbox_ok(refresh=True), reason="bwrap cannot start on this host")
def test_code_change_conclusion_runs_in_the_sandbox_through_the_gate(tmp_path):
    p = plan(); g = gate(tmp_path)
    src = "def add(a, b):\n    return a + b\n"
    t = "from mod import add\ndef test_a():\n    assert add(1, 2) == 3\n"
    good = Conclusion("add works", "code_change", dict(source=src, tests=t, expected_passed=1), plan_digest=p.digest())
    g.authorize(p, evid(p), [good])
    assert g.ledger()[0]["proofs"][0]["status"] == "VERIFIED"
    tampered = Conclusion("add works", "code_change",
                          dict(source="def add(a, b):\n    return a - b\n", tests=t, expected_passed=1), plan_digest=p.digest())
    with pytest.raises(PlanRefused):
        gate(tmp_path / "2").authorize(p, evid(p), [tampered])


def test_exec_kind_on_host_without_sandbox_is_refused_by_the_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "bwrap_path", lambda: None); pc._PROBE.clear()
    p = plan(); g = gate(tmp_path)
    c = Conclusion("a", "analysis", dict(script="print(1)", output_sha256=sha(b"1\n")), plan_digest=p.digest())
    with pytest.raises(PlanRefused) as e:
        g.authorize(p, evid(p), [c])
    assert "SANDBOX_UNAVAILABLE" in e.value.detail
    pc._PROBE.clear()
