"""exact-replacement mutation battery. Run from repository root with Python >=3.12.
Named released selectors must pass before mutation. CAUGHT requires pytest rc=1,
at least one FAILED line and no collection error, internal error, crash or timeout.
SURVIVED/INVALID/NOT-APPLICABLE are reported separately. Every file is restored
in finally and SHA-256 compared with its original bytes. Receipts default to
this audit directory's mutation_receipts.txt; an alternate path may be supplied.
"""
import hashlib, os, subprocess, sys

TESTS = 'tests/runtime/guardrails/test_effect_bindings.py tests/runtime/guardrails/test_egress_coverage_ratchet.py'
MUT = [('I1 exempt generic m01 transport', 'tests/runtime/guardrails/effect_bindings.py', 'if rel in WRITE_CAPABLE_TRANSPORTS:', 'if False:', 'tests/runtime/guardrails/test_effect_bindings.py::test_generic_m01_transport_is_not_read_exempt'), ('I2 dead import classified gated', 'tests/runtime/guardrails/effect_bindings.py', 'and gate_calls & GATE_CALLS:', ':', 'tests/runtime/guardrails/test_effect_bindings.py::test_dead_gate_import_cannot_make_egress_gated'), ('I3 vacuous package callers gated', 'tests/runtime/guardrails/effect_bindings.py', 'ok = bool(sites)', 'ok = True', 'tests/runtime/guardrails/test_effect_bindings.py::test_no_package_publish_call_cannot_vacuously_gate')]
MUT += [
    ("I4 remove reviewed clicky live guard", "backend/app/modules/c31/clicky.py", 'if live_approved is not True or os.environ.get(LIVE_ENV_FLAG) != "1":', 'if False:', "tests/runtime/guardrails/test_effect_bindings.py::test_reviewed_ungated_rationale_is_code_bound"),
    ("I5 change reviewed clicky GET to POST", "backend/app/modules/c31/clicky.py", 'method="GET")', 'method="POST")', "tests/runtime/guardrails/test_effect_bindings.py::test_reviewed_ungated_rationale_is_code_bound"),
    ("I6 overclaim reviewed clicky authority", "tests/runtime/guardrails/effect_bindings.py", "default-off guard, not M00 authority", "M00 authority verified", "tests/runtime/guardrails/test_effect_bindings.py::test_clicky_rationale_wording_cannot_overclaim_owner_authority tests/runtime/guardrails/test_effect_bindings.py::test_reviewed_ungated_rationale_is_code_bound"),
]
ENV =dict(os.environ, ATLAS_DEV_NO_AUTH="1", ATLAS_ENV="development", PYTHONPATH="backend")
TIMEOUT_S = 120

def run(tests):
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *tests.split(), "-q", "-rf"],
                           capture_output=True, text=True, env=ENV, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", []
    lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
    failed = [l.split(" - ")[0][len("FAILED "):] for l in lines if l.startswith("FAILED ")]
    return r.returncode, (lines[-1] if lines else ""), ([] if "ERROR collecting" in r.stdout or "INTERNALERROR" in r.stdout or "Fatal Python error" in r.stderr else failed)

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

def main(out):
    lines = []
    files = sorted({m[1] for m in MUT})
    before = {f: sha(f) for f in files}
    for tests in (TESTS,):
        rc, last, _ = run(tests); lines.append("BASELINE %s -> rc=%s %s" % (tests, rc, last)); assert rc == 0, last
    counts = {"CAUGHT": 0, "SURVIVED": 0, "INVALID": 0, "NOT-APPLICABLE": 0}
    for mid, f, old, new, tests in MUT:
        src = open(f).read()
        if src.count(old) < 1:
            counts["NOT-APPLICABLE"] += 1
            lines.append("%s | NOT-APPLICABLE (old text not found)" % mid); continue
        open(f, "w").write(src.replace(old, new, 1))
        try:
            rc, last, failed = run(tests)
        finally:
            open(f, "w").write(src)
        if rc == 0:
            verdict = "SURVIVED"
        elif rc == 1 and failed and "ERROR" not in last:
            verdict = "CAUGHT"
        else:
            verdict = "INVALID"
        counts[verdict] += 1
        lines.append("%s | %s | %s | rc=%s | %s | failing: %s" % (mid, f.split("/")[-1], verdict, rc, last, "; ".join(x.split("::")[-1] for x in failed[:3]) or "-"))
    restored = all(sha(f) == before[f] for f in files)
    lines.append("counts: " + ", ".join("%s=%d" % kv for kv in counts.items()))
    lines.append("mutated files byte-identical to pre-run state (sha256): %s" % restored)
    open(out, "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
    sys.exit(0 if restored else 3)

main(sys.argv[1] if len(sys.argv) > 1 else "audits/egress-inventory/mutation_receipts.txt")
