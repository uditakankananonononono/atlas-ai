"""exact-replacement mutation battery. Run from repository root with Python >=3.12.
Named released selectors must pass before mutation. CAUGHT requires pytest rc=1,
at least one FAILED line and no collection error, internal error, crash or timeout.
SURVIVED/INVALID/NOT-APPLICABLE are reported separately. Every file is restored
in finally and SHA-256 compared with its original bytes. Receipts default to
this audit directory's mutation_receipts.txt; an alternate path may be supplied.
"""
import hashlib, os, subprocess, sys

TESTS = 'tests/modules/test_m14_report_identity.py tests/modules/test_m14_report_gate.py tests/modules/test_m14_wiring.py'
MUT = [('ID1 truncate project identity', 'backend/app/modules/m14_project_builder/service.py', '"project_id":project.id,', '"project_id":project.id[:64],', 'tests/modules/test_m14_report_identity.py::test_complete_report_identity_distinguishes_long_shared_prefixes'), ('ID2 omit tenant binding', 'backend/app/modules/m14_project_builder/service.py', '"tenant_id":project.tenant_id,', '"tenant_id":"",', 'tests/modules/test_m14_report_identity.py::test_identity_binds_tenant_kind_body_and_subsecond_time'), ('ID3 omit report body binding', 'backend/app/modules/m14_project_builder/service.py', '"body":body}', '"body":""}', 'tests/modules/test_m14_report_identity.py::test_identity_binds_tenant_kind_body_and_subsecond_time'), ('ID4 drop subsecond identity', 'backend/app/modules/m14_project_builder/service.py', 'generated.isoformat(),"body"', 'str(int(generated.timestamp())),"body"', 'tests/modules/test_m14_report_identity.py::test_identity_binds_tenant_kind_body_and_subsecond_time'), ('ID5 restore prefix truncated service id', 'backend/app/modules/m14_project_builder/service.py', '_report_id("status",project,generated,markdown)', 'f"m14-status-{project.id}-{int(generated.timestamp())}"[:64]', 'tests/modules/test_m14_report_identity.py::test_status_report_ids_remain_distinct_for_long_project_ids'), ('ID6 random rather than bound README id', 'backend/app/modules/m14_project_builder/service.py', '_report_id("readme",project,generated,readme)', 'uuid4().hex', 'tests/modules/test_m14_report_identity.py::test_export_readme_and_status_use_content_bound_identity')]
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

main(sys.argv[1] if len(sys.argv) > 1 else "audits/m14-report-identity/mutation_receipts.txt")
