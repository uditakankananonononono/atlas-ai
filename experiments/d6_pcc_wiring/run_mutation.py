"""Mutation run on the direction-6 wiring. Mutant generator: experiments/e5_gate_quality/mutants.py (frozen, unmodified).
Semantics match improvement_gate.run_mutations: replace the first occurrence, 'killed' if pytest exits non-zero,
'survived' if it exits 0, 'timeout' counted as killed only if reported separately. Baseline must pass first.
Parallel over private copies of the tree. Usage: python run_mutation.py [--target NAME] [--limit N] [--out FILE]
Env: PYTHON (interpreter, default sys.executable)."""
import argparse, concurrent.futures as cf, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "e5_gate_quality"))
from mutants import generate  # noqa: E402

SB = "tests/self_improve/test_proof_carrying_sandbox.py"
GT = "tests/self_improve/test_proof_gate.py"
CL = "tests/modules/test_m21_claire_claim_proofs.py"
TARGETS = {
    "proof_carrying": ("backend/app/self_improve/proof_carrying.py", [SB, GT, CL]),
    "proof_gate": ("backend/app/self_improve/proof_gate.py", [GT]),
    "claim_proofs": ("backend/app/modules/m21_claire/claim_proofs.py", [CL]),
}
PY = os.environ.get("PYTHON", sys.executable)


def make_copy(dst: Path):
    shutil.copytree(ROOT / "backend", dst / "backend", ignore=shutil.ignore_patterns("__pycache__", "tests_g1_16"))
    (dst / "tests/self_improve").mkdir(parents=True); (dst / "tests/modules").mkdir(parents=True)
    shutil.copy(ROOT / "tests/conftest.py", dst / "tests/conftest.py")
    for t in (SB, GT, CL):
        shutil.copy(ROOT / t, dst / t)
    shutil.copy(ROOT / "pyproject.toml", dst / "pyproject.toml")


def pytest(work: Path, paths, timeout):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        r = subprocess.run([PY, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *paths], cwd=work, env=env,
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout[-400:]
    except subprocess.TimeoutExpired:
        return "timeout", ""


def worker(args):
    wid, items, target_rel, paths, timeout = args
    with tempfile.TemporaryDirectory(prefix=f"mut{wid}_") as tmp:
        work = Path(tmp); make_copy(work)
        tp = work / target_rel; orig = tp.read_text()
        out = []
        for i, old, new in items:
            if orig.count(old) == 0:
                out.append((i, "nomatch", "")); continue
            tp.write_text(orig.replace(old, new, 1))
            try:
                rc, tail = pytest(work, paths, timeout)
            finally:
                tp.write_text(orig)
            out.append((i, "timeout" if rc == "timeout" else ("killed" if rc != 0 else "survived"), tail))
        return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--target", action="append"); ap.add_argument("--limit", type=int)
    ap.add_argument("--only", help="comma list of mutant indices (from a previous run)")
    ap.add_argument("--workers", type=int, default=2); ap.add_argument("--timeout", type=float, default=150)
    ap.add_argument("--out", default=str(Path(__file__).with_name("mutation_results.json")))
    a = ap.parse_args()
    report = {"python": subprocess.run([PY, "-V"], capture_output=True, text=True).stdout.strip(), "targets": {}}
    for name in a.target or list(TARGETS):
        rel, paths = TARGETS[name]
        src = (ROOT / rel).read_text()
        muts = generate(src)
        if a.limit: muts = muts[:a.limit]
        only = {int(x) for x in a.only.split(',')} if a.only else None
        with tempfile.TemporaryDirectory(prefix="base_") as tmp:
            make_copy(Path(tmp)); rc, tail = pytest(Path(tmp), paths, 600)
        assert rc == 0, f"baseline fails for {name}: {tail}"
        chunks = [[(i, o, n) for i, (o, n) in enumerate(muts) if i % a.workers == w and (only is None or i in only)] for w in range(a.workers)]
        t0 = time.time()
        with cf.ProcessPoolExecutor(a.workers) as ex:
            res = sorted(sum(ex.map(worker, [(w, c, rel, paths, a.timeout) for w, c in enumerate(chunks)]), []))
        rows = [{"index": i, "outcome": o, "old": muts[i][0].strip()[:90], "new": muts[i][1].strip()[:90]} for i, o, _ in res]
        cnt = {k: sum(r["outcome"] == k for r in rows) for k in ("killed", "survived", "nomatch", "timeout")}
        report["targets"][name] = {"file": rel, "total": len(rows), **cnt, "seconds": round(time.time() - t0), "rows": rows}
        print(name, len(rows), cnt, flush=True)
        Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
