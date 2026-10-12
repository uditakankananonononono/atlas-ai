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

TESTS = 'tests/modules/test_m06_publish_guardrail.py tests/modules/test_m06_scheduler.py'
MUT = [('P1 stale entry adapter platform', 'backend/app/modules/m06_social_media_manager/scheduler.py', 'self._adapters.for_platform(Platform(request.platform))', 'self._adapters.for_platform(entry.platform)', 'tests/modules/test_m06_publish_guardrail.py::test_factory_and_request_share_canonical_platform_not_stale_entry'), ('P2 fixed twitter adapter', 'backend/app/modules/m06_social_media_manager/scheduler.py', 'self._adapters.for_platform(Platform(request.platform))', 'self._adapters.for_platform(Platform.TWITTER)', 'tests/modules/test_m06_publish_guardrail.py::test_factory_and_request_share_canonical_platform_not_stale_entry'), ('P3 detached request platform', 'backend/app/modules/m06_social_media_manager/scheduler.py', 'platform=a["platform"], text=a["text"]', 'platform=entry.platform.value, text=a["text"]', 'tests/modules/test_m06_publish_guardrail.py::test_factory_and_request_share_canonical_platform_not_stale_entry'), ('P4 factory before admission', 'backend/app/modules/m06_social_media_manager/scheduler.py', '                moment = _aware(self._clock())', '                self._adapters.for_platform(entry.platform)\n                moment = _aware(self._clock())', 'tests/modules/test_m06_publish_guardrail.py::test_real_gate_refuses_platform_drift_before_factory_or_publish')]
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
        lines.append("%s | %s | %s | rc=%s | %s | failing: %s" % (mid, f.split("/")[-1], verdict, rc, last, "; ".join(failed) or "-"))
    restored = all(sha(f) == before[f] for f in files)
    lines.append("counts: " + ", ".join("%s=%d" % kv for kv in counts.items()))
    lines.append("mutated files byte-identical to pre-run state (sha256): %s" % restored)
    open(out, "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
    sys.exit(0 if restored else 3)

main(sys.argv[1] if len(sys.argv) > 1 else "audits/social-platform-binding/mutation_receipts.txt")
