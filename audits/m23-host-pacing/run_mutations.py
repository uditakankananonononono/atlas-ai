"""Mutation receipts. Run from repo root:
    ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python audits/m23-host-pacing/run_mutations.py [out.txt]
(out.txt defaults to audits/m23-host-pacing/mutation_receipts.txt). Each mutant is an exact single textual
replacement (old -> new) in one file. The named test file is run before (must be green) and after.
A mutant is CAUGHT only when pytest exits 1 with at least one FAILED test ID.
FAILED includes product KeyError/RuntimeError, not just assertions. Mixed FAILED plus SKIP is not rejected.
There is no independent ERROR/collection/internal/fatal screening beyond rc and FAILED-ID presence.
Timeout, nonzero rc other than 1, or rc1 without FAILED IDs is INVALID (not counted as caught).
rc0 is SURVIVED, including rc0 with skips. Restore is verified by SHA-256 of
every mutated file against its pre-run content (exact), independent of git state."""
import hashlib, os, subprocess, sys

B = "backend/app/modules/m23_study_abroad/admitted_cases_bounded.py"
TESTS = ("tests/modules/test_m23_host_pacing.py tests/modules/test_m23_admitted_cases_legacy_delegation.py "
         "tests/modules/test_m23_admitted_cases_crawl_delay.py tests/modules/test_m23_admitted_cases_bounded.py "
         "tests/modules/test_m23_admitted_cases.py")
MUT = [
 ('Q1 host never marked busy', B, "            self._busy.add(host)\n            return True, spacing", "            return True, spacing", TESTS),
 ('Q2 release does not clear busy', B, "self._busy.discard(host)\n            self._cond.notify_all()", "pass\n            self._cond.notify_all()", TESTS),
 ('Q3 release does not notify waiters', B, "self._busy.discard(host)\n            self._cond.notify_all()", "self._busy.discard(host)", TESTS),
 ('Q4 queued caller refused immediately', B, "                self._cond.wait(remaining)", "                return False, 1.0", TESTS),
 ('Q5 spacing ignores the delay', B, "+ self._delay.get(host, 0.0) - self._clock())", "- self._clock())", TESTS),
 ('Q6 finish time not updated after first call', B, "self._last_end[host] = self._clock()", "self._last_end.setdefault(host, self._clock())", TESTS),
 ('Q7 delay not stored on release', B, "self._delay[host] = float(delay)", "pass", TESTS),
 ('Q8 spacing cap boundary (>=)', B, "            if spacing > max_wait:", "            if spacing >= max_wait:", TESTS),
 ('Q9 spacing refusal disabled', B, "            if spacing > max_wait:\n                return False, spacing", "            if False:\n                return False, spacing", TESTS),
 ('Q10 queue retry_after below 1', B, "return False, max(1.0, self._delay.get(host, 0.0))", "return False, 0.0", TESTS),
 ('Q11 ledger spacing not slept', B, "        if wait > 0:\n            sleep(wait)", "        if False:\n            sleep(wait)", TESTS),
 ('Q12 release not run in finally', B, "    finally:\n        ledger.release(host, seen_delay)", "    finally:\n        pass", TESTS),
 ('Q13 one shared host key', B, "host = parsed.hostname.lower()", "host = 'x'", TESTS),
 ('Q14 delay not remembered', B, "seen_delay = delay or 0", "seen_delay = None", TESTS),
 ('Q15 max_pace_wait validation removed', B, "or not 0 <= max_pace_wait <= 600:", "or False:", TESTS),
 ('Q16 default pacer is a fresh ledger per call', B, "ledger = DEFAULT_PACER if pacer is None else pacer", "ledger = HostPacer() if pacer is None else pacer", TESTS),
 ('Q17 busy status dropped from closed set', B, "'crawl_delay_too_long', 'host_pacing_busy',", "'crawl_delay_too_long',", TESTS),
 ('Q18 retry_after omitted', B, "return _safe(row, 'host_pacing_busy', retry_after_seconds=math.ceil(wait))", "return _safe(row, 'host_pacing_busy')", TESTS),
 ('Q19 refusal not honored (proceeds anyway)', B, "    if not admitted:\n        return", "    if False:\n        return", TESTS),
]
ENV =dict(os.environ, ATLAS_DEV_NO_AUTH="1", ATLAS_ENV="development", PYTHONPATH="backend")
TIMEOUT_S = 90

def run(tests):
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *tests.split(), "-q", "-rf"],
                           capture_output=True, text=True, env=ENV, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", []
    lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
    failed = [l.split(" - ")[0][len("FAILED "):] for l in lines if l.startswith("FAILED ")]
    return r.returncode, (lines[-1] if lines else ""), failed

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
        elif rc == 1 and failed:
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

main(sys.argv[1] if len(sys.argv) > 1 else "audits/m23-host-pacing/mutation_receipts.txt")
