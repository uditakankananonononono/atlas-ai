"""Instinct-doc groups 1-16: program evidence verifier.

Unlike the declaration registers (p77/p254/p255/p258), nothing here trusts a
caller-supplied claim. Each project is checked by resolving its evidence:
  * repo      - the declared path must itself be the top level of a git checkout with commits
  * datasets  - each dataset file must exist; sha256 and byte size recomputed
  * tools     - the declared argv is executed here (no shell, stripped env, timeout, resource
                limits); exit 0 and the output hash are taken from this run, not from the caller
  * papers    - a PDF must exist; page count and Times font read via pdfinfo/pdffonts
  * judge     - the transcript is hash-matched and PARSED; the score trend comes from its lines
  * benchmark - the argv is re-run; its stdout hash must match
Limit: the sandbox is rlimits plus a stripped environment, not network or filesystem isolation.
Thresholds are parameters so the 40-each / 200-each / 200-overall rulings are all
supported without rework (see STRICT, LENIENT). Pure stdlib; subprocess only for
git/pdfinfo/pdffonts and explicit benchmark commands.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field

VERDICTS = ("VERIFIED", "PARTIAL", "UNSUPPORTED")


@dataclass(frozen=True)
class Thresholds:
    datasets_per_project: int = 120
    tools_per_project: int = 40
    tools_program: int = 200
    tools_distinct_program: bool = True
    paper_pages: int = 50
    paper_font: str = "Times"
    judge_rounds: int = 1
    benchmarks_per_project: int = 1
    paper_sections: tuple = ("abstract", "introduction", "methods", "results", "discussion", "references")


LENIENT = Thresholds()  # 40+/project, 200+ across program
STRICT = Thresholds(tools_per_project=200)  # 200+ per project


def _err(code):
    return ValueError("G1-16:" + code)


def sha256_file(path, _chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(_chunk)
            if not b:
                return h.hexdigest()
            h.update(b)


def _resolve(base, rel):
    if not isinstance(rel, str) or not rel or "\x00" in rel:
        raise _err("bad_path")
    p = os.path.realpath(os.path.join(base, rel))
    root = os.path.realpath(base)
    if p != root and not p.startswith(root + os.sep):
        raise _err("path_escape:" + rel)
    return p


def default_remote_probe(url):
    """Return the remote HEAD sha via git ls-remote (network). Injectable for tests."""
    r = subprocess.run(["git", "ls-remote", url, "HEAD"], capture_output=True, text=True, timeout=60)
    return r.stdout.split()[0] if r.returncode == 0 and r.stdout.split() else ""


def check_repo(base, spec, probe=None):
    """spec: {path, remote?}. Passes only if path is the top level of a git checkout with
    commits. When spec has "remote", probe(remote) must return the local HEAD sha."""
    try:
        p = _resolve(base, spec["path"])
        top = subprocess.run(["git", "-C", p, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=30)
        if top.returncode != 0 or os.path.realpath(top.stdout.strip()) != p:
            return {"ok": False, "commits": 0, "reason": "not_toplevel"}
        n = int(subprocess.run(["git", "-C", p, "rev-list", "--count", "HEAD"],
                               capture_output=True, text=True, timeout=30).stdout.strip() or 0)
        head = subprocess.run(["git", "-C", p, "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=30).stdout.strip()
        if n > 0 and spec.get("remote"):
            got = (probe or default_remote_probe)(spec["remote"])
            if got != head:
                return {"ok": False, "commits": n, "reason": "remote_head_mismatch"}
    except (KeyError, ValueError, OSError, TypeError, AttributeError, subprocess.SubprocessError):
        return {"ok": False, "commits": 0, "reason": "unreadable"}
    return {"ok": n > 0, "commits": n}


def check_datasets(base, specs, minimum):
    good, bad = set(), []
    for s in specs or []:
        if not isinstance(s, dict):
            bad.append(None)
            continue
        try:
            p = _resolve(base, s["path"])
            if os.path.getsize(p) > 0 and sha256_file(p) == s["sha256"] and s.get("origin"):
                good.add(s["sha256"])  # identical content counts once
            else:
                bad.append(s.get("path"))
        except (KeyError, ValueError, OSError, TypeError):
            bad.append(s.get("path"))
    return {"counted": len(good), "rejected": bad, "ok": len(good) >= minimum}


def _limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (256 << 20, 256 << 20))
    os.setsid()


BENCH_ALLOWED = (("python3", "-m", "unittest"), ("python3", "-m", "pytest"), ("pytest",))


def _allowed(argv, allowlist):
    """argv must start with one of the allowlisted prefixes; no shell is ever used."""
    return any(tuple(argv[:len(a)]) == tuple(a) for a in allowlist)


def _sandbox_run(base, argv, allowlist, timeout=60):
    """Trusted-local runner: allowlisted argv prefixes only, cwd fixed to base, stripped
    env, rlimits, timeout. It is not network or filesystem isolation."""
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise _err("bad_argv")
    if not _allowed(argv, allowlist):
        raise _err("command_not_allowlisted")
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": base, "LANG": "C"}
    return subprocess.run(argv, cwd=base, env=env, capture_output=True, timeout=timeout,
                          preexec_fn=_limits, stdin=subprocess.DEVNULL)


def check_tools(base, specs, runner=None, allowlist=()):
    """Spec: {name, argv, output_path?, output_sha256}. The argv is executed here.

    Counts a tool only when this run exits 0 and the hash of output_path (read after the
    run) or of stdout (when no output_path) equals output_sha256. Caller-supplied exit
    codes are ignored. With no allowlist nothing is executed, so nothing counts.
    Returns the set of lower-cased names."""
    run = runner or (lambda argv: _sandbox_run(base, argv, allowlist))
    names = set()
    for s in specs or []:
        try:
            name = s["name"].strip().lower()
            if not name:
                continue
            if s.get("output_path"):
                p = _resolve(base, s["output_path"])
                if os.path.isfile(p):
                    os.remove(p)  # the run itself must produce the output file
            r = run(s["argv"])
            if r.returncode != 0:
                continue
            if s.get("output_path"):
                got = sha256_file(p) if os.path.getsize(p) > 0 else ""
            else:
                got = hashlib.sha256(r.stdout).hexdigest() if r.stdout else ""
            if got and got == s["output_sha256"]:
                names.add(name)
        except (KeyError, ValueError, OSError, TypeError, AttributeError, subprocess.SubprocessError):
            continue
    return names


SCORE_PREFIX = "JUDGE_SCORE"  # transcript line: JUDGE_SCORE round=<int> value=<float>


def parse_judge_scores(text):
    """Return [(round, value)] from transcript lines; malformed lines are ignored."""
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == SCORE_PREFIX and parts[1].startswith("round=") \
                and parts[2].startswith("value="):
            try:
                out.append((int(parts[1][6:]), float(parts[2][6:])))
            except ValueError:
                continue
    return sorted(out)


def check_judge(base, rounds, t):
    """Each item: {transcript_path, transcript_sha256}. The score trend is parsed from the
    transcript: it needs at least 2 distinct rounds and the last value above the first.
    Caller-supplied before/after numbers are not read."""
    done_hashes = set()
    for r in rounds or []:
        try:
            if not isinstance(r, dict):
                continue
            p = _resolve(base, r["transcript_path"])
            if os.path.getsize(p) == 0 or sha256_file(p) != r["transcript_sha256"]:
                continue
            if r["transcript_sha256"] in done_hashes:
                continue  # identical transcript counts once
            with open(p, encoding="utf-8", errors="replace") as fh:
                sc = parse_judge_scores(fh.read())
            if len({k for k, _ in sc}) >= 2 and sc[-1][1] > sc[0][1]:
                done_hashes.add(r["transcript_sha256"])
        except (KeyError, ValueError, OSError, TypeError):
            continue
    return {"rounds": len(done_hashes), "ok": len(done_hashes) >= t.judge_rounds}


def check_benchmarks(base, specs, t, runner=None):
    """Re-run argv in the sandbox; stdout sha256 must equal expected. Never trusts a score."""
    run = runner or (lambda argv: _sandbox_run(base, argv, BENCH_ALLOWED, 300))
    seen = set()
    for s in specs or []:
        try:
            key = (tuple(s["argv"]), s["stdout_sha256"])
            if key in seen:
                continue  # same command and expected output counts once
            r = run(s["argv"])
            if r.returncode == 0 and hashlib.sha256(r.stdout).hexdigest() == s["stdout_sha256"]:
                seen.add(key)
        except (KeyError, ValueError, OSError, TypeError, subprocess.SubprocessError):
            continue
    return {"reproduced": len(seen), "ok": len(seen) >= t.benchmarks_per_project}


def _pdf_fonts(text):
    """Font names from pdffonts output (skips the 2 header lines)."""
    return [l.split()[0] for l in text.splitlines()[2:] if l.strip()]


def check_paper(base, spec, t):
    """Page count >= t.paper_pages; every embedded font is Times family (subset prefix
    stripped; Symbol/Math faces allowed only as extras, never as the only font); text
    contains each required section heading. The source doc (line 9) asks for a neat paper
    in Times New Roman with good formatting; it names no border colour, so none is checked."""
    try:
        p = _resolve(base, spec["path"])
        if not shutil.which("pdfinfo") or not shutil.which("pdffonts") or not shutil.which("pdftotext"):
            return {"ok": False, "reason": "pdf_tools_missing"}
        info = subprocess.run(["pdfinfo", p], capture_output=True, text=True, timeout=30).stdout
        pages = next((int(l.split()[-1]) for l in info.splitlines() if l.startswith("Pages:")), 0)
        names = [n.split("+")[-1] for n in _pdf_fonts(subprocess.run(["pdffonts", p], capture_output=True, text=True, timeout=30).stdout)]
        extra = ("symbol", "math", "cmsy", "cmmi")
        body = [n for n in names if not n.lower().startswith(extra)]
        fonts_ok = bool(body) and all(t.paper_font.lower() in n.lower() for n in body)
        text = subprocess.run(["pdftotext", p, "-"], capture_output=True, text=True, timeout=60).stdout.lower()
        missing = [x for x in t.paper_sections if x not in text]
        return {"ok": pages >= t.paper_pages and fonts_ok and not missing, "pages": pages,
                "times_only": fonts_ok, "missing_sections": missing}
    except (KeyError, ValueError, OSError, TypeError, subprocess.SubprocessError):
        return {"ok": False, "reason": "unreadable"}


def verify_project(base, project, t=LENIENT, runner=None, probe=None, tool_allowlist=()):
    checks = {
        "repo": check_repo(base, project.get("repo", {}), probe),
        "datasets": check_datasets(base, project.get("datasets"), t.datasets_per_project),
        "paper": check_paper(base, project.get("paper") or {}, t),
        "judge": check_judge(base, project.get("judge_rounds"), t),
        "benchmarks": check_benchmarks(base, project.get("benchmarks"), t, runner),
    }
    tools = check_tools(base, project.get("tools"), runner, tool_allowlist)
    checks["tools"] = {"counted": len(tools), "ok": len(tools) >= t.tools_per_project}
    passed = sum(1 for c in checks.values() if c["ok"])
    verdict = "VERIFIED" if passed == len(checks) else ("PARTIAL" if passed else "UNSUPPORTED")
    return {"project": project.get("id", ""), "verdict": verdict, "checks": checks,
            "_tools": sorted(tools)}


def verify_program(base, projects, t=LENIENT, runner=None, probe=None, tool_allowlist=()):
    rows = [verify_project(base, p, t, runner, probe, tool_allowlist) for p in projects]
    allt, total = set(), 0
    for r in rows:
        tools = r.pop("_tools")
        allt.update(tools)
        total += len(tools)
    n = len(allt) if t.tools_distinct_program else total
    prog_ok = n >= t.tools_program
    all_ok = prog_ok and bool(rows) and all(r["verdict"] == "VERIFIED" for r in rows)
    return {"thresholds": t.__dict__, "projects": rows,
            "program_distinct_tools_verified": len(allt), "program_tools_counted": n,
            "program_tools_ok": prog_ok,
            "verdict": "VERIFIED" if all_ok else ("PARTIAL" if rows else "UNSUPPORTED"),
            "not_covered": ["discovery or breakthrough", "5-year-equivalence",
                            "world-best claims", "model training"]}


def render(report):
    lines = ["program %s tools=%d" % (report["verdict"], report["program_distinct_tools_verified"])]
    for r in report["projects"]:
        fails = [k for k, v in r["checks"].items() if not v["ok"]]
        lines.append("%s %s%s" % (r["project"], r["verdict"], " FAIL:" + ",".join(fails) if fails else ""))
    lines.append("NOT COVERED: " + "; ".join(report["not_covered"]))
    return "\n".join(lines)


if __name__ == "__main__":  # python -m ... <base> <projects.json> [strict]
    import sys
    base, pj = sys.argv[1], sys.argv[2]
    th = STRICT if len(sys.argv) > 3 and sys.argv[3] == "strict" else LENIENT
    print(render(verify_program(base, json.load(open(pj)), th)))
