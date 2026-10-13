"""E8: proof-carrying conclusions (direction 6). A conclusion is reported VERIFIED only if an independent checker
accepts its evidence; confidence is a separate number that never changes the status. Kinds with no checker report
VERIFICATION_IMPOSSIBLE with a reason. Checkers re-run or re-read evidence; they do not trust the stated result."""
import hashlib, subprocess, sys, tempfile, os
from dataclasses import dataclass, field
from typing import Any

VERIFIED, UNVERIFIED, IMPOSSIBLE = "VERIFIED", "UNVERIFIED", "VERIFICATION_IMPOSSIBLE"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@dataclass
class Conclusion:
    claim: str
    kind: str                      # factorization | analysis | code_change | sourced_quote | opinion
    evidence: dict = field(default_factory=dict)
    confidence: float = 0.5        # self-reported; never used by verify()


def check_factorization(ev):
    """claim: n is composite with factors ev['factors']; checker multiplies and checks each factor > 1 and < n."""
    n, fs = ev.get("n"), ev.get("factors")
    if not isinstance(n, int) or not fs or not all(isinstance(f, int) and 1 < f < n for f in fs):
        return False, "malformed or trivial factors"
    p = 1
    for f in fs:
        p *= f
    return p == n, "product of factors equals n" if p == n else f"product is {p}, not {n}"


def check_analysis(ev):
    """Re-run the script in a fresh process; the output hash must equal the stated one."""
    script, want = ev.get("script"), ev.get("output_sha256")
    if not script or not want:
        return False, "missing script or output hash"
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.py"); open(p, "w").write(script)
        r = subprocess.run([sys.executable, p], capture_output=True, text=True, timeout=30, cwd=d)
    if r.returncode != 0:
        return False, f"script exit {r.returncode}"
    got = sha(r.stdout.encode())
    return got == want, "re-run output hash matches" if got == want else "re-run output hash differs"


def _summary(out: str) -> dict:
    """Exact parse of pytest's last summary line, e.g. '3 passed, 1 skipped in 0.02s' -> {'passed': 3, 'skipped': 1}."""
    import re
    lines = [l for l in out.strip().splitlines() if re.search(r"\bin \d+(\.\d+)?s\b", l)]
    if not lines:
        return {}
    return {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|skipped|error|errors|xfailed|xpassed|warnings?|deselected)", lines[-1])
            if k not in ("warning", "warnings")}


def check_code_change(ev):
    """Tests must exit 0 when re-run on the patched source and the reported test count must be positive and match."""
    src, tests, want = ev.get("source"), ev.get("tests"), ev.get("expected_passed")
    if not src or not tests or not want:
        return False, "missing source, tests or expected count"
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "mod.py"), "w").write(src); open(os.path.join(d, "test_mod.py"), "w").write(tests)
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_mod.py"], capture_output=True, text=True, timeout=60, cwd=d,
                           env={"PYTHONPATH": d, "PATH": os.environ.get("PATH", "")})
    summ = _summary(r.stdout)
    ok = r.returncode == 0 and summ == {"passed": want}   # exact: no skipped, failed, errors or extra tests
    return ok, "tests re-run and pass" if ok else f"tests did not reproduce (exit {r.returncode}, summary {summ})"


def check_sourced_quote(ev):
    """The quote must occur verbatim in the stored source text, whose hash must match the stated one."""
    text, h, q = ev.get("source_text"), ev.get("source_sha256"), ev.get("quote")
    if not (text and h and q):
        return False, "missing source text, hash or quote"
    if sha(text.encode()) != h:
        return False, "source hash mismatch"
    return q in text, "quote found in hashed source" if q in text else "quote not in source"


CHECKERS = {"factorization": check_factorization, "analysis": check_analysis, "code_change": check_code_change, "sourced_quote": check_sourced_quote}


def verify(c: Conclusion) -> dict:
    chk = CHECKERS.get(c.kind)
    if chk is None:
        return dict(status=IMPOSSIBLE, reason=f"no checker for kind {c.kind!r}", confidence=c.confidence)
    try:
        ok, why = chk(c.evidence)
    except Exception as e:  # a crashing checker is not a pass
        ok, why = False, f"checker error: {type(e).__name__}"
    return dict(status=VERIFIED if ok else UNVERIFIED, reason=why, confidence=c.confidence)
