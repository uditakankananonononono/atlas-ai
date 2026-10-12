"""Row 16: per-module evidence generator for the Sugarcode matrix.

For each of the 77 spec slugs it looks for test files named test_<slug>*.py, finds data
files under tests/data and tests/fixtures whose file names appear in those test files AND in
PROVENANCE.md (the origin record), and emits a module_run evidence entry for the matrix:
  argv  = python3 -m pytest -q -p no:cacheprovider <that slug's test files>
  stdout_regex = "\\d+ passed"
The matrix then executes that argv itself (the generator does not vouch for it). Slugs
with no provenance-listed fixture named in their tests get no module_run entry, so their
data_run column stays UNVERIFIED. The report records which Sugarcode HEAD was used.
"""
from __future__ import annotations

import json
import os
import sys
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    key = "pe_" + name
    if key in sys.modules:
        return sys.modules[key]
    s = importlib.util.spec_from_file_location(key, os.path.join(_here, name + ".py"))
    m = importlib.util.module_from_spec(s); sys.modules[key] = m; s.loader.exec_module(m)
    return m


pe = _load("program_evidence_g1_16")
mx = _load("sugarcode_matrix_g16")


def _data_files(root):
    out = []
    for sub in ("tests/data", "tests/fixtures"):
        base = os.path.join(root, sub)
        for r, _, fs in os.walk(base):
            for f in fs:
                out.append(os.path.relpath(os.path.join(r, f), root))
    return sorted(out)


def generate(root):
    slugs = mx.spec_slugs(root)
    try:
        with open(os.path.join(root, "PROVENANCE.md"), encoding="utf-8", errors="replace") as fh:
            prov = fh.read()
    except OSError:
        prov = ""
    files = _data_files(root)
    tdir = os.path.join(root, "tests")
    evidence, skipped = {}, {}
    for slug in slugs:
        if not slug.isidentifier():
            continue
        tests = sorted("tests/" + f for f in os.listdir(tdir) if f.startswith("test_" + slug) and f.endswith(".py"))
        if not tests:
            skipped[slug] = "no_tests"
            continue
        srcs = []
        for t in tests:
            with open(os.path.join(root, t), encoding="utf-8", errors="replace") as fh:
                srcs.append(fh.read())
        ds = []
        for rel in files:
            name = os.path.basename(rel)
            if any(name in s for s in srcs) and name in prov and os.path.getsize(os.path.join(root, rel)) > 0:
                ds.append({"path": rel, "sha256": pe.sha256_file(os.path.join(root, rel)),
                           "origin": "PROVENANCE.md:" + name})
        if not ds:
            skipped[slug] = "no_provenance_listed_fixture_named_in_tests"
            continue
        evidence[slug] = {"module_run": {
            "argv": ["python3", "-m", "pytest", "-q", "-p", "no:cacheprovider"] + tests,
            "stdout_regex": r"\d+ passed", "datasets": ds, "referenced_in": tests}}
    return {"sugarcode_head": mx.head(root), "evidence": evidence, "skipped": skipped}


if __name__ == "__main__":
    g = generate(sys.argv[1])
    with open(sys.argv[2], "w") as fh:
        json.dump(g["evidence"], fh, indent=1, sort_keys=True)
    print("base", g["sugarcode_head"], "entries", len(g["evidence"]), "skipped", len(g["skipped"]))
