"""Instinct-doc groups 1-16: bounded program evidence verifier.

Verifies repo existence, dataset hash integrity, and repeatable command output
under a caller-supplied allowlist; does NOT verify provenance, scientific validity,
or judge authenticity. PDF checks are format gates, not visual quality review.
Leader values, dataset origin labels and judge identities remain caller claims.

The default trusted-local runner uses stripped environment, rlimits and timeout,
not network/filesystem isolation. Only run code the operator already trusts.
runner= replaces the default runner and bypasses its allowlist/resource limits;
project and program reports explicitly mark this as injected execution.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
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
    min_section_words: int = 150
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
    """Require a committed top-level checkout with a clean tracked tree.

    Optional spec.remote is only an expected origin, never a probe destination.
    Remote HEAD is always obtained from the checkout's configured origin.
    Untracked files do not affect the tracked-clean verdict.
    """
    try:
        p = _resolve(base, spec["path"])
        def git(*args):
            result = subprocess.run(["git", "-C", p, *args], capture_output=True,
                                    text=True, timeout=30)
            if result.returncode != 0:
                raise _err("git_command_failed")
            return result.stdout.strip()
        top = subprocess.run(["git", "-C", p, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=30)
        if top.returncode != 0 or os.path.realpath(top.stdout.strip()) != p:
            return {"ok": False, "commits": 0, "reason": "not_toplevel"}
        n = int(git("rev-list", "--count", "HEAD") or 0)
        head = git("rev-parse", "HEAD")
        if git("status", "--porcelain", "--untracked-files=no"):
            return {"ok": False, "commits": n, "reason": "tracked_tree_dirty"}
        origin_result = subprocess.run(["git", "-C", p, "remote", "get-url", "origin"],
                                      capture_output=True, text=True, timeout=30)
        origin = origin_result.stdout.strip() if origin_result.returncode == 0 else ""
        if spec.get("remote") and spec["remote"] != origin:
            return {"ok": False, "commits": n, "reason": "origin_mismatch"}
        if origin:
            got = (probe or default_remote_probe)(origin)
            if got != head:
                return {"ok": False, "commits": n, "reason": "remote_head_mismatch",
                        "configured_origin": origin}
    except (KeyError, ValueError, OSError, TypeError, AttributeError, subprocess.SubprocessError):
        return {"ok": False, "commits": 0, "reason": "unreadable"}
    return {"ok": n > 0, "commits": n, "configured_origin": origin,
            "tracked_clean": True, "remote_verified": bool(origin),
            "remote_probe_injected": probe is not None}


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


SANDBOX_ENV = {}  # operator-extendable extra env for allowlisted runs (e.g. PYTHONUSERBASE)


def _allowed(argv, allowlist):
    """argv must start with one of the allowlisted prefixes; no shell is ever used."""
    return any(tuple(argv[:len(a)]) == tuple(a) for a in allowlist)


def _sandbox_run(base, argv, allowlist, timeout=60, extra_env=None):
    """Trusted-local runner: allowlisted argv prefixes only, cwd fixed to base, stripped
    env, rlimits, timeout. NOT a security sandbox: no network or filesystem isolation."""
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise _err("bad_argv")
    if not _allowed(argv, allowlist):
        raise _err("command_not_allowlisted")
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": base, "LANG": "C"}
    env.update(SANDBOX_ENV)
    env.update(extra_env or {})
    return subprocess.run(argv, cwd=base, env=env, capture_output=True, timeout=timeout,
                          preexec_fn=_limits, stdin=subprocess.DEVNULL)


def _identity(argv, out_hash):
    exe = shutil.which(argv[0]) or argv[0]
    return hashlib.sha256(json.dumps([exe, list(argv), out_hash]).encode()).hexdigest()


def _run_checked(base, argv, allowlist, runner, timeout=300, extra_env=None):
    """Allowlist first, then execute. runner= bypasses the allowlist (see module doc)."""
    if runner is None:
        if not isinstance(argv, list) or not argv or not _allowed(argv, allowlist):
            return None
        return _sandbox_run(base, argv, allowlist, timeout, extra_env)
    return runner(argv)


def check_tools(base, specs, runner=None, allowlist=()):
    """Spec: {name, argv, output_name?, output_sha256}. The argv is executed here.

    The allowlist is checked BEFORE anything else happens. The run gets a fresh temp
    directory in env var SC_OUTPUT_DIR; output_name (a bare file name) is read from it
    afterwards, otherwise stdout is hashed. Nothing the caller names is ever deleted.
    A tool counts once per identity = (executable, argv, output hash); extra names for the
    same command add nothing. With no allowlist nothing runs. Returns identity digests."""
    ids = set()
    for s in specs or []:
        try:
            argv = s["argv"]
            if not isinstance(s["name"], str) or not s["name"].strip():
                continue
            name = s.get("output_name")
            if name is not None and (not isinstance(name, str) or os.path.basename(name) != name or name in ("", ".", "..")):
                continue
            with tempfile.TemporaryDirectory() as out_dir:
                r = _run_checked(base, argv, allowlist, runner, 60, {"SC_OUTPUT_DIR": out_dir})
                if r is None or r.returncode != 0:
                    continue
                if name:
                    fp = os.path.join(out_dir, name)
                    got = sha256_file(fp) if os.path.isfile(fp) and os.path.getsize(fp) > 0 else ""
                else:
                    got = hashlib.sha256(r.stdout).hexdigest() if r.stdout else ""
            if got and got == s["output_sha256"]:
                ids.add(_identity(argv, got))
        except (KeyError, ValueError, OSError, TypeError, AttributeError, subprocess.SubprocessError):
            continue
    return ids


SCORE_PREFIX = "JUDGE_SCORE"  # stream line: JUDGE_SCORE round=<int> value=<float>


def parse_judge_scores(text):
    """Return sorted [(round, value)] or None when the stream is unusable.

    Malformed lines are ignored. A non-finite value, a negative round, or two different
    values for one round make the whole stream unusable (None)."""
    seen = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == SCORE_PREFIX and parts[1].startswith("round=") \
                and parts[2].startswith("value="):
            try:
                rnd, val = int(parts[1][6:]), float(parts[2][6:])
            except ValueError:
                continue
            if rnd < 0 or not math.isfinite(val):
                return None
            if rnd in seen and seen[rnd] != val:
                return None
            seen[rnd] = val
    return sorted(seen.items())


def check_judge(base, rounds, t, runner=None, allowlist=BENCH_ALLOWED):
    """Each item: {argv}. The judge command is run here and its captured stdout is the score
    stream: >= 2 distinct rounds, finite values, no conflicting repeats, last above first.
    A transcript file written by the caller is not accepted: items without argv are counted
    under "unattributed" and never pass. Scores inside a stream a command prints are still
    only as honest as that command; this proves who ran it, not that a model judged it."""
    seen, unattributed = set(), 0
    for r in rounds or []:
        try:
            if not isinstance(r, dict) or "argv" not in r:
                unattributed += 1
                continue
            res = _run_checked(base, r["argv"], allowlist, runner)
            if res is None or res.returncode != 0:
                continue
            sc = parse_judge_scores(res.stdout.decode("utf-8", "replace"))
            if sc and len(sc) >= 2 and sc[-1][1] > sc[0][1]:
                seen.add((tuple(r["argv"]), hashlib.sha256(res.stdout).hexdigest()))
        except (KeyError, ValueError, OSError, TypeError, AttributeError, subprocess.SubprocessError):
            continue
    return {"rounds": len(seen), "unattributed": unattributed, "ok": len(seen) >= t.judge_rounds}


def check_benchmarks(base, specs, t, runner=None, allowlist=BENCH_ALLOWED):
    """Reproduction only: re-run argv; non-empty stdout must hash to stdout_sha256. This shows
    a command is repeatable. It says nothing about a leader; see check_leader_benchmarks."""
    seen = set()
    for s in specs or []:
        try:
            key = (tuple(s["argv"]), s["stdout_sha256"])
            if key in seen:
                continue
            r = _run_checked(base, s["argv"], allowlist, runner)
            if r is not None and r.returncode == 0 and r.stdout and hashlib.sha256(r.stdout).hexdigest() == s["stdout_sha256"]:
                seen.add(key)
        except (KeyError, ValueError, OSError, TypeError, subprocess.SubprocessError):
            continue
    return {"reproduced": len(seen), "ok": len(seen) >= t.benchmarks_per_project}


BENCH_PREFIX = "BENCH"  # stream line: BENCH leader=<id> metric=<name> subject=<float> leader_value=<float>


def parse_bench(text):
    """Return a list of dicts from BENCH lines with finite numeric values; others ignored."""
    out = []
    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0] != BENCH_PREFIX:
            continue
        kv = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
        try:
            row = {"leader": kv["leader"], "metric": kv["metric"],
                   "subject": float(kv["subject"]), "leader_value": float(kv["leader_value"])}
        except (KeyError, ValueError):
            continue
        if row["leader"] and row["metric"] and math.isfinite(row["subject"]) and math.isfinite(row["leader_value"]):
            out.append(row)
    return out


def check_leader_benchmarks(base, specs, runner=None, allowlist=BENCH_ALLOWED):
    """Spec: {argv, leader, metric, higher_is_better(bool)}. The benchmark is executed here;
    its stdout must hold exactly one BENCH line for that leader and metric, and the subject
    must beat (or match) the leader value in the declared direction. The leader identity,
    metric and criterion are all declared up front and compared with what the run printed.
    This proves what the command printed, not that the leader value is the true state of the
    art. Returns {"compared": n, "beat": n, "ok": beat >= 1}."""
    compared = beat = 0
    for s in specs or []:
        try:
            if not isinstance(s.get("higher_is_better"), bool) or not s.get("leader") or not s.get("metric"):
                continue
            r = _run_checked(base, s["argv"], allowlist, runner)
            if r is None or r.returncode != 0:
                continue
            rows = [x for x in parse_bench(r.stdout.decode("utf-8", "replace"))
                    if x["leader"] == s["leader"] and x["metric"] == s["metric"]]
            if len(rows) != 1:
                continue
            compared += 1
            x = rows[0]
            if (x["subject"] >= x["leader_value"]) if s["higher_is_better"] else (x["subject"] <= x["leader_value"]):
                beat += 1
        except (KeyError, ValueError, OSError, TypeError, AttributeError, subprocess.SubprocessError):
            continue
    return {"compared": compared, "beat": beat, "ok": beat >= 1}


def check_module_run(base, spec, runner=None, allowlist=BENCH_ALLOWED):
    """Spec: {argv, stdout_regex, datasets:[{path, sha256, origin}], referenced_in:[test file]}.
    A module data run counts only when (a) each dataset file exists with the given hash and a
    stated origin, (b) at least one named source file mentions each dataset's file name, and
    (c) the argv, executed here through the allowlist, exits 0 and its captured stdout matches
    stdout_regex. (b) is a static check: it shows the code names the file, not that the run
    read it."""
    try:
        ds = spec["datasets"]
        if not ds or not pe_ok_datasets(base, ds):
            return {"ok": False, "reason": "datasets"}
        srcs = []
        for rel in spec.get("referenced_in") or []:
            with open(_resolve(base, rel), encoding="utf-8", errors="replace") as fh:
                srcs.append(fh.read())
        if not srcs or not all(any(os.path.basename(d["path"]) in t for t in srcs) for d in ds):
            return {"ok": False, "reason": "not_referenced"}
        r = _run_checked(base, spec["argv"], allowlist, runner)
        if r is None or r.returncode != 0 or not r.stdout:
            return {"ok": False, "reason": "run_failed"}
        if not re.search(spec["stdout_regex"], r.stdout.decode("utf-8", "replace")):
            return {"ok": False, "reason": "stdout_mismatch"}
        return {"ok": True}
    except (KeyError, ValueError, OSError, TypeError, AttributeError, re.error, subprocess.SubprocessError):
        return {"ok": False, "reason": "unreadable"}


def pe_ok_datasets(base, ds):
    r = check_datasets(base, ds, 1)
    return r["ok"] and not r["rejected"]


def _pdf_fonts(text):
    """Font names from pdffonts output (skips the 2 header lines)."""
    return [l.split()[0] for l in text.splitlines()[2:] if l.strip()]


_HEAD = re.compile(r"^(?:(?:\d+|[ivx]+)\.?\s+)?([a-z ]+?)\.?$")


def section_words(page_texts, sections):
    """Words under each section heading, in reading order. A heading is a line that, stripped,
    lower-cased and without a leading number, equals a section name exactly. Returns
    ({section: words}, order_found)."""
    counts, order, cur = {}, [], None
    for pg in page_texts:
        for line in pg.splitlines():
            m = _HEAD.match(line.strip().lower())
            if m and m.group(1) in sections and m.group(1) not in counts:
                cur = m.group(1); counts[cur] = 0; order.append(cur)
            elif cur:
                counts[cur] += len(line.split())
    return counts, order


def check_paper(base, spec, t):
    """Format gate using poppler. NOT proof of a good or neat paper; look at the pages.
      * pdfinfo page count >= t.paper_pages
      * every embedded font (subset prefix stripped) starts with 'Times'; only math and
        symbol faces are exempt, never as the only font
      * at least t.paper_pages pages carry >= 50 words of text (no blank padding)
      * each required section name is a standalone heading line, in the required order, with
        >= t.min_section_words words under it before the next heading
    The source line asks for a neat paper in Times New Roman with good formatting and names
    no border colour, so none is checked."""
    try:
        p = _resolve(base, spec["path"])
        if not all(shutil.which(x) for x in ("pdfinfo", "pdffonts", "pdftotext")):
            return {"ok": False, "reason": "pdf_tools_missing"}
        info_run = subprocess.run(["pdfinfo", p], capture_output=True, text=True, timeout=30)
        if info_run.returncode != 0:
            return {"ok": False, "reason": "pdfinfo_failed", "returncode": info_run.returncode}
        info = info_run.stdout
        pages = next((int(l.split()[-1]) for l in info.splitlines() if l.startswith("Pages:")), 0)
        fonts_run = subprocess.run(["pdffonts", p], capture_output=True, text=True, timeout=30)
        if fonts_run.returncode != 0:
            return {"ok": False, "reason": "pdffonts_failed", "returncode": fonts_run.returncode}
        names = [n.split("+")[-1] for n in _pdf_fonts(fonts_run.stdout)]
        extra = ("symbol", "math", "cmsy", "cmmi")
        body = [n for n in names if not n.lower().startswith(extra)]
        fonts_ok = bool(body) and all(n.lower().startswith(t.paper_font.lower()) for n in body)
        text_run = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True, timeout=120)
        if text_run.returncode != 0:
            return {"ok": False, "reason": "pdftotext_failed", "returncode": text_run.returncode}
        text = text_run.stdout
        page_texts = text.split("\f")
        full = sum(1 for pg in page_texts if len(pg.split()) >= 50)
        counts, order = section_words(page_texts, t.paper_sections)
        missing = [x for x in t.paper_sections if x not in counts]
        thin = [x for x, n in counts.items() if n < t.min_section_words]
        in_order = order == [x for x in t.paper_sections if x in counts]
        ok = (pages >= t.paper_pages and full >= t.paper_pages and fonts_ok
              and not missing and not thin and in_order)
        return {"ok": ok, "pages": pages, "pages_with_text": full, "times_only": fonts_ok,
                "missing_headings": missing, "thin_sections": thin, "in_order": in_order}
    except (KeyError, ValueError, OSError, TypeError, subprocess.SubprocessError):
        return {"ok": False, "reason": "unreadable"}


def verify_project(base, project, t=LENIENT, runner=None, probe=None, tool_allowlist=(), command_allowlist=BENCH_ALLOWED):
    checks = {
        "repo": check_repo(base, project.get("repo", {}), probe),
        "datasets": check_datasets(base, project.get("datasets"), t.datasets_per_project),
        "paper": check_paper(base, project.get("paper") or {}, t),
        "judge": check_judge(base, project.get("judge_rounds"), t, runner, command_allowlist),
        "benchmarks": check_benchmarks(base, project.get("benchmarks"), t, runner, command_allowlist),
        "leader_benchmarks": check_leader_benchmarks(base, project.get("leader_benchmarks"), runner, command_allowlist),
        "module_run": check_module_run(base, project.get("module_run") or {}, runner, command_allowlist),
    }
    tools = check_tools(base, project.get("tools"), runner, tool_allowlist)
    checks["tools"] = {"counted": len(tools), "ok": len(tools) >= t.tools_per_project}
    passed = sum(1 for c in checks.values() if c["ok"])
    verdict = "VERIFIED" if passed == len(checks) else ("PARTIAL" if passed else "UNSUPPORTED")
    return {"project": project.get("id", ""), "verdict": verdict, "checks": checks,
            "_tools": sorted(tools), "runner_injected": runner is not None,
            "execution_mode": "injected_runner_allowlist_bypassed" if runner is not None else "trusted_local_allowlisted"}


def verify_program(base, projects, t=LENIENT, runner=None, probe=None, tool_allowlist=(), command_allowlist=BENCH_ALLOWED):
    rows = [verify_project(base, p, t, runner, probe, tool_allowlist, command_allowlist) for p in projects]
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
            "verdict": "VERIFIED" if all_ok else ("PARTIAL" if any(r["verdict"] != "UNSUPPORTED" for r in rows) else "UNSUPPORTED"),
            "runner_injected": runner is not None,
            "execution_mode": "injected_runner_allowlist_bypassed" if runner is not None else "trusted_local_allowlisted",
            "not_covered": ["discovery or breakthrough", "5-year-equivalence",
                            "world-best claims", "model training"]}


def render(report):
    lines = ["program %s tools=%d" % (report["verdict"], report["program_distinct_tools_verified"])]
    if report.get("runner_injected"):
        lines.append("EXECUTION: injected runner; default allowlist/resource limits bypassed")
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
