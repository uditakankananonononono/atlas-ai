"""Row 98 SOCIAL98 tests. Hermetic, stdlib unittest, exact N/N+1 pins."""
import copy, importlib.util, math, pathlib, sys, unittest
from fractions import Fraction

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/social_proof_deployment98.py"
_spec = importlib.util.spec_from_file_location("social_proof_deployment98", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["social_proof_deployment98"] = m
_spec.loader.exec_module(m)


def packet(**kw):
    d = {"claim": "60 of 100 respondents chose option A",
         "evidence": {"source": "survey-1", "as_of": "2026-10-01", "observed_count": 60, "sample_size": 100},
         "as_of": "2026-10-11", "min_sample": 30, "max_age_days": 30, "z": "196/100", "claimed_percent": 60}
    d.update(kw)
    return d


def ev(**kw):
    e = {"source": "survey-1", "as_of": "2026-10-01", "observed_count": 60, "sample_size": 100}
    e.update(kw)
    return e


def refusal(test, p):
    with test.assertRaises(m.Social98Error) as cm:
        m.evaluate_social_proof(p)
    return str(cm.exception)


def wilson_float(k, n, z):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


class Compute(unittest.TestCase):
    def test_exact_fields(self):
        r = m.evaluate_social_proof(packet())
        self.assertEqual(r["proportion"], "3/5")
        self.assertEqual(r["percent_rounded"], 60)
        self.assertEqual(r["evidence"], {"source": "survey-1", "as_of": "2026-10-01", "observed_count": 60, "sample_size": 100, "age_days": 10})
        self.assertEqual(r["rules"], {"min_sample_met": True, "claim_consistent": True, "evidence_fresh": True})
        self.assertEqual(r["blocked_reasons"], [])
        self.assertTrue(r["deployment_allowed"])
        self.assertEqual(r["disclosure"], "60 of 100 responses from survey-1 as of 2026-10-01.")
        self.assertEqual(r["scope"], "caller_declared_counts_only")
        self.assertIs(r["real_world_effect_verified"], False)

    def test_interval_encloses_float_wilson_within_grid(self):
        for k, n in ((60, 100), (0, 1), (1, 1), (5, 40), (39, 40), (1, 1000), (500, 1000)):
            r = m.evaluate_social_proof(packet(claimed_percent=None, evidence=ev(observed_count=k, sample_size=n), min_sample=1))
            lo, hi = (Fraction(x) for x in r["wilson_interval"])
            flo, fhi = wilson_float(k, n, 1.96)
            self.assertLessEqual(lo, Fraction(flo) + Fraction(1, 10**9), (k, n))
            self.assertGreaterEqual(hi, Fraction(fhi) - Fraction(1, 10**9), (k, n))
            self.assertLess(Fraction(flo) - lo, Fraction(2, 10**6), (k, n))
            self.assertLess(hi - Fraction(fhi), Fraction(2, 10**6), (k, n))
            self.assertTrue(0 <= lo <= hi <= 1)

    def test_degenerate_exact_edges(self):
        r = m.evaluate_social_proof(packet(claimed_percent=None, evidence=ev(observed_count=0, sample_size=1), min_sample=1))
        self.assertEqual(r["wilson_interval"][0], "0.000000")
        exact_hi = Fraction(196 ** 2, 100 ** 2 + 196 ** 2)  # z^2/(1+z^2)
        hi = Fraction(r["wilson_interval"][1])
        self.assertGreaterEqual(hi, exact_hi)
        self.assertLess(hi - exact_hi, Fraction(2, 10**6))
        r = m.evaluate_social_proof(packet(claimed_percent=None, evidence=ev(observed_count=1, sample_size=1), min_sample=1))
        self.assertEqual(r["wilson_interval"][1], "1.000000")

    def test_percent_half_up(self):
        for k, n, pct in ((1, 8, 13), (1, 16, 6), (1, 3, 33), (2, 3, 67), (199, 400, 50), (1, 200, 1), (0, 5, 0), (5, 5, 100)):
            r = m.evaluate_social_proof(packet(claimed_percent=None, evidence=ev(observed_count=k, sample_size=n), min_sample=1))
            self.assertEqual(r["percent_rounded"], pct, (k, n))

    def test_min_sample_n_and_n_plus_1(self):
        ok = m.evaluate_social_proof(packet(claimed_percent=None, evidence=ev(observed_count=15, sample_size=30)))
        self.assertTrue(ok["rules"]["min_sample_met"] and ok["deployment_allowed"])
        low = m.evaluate_social_proof(packet(claimed_percent=None, evidence=ev(observed_count=14, sample_size=29)))
        self.assertFalse(low["rules"]["min_sample_met"])
        self.assertEqual(low["blocked_reasons"], ["min_sample_not_met"])
        self.assertFalse(low["deployment_allowed"])
        self.assertIsNone(low["disclosure"])

    def test_claim_consistency(self):
        r = m.evaluate_social_proof(packet(claimed_percent=61))
        self.assertEqual(r["blocked_reasons"], ["claim_mismatch"])
        self.assertIs(r["rules"]["claim_consistent"], False)
        r = m.evaluate_social_proof(packet(claimed_percent=59))
        self.assertEqual(r["blocked_reasons"], ["claim_mismatch"])
        r = m.evaluate_social_proof(packet(claimed_percent=None))
        self.assertIsNone(r["rules"]["claim_consistent"])
        self.assertTrue(r["deployment_allowed"])
        p = packet(); del p["claimed_percent"]
        self.assertIsNone(m.evaluate_social_proof(p)["rules"]["claim_consistent"])

    def test_freshness_n_and_n_plus_1(self):
        fresh = m.evaluate_social_proof(packet(evidence=ev(as_of="2026-09-11")))  # exactly 30 days
        self.assertEqual(fresh["evidence"]["age_days"], 30)
        self.assertTrue(fresh["rules"]["evidence_fresh"])
        stale = m.evaluate_social_proof(packet(evidence=ev(as_of="2026-09-10")))  # 31 days
        self.assertEqual(stale["evidence"]["age_days"], 31)
        self.assertEqual(stale["blocked_reasons"], ["evidence_stale"])
        same = m.evaluate_social_proof(packet(evidence=ev(as_of="2026-10-11")))
        self.assertEqual(same["evidence"]["age_days"], 0)
        self.assertTrue(same["deployment_allowed"])

    def test_future_evidence_refused(self):
        self.assertEqual(refusal(self, packet(evidence=ev(as_of="2026-10-12"))), "SOCIAL98: evidence as_of is after packet as_of")

    def test_blocked_reasons_sorted_and_all(self):
        r = m.evaluate_social_proof(packet(claimed_percent=99, min_sample=101, evidence=ev(as_of="2025-01-01")))
        self.assertEqual(r["blocked_reasons"], ["claim_mismatch", "evidence_stale", "min_sample_not_met"])

    def test_determinism_no_mutation_no_alias(self):
        p = packet(); old = copy.deepcopy(p)
        a = m.evaluate_social_proof(p); b = m.evaluate_social_proof(copy.deepcopy(p))
        self.assertEqual(a, b); self.assertEqual(p, old)
        a["evidence"]["source"] = "x"; a["blocked_reasons"].append("x")
        self.assertEqual(p, old)

    def test_limits_not_aliased(self):
        r = m.evaluate_social_proof(packet())
        r["limits"]["claim"] = 1
        self.assertEqual(m.evaluate_social_proof(packet())["limits"]["claim"], 500)
        self.assertEqual(m.LIMITS["claim"], 500)

    def test_z_changes_interval(self):
        a = m.evaluate_social_proof(packet(z="196/100"))["wilson_interval"]
        b = m.evaluate_social_proof(packet(z="258/100"))["wilson_interval"]
        self.assertLess(Fraction(b[0]), Fraction(a[0])); self.assertGreater(Fraction(b[1]), Fraction(a[1]))
        self.assertEqual(m.evaluate_social_proof(packet(z="2"))["z"], "2")
        self.assertEqual(m.evaluate_social_proof(packet(z="196/100"))["z"], "49/25")


class Refusals(unittest.TestCase):
    def check(self, p, text):
        self.assertEqual(refusal(self, p), "SOCIAL98: " + text)

    def test_packet_shape(self):
        for bad in (None, [], "x", 3):
            self.check(bad, "packet must be a dict")
        p = packet(); p["extra"] = 1
        self.check(p, "packet keys must be claim, evidence, as_of, min_sample, max_age_days, z and optional claimed_percent")
        p = packet(); del p["z"]
        self.check(p, "packet keys must be claim, evidence, as_of, min_sample, max_age_days, z and optional claimed_percent")
        e = ev(); e["x"] = 1
        self.check(packet(evidence=e), "evidence keys must be exactly source, as_of, observed_count, sample_size")
        self.check(packet(evidence="s"), "evidence keys must be exactly source, as_of, observed_count, sample_size")

    def test_text_limits_n_and_n_plus_1(self):
        m.evaluate_social_proof(packet(claim="a" * 500, claimed_percent=None))
        self.check(packet(claim="a" * 501), "claim must be a nonblank string of at most 500 characters without control characters")
        m.evaluate_social_proof(packet(evidence=ev(source="s" * 200)))
        self.check(packet(evidence=ev(source="s" * 201)), "source must be a nonblank string of at most 200 characters without control characters")
        for bad in ("", "  ", 5, None, "a\nb", "a\x7fb"):
            self.check(packet(claim=bad), "claim must be a nonblank string of at most 500 characters without control characters")
            self.check(packet(evidence=ev(source=bad)), "source must be a nonblank string of at most 200 characters without control characters")

    def test_counts_n_and_n_plus_1(self):
        m.evaluate_social_proof(packet(claimed_percent=None, evidence=ev(observed_count=100, sample_size=100)))
        self.check(packet(evidence=ev(observed_count=101, sample_size=100)), "observed_count must be an integer within 0..sample_size")
        self.check(packet(evidence=ev(observed_count=-1)), "observed_count must be an integer within 0..sample_size")
        m.evaluate_social_proof(packet(claimed_percent=None, min_sample=1, evidence=ev(observed_count=0, sample_size=1)))
        self.check(packet(evidence=ev(observed_count=0, sample_size=0)), "sample_size must be an integer within 1..1000000000")
        m.evaluate_social_proof(packet(claimed_percent=None, min_sample=1, evidence=ev(observed_count=0, sample_size=10**9)))
        self.check(packet(evidence=ev(observed_count=0, sample_size=10**9 + 1)), "sample_size must be an integer within 1..1000000000")
        for bad in (True, 1.0, "5", None):
            self.check(packet(evidence=ev(sample_size=bad)), "sample_size must be an integer within 1..1000000000")
            self.check(packet(evidence=ev(observed_count=bad)), "observed_count must be an integer within 0..sample_size")

    def test_min_sample_and_age_bounds(self):
        m.evaluate_social_proof(packet(min_sample=1)); m.evaluate_social_proof(packet(min_sample=10**9))
        for bad in (0, 10**9 + 1, True, 1.5, "30"):
            self.check(packet(min_sample=bad), "min_sample must be an integer within 1..1000000000")
        m.evaluate_social_proof(packet(max_age_days=0)); m.evaluate_social_proof(packet(max_age_days=3650))
        for bad in (-1, 3651, True, 1.5, "30"):
            self.check(packet(max_age_days=bad), "max_age_days must be an integer within 0..3650")

    def test_claimed_percent_bounds(self):
        m.evaluate_social_proof(packet(claimed_percent=0)); m.evaluate_social_proof(packet(claimed_percent=100))
        for bad in (-1, 101, True, 60.0, "60"):
            self.check(packet(claimed_percent=bad), "claimed_percent must be an integer within 0..100")

    def test_z_grammar_and_bounds(self):
        for ok in ("1", "5", "196/100", "1/1", "5000000/1000000", "1000000/1000000"):
            m.evaluate_social_proof(packet(z=ok))
        for bad in ("0", "1/0", "-1", "0.5", "5000001/1000000", "6", "1e0", " 2", "2 ", "2\n", "\u0662", "٣/١", "12345678/1", "1/12345678", 2, 1.96, None, True, ""):
            self.check(packet(z=bad), "z must be a rational string p or p/q with 1 <= z <= 5 and components of at most 7 digits")

    def test_dates(self):
        for bad in ("2026-10-11\n", " 2026-10-11", "2026-10-11 ", "2026-1-1", "20261011", "2026-02-30", "\u0662\u0660\u0662\u0666-\u0661\u0660-\u0661\u0661", "", 5, None):
            self.check(packet(as_of=bad), "as_of must be an ASCII YYYY-MM-DD calendar date")
            self.check(packet(evidence=ev(as_of=bad)), "evidence as_of must be an ASCII YYYY-MM-DD calendar date")
        m.evaluate_social_proof(packet(as_of="2028-02-29", evidence=ev(as_of="2028-02-29")))

    def test_date_gate_independent_of_stdlib_parser(self):
        import datetime
        from unittest import mock

        class Lenient(datetime.date):
            @classmethod
            def fromisoformat(cls, value):
                return datetime.date(2026, 10, 11)

        with mock.patch.object(m, "date", Lenient):
            for bad in ("2026-10-11\n", "2026-10-11 ", " 2026-10-11", "2026-1-1", "20261011",
                        "\u0662\u0660\u0662\u0666-\u0661\u0660-\u0661\u0661", "2026-10-111", "x2026-10-11"):
                self.check(packet(as_of=bad), "as_of must be an ASCII YYYY-MM-DD calendar date")
                self.check(packet(evidence=ev(as_of=bad)), "evidence as_of must be an ASCII YYYY-MM-DD calendar date")
            m.evaluate_social_proof(packet())

    def test_reason_never_echoes_input(self):
        msg = refusal(self, packet(claim="SECRETWORD\x00"))
        self.assertNotIn("SECRETWORD", msg)
        self.assertTrue(msg.startswith("SOCIAL98: "))


class Surface(unittest.TestCase):
    def test_public_surface_and_offline(self):
        names = sorted(n for n in dir(m) if callable(getattr(m, n)) and not n.startswith("_")
                       and getattr(m, n).__module__ == "social_proof_deployment98")
        self.assertEqual(names, ["Social98Error", "evaluate_social_proof"])
        src = _P.read_text()
        for bad in ("import requests", "import urllib", "import socket", "import httpx", "subprocess", "open(", "random", "time.", "datetime.now", "float("):
            self.assertNotIn(bad, src, bad)
        self.assertNotIn("negotiation_behavior_0085_0109", src)
        self.assertIsInstance(m.Social98Error("x"), ValueError)

    def test_no_efficacy_or_persuasion_claims_in_output(self):
        r = m.evaluate_social_proof(packet())
        blob = repr(r).lower()
        for bad in ("persuad", "convert", "influence", "manipulat", "drive sales", "will increase"):
            self.assertNotIn(bad, blob)
        self.assertIn("not", r["boundary"].lower())


if __name__ == "__main__":
    unittest.main()
