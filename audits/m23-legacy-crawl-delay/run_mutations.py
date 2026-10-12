"""Mutation receipts. Run from repo root:
    ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python audits/m23-legacy-crawl-delay/run_mutations.py [out.txt]
(out.txt defaults to audits/m23-legacy-crawl-delay/mutation_receipts.txt). Each mutant is an exact single textual
replacement (old -> new) in one file. The named test file is run before (must be green) and after.
A mutant is CAUGHT only when pytest exits 1 with at least one FAILED test ID.
FAILED includes product KeyError/RuntimeError, not just assertions. Mixed FAILED plus SKIP is not rejected.
There is no independent ERROR/collection/internal/fatal screening beyond rc and FAILED-ID presence.
Timeout, nonzero rc other than 1, or rc1 without FAILED IDs is INVALID (not counted as caught).
rc0 is SURVIVED, including rc0 with skips. Restore is verified by SHA-256 of
every mutated file against its pre-run content (exact), independent of git state."""
import hashlib, os, subprocess, sys

B = "backend/app/modules/m23_study_abroad/admitted_cases.py"
TESTS = "tests/modules/test_m23_admitted_cases_legacy_delegation.py tests/modules/test_m23_admitted_cases_crawl_delay.py tests/modules/test_m23_admitted_cases_bounded.py tests/modules/test_m23_admitted_cases.py"
RET = "return fetch_case_metadata_bounded(case_id, transport, **kwargs)"
MUT = [
 ("L1 transport dropped (replaced by a 500 mock)", B, RET, "return fetch_case_metadata_bounded(case_id, httpx.MockTransport(lambda r: httpx.Response(500)), **kwargs)", TESTS),
 ("L2 kwargs dropped", B, RET, "return fetch_case_metadata_bounded(case_id, transport)", TESTS),
 ("L3 wrong case id", B, RET, "return fetch_case_metadata_bounded('hamilton', transport, **kwargs)", TESTS),
 ("L4 cap forced to 120", B, RET, "return fetch_case_metadata_bounded(case_id, transport, **{**kwargs, 'max_crawl_delay': 120})", TESTS),
 ("L5 injected sleep overridden by no-op", B, RET, "return fetch_case_metadata_bounded(case_id, transport, **{**kwargs, 'sleep': lambda s: None})", TESTS),
 ("L6 KeyError swallowed", B, RET, "try:\n        return fetch_case_metadata_bounded(case_id, transport, **kwargs)\n    except KeyError:\n        return {}", TESTS),
 ("L7 delegate result discarded to a fixed row", B, RET, "fetch_case_metadata_bounded(case_id, transport, **kwargs)\n    return {'live_status': 'page_reachable'}", TESTS),
 ("L8 own legacy path restored (ignores Crawl-delay)", B, RET, "import httpx as _h\n    with httpx.Client(transport=transport) as client:\n        RobotFileParser()\n        return {'live_status': 'page_reachable'}", TESTS),
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

main(sys.argv[1] if len(sys.argv) > 1 else "audits/m23-legacy-crawl-delay/mutation_receipts.txt")
