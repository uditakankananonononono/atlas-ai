"""Row 16: 77-module Sugarcode validation matrix generator.

Reads a Sugarcode checkout (pinned by git HEAD) and, for each of the 77 spec
slugs in spec/index.json, records what is observable by reading files: module
source file hashes and test file names. Function-level columns
(data_run, improvement, discovery, benchmark_vs_leader) are filled only from
evidence in an optional file {slug: {...}} that is re-checked through
program_evidence_g1_16 (module runs, judge commands and leader benchmarks are executed here);
otherwise they are UNVERIFIED. A module is never VERIFIED
from structure alone: the best structure-only verdict is PARTIAL.
"""
from __future__ import annotations

import json
import os
import subprocess
import importlib.util
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_KEY = "pe_program_evidence_g1_16"  # one shared module object, so SANDBOX_ENV is shared
if _KEY not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_KEY, os.path.join(_here, "program_evidence_g1_16.py"))
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[_KEY] = _m
    _spec.loader.exec_module(_m)
pe = sys.modules[_KEY]

EXEC_EVIDENCE = "EXECUTION_EVIDENCE"
# Column states:
#   data_run            VERIFIED only when the full chain held: dataset hash + stated origin,
#                       file name named in the module's tests, allowlisted run executed here
#                       with exit 0 and matching stdout. The run is not proven to have read the file.
#   improvement         EXECUTION_EVIDENCE: the judge command ran here and printed an increasing,
#   benchmark_vs_leader finite score stream (or a BENCH line meeting the declared criterion).
#                       This proves command stdout provenance only. It is not authenticated judge
#                       truth and not proof of the true state of the art.
#   discovery           CLAIMED_NOT_CHECKABLE at best; code cannot check a discovery.
COLUMNS = ("data_run", "improvement", "discovery", "benchmark_vs_leader")


def _files(d, pred):
    out = []
    for r, _, fs in os.walk(d):
        for f in sorted(fs):
            if pred(f):
                p = os.path.join(r, f)
                out.append(os.path.relpath(p, d))
    return sorted(out)


def spec_slugs(root):
    with open(os.path.join(root, "spec", "index.json")) as fh:
        idx = json.load(fh)
    return [e["slug"] for e in idx if isinstance(e, dict) and isinstance(e.get("slug"), str)]


def head(root):
    r = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def build_matrix(root, evidence=None, runner=None):
    evidence = evidence if isinstance(evidence, dict) else {}
    rows = []
    for slug in spec_slugs(root):
        if not slug.isidentifier():
            continue  # slug becomes a path part; refuse anything odd
        spec_p = os.path.join(root, "spec", slug + ".md")
        mod_d = os.path.join(root, "src", "sugarcode", "modules", slug)
        mod_files = _files(mod_d, lambda f: f.endswith(".py")) if os.path.isdir(mod_d) else []
        tdir = os.path.join(root, "tests")
        tests = sorted(f for f in os.listdir(tdir) if f.startswith("test_" + slug) and f.endswith(".py")) if os.path.isdir(tdir) else []
        ev = evidence.get(slug) if isinstance(evidence.get(slug), dict) else {}
        cols = {c: "UNVERIFIED" for c in COLUMNS}
        t = pe.Thresholds(judge_rounds=1)
        mr = ev.get("module_run")
        if isinstance(mr, dict) and pe.check_module_run(root, mr, runner)["ok"]:
            cols["data_run"] = "VERIFIED"  # module run executed here + dataset hashed + named in tests
        if pe.check_judge(root, ev.get("judge_rounds"), t, runner)["ok"]:
            cols["improvement"] = EXEC_EVIDENCE  # judge command executed here, scores parsed from its stdout
        if pe.check_leader_benchmarks(root, ev.get("leader_benchmarks"), runner)["ok"]:
            cols["benchmark_vs_leader"] = EXEC_EVIDENCE  # leader/metric/criterion declared, run executed here
        if ev.get("discovery_claim"):
            cols["discovery"] = "CLAIMED_NOT_CHECKABLE"  # code cannot check a discovery claim
        structure = bool(os.path.isfile(spec_p) and mod_files and tests)
        all_ok = cols["data_run"] == "VERIFIED" and all(cols[c] == EXEC_EVIDENCE for c in ("improvement", "benchmark_vs_leader")) and cols["discovery"] == "VERIFIED"  # discovery never reaches VERIFIED
        rows.append({
            "slug": slug, "spec_present": os.path.isfile(spec_p),
            "module_files": len(mod_files), "test_files": len(tests),
            "module_sha": {f: pe.sha256_file(os.path.join(mod_d, f)) for f in mod_files},
            "columns": cols,
            "verdict": "VERIFIED" if (structure and all_ok) else ("PARTIAL" if structure else "UNSUPPORTED"),
        })
    return {"sugarcode_head": head(root), "modules": len(rows), "rows": rows,
            "counts": {v: sum(1 for r in rows if r["verdict"] == v) for v in pe.VERDICTS}}


def render(m):
    lines = ["sugarcode %s modules=%d %s" % (m["sugarcode_head"][:8], m["modules"], m["counts"])]
    for r in m["rows"]:
        lines.append("%s %s files=%d tests=%d %s" % (r["slug"], r["verdict"], r["module_files"], r["test_files"],
                     ",".join(c + "=" + v for c, v in r["columns"].items() if v not in ("VERIFIED", EXEC_EVIDENCE)) or "no-unverified-columns"))
    return "\n".join(lines)


if __name__ == "__main__":
    root = sys.argv[1]
    ev = None
    if len(sys.argv) > 2:
        with open(sys.argv[2]) as fh:
            ev = json.load(fh)
    print(render(build_matrix(root, ev)))
