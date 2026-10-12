"""E2 step 1: ground truth. Run each self_improve module's own tests against fixed line mutants.

Writes mutants.jsonl: one row per mutant with static features (known before running) and the outcome.
Needs Python 3.12 + pytest + sqlalchemy/fastapi/httpx (what tests/self_improve imports).
"""
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "e5_gate_quality"))
import mutants as mut  # noqa: E402

SI = ROOT / "backend/app/self_improve"
TESTS = ROOT / "tests/self_improve"
MODULES = ["codegen", "detector", "engine", "events", "gate", "improvement_gate", "mixin", "planner", "plans",
           "registry", "safety", "sandbox", "self_eval", "testsynth"]
ALL_TEST_TEXT = "\n".join(p.read_text(encoding="utf-8") for p in TESTS.glob("test_*.py"))


def op_kind(old, new):
    for a, b in mut.SUBS:
        if a in old and old.replace(a, b, 1) == new:
            return a.strip() or a
    if new.strip().endswith("return None"):
        return "return_none"
    return "int_literal"


def feats(mod, src, old, new):
    tree = ast.parse(src)
    line = old.strip()
    lines = src.split("\n")
    lineno = next(i + 1 for i, l in enumerate(lines) if l.strip() == line)
    fn = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= lineno <= (n.end_lineno or n.lineno):
            if fn is None or n.lineno > fn.lineno:
                fn = n
    fname = fn.name if fn else None
    test_files = [p for p in TESTS.glob(f"test_{mod}*.py")]
    test_loc = sum(len(p.read_text().split("\n")) for p in test_files)
    mod_loc = len(lines)
    return dict(
        op=op_kind(old, new), line_kind=line.split()[0] if line.split() else "",
        fn_named_in_tests=bool(fname and re.search(r"\b" + re.escape(fname) + r"\b", ALL_TEST_TEXT)),
        fn_private=bool(fname and fname.startswith("_")),
        in_function=fname is not None, has_string="'" in line or '"' in line,
        test_ratio=round(test_loc / max(1, mod_loc), 3), n_test_files=len(test_files))


def run_one(args):
    mod, old, new = args
    src = (SI / f"{mod}.py").read_text(encoding="utf-8")
    f = feats(mod, src, old, new)
    with tempfile.TemporaryDirectory(prefix="e2_") as tmp:
        t = Path(tmp)
        shutil.copytree(ROOT / "backend", t / "backend", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(TESTS, t / "tests/self_improve", ignore=shutil.ignore_patterns("__pycache__"))
        tgt = t / f"backend/app/self_improve/{mod}.py"
        tgt.write_text(src.replace(old, new, 1), encoding="utf-8")
        paths = [str(p) for p in (t / "tests/self_improve").glob(f"test_{mod}*.py")] or ["tests/self_improve"]
        env = {"PYTHONPATH": str(t / "backend"), "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"}
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                                "--noconftest", *paths], cwd=t, env=env, capture_output=True, text=True, timeout=90)
            # pytest exit codes: 0 all passed, 1 tests failed (killed), anything else = harness/collection
            # problem, recorded as invalid and excluded from analysis (an earlier draft counted these as kills).
            killed = r.returncode == 1
            invalid = r.returncode not in (0, 1)
            used_fallback = paths == ["tests/self_improve"]
        except subprocess.TimeoutExpired:
            killed, invalid, used_fallback = True, False, paths == ["tests/self_improve"]
    return dict(module=mod, old=old.strip()[:80], new=new.strip()[:80], killed=killed, invalid=invalid, fallback_all_tests=used_fallback, **f)


def baseline(mod):
    with tempfile.TemporaryDirectory(prefix="e2b_") as tmp:
        t = Path(tmp)
        shutil.copytree(ROOT / "backend", t / "backend", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(TESTS, t / "tests/self_improve", ignore=shutil.ignore_patterns("__pycache__"))
        paths = [str(p) for p in (t / "tests/self_improve").glob(f"test_{mod}*.py")] or ["tests/self_improve"]
        env = {"PYTHONPATH": str(t / "backend"), "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"}
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--noconftest", *paths],
                           cwd=t, env=env, capture_output=True, text=True, timeout=180)
        return r.returncode, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""


def main():
    usable = []
    for m in MODULES:  # a module needs its own test file and a passing unmutated baseline, else kill counts mean nothing
        if not list(TESTS.glob(f"test_{m}*.py")):
            print("excluded (no dedicated test file):", m, flush=True)
            continue
        rc, tail = baseline(m)
        print("baseline", m, rc, tail, flush=True)
        if rc == 0:
            usable.append(m)
        else:
            print("excluded (baseline fails in scratch copy):", m, flush=True)
    jobs = []
    for mod in usable:
        src = (SI / f"{mod}.py").read_text(encoding="utf-8")
        jobs += [(mod, o, n) for o, n in mut.generate(src)]
    print(len(jobs), "mutants", flush=True)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    with Pool(4) as p, (out / "mutants.jsonl").open("w") as fh:
        for i, row in enumerate(p.imap_unordered(run_one, jobs, chunksize=2)):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            if i % 50 == 0:
                print(i, flush=True)


if __name__ == "__main__":
    main()
