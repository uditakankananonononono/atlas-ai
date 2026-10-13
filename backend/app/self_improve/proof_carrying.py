"""Proof-carrying conclusions with a sandboxed checker (direction 6, wiring of experiments/e8_proof_carrying/pcc.py).

A conclusion is VERIFIED only when an independent checker accepts its evidence. Confidence is a separate number and
never changes the status. A kind with no checker is VERIFICATION_IMPOSSIBLE. Checkers that execute conclusion-author
code (analysis, code_change) run it under bubblewrap: no network (new net namespace), read-only system mounts, a private
writable work dir, a cleared environment, rlimits (CPU, address space, file size, open files, processes), a wall-clock
timeout and a process-group kill. If bubblewrap is unavailable these kinds fail closed (UNVERIFIED, reason
SANDBOX_UNAVAILABLE); they never run unsandboxed.

Named limits (see experiments/d6_pcc_wiring/RESULTS.md): the sandbox does not stop code that runs inside the checked
process from forging that process's own result files; it does not cap total disk written to the private work dir; the
host kernel is trusted. Stdlib only.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
import resource
import shutil
import site
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VERIFIED, UNVERIFIED, IMPOSSIBLE = "VERIFIED", "UNVERIFIED", "VERIFICATION_IMPOSSIBLE"
MAX_TEXT = 1_000_000
MAX_BITS = 4096
MAX_FACTORS = 64


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@dataclass
class Conclusion:
    claim: str
    kind: str
    evidence: dict = field(default_factory=dict)
    confidence: float = 0.5          # self-reported; never read by verify()
    plan_digest: str | None = None   # optional binding to a ChangePlan digest (checked by ProofCarryingGate)


@dataclass(frozen=True)
class Verdict:
    status: str
    reason: str
    confidence: float | None
    sandbox: str | None = None

    def __getitem__(self, k):            # dict-style access, same keys as pcc.verify()
        return getattr(self, k)


@dataclass(frozen=True)
class Limits:
    wall_s: float = 20.0
    cpu_s: int = 10
    mem_mb: int = 1024
    fsize_mb: int = 8
    nofile: int = 128
    max_out: int = 200_000
    nproc_extra: int = 48


class SandboxUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    junit: str | None = None


def bwrap_path() -> str | None:
    return shutil.which("bwrap")


_PROBE: dict = {}


def sandbox_ok(refresh: bool = False) -> bool:
    """True only if bwrap exists AND can actually start an isolated python here (user namespaces may be denied)."""
    if refresh or "ok" not in _PROBE:
        ok = False
        if bwrap_path():
            try:
                r = run_sandboxed([sys.executable, "-I", "-B", "-c", "print(40+2)"], {}, Limits(wall_s=15.0))
                ok = r.returncode == 0 and r.stdout.strip() == "42"
            except Exception:
                ok = False
        _PROBE["ok"] = ok
    return _PROBE["ok"]


def _count_uid_procs() -> int:
    uid = os.getuid()
    n = 0
    try:
        for p in os.listdir("/proc"):
            if p.isdigit():
                try:
                    if os.stat(f"/proc/{p}").st_uid == uid:
                        n += 1
                except OSError:
                    pass
    except OSError:
        pass
    return n


def _py_mounts() -> list[str]:
    cands = {sys.prefix, sys.base_prefix, sys.exec_prefix, os.path.dirname(os.path.realpath(sys.executable))}
    cands.update(site.getsitepackages())
    # resolve the interpreter symlink target prefix (uv/venv layouts)
    cands.add(os.path.dirname(os.path.dirname(os.path.realpath(sys.executable))))
    cur = sys.executable                      # every literal path along the interpreter's symlink chain must exist inside
    for _ in range(8):
        if not os.path.islink(cur):
            break
        cur = os.path.abspath(os.path.join(os.path.dirname(cur), os.readlink(cur)))
        cands.add(os.path.dirname(os.path.dirname(cur)))
    out = []
    for c in sorted(cands):
        if c and os.path.isdir(c) and c not in ("/", "/usr", "/home") and not c.startswith("/usr/"):
            out.append(c)
    return out


def _bwrap_argv(work: str, outdir: str, argv: list[str]) -> list[str]:
    b = bwrap_path()
    if not b:
        raise SandboxUnavailable("bwrap not found")
    a = [b, "--unshare-all", "--die-with-parent", "--new-session", "--ro-bind", "/usr", "/usr"]
    for link, tgt in (("/bin", "usr/bin"), ("/lib", "usr/lib"), ("/lib64", "usr/lib64"), ("/sbin", "usr/sbin")):
        if os.path.isdir("/usr/" + tgt.split("/", 1)[1]):
            a += ["--symlink", tgt, link]
    for m in _py_mounts():
        a += ["--ro-bind", m, m]
    a += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
          "--bind", work, "/work", "--bind", outdir, "/out", "--chdir", "/work", "--clearenv",
          "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/work", "--setenv", "LANG", "C.UTF-8",
          "--setenv", "PYTHONDONTWRITEBYTECODE", "1", "--setenv", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1", "--"]
    return a + argv


def run_sandboxed(argv: list[str], files: dict[str, str], limits: Limits = Limits()) -> RunResult:
    """Run argv (paths as seen inside: cwd /work, scratch /out) with `files` written into /work."""
    with tempfile.TemporaryDirectory(prefix="pcc_") as root:
        work, outdir = os.path.join(root, "work"), os.path.join(root, "out")
        os.mkdir(work); os.mkdir(outdir)
        for name, text in files.items():
            if "/" in name or name.startswith("."):
                raise ValueError("bad file name")
            Path(work, name).write_text(text, encoding="utf-8")
        full = _bwrap_argv(work, outdir, argv)
        cap = _count_uid_procs() + limits.nproc_extra

        def pre():
            resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_s, limits.cpu_s))
            resource.setrlimit(resource.RLIMIT_AS, (limits.mem_mb << 20, limits.mem_mb << 20))
            resource.setrlimit(resource.RLIMIT_FSIZE, (limits.fsize_mb << 20, limits.fsize_mb << 20))
            resource.setrlimit(resource.RLIMIT_NOFILE, (limits.nofile, limits.nofile))
            resource.setrlimit(resource.RLIMIT_NPROC, (cap, cap))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        so, se = Path(root, "stdout"), Path(root, "stderr")
        timed_out = False
        with open(so, "wb") as fo, open(se, "wb") as fe:
            p = subprocess.Popen(full, stdin=subprocess.DEVNULL, stdout=fo, stderr=fe, preexec_fn=pre,
                                 start_new_session=True, env={"PATH": "/usr/bin:/bin"})
            try:
                p.wait(timeout=limits.wall_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(p.pid, 9)
                except ProcessLookupError:
                    pass
                p.wait()
            else:
                try:   # reap anything the child left in its group
                    os.killpg(p.pid, 9)
                except (ProcessLookupError, PermissionError):
                    pass
        def rd(path):
            b = path.read_bytes()
            return b[:limits.max_out].decode("utf-8", "replace"), len(b) > limits.max_out
        out, t1 = rd(so); err, t2 = rd(se)
        extra = {}
        jx = Path(outdir, "junit.xml")
        if jx.exists():
            extra["junit"] = jx.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT]
        return RunResult(p.returncode, out, err, timed_out, t1 or t2, extra.get("junit"))


# ---------------------------------------------------------------- checkers: (ok, reason)
def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def check_factorization(ev, limits=Limits()):
    n, fs = ev.get("n"), ev.get("factors")
    if not _is_int(n) or not isinstance(fs, list) or not fs or len(fs) > MAX_FACTORS:
        return False, "malformed factors"
    if n.bit_length() > MAX_BITS or not all(_is_int(f) and 1 < f < n for f in fs):
        return False, "malformed or trivial factors"
    p = 1
    for f in fs:
        p *= f
    return (p == n), ("product of factors equals n" if p == n else f"product is {p}, not {n}")


def check_sourced_quote(ev, limits=Limits()):
    text, h, q = ev.get("source_text"), ev.get("source_sha256"), ev.get("quote")
    if not (isinstance(text, str) and isinstance(h, str) and isinstance(q, str)) or not text or not q.strip():
        return False, "missing source text, hash or quote"
    if len(text) > MAX_TEXT or len(q) > MAX_TEXT:
        return False, "evidence too large"
    if not hmac.compare_digest(sha(text.encode()), h):
        return False, "source hash mismatch"
    return (q in text), ("quote found in hashed source" if q in text else "quote not in source")


def check_analysis(ev, limits=Limits()):
    """Re-run the script twice in the sandbox; both outputs must be identical and hash to the stated value."""
    script, want = ev.get("script"), ev.get("output_sha256")
    if not (isinstance(script, str) and isinstance(want, str)) or not script or not want:
        return False, "missing script or output hash"
    if len(script) > MAX_TEXT:
        return False, "evidence too large"
    outs = []
    for _ in range(2):
        r = run_sandboxed([sys.executable, "-I", "-B", "/work/a.py"], {"a.py": script}, limits)
        if r.timed_out:
            return False, "script timed out"
        if r.returncode != 0:
            return False, f"script exit {r.returncode}"
        if r.truncated:
            return False, "script output exceeded cap"
        outs.append(r.stdout.encode())
    if outs[0] != outs[1]:
        return False, "script output is not deterministic"
    got = sha(outs[0])
    return (hmac.compare_digest(got, want)), ("re-run output hash matches" if got == want else "re-run output hash differs")


_SUMMARY = re.compile(r"(\d+) (passed|failed|skipped|error|errors|xfailed|xpassed|deselected)")


def _stdout_summary(out: str) -> dict:
    lines = [l for l in out.strip().splitlines() if re.search(r"\bin \d+(\.\d+)?s\b", l)]
    return {k: int(n) for n, k in _SUMMARY.findall(lines[-1])} if lines else {}


def _junit_counts(xml: str):
    root = ET.fromstring(xml)
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if len(suites) != 1:
        return None
    s = suites[0]
    cases = list(s.iter("testcase"))
    bad = [c for c in cases if any(ch.tag in ("failure", "error", "skipped") for ch in c)]
    return {"tests": int(s.get("tests", -1)), "failures": int(s.get("failures", -1)), "errors": int(s.get("errors", -1)),
            "skipped": int(s.get("skipped", -1)), "cases": len(cases), "bad": len(bad)}


def check_code_change(ev, limits=Limits()):
    """Tests re-run in the sandbox on the given source. Accepts only if pytest exits 0, the junit XML (written outside
    the work dir by pytest) says exactly N tests with no failure/error/skip, and stdout's summary agrees."""
    src, tests, want = ev.get("source"), ev.get("tests"), ev.get("expected_passed")
    if not (isinstance(src, str) and isinstance(tests, str)) or not src or not tests or not _is_int(want) or want <= 0:
        return False, "missing source, tests or expected count"
    if len(src) > MAX_TEXT or len(tests) > MAX_TEXT:
        return False, "evidence too large"
    r = run_sandboxed([sys.executable, "-I", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
                       "--junitxml=/out/junit.xml", "test_mod.py"], {"mod.py": src, "test_mod.py": tests},
                      Limits(**{**limits.__dict__, "wall_s": max(limits.wall_s, 40.0)}))
    if r.timed_out:
        return False, "tests timed out"
    if r.returncode != 0:
        return False, f"tests did not reproduce (exit {r.returncode})"
    if not r.junit:
        return False, "no junit report"
    try:
        jc = _junit_counts(r.junit)
    except (ET.ParseError, ValueError):
        return False, "unparseable junit report"
    if jc is None or jc != {"tests": want, "failures": 0, "errors": 0, "skipped": 0, "cases": want, "bad": 0}:
        return False, f"junit counts do not match expected {want}: {jc}"
    if _stdout_summary(r.stdout) != {"passed": want}:
        return False, "stdout summary disagrees with junit"
    return True, "tests re-run in sandbox and pass"


CHECKERS = {"factorization": check_factorization, "analysis": check_analysis,
            "code_change": check_code_change, "sourced_quote": check_sourced_quote}
_SANDBOXED = {"analysis", "code_change"}


def verify(c: Any, limits: Limits = Limits()) -> Verdict:
    if not isinstance(c, Conclusion) or not isinstance(c.kind, str) or not isinstance(c.evidence, dict):
        return Verdict(UNVERIFIED, "malformed conclusion", None)
    conf = c.confidence if isinstance(c.confidence, (int, float)) and not isinstance(c.confidence, bool) \
        and math.isfinite(c.confidence) else None
    chk = CHECKERS.get(c.kind)
    if chk is None:
        return Verdict(IMPOSSIBLE, f"no checker for kind {c.kind!r}", conf)
    if c.kind in _SANDBOXED and not sandbox_ok():
        return Verdict(UNVERIFIED, "SANDBOX_UNAVAILABLE: refusing to run evidence code unsandboxed", conf)
    try:
        ok, why = chk(c.evidence, limits)
    except SandboxUnavailable:
        return Verdict(UNVERIFIED, "SANDBOX_UNAVAILABLE: refusing to run evidence code unsandboxed", conf)
    except Exception as e:      # a crashing checker is not a pass
        return Verdict(UNVERIFIED, f"checker error: {type(e).__name__}", conf)
    return Verdict(VERIFIED if ok is True else UNVERIFIED, why, conf, "bwrap" if c.kind in _SANDBOXED else None)
