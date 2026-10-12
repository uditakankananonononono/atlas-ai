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

TESTS = 'tests/modules/test_m14_report_gate.py tests/modules/test_m14_reports.py tests/modules/test_m14_exports.py tests/modules/test_m14_wiring.py'
MUT = [('R1 bypass direct status renderer gate', 'backend/app/modules/m14_project_builder/reports.py', 'emit_report(uuid4().hex, body, now=stamp)', 'pass', 'tests/modules/test_m14_report_gate.py::test_real_direct_renderer_refuses_unmarked_supplied_goal[status]'), ('R2 bypass direct README gate', 'backend/app/modules/m14_project_builder/exports.py', 'emit_report(uuid4().hex, body, now=stamp)', 'pass', 'tests/modules/test_m14_report_gate.py::test_real_direct_renderer_refuses_unmarked_supplied_goal[readme]'), ('R3 bypass alternate README gate', 'backend/app/modules/m14_project_builder/service.py', 'self._report_gate().emit_report(_report_id("readme",project,generated,readme),readme,now=generated.strftime("%Y-%m-%dT%H:%M:%SZ"))', 'pass', 'tests/modules/test_m14_report_gate.py::test_alternate_readme_renderer_refused_before_files'), ('R4 omit exported STATUS validation', 'backend/app/modules/m14_project_builder/service.py', 'status_md=self.status_report(project).markdown', 'status_md="unchecked"', 'tests/modules/test_m14_report_gate.py::test_alternate_status_renderer_refused_before_export_files'), ('R5 write export directory before validation', 'backend/app/modules/m14_project_builder/service.py', '    def export_project(self,project:ProjectView,base_dir:Path|None=None)->ExportView:\n        manifests=self.list_artifacts(project)\n', '    def export_project(self,project:ProjectView,base_dir:Path|None=None)->ExportView:\n        (base_dir / project.id).mkdir(parents=True, exist_ok=True)\n        manifests=self.list_artifacts(project)\n', 'tests/modules/test_m14_report_gate.py::test_real_service_export_refuses_unmarked_goal_before_any_files')]
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

main(sys.argv[1] if len(sys.argv) > 1 else "audits/m14-render-binding/mutation_receipts.txt")
