"""exact-replacement mutation battery. Run from repository root with Python >=3.12.
Named released selectors must pass before mutation. CAUGHT requires pytest rc=1,
at least one FAILED line and no collection error, internal error, crash or timeout.
SURVIVED/INVALID/NOT-APPLICABLE are reported separately. Every file is restored
in finally and SHA-256 compared with its original bytes. Receipts default to
this audit directory's mutation_receipts.txt; an alternate path may be supplied.
"""
import hashlib, os, subprocess, sys

TESTS = 'tests/runtime/test_approved_execution.py tests/modules/test_worker_outbound_gate.py'
MUT = [('X1 allow classification override', 'backend/app/runtime/approved_execution.py', 'if effect_kinds is not None:', 'if False:', 'tests/runtime/test_approved_execution.py::test_effect_classification_cannot_be_overridden'), ('X2 unknown dispatcher default allow', 'backend/app/runtime/approved_execution.py', 'if effect_kind is None and (action_type not in LOCAL_ACTION_TYPES\n                                    or target != ACTION_ALLOWLIST[action_type]):', 'if False:', 'tests/runtime/test_approved_execution.py::test_non_allowlisted_action_is_refused_and_audited'), ('X3 shallow authority bind', 'backend/app/runtime/approved_execution.py', 'self._bound[approval_id] = copy.deepcopy(fields)', 'self._bound[approval_id] = dict(fields)', 'tests/runtime/test_approved_execution.py::test_authority_binder_deep_copies_execution_fields'), ('X4 ignore module identity drift', 'backend/app/runtime/approved_execution.py', 'or view.get("module_id") != fields["approval_module_id"]', 'or False', 'tests/runtime/test_approved_execution.py::test_prod_hook_rejects_nested_and_identity_drift_after_bind'), ('X5 detached dispatcher callback', 'backend/app/runtime/approved_execution.py', 'RuntimeContext(**a["context"]),\n                        Handoff(**a["handoff"], payload=a["payload"])', 'context, handoff', 'tests/runtime/test_approved_execution.py::test_dispatcher_effect_uses_only_canonical_gate_action'), ('X6 reset worker ledger each task', 'backend/app/workers/tasks.py', 'if key not in _OUTBOUND:', 'if True:', 'tests/modules/test_worker_outbound_gate.py::test_worker_rate_history_is_retained_across_tasks'), ('X7 allow unknown worker action', 'backend/app/workers/tasks.py', 'if (str(view["action_type"]) not in LOCAL_ACTION_TYPES\n                or view["module_id"] != ACTION_ALLOWLIST[str(view["action_type"])][0]):', 'if False:', 'tests/modules/test_worker_outbound_gate.py::test_unknown_worker_action_refused_before_permit'), ('X8 truncate claim id', 'backend/app/workers/tasks.py', 'ident(effect_id, "effect_id", fail=make_fail("WORKER"))', 'effect_id = effect_id[:64]', 'tests/modules/test_worker_outbound_gate.py::test_worker_long_effect_id_refused_without_truncation')]
MUT += [
    ("X9 skip bound digest", "backend/app/runtime/approved_execution.py", "payload_sha256(fields) == action_digest == payload_sha256(current)", "action_digest == payload_sha256(current)", "tests/runtime/test_approved_execution.py::test_authority_binder_deep_copies_execution_fields"),
    ("X10 redirect local dispatcher target", "backend/app/runtime/approved_execution.py", "or target != ACTION_ALLOWLIST[action_type]", "or False", "tests/runtime/test_approved_execution.py::test_local_action_cannot_be_redirected_to_an_effect_target"),
    ("X11 reuse local worker name on effect module", "backend/app/workers/tasks.py", 'or view["module_id"] != ACTION_ALLOWLIST[str(view["action_type"])][0]', "or False", "tests/modules/test_worker_outbound_gate.py::test_worker_local_name_cannot_be_reused_on_effect_module"),
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

main(sys.argv[1] if len(sys.argv) > 1 else "audits/execution-binding/mutation_receipts.txt")
