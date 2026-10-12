"""E5: does the evidence gate (tests + mutation) catch bad patches that tests alone accept?

Usage: python run_experiment.py [out_dir]   (needs pytest; stdlib otherwise)
Deterministic: no randomness, so there is no seed noise. The only variance is
corpus authoring, which this run cannot measure.
"""
import json
import os
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.self_improve import improvement_gate as ig  # noqa: E402
from app.self_improve.self_eval import PytestResult, run_pytest  # noqa: E402
import corpus  # noqa: E402
import mutants as mut  # noqa: E402

ROOTS = ("tests/self_improve/",)
FIX = "tests/self_improve/e5_fixture/"


def count_tests(src):
    return sum(1 for l in src.split("\n") if l.startswith("def test_"))


def build_cases():
    cases = []
    for name, t in corpus.T.items():
        n_thorough = count_tests(t["thorough"])
        cases += [
            dict(id=f"{name}:A", tpl=name, cond="A", label="good", code=t["good"], tests=t["thorough"]),
            dict(id=f"{name}:B", tpl=name, cond="B", label="good_undertested", code=t["good"], tests=t["weak"]),
            dict(id=f"{name}:C", tpl=name, cond="C", label="bad", code=t["bug"], tests=t["weak"]),
            dict(id=f"{name}:D", tpl=name, cond="D", label="bad", code=t["bug"], tests=t["thorough"]),
            dict(id=f"{name}:E", tpl=name, cond="E", label="bad", code=t["good"], tests=t["thorough"],
                 extra_file="backend/app/core/approvals.py"),
            dict(id=f"{name}:F", tpl=name, cond="F", label="bad", code=t["bug"], tests=t["weak"],
                 baseline=n_thorough),
        ]
        if "omit_tests" in t:
            cases.append(dict(id=f"{name}:G", tpl=name, cond="G", label="bad", code=t["bug"], tests=t["omit_tests"]))
    return cases


def run_case(c):
    name = c["tpl"]
    with tempfile.TemporaryDirectory(prefix="e5_") as tmp:
        d = Path(tmp)
        (d / f"m_{name}.py").write_text(c["code"], encoding="utf-8")
        (d / f"test_m_{name}.py").write_text(c["tests"], encoding="utf-8")
        files = (FIX + f"m_{name}.py", FIX + f"test_m_{name}.py")
        if c.get("extra_file"):
            files = files + (c["extra_file"],)
        plan = ig.ChangePlan(module_slug="e5", feature=c["id"], branch="selfimprove/e5-" + name, files=files)
        base = c.get("baseline")
        tests = run_pytest(["."], cwd=d, timeout=60)
        # T0: tests only
        t0 = tests.returncode == 0 and bool(tests.passed)
        # T1: tests + test-count baseline + sandbox/plan validity (everything except mutation)
        gate = ig.ImprovementGate("e5", Path(tmp) / "state", sandbox_roots=ROOTS, max_changes_per_window=10 ** 6)
        try:
            gate._validate_plan(plan)
            plan_ok = True
        except ig.PlanRefused as e:
            plan_ok, plan_code = False, e.code
        t1 = t0 and plan_ok and (base is None or (tests.passed or 0) >= base)
        # Full gate
        ms = mut.generate(c["code"])
        mrun, gate_code, survivors = None, None, []
        if not ms:
            gate_ok, gate_code = False, "PLAN_REFUSED_UNGATED(no mutants generated)"
        else:
            try:
                mrun = ig.run_mutations(f"m_{name}.py", ms, ["."], cwd=d, timeout=60)
                survivors = [r for r in mrun.results if r["outcome"] == "survived"]
                ev = ig.GateEvidence(plan.digest(), tests, mrun, baseline_passed=base)
                gate.authorize(plan, ev)
                gate_ok = True
            except ig.PlanRefused as e:
                gate_ok, gate_code = False, e.code
    return dict(id=c["id"], cond=c["cond"], label=c["label"], tests_passed=tests.passed, tests_failed=tests.failed,
                T0=t0, T1=t1, GATE=gate_ok, gate_code=gate_code,
                mutants=None if mrun is None else mrun.total,
                survivors=[(s["old"].strip(), s["new"].strip()) for s in survivors])


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    cases = build_cases()
    with Pool(4) as p:
        res = p.map(run_case, cases)
    (out / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"{len(res)} patches; wrote {out/'results.json'}")


if __name__ == "__main__":
    main()
