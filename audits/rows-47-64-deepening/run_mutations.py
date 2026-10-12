"""Mutation harness for the rows 47-64 deepening batteries. Run from repo root:
    ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 audits/rows-47-64-deepening/run_mutations.py <battery> [out.txt]
<battery> is a module in audits/rows-47-64-deepening/batteries/ that defines MUT = [(id, row, file, old, new, tests)].
Each mutant is one exact textual replacement (old -> new, first occurrence; the old text must occur exactly once or the
mutant is NOT-APPLICABLE). Baseline: every named test file must pass before any mutant runs. CAUGHT only when pytest
exits 1 with at least one FAILED line; rc 2/4/5, a timeout, or rc 1 with no FAILED line is INVALID; rc 0 is SURVIVED.
Restore is verified by SHA-256 of every mutated file against its pre-run content. Commit source and tests before a run:
a killed run can leave a mutant on disk, and `git checkout -- backend` restores it only from a committed state."""
import hashlib, importlib.util, os, subprocess, sys

ENV = dict(os.environ, ATLAS_DEV_NO_AUTH="1", ATLAS_ENV="development", PYTHONPATH="backend")
TIMEOUT_S = 180


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


def main(name, out):
    spec = importlib.util.spec_from_file_location("battery", "audits/rows-47-64-deepening/batteries/%s.py" % name)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    MUT = mod.MUT
    lines = []
    files = sorted({m[2] for m in MUT})
    before = {f: sha(f) for f in files}
    for tests in sorted({m[5] for m in MUT}):
        rc, last, _ = run(tests)
        lines.append("BASELINE %s -> rc=%s %s" % (tests, rc, last))
        assert rc == 0, last
    counts = {"CAUGHT": 0, "SURVIVED": 0, "INVALID": 0, "NOT-APPLICABLE": 0}
    for mid, row, f, old, new, tests in MUT:
        src = open(f).read()
        if src.count(old) != 1:
            counts["NOT-APPLICABLE"] += 1
            lines.append("%s | row %s | NOT-APPLICABLE (old text occurs %d times)" % (mid, row, src.count(old)))
            continue
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
        lines.append("%s | row %s | %s | %s | rc=%s | %s | failing: %s" % (
            mid, row, os.path.basename(f), verdict, rc, last, ", ".join(failed[:3]) or "-"))
        lines.append("    old: %r" % old[:200]); lines.append("    new: %r" % new[:200])
    after = {f: sha(f) for f in files}
    ok = before == after
    lines.append("TOTAL mutants=%d CAUGHT=%d SURVIVED=%d INVALID=%d NOT-APPLICABLE=%d | SHA restore %s"
                 % (len(MUT), counts["CAUGHT"], counts["SURVIVED"], counts["INVALID"], counts["NOT-APPLICABLE"], ok))
    open(out, "w").write("\n".join(lines) + "\n")
    print(lines[-1])
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    n = sys.argv[1]
    main(n, sys.argv[2] if len(sys.argv) > 2 else "audits/rows-47-64-deepening/receipts_%s.txt" % n)
