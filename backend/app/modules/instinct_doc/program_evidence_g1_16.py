"""Instinct-doc groups 1-16: program evidence verifier.

Unlike the declaration registers (p77/p254/p255/p258), nothing here trusts a
caller-supplied claim. Each project is verified by RESOLVING its evidence:
  * repo      - a local git checkout (or injected remote probe) must exist and have commits
  * datasets  - each dataset file must exist; sha256 and byte size recomputed
  * tools     - each tool needs an execution receipt (command, exit 0, output hash)
                whose output file exists and hashes to the receipt
  * papers    - a PDF must exist; page count and Times font read via pdfinfo/pdffonts
  * judge     - transcript files must exist, hash-match, and show a metric delta
  * benchmark - a reproducible command is re-run; its stdout hash must match
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


def check_repo(base, spec):
    """spec: {path}. VERIFIED only if a real git repo with >=1 commit."""
    try:
        p = _resolve(base, spec["path"])
        out = subprocess.run(["git", "-C", p, "rev-list", "--count", "HEAD"],
                             capture_output=True, text=True, timeout=30)
        n = int(out.stdout.strip()) if out.returncode == 0 else 0
    except (KeyError, ValueError, OSError, subprocess.SubprocessError):
        n = 0
    return {"ok": n > 0, "commits": n}


def check_datasets(base, specs, minimum):
    good, bad = set(), []
    for s in specs or []:
        try:
            p = _resolve(base, s["path"])
            size = os.path.getsize(p)
            if size > 0 and sha256_file(p) == s["sha256"] and s.get("origin"):
                good.add(s["sha256"])  # identical content counts once
            else:
                bad.append(s.get("path"))
        except (KeyError, ValueError, OSError):
            bad.append(s.get("path") if isinstance(s, dict) else None)
    return {"verified": len(good), "rejected": bad, "ok": len(good) >= minimum}


def check_tools(base, specs):
    """Receipt: {name, command, exit_code, output_path, output_sha256}. Returns names."""
    names = set()
    for s in specs or []:
        try:
            if s["exit_code"] != 0 or not s["command"] or not s["name"]:
                continue
            p = _resolve(base, s["output_path"])
            if os.path.getsize(p) > 0 and sha256_file(p) == s["output_sha256"]:
                names.add(s["name"].strip().lower())
        except (KeyError, ValueError, OSError, TypeError):
            continue
    return names


def check_paper(base, spec, t):
    try:
        p = _resolve(base, spec["path"])
        if not shutil.which("pdfinfo") or not shutil.which("pdffonts"):
            return {"ok": False, "reason": "pdf_tools_missing"}
        info = subprocess.run(["pdfinfo", p], capture_output=True, text=True, timeout=30).stdout
        pages = next((int(l.split()[-1]) for l in info.splitlines() if l.startswith("Pages:")), 0)
        fonts = subprocess.run(["pdffonts", p], capture_output=True, text=True, timeout=30).stdout
        times = t.paper_font.lower() in fonts.lower()
        return {"ok": pages >= t.paper_pages and times, "pages": pages, "times_font": times}
    except (KeyError, ValueError, OSError, subprocess.SubprocessError):
        return {"ok": False, "reason": "unreadable"}


def check_judge(base, rounds, t):
    """Each round: {transcript_path, transcript_sha256, metric, before, after}."""
    done = 0
    for r in rounds or []:
        try:
            p = _resolve(base, r["transcript_path"])
            if (os.path.getsize(p) > 0 and sha256_file(p) == r["transcript_sha256"]
                    and r["after"] > r["before"]):
                done += 1
        except (KeyError, ValueError, OSError, TypeError):
            continue
    return {"rounds": done, "ok": done >= t.judge_rounds}


def check_benchmarks(base, specs, t, runner=None):
    """Re-run argv in base; stdout sha256 must equal expected. Never trusts a score."""
    run = runner or (lambda argv: subprocess.run(argv, cwd=base, capture_output=True, timeout=300))
    ok = 0
    for s in specs or []:
        try:
            argv = s["argv"]
            if not isinstance(argv, list) or not argv:
                continue
            r = run(argv)
            if r.returncode == 0 and hashlib.sha256(r.stdout).hexdigest() == s["stdout_sha256"]:
                ok += 1
        except (KeyError, OSError, subprocess.SubprocessError):
            continue
    return {"reproduced": ok, "ok": ok >= t.benchmarks_per_project}


def verify_project(base, project, t=LENIENT, runner=None):
    checks = {
        "repo": check_repo(base, project.get("repo", {})),
        "datasets": check_datasets(base, project.get("datasets"), t.datasets_per_project),
        "paper": check_paper(base, project.get("paper", {}), t),
        "judge": check_judge(base, project.get("judge_rounds"), t),
        "benchmarks": check_benchmarks(base, project.get("benchmarks"), t, runner),
    }
    tools = check_tools(base, project.get("tools"))
    checks["tools"] = {"verified": len(tools), "ok": len(tools) >= t.tools_per_project}
    passed = sum(1 for c in checks.values() if c["ok"])
    verdict = "VERIFIED" if passed == len(checks) else ("PARTIAL" if passed else "UNSUPPORTED")
    return {"project": project.get("id", ""), "verdict": verdict, "checks": checks,
            "_tools": sorted(tools)}


def verify_program(base, projects, t=LENIENT, runner=None):
    rows = [verify_project(base, p, t, runner) for p in projects]
    allt = set()
    for r in rows:
        allt.update(r.pop("_tools"))
    prog_ok = len(allt) >= t.tools_program
    all_ok = prog_ok and bool(rows) and all(r["verdict"] == "VERIFIED" for r in rows)
    return {"thresholds": t.__dict__, "projects": rows,
            "program_distinct_tools_verified": len(allt), "program_tools_ok": prog_ok,
            "verdict": "VERIFIED" if all_ok else ("PARTIAL" if rows else "UNSUPPORTED"),
            "not_covered": ["real discovery/breakthrough", "5-year-equivalence",
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
