"""S7.1 / c36.ev mutation battery. Each mutant is a single textual edit of
ev.py, written to a temp copy, and the S7.1 test file is run against it.
Outcome classes are counted separately: killed-by-assertion, killed-by-error
(any non-assertion failure, e.g. exception or import), timeout, non-compile,
SURVIVED. A negative control (unmutated copy) must pass.

Run: python -B tests/modules/test_c36_ev_s71_mutants.py   (prints a table)
Under unittest/pytest the module checks only the harness (negative control
and that every mutant pattern still matches the source exactly once)."""
import pathlib, re, subprocess, sys, tempfile, shutil, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/c36/ev.py"
TESTS = ROOT / "tests/modules/test_c36_ev_s71.py"

# (id, old, new, note). Equivalent mutants carry a written argument in the contract.
MUTANTS = [
    ("M01 ev uses low prob", "ev = pp * ba * rp", "ev = pl * ba * rp", ""),
    ("M02 ev omits cash", "ev = pp * ba * rp - cash_b - time_cost", "ev = pp * ba * rp - time_cost", ""),
    ("M03 ev omits time cost", "ev = pp * ba * rp - cash_b - time_cost", "ev = pp * ba * rp - cash_b", ""),
    ("M04 ev adds cash", "ev = pp * ba * rp - cash_b - time_cost", "ev = pp * ba * rp + cash_b - time_cost", ""),
    ("M05 ev_low uses high payoff", "ev_low = pl * lo * rp", "ev_low = pl * hi * rp", ""),
    ("M06 ev_high uses base payoff", "ev_high = ph * hi * rp", "ev_high = ph * ba * rp", ""),
    ("M07 payoff not converted", "ev = pp * ba * rp", "ev = pp * ba", ""),
    ("M08 cash not converted", "cash_b = cash * rc", "cash_b = cash", ""),
    ("M09 hourly applied once not per hour", "time_cost = hours * hourly", "time_cost = hourly", ""),
    ("M10 spend gate drops cash", 'if x["cash_positive"] or x["spend"]', 'if x["spend"]', ""),
    ("M12 cash_positive uses >= 0", '"cash_positive": cash_b > 0', '"cash_positive": cash_b >= 0', ""),
    ("M13 actionable includes held", "live if not (x[\"cash_positive\"] or x[\"spend\"])", "live", ""),
    ("M14 expired uses <=", 'x["days"] < 0), key', 'x["days"] <= 0), key', ""),
    ("M15 live uses >", 'live = [x for x in items if x["days"] >= 0]', 'live = [x for x in items if x["days"] > 0]', ""),
    ("M16 weeks floor not ceil", "max(1, -(-days // 7))", "max(1, days // 7)", ""),
    ("M17 weeks no min 1", "max(1, -(-days // 7))", "-(-days // 7)", ""),
    ("M18 sort ev ascending", "return (-x[\"ev\"], x[\"hours\"]", "return (x[\"ev\"], x[\"hours\"]", ""),
    ("M19 tie hours descending", "return (-x[\"ev\"], x[\"hours\"], x[\"deadline\"]", "return (-x[\"ev\"], -x[\"hours\"], x[\"deadline\"]", ""),
    ("M20 tie deadline dropped", "x[\"hours\"], x[\"deadline\"], x[\"id\"])", "x[\"hours\"], x[\"id\"])", ""),
    ("M21 tie id dropped", "x[\"hours\"], x[\"deadline\"], x[\"id\"])\n\n\ndef _row", "x[\"hours\"], x[\"deadline\"])\n\n\ndef _row", ""),
    ("M22 prob upper bound >=", "if f < 0 or f > 1:", "if f < 0 or f >= 1:", ""),
    ("M23 prob lower bound <=", "if f < 0 or f > 1:", "if f <= 0 or f > 1:", ""),
    ("M24 prob order unchecked", "if not pl <= pp <= ph:", "if False:", ""),
    ("M25 payoff order unchecked", "if not lo <= ba <= hi:", "if False:", ""),
    ("M26 payoff order strict", "if not lo <= ba <= hi:", "if not lo < ba < hi:", ""),
    ("M27 guarantee check off", "if any(p in low for p in GUARANTEE_PHRASES):", "if False:", ""),
    ("M28 guarantee case sensitive", "low = text.lower()", "low = text", ""),
    ("M29 guarantee drops risk-free", '"risk-free", ', "", ""),
    ("M30 guarantee drops certain profit", '"sure thing",\n                     "certain profit")', '"sure thing")', ""),
    ("M31 banner altered", "not a promise of income.", "a promise of income.", ""),
    ("M32 fx missing currency passes", "    if cur not in table:\n        _refuse(\"CURRENCY\", cur)\n", "    if cur not in table:\n        return Fraction(1)\n", ""),
    ("M33 fx rate zero allowed", "or not math.isfinite(rate) or rate <= 0:", "or not math.isfinite(rate) or rate < 0:", ""),
    ("M35 cost currency override ignored", "ccur = _currency(cost[\"currency\"], \"cost.currency\") if cost.get(\"currency\") is not None \\\n        else pcur", "ccur = pcur", ""),
    ("M36 duplicate id allowed", "        if x[\"id\"] in seen:\n            _refuse(\"BAD_TYPE\", \"id\")", "        if False:\n            _refuse(\"BAD_TYPE\", \"id\")", ""),
    ("M37 brute force off", "if len(actionable) <= MAX_BRUTE:", "if False:", ""),
    ("M38 brute bound 14", "MAX_BRUTE = 15", "MAX_BRUTE = 14", ""),
    ("M39 brute bound 16", "MAX_BRUTE = 15", "MAX_BRUTE = 16", ""),
    ("M40 feasibility budget ignores weeks", "if total > weekly * x[\"weeks\"]:", "if total > weekly:", ""),
    ("M41 feasibility strict", "if total > weekly * x[\"weeks\"]:", "if total >= weekly * x[\"weeks\"]:", ""),
    ("M42 greedy allows negative ev", "pool = [x for x in items if x[\"ev\"] > 0]", "pool = list(items)", ""),
    ("M43 greedy order by ev not per hour", "(1, -(x[\"ev\"] / x[\"hours\"]), -x[\"ev\"], x[\"id\"])", "(1, -x[\"ev\"], -x[\"ev\"], x[\"id\"])", ""),
    ("M44 greedy skips feasibility", "if _feasible(chosen + [x], weekly):", "if True:", ""),
    ("M45 greedy zero-hour not first", "(0, 0, -x[\"ev\"], x[\"id\"]) if x[\"hours\"] == 0", "(1, 0, -x[\"ev\"], x[\"id\"]) if x[\"hours\"] == 0", ""),
    ("M46 ev per hour for zero hours", "if x[\"hours\"] > 0 else None,", "if x[\"hours\"] >= 0 else None,", ""),
    ("M47 brute prefers more hours", "(ev == best_key[0] and hrs < -best_key[1])", "(ev == best_key[0] and hrs > -best_key[1])", ""),
    ("M48 warning share threshold", "x[\"ev\"] * 2 >= total_pos", "x[\"ev\"] * 2 >= total_pos * 10", ""),
    ("M49 warning drops variance test", "and (x[\"ev_high\"] - x[\"ev_low\"]) > x[\"ev\"]", "", ""),
    ("M50 negative ev warning off", "if x[\"ev\"] < 0:\n            warnings.append", "if False:\n            warnings.append", ""),
    ("M51 outreach flag dropped", '["draft_only_needs_approval"] if x["outreach"] else []', "[]", ""),
    ("M52 clean_text bypassed for name", 'name = _text(_need(o, "name"), "name")', 'name = _need(o, "name")', ""),
    ("M53 source_url unchecked", 'url = _text(_need(o, "source_url"), "source_url")', 'url = o.get("source_url") or ""', ""),
    ("M54 hours bool accepted", "if isinstance(value, bool) or not isinstance(value, (int, float)) \\\n            or not math.isfinite(value):\n        _refuse(\"BAD_TYPE\", field)", "if not isinstance(value, (int, float)) \\\n            or not math.isfinite(value):\n        _refuse(\"BAD_TYPE\", field)", ""),
    ("M55a _num float via binary not repr", "Fraction(repr(value)) if isinstance(value, float) else Fraction(value)\n    if minimum", "Fraction(value)\n    if minimum", ""),
    ("M55b _prob float via binary not repr", "Fraction(repr(value)) if isinstance(value, float) else Fraction(value)\n    if f < 0 or f > 1:", "Fraction(value)\n    if f < 0 or f > 1:", ""),
    ("M56 output not rounded", "return round(float(x), 6) + 0.0", "return float(x)", ""),
    ("M58 usage counts same-deadline members only", 'members = [x for x in chosen if x["deadline"] <= d]', 'members = [x for x in chosen if x["deadline"] == d]', ""),
    ("M59 over_budget flag not added to rows", 'row["flags"] = row["flags"] + ["over_budget"]', 'row["flags"] = row["flags"]', ""),
    ("M60 over_budget list empty", 'block["over_budget"] = sorted(x["id"] for x in skipped)', 'block["over_budget"] = []', ""),
    ("M61 capacity ignores weeks", '"capacity_hours": _original(weekly * next(\n                        x["weeks"] for x in chosen if x["deadline"] == d))})', '"capacity_hours": _original(weekly)})', ""),
    ("M62 skipped item still chosen", "        else:\n            skipped.append(x)", "        else:\n            skipped.append(x)\n            chosen.append(x)", ""),
    ("M57 scope removed", "\"scope\": policy.scope(", "\"scope\": dict(", ""),
]


def run_mutant(old, new, timeout=120):
    text = SRC.read_text()
    if text.count(old) != 1:
        return "PATTERN_MISMATCH(%d)" % text.count(old)
    mut = text.replace(old, new)
    if mut == text:
        return "NOOP"
    d = pathlib.Path(tempfile.mkdtemp(prefix="c36mut"))
    try:
        for rel in ("backend/app/modules/c36", "backend/app/modules/c30", "tests/modules"):
            (d / rel).mkdir(parents=True, exist_ok=True)
        for f in (ROOT / "backend/app/modules/c30").glob("*.py"):
            shutil.copy(f, d / "backend/app/modules/c30" / f.name)
        (d / "backend/app/modules/__init__.py").write_text("")
        (d / "backend/app/__init__.py").write_text("")
        (d / "backend/app/modules/c36/__init__.py").write_text("")
        (d / "backend/app/modules/c36/ev.py").write_text(mut)
        shutil.copy(TESTS, d / "tests/modules" / TESTS.name)
        try:
            compile(mut, "ev.py", "exec")
        except SyntaxError:
            return "NON_COMPILE"
        try:
            p = subprocess.run([sys.executable, "-B", "tests/modules/" + TESTS.name],
                               cwd=d, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        if p.returncode == 0:
            return "SURVIVED"
        out = p.stderr
        fails = len(re.findall(r"^FAIL:", out, re.M))
        errs = len(re.findall(r"^ERROR:", out, re.M))
        if fails:
            return "KILLED_ASSERTION(fail=%d,err=%d)" % (fails, errs)
        return "KILLED_ERROR(err=%d)" % errs
    finally:
        shutil.rmtree(d, ignore_errors=True)


class Harness(unittest.TestCase):
    def test_every_pattern_matches_exactly_once(self):
        text = SRC.read_text()
        bad = [m[0] for m in MUTANTS if text.count(m[1]) != 1]
        self.assertEqual(bad, [])

    def test_negative_control_passes(self):
        self.assertEqual(run_mutant("MAX_BRUTE = 15", "MAX_BRUTE = 15 + 0"), "SURVIVED")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "unit":
        unittest.main(argv=["x"])
    rows = [(m[0], run_mutant(m[1], m[2])) for m in MUTANTS]
    for name, res in rows:
        print("%-46s %s" % (name, res))
    tally = {}
    for _, r in rows:
        k = r.split("(")[0]
        tally[k] = tally.get(k, 0) + 1
    print("TOTAL", len(rows), tally)
