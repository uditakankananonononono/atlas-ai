"""exact-replacement mutation battery. Run from repository root with Python >=3.12.
Named released selectors must pass before mutation. CAUGHT requires pytest rc=1,
at least one FAILED line and no screened collection/internal/fatal error or timeout.
FAILED includes product exceptions such as KeyError/RuntimeError, not only assertions.
Mixed FAILED plus SKIP is not rejected by this runner; counts are failure sensitivity.
SURVIVED/INVALID/NOT-APPLICABLE are reported separately. Every file is restored
in finally and SHA-256 compared with its original bytes. Receipts default to
this audit directory's mutation_receipts.txt; an alternate path may be supplied.
"""
import hashlib, os, subprocess, sys

TESTS = 'tests/modules/test_m14_report_identity.py tests/modules/test_m14_report_gate.py tests/modules/test_m14_wiring.py'
MUT = [('status random valid 64-char id', 'backend/app/modules/m14_project_builder/service.py', '_report_id("status",project,generated,markdown)', 'uuid4().hex + uuid4().hex', 'tests/modules/test_m14_report_identity.py::test_status_emit_callsite_binds_exact_actual_identity'), ('status wrong body', 'backend/app/modules/m14_project_builder/service.py', '_report_id("status",project,generated,markdown)', '_report_id("status",project,generated,"")', 'tests/modules/test_m14_report_identity.py::test_status_emit_callsite_binds_exact_actual_identity'), ('status wrong kind', 'backend/app/modules/m14_project_builder/service.py', '_report_id("status",project,generated,markdown)', '_report_id("other",project,generated,markdown)', 'tests/modules/test_m14_report_identity.py::test_status_emit_callsite_binds_exact_actual_identity'), ('readme random valid 64-char id', 'backend/app/modules/m14_project_builder/service.py', '_report_id("readme",project,generated,readme)', 'uuid4().hex + uuid4().hex', 'tests/modules/test_m14_report_identity.py::test_export_emit_callsites_bind_exact_readme_and_status_identity'), ('readme wrong body', 'backend/app/modules/m14_project_builder/service.py', '_report_id("readme",project,generated,readme)', '_report_id("readme",project,generated,"")', 'tests/modules/test_m14_report_identity.py::test_export_emit_callsites_bind_exact_readme_and_status_identity'), ('readme wrong kind', 'backend/app/modules/m14_project_builder/service.py', '_report_id("readme",project,generated,readme)', '_report_id("other",project,generated,readme)', 'tests/modules/test_m14_report_identity.py::test_export_emit_callsites_bind_exact_readme_and_status_identity')]
ENV =dict(os.environ, ATLAS_DEV_NO_AUTH="1", ATLAS_ENV="development", PYTHONPATH="backend")
TIMEOUT_S = 120

def run(tests):
    global RUN_INDEX
    RUN_INDEX += 1
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *tests.split(), "-q", "-rf"],
                           capture_output=True, text=True, env=ENV, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", []
    (RAW_DIR / ("run-%02d.log" % RUN_INDEX)).write_text("selector: " + tests + "\nrc=" + str(r.returncode) + "\nSTDOUT\n" + r.stdout + "\nSTDERR\n" + r.stderr)
    lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
    failed = [l.split(" - ")[0][len("FAILED "):] for l in lines if l.startswith("FAILED ")]
    return r.returncode, (lines[-1] if lines else ""), ([] if "ERROR collecting" in r.stdout or "INTERNALERROR" in r.stdout or "Fatal Python error" in r.stderr else failed)

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

def main(out):
    from pathlib import Path
    import json
    folder = Path(out).parent
    folder.mkdir(parents=True, exist_ok=True)
    global RAW_DIR, RUN_INDEX
    RAW_DIR, RUN_INDEX = folder, 0
    provenance = {"base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  "base_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
                  "sha256": {p: sha(p) for p in sorted({m[1] for m in MUT} | {str(Path(__file__).resolve().relative_to(Path.cwd())), "tests/modules/test_m14_report_identity.py"})}}
    (folder / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
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
        lines.append("%s | %s | %s | rc=%s | %s | failing: %s" % (mid, f.split("/")[-1], verdict, rc, last, "; ".join(failed) or "-"))
    restored = all(sha(f) == before[f] for f in files)
    lines.append("counts: " + ", ".join("%s=%d" % kv for kv in counts.items()))
    lines.append("mutated files byte-identical to pre-run state (sha256): %s" % restored)
    open(out, "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
    sys.exit(0 if restored else 3)

main(sys.argv[1] if len(sys.argv) > 1 else "audits/m14-callsite-identity/mutation_receipts.txt")
