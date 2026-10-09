"""Remaining lever components for the prototype builder (stdlib only, synthetic fixtures)."""
MORE: dict[str, tuple[str, str]] = {}

MORE["sustainability_proof"] = ('''
"""Claim ledger: a sustainability claim is publishable only when its evidence covers it."""

class Ledger:
    def __init__(self): self.claims, self.evidence = {}, {}
    def claim(self, cid, text, required_kinds):
        if not required_kinds: raise ValueError("a claim needs required evidence kinds")
        self.claims[cid] = {"text": text, "required": set(required_kinds)}
    def attach(self, cid, kind, ref, valid_until):
        if cid not in self.claims: raise KeyError(cid)
        self.evidence.setdefault(cid, []).append({"kind": kind, "ref": ref, "valid_until": valid_until})
    def status(self, cid, today):
        have = {e["kind"] for e in self.evidence.get(cid, []) if e["valid_until"] >= today}
        missing = self.claims[cid]["required"] - have
        expired = sorted({e["kind"] for e in self.evidence.get(cid, []) if e["valid_until"] < today} & missing)
        return {"publishable": not missing, "missing": sorted(missing), "expired": expired}
    def publishable_claims(self, today): return sorted(c for c in self.claims if self.status(c, today)["publishable"])
''', '''
import unittest
from sustainability_proof import Ledger

class T(unittest.TestCase):
    def mk(self):
        l = Ledger(); l.claim("c1", "100% recycled strap", ["supplier_cert", "lab_test"]); return l
    def test_missing_evidence_blocks(self):
        l = self.mk(); l.attach("c1", "supplier_cert", "r1", "2027-01-01"); self.assertEqual(l.status("c1", "2026-10-01")["missing"], ["lab_test"])
    def test_complete_is_publishable(self):
        l = self.mk(); l.attach("c1", "supplier_cert", "r1", "2027-01-01"); l.attach("c1", "lab_test", "r2", "2027-01-01")
        self.assertTrue(l.status("c1", "2026-10-01")["publishable"]); self.assertEqual(l.publishable_claims("2026-10-01"), ["c1"])
    def test_expired_evidence_does_not_count(self):
        l = self.mk(); l.attach("c1", "supplier_cert", "r1", "2027-01-01"); l.attach("c1", "lab_test", "r2", "2026-06-01")
        s = l.status("c1", "2026-10-01"); self.assertFalse(s["publishable"]); self.assertEqual(s["expired"], ["lab_test"])
    def test_unknown_claim_and_empty_requirements(self):
        l = Ledger()
        with self.assertRaises(KeyError): l.attach("x", "k", "r", "2027-01-01")
        with self.assertRaises(ValueError): l.claim("c", "t", [])
    def test_excess_evidence_kind_irrelevant(self):
        l = self.mk(); l.attach("c1", "press_release", "r9", "2027-01-01"); self.assertFalse(l.status("c1", "2026-10-01")["publishable"])
if __name__ == "__main__": unittest.main()
''')

MORE["digital_world"] = ('''
"""Licensing guard: checks a proposed fan-product use against registered license terms."""

class Licenses:
    def __init__(self): self.terms = {}
    def register(self, asset, allowed_uses, territories, audience_min_age, expires):
        self.terms[asset] = {"uses": set(allowed_uses), "territories": set(territories), "min_age": audience_min_age, "expires": expires}
    def check(self, asset, use, territory, audience_age, today):
        t = self.terms.get(asset)
        if t is None: return {"allowed": False, "reasons": ["asset not licensed"]}
        why = []
        if use not in t["uses"]: why.append("use not permitted: " + use)
        if territory not in t["territories"]: why.append("territory not licensed: " + territory)
        if audience_age < t["min_age"]: why.append("audience younger than licensed minimum age")
        if today > t["expires"]: why.append("license expired")
        return {"allowed": not why, "reasons": why}
''', '''
import unittest
from digital_world import Licenses

class T(unittest.TestCase):
    def mk(self):
        l = Licenses(); l.register("hero", ["game", "stickers"], ["US", "JP"], 6, "2027-12-31"); return l
    def test_allowed(self): self.assertTrue(self.mk().check("hero", "game", "US", 8, "2026-10-01")["allowed"])
    def test_each_violation_reported(self):
        r = self.mk().check("hero", "film", "FR", 3, "2028-01-01"); self.assertFalse(r["allowed"]); self.assertEqual(len(r["reasons"]), 4)
    def test_unknown_asset(self): self.assertEqual(self.mk().check("villain", "game", "US", 9, "2026-10-01")["reasons"], ["asset not licensed"])
    def test_expiry_boundary_inclusive(self): self.assertTrue(self.mk().check("hero", "game", "US", 6, "2027-12-31")["allowed"])
    def test_age_boundary(self): self.assertFalse(self.mk().check("hero", "game", "US", 5, "2026-10-01")["allowed"])
if __name__ == "__main__": unittest.main()
''')

MORE["operations_quality"] = ('''
"""Service-gap detector: flags days where staffing per guest fell below a floor or complaints spiked."""
from statistics import mean, pstdev

def detect(days, min_staff_per_guest, z=2.0):
    """days: list of {date, guests, staff, complaints}. Returns flagged days with reasons."""
    if not days: raise ValueError("no data")
    flagged = []
    comp = [d["complaints"] for d in days]
    mu, sd = mean(comp), pstdev(comp)
    for d in days:
        reasons = []
        if d["guests"] > 0 and d["staff"] / d["guests"] < min_staff_per_guest:
            reasons.append("staffing below floor")
        if sd > 0 and (d["complaints"] - mu) / sd >= z:
            reasons.append("complaint spike")
        if reasons: flagged.append({"date": d["date"], "reasons": reasons})
    return flagged
''', '''
import unittest
from operations_quality import detect

def day(i, g, s, c): return {"date": f"2026-10-{i:02d}", "guests": g, "staff": s, "complaints": c}
class T(unittest.TestCase):
    def test_staffing_floor(self):
        r = detect([day(1, 100, 20, 1), day(2, 100, 5, 1)], 0.1); self.assertEqual([x["date"] for x in r], ["2026-10-02"])
    def test_complaint_spike(self):
        ds = [day(i, 100, 20, 1) for i in range(1, 10)] + [day(10, 100, 20, 30)]
        r = detect(ds, 0.1); self.assertEqual(r, [{"date": "2026-10-10", "reasons": ["complaint spike"]}])
    def test_both_reasons(self):
        ds = [day(i, 100, 20, 1) for i in range(1, 10)] + [day(10, 100, 2, 30)]
        self.assertEqual(detect(ds, 0.1)[0]["reasons"], ["staffing below floor", "complaint spike"])
    def test_flat_data_no_flags(self): self.assertEqual(detect([day(i, 100, 20, 2) for i in range(1, 6)], 0.1), [])
    def test_empty_rejected(self):
        with self.assertRaises(ValueError): detect([], 0.1)
    def test_zero_guests_not_divided(self): self.assertEqual(detect([day(1, 0, 0, 0)], 0.1), [])
if __name__ == "__main__": unittest.main()
''')

MORE["pricing_demand"] = ('''
"""Price-sensitivity estimate: log-log least squares elasticity from (price, quantity) observations."""
from math import log

def elasticity(obs):
    """obs: list of (price, quantity). Returns slope (elasticity), intercept, n, r2."""
    pts = [(log(p), log(q)) for p, q in obs if p > 0 and q > 0]
    n = len(pts)
    if n < 3: raise ValueError("need at least 3 valid observations")
    mx, my = sum(x for x, _ in pts) / n, sum(y for _, y in pts) / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    if sxx == 0: raise ValueError("prices do not vary")
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    b = sxy / sxx; a = my - b * mx
    ss_tot = sum((y - my) ** 2 for _, y in pts)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in pts)
    return {"elasticity": b, "intercept": a, "n": n, "r2": 1.0 if ss_tot == 0 else 1 - ss_res / ss_tot}

def classify(e):
    return "elastic" if e < -1 else "inelastic" if e < 0 else "not price-sensitive (non-negative)"
''', '''
import unittest
from pricing_demand import elasticity, classify

class T(unittest.TestCase):
    def test_recovers_known_elasticity(self):
        obs = [(p, 1000 * p ** -1.5) for p in (10, 20, 40, 80)]
        r = elasticity(obs); self.assertAlmostEqual(r["elasticity"], -1.5, places=6); self.assertAlmostEqual(r["r2"], 1.0, places=6)
    def test_classify(self):
        self.assertEqual(classify(-1.5), "elastic"); self.assertEqual(classify(-0.4), "inelastic"); self.assertIn("non-negative", classify(0.2))
    def test_too_few_points(self):
        with self.assertRaises(ValueError): elasticity([(1, 1), (2, 1)])
    def test_constant_price_rejected(self):
        with self.assertRaises(ValueError): elasticity([(5, 1), (5, 2), (5, 3)])
    def test_ignores_nonpositive(self):
        r = elasticity([(10, 100), (20, 50), (40, 25), (0, 9), (5, -1)]); self.assertEqual(r["n"], 3)
    def test_noisy_data_r2_below_one(self):
        r = elasticity([(10, 100), (20, 70), (40, 20), (80, 30)]); self.assertLess(r["r2"], 1.0)
if __name__ == "__main__": unittest.main()
''')
