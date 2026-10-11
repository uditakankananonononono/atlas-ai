import math
import unittest
from fractions import Fraction

from app.modules.m20_general_cognitive_worker import accelerated_life_testing1544 as al

P = "ACCLIF1544:"
KB = Fraction(8617333262, 10 ** 14)


import sys
import unicodedata

_CF = [chr(i) for i in range(sys.maxunicode + 1) if unicodedata.category(chr(i)) == "Cf"]


def lvl(i="s1", t=350, h=1000, n=10, f=0):
    return {"id": i, "temperature_k": t, "hours": h, "units_on_test": n, "failures": f}


def req(**k):
    r = {"model": "arrhenius", "failure_mechanism": "oxide wear-out", "activation_energy_ev": 0.7,
         "use_temperature_k": 300, "stress_levels": [lvl("s1", 350, 1000, 10, 1), lvl("s2", 400, 500, 20, 2)]}
    r.update(k)
    return r


def err(r):
    try:
        al.run(r)
    except ValueError as e:
        return str(e)
    raise AssertionError("no refusal")


def oracle_x(ea, tuse, ttest):
    return Fraction(str(ea)) / KB * (1 / Fraction(str(tuse)) - 1 / Fraction(str(ttest)))


class Behaviour(unittest.TestCase):
    def test_exponent_and_factor_match_independent_oracle(self):
        out = al.run(req())
        x = oracle_x(0.7, 300, 350)
        lv = out["levels"][0]
        self.assertEqual(lv["exponent"], "%d/%d" % (x.numerator, x.denominator))
        self.assertAlmostEqual(lv["acceleration_factor"], math.exp(float(x)), places=9)
        self.assertGreater(lv["acceleration_factor"], 1)
        self.assertEqual([l["id"] for l in out["levels"]], ["s1", "s2"])

    def test_device_hours_exact_and_totals(self):
        out = al.run(req())
        self.assertEqual(out["levels"][0]["device_hours"], "10000")
        self.assertEqual(out["levels"][1]["device_hours"], "10000")
        self.assertEqual(out["totals"], {"device_hours": "20000", "failures": 3, "units_on_test": 30})

    def test_fractional_hours_exact(self):
        out = al.run(req(stress_levels=[lvl("a", 350, 0.1, 3, 0)]))
        self.assertEqual(out["levels"][0]["device_hours"], "0.3")

    def test_use_temperature_level_is_unity(self):
        out = al.run(req(stress_levels=[lvl("a", 300)]))
        self.assertEqual(out["levels"][0]["exponent"], "0")
        self.assertEqual(out["levels"][0]["acceleration_factor"], 1.0)
        self.assertEqual(out["levels"][0]["stress_relation"], "at_use")

    def test_below_use_is_flagged_not_refused(self):
        out = al.run(req(stress_levels=[lvl("a", 280)]))
        self.assertEqual(out["levels"][0]["stress_relation"], "below_use")
        self.assertLess(out["levels"][0]["acceleration_factor"], 1)
        self.assertEqual(al.run(req())["levels"][0]["stress_relation"], "above_use")

    def test_zero_failures_allowed_and_no_life_fields(self):
        out = al.run(req(stress_levels=[lvl("a", 350, 10, 1, 0)]))
        self.assertEqual(out["status"], "supplied_stress_bookkeeping_only")
        self.assertIs(out["mechanism_equivalence_validated"], False)
        for banned in ("life", "mttf", "equivalent_use_hours", "reliability"):
            self.assertFalse(any(banned in k for k in out), banned)
            self.assertFalse(any(banned in k for l in out["levels"] for k in l), banned)

    def test_deterministic_and_input_not_mutated(self):
        r = req()
        import copy
        before = copy.deepcopy(r)
        self.assertEqual(al.run(r), al.run(r))
        self.assertEqual(r, before)


class Refusals(unittest.TestCase):
    def test_request_shape(self):
        self.assertEqual(err([]), P + "invalid_request")
        self.assertEqual(err(dict(req(), extra=1)), P + "unknown_key")
        self.assertEqual(err(dict(req(), **{"k%d" % i: 1 for i in range(65)})), P + "invalid_count:keys")

    def test_model(self):
        self.assertEqual(err(req(model="eyring")), P + "unsupported_model")
        self.assertEqual(err(req(model=1)), P + "unsupported_model")
        r = req(); del r["model"]
        self.assertEqual(err(r), P + "unsupported_model")

    def test_text_fields(self):
        for bad in ("", "  ", 5, "a\x00b", "a\u200bb", "x" * 129):
            self.assertEqual(err(req(failure_mechanism=bad)), P + "invalid_text:failure_mechanism", repr(bad))
            self.assertEqual(err(req(stress_levels=[lvl(i=bad)])), P + "invalid_text:id", repr(bad))
        self.assertEqual(al.run(req(failure_mechanism="x" * 128))["failure_mechanism"], "x" * 128)

    def test_unicode_categories_full_cf_and_zs_accepted(self):
        cf = _CF
        self.assertIn("\u00ad", cf)
        self.assertIn("\u2060", cf)
        for ch in cf + ["\x00", "\x1f", "\x7f", "\x85", "\u2028", "\u2029"]:
            self.assertEqual(err(req(failure_mechanism="a" + ch + "b")), P + "invalid_text:failure_mechanism", hex(ord(ch)))
            self.assertEqual(err(req(stress_levels=[lvl(i="a" + ch)])), P + "invalid_text:id", hex(ord(ch)))
        for ch in ("\u00a0", "\u2003", "\u3000", " "):
            self.assertEqual(al.run(req(failure_mechanism="a" + ch + "b"))["failure_mechanism"], "a" + ch + "b")

    def test_length_cap_applies_before_unicode_or_strip(self):
        # over-cap text made only of refusable and blank characters still gives the same fixed code
        self.assertEqual(err(req(failure_mechanism=" " * 129)), P + "invalid_text:failure_mechanism")
        self.assertEqual(err(req(failure_mechanism="\u200b" * 10 ** 5)), P + "invalid_text:failure_mechanism")

    def test_top_level_key_cap_n_and_n_plus_1(self):
        base = req()
        pad = lambda n: {"k%d" % i: 1 for i in range(n - len(base))}
        self.assertEqual(err(dict(base, **pad(64))), P + "unknown_key")
        self.assertEqual(err(dict(base, **pad(65))), P + "invalid_count:keys")

    def test_level_key_cap_n_and_n_plus_1(self):
        base = lvl()
        pad = lambda n: {"k%d" % i: 1 for i in range(n - len(base))}
        self.assertEqual(err(req(stress_levels=[dict(base, **pad(64))])), P + "unknown_key")
        self.assertEqual(err(req(stress_levels=[dict(base, **pad(65))])), P + "invalid_count:keys")

    def test_exponent_exactly_700_allowed_and_above_refused(self):
        # Ea 0.8617333262 eV / kB = 10**4 K exactly, so x = 10**4 * (1/Tuse - 1/T)
        ok = al.run(req(activation_energy_ev=0.8617333262, use_temperature_k=12.5, stress_levels=[lvl(t=100)]))
        self.assertEqual(ok["levels"][0]["exponent"], "700")
        self.assertEqual(oracle_x(0.8617333262, 12.5, 100), 700)
        self.assertEqual(err(req(activation_energy_ev=0.8617333262, use_temperature_k=12.5, stress_levels=[lvl(t=101)])), P + "invalid_range:exponent")
        neg = al.run(req(activation_energy_ev=0.8617333262, use_temperature_k=100, stress_levels=[lvl(t=12.5)]))
        self.assertEqual(neg["levels"][0]["exponent"], "-700")
        self.assertEqual(err(req(activation_energy_ev=0.8617333262, use_temperature_k=101, stress_levels=[lvl(t=12.5)])), P + "invalid_range:exponent")

    def test_negative_exponent_string_matches_oracle(self):
        x = oracle_x(0.7, 300, 280)
        self.assertLess(x, 0)
        self.assertEqual(al.run(req(stress_levels=[lvl(t=280)]))["levels"][0]["exponent"], "-%d/%d" % (-x.numerator, x.denominator))

    def test_device_hours_exact_decimal_rendering(self):
        for hours, units in ((1234.56789, 7), (0.001, 1), (12.5, 3), (0.125, 8), (1000000, 3), (0.5, 1), (0.25, 1), (0.0625, 1), (0.375, 1)):
            exact = Fraction(str(hours)) * units
            out = al.run(req(stress_levels=[lvl(h=hours, n=units)]))["levels"][0]["device_hours"]
            self.assertEqual(Fraction(out), exact, (hours, units))
            self.assertNotIn("e", out)
            self.assertFalse("." in out and out.endswith("0"))
        self.assertEqual(al.run(req(stress_levels=[lvl(h=1234.56789, n=7)]))["levels"][0]["device_hours"], "8641.97523")

    def test_numbers(self):
        for k in ("activation_energy_ev", "use_temperature_k"):
            for bad in (0, -1, True, "1", None, float("nan"), float("inf"), 10 ** 13):
                self.assertEqual(err(req(**{k: bad})), P + "invalid_number:" + k, (k, bad))
        for k in ("temperature_k", "hours"):
            for bad in (0, -1, True, "1", None, float("nan"), float("inf")):
                self.assertEqual(err(req(stress_levels=[dict(lvl(), **{k: bad})])), P + "invalid_number:" + k, (k, bad))
        for k in ("units_on_test", "failures"):
            for bad in (-1, 1.5, True, "1", None):
                self.assertEqual(err(req(stress_levels=[dict(lvl(), **{k: bad})])), P + "invalid_number:" + k, (k, bad))
        self.assertEqual(err(req(stress_levels=[dict(lvl(), units_on_test=0)])), P + "invalid_number:units_on_test")

    def test_bounds_n_and_n_plus_1(self):
        ok = al.run(req(activation_energy_ev=10, use_temperature_k=300, stress_levels=[lvl(t=300)]))
        self.assertEqual(ok["levels"][0]["acceleration_factor"], 1.0)
        self.assertEqual(err(req(activation_energy_ev=10.5)), P + "invalid_number:activation_energy_ev")
        self.assertEqual(err(req(use_temperature_k=10001)), P + "invalid_number:use_temperature_k")
        self.assertEqual(al.run(req(use_temperature_k=10000, stress_levels=[lvl(t=10000)]))["levels"][0]["acceleration_factor"], 1.0)
        self.assertEqual(err(req(stress_levels=[lvl(t=10001)])), P + "invalid_number:temperature_k")
        self.assertEqual(al.run(req(stress_levels=[lvl(h=10 ** 9)]))["levels"][0]["device_hours"], "10000000000")
        self.assertEqual(err(req(stress_levels=[lvl(h=10 ** 9 + 1)])), P + "invalid_number:hours")
        self.assertEqual(al.run(req(stress_levels=[lvl(n=10 ** 6, f=0)]))["totals"]["units_on_test"], 10 ** 6)
        self.assertEqual(err(req(stress_levels=[lvl(n=10 ** 6 + 1)])), P + "invalid_number:units_on_test")

    def test_failures_not_above_units(self):
        self.assertEqual(al.run(req(stress_levels=[lvl(n=5, f=5)]))["totals"]["failures"], 5)
        self.assertEqual(err(req(stress_levels=[lvl(n=5, f=6)])), P + "failures_exceed_units")

    def test_exponent_range(self):
        # exponent magnitude above 700 refused (would overflow or underflow float)
        self.assertEqual(err(req(activation_energy_ev=10, use_temperature_k=1, stress_levels=[lvl(t=10000)])), P + "invalid_range:exponent")
        self.assertEqual(err(req(activation_energy_ev=10, use_temperature_k=10000, stress_levels=[lvl(t=1)])), P + "invalid_range:exponent")

    def test_exponent_boundary_exact(self):
        # pick Ea so that exponent is just under/over 700 using exact arithmetic
        tuse, tt = Fraction(100), Fraction(10000)
        per_ev = (1 / tuse - 1 / tt) / KB
        ea_ok = float(Fraction(699) / per_ev)
        ea_bad = float(Fraction(701) / per_ev)
        self.assertLess(oracle_x(ea_ok, 100, 10000), 700)
        self.assertGreater(oracle_x(ea_bad, 100, 10000), 700)
        al.run(req(activation_energy_ev=ea_ok, use_temperature_k=100, stress_levels=[lvl(t=10000)]))
        self.assertEqual(err(req(activation_energy_ev=ea_bad, use_temperature_k=100, stress_levels=[lvl(t=10000)])), P + "invalid_range:exponent")

    def test_levels_shape(self):
        self.assertEqual(err(req(stress_levels=[])), P + "invalid_count:stress_levels")
        self.assertEqual(err(req(stress_levels="ab")), P + "invalid_count:stress_levels")
        self.assertEqual(err(req(stress_levels={})), P + "invalid_count:stress_levels")
        self.assertEqual(err(req(stress_levels=[1])), P + "invalid_item:stress_levels")
        self.assertEqual(err(req(stress_levels=[dict(lvl(), z=1)])), P + "unknown_key")
        self.assertEqual(err(req(stress_levels=[lvl("a"), lvl("a")])), P + "duplicate_id:stress_levels")
        self.assertEqual(len(al.run(req(stress_levels=[lvl("i%d" % i) for i in range(32)]))["levels"]), 32)
        self.assertEqual(err(req(stress_levels=[lvl("i%d" % i) for i in range(33)])), P + "invalid_count:stress_levels")

    def test_level_key_cap_before_iteration(self):
        self.assertEqual(err(req(stress_levels=[dict(lvl(), **{"k%d" % i: 1 for i in range(65)})])), P + "invalid_count:keys")

    def test_ambient_decimal_context_irrelevant(self):
        import decimal
        base = al.run(req())
        ctx = decimal.getcontext().copy()
        try:
            decimal.getcontext().prec = 3
            decimal.getcontext().rounding = decimal.ROUND_DOWN
            self.assertEqual(al.run(req()), base)
        finally:
            decimal.setcontext(ctx)

    def test_big_int_guard(self):
        self.assertEqual(err(req(use_temperature_k=2 ** 70)), P + "invalid_number:use_temperature_k")

    def test_no_text_echo(self):
        self.assertNotIn("SECRETWORD", err(req(failure_mechanism="SECRETWORD\x00")))


class SpyKey(str):
    """str subclass whose hash/eq calls are counted. Mechanics (grounded by running): building a dict with this key
    calls __hash__ during construction; set(d) on an exact dict reuses stored hashes, but the later set difference and
    lookups call __eq__. The counters are reset after the input is built and must stay empty when the exact-type check
    refuses first. This makes no claim about hashing done while the caller builds the input."""
    calls = []

    def __hash__(self):
        SpyKey.calls.append("hash")
        return str.__hash__(self)

    def __eq__(self, other):
        SpyKey.calls.append("eq")
        return str.__eq__(self, other)


def _shapes(key):
    root = req()
    lv = lvl()
    return {
        "root": {**{k: v for k, v in root.items() if k != "model"}, key("model"): "arrhenius"},
        "level": {**root, "stress_levels": [{**{k: v for k, v in lv.items() if k != "id"}, key("id"): "s1"}]},
    }


class KeyTypeFirst(unittest.TestCase):
    def test_exact_str_keys_accepted(self):
        for name, r in _shapes(str).items():
            self.assertEqual(al.run(r)["model"], "arrhenius", name)

    def test_str_subclass_key_refused_before_any_comparison(self):
        for name, r in _shapes(SpyKey).items():
            SpyKey.calls.clear()
            self.assertEqual(err(r), P + "unknown_key", name)
            self.assertEqual(SpyKey.calls, [], name)

    def test_non_str_keys_refused(self):
        for name, r in _shapes(lambda k: 5).items():
            self.assertEqual(err(r), P + "unknown_key", name)

    def test_count_cap_first_with_subclass_keys(self):
        big = {SpyKey("k%d" % i): 1 for i in range(65)}
        SpyKey.calls.clear()
        self.assertEqual(err(big), P + "invalid_count:keys")
        self.assertEqual(SpyKey.calls, [])


class ModelFirst(unittest.TestCase):
    """_model order: exact type str, then raw length cap, then the enum compare."""

    def test_arbitrary_eq_never_called_and_subclass_refused(self):
        calls = []

        class Evil:
            def __eq__(self, other):
                calls.append("eq")
                return True

            def __ne__(self, other):
                calls.append("ne")
                return False

            __hash__ = None

        class SubStr(str):
            def __eq__(self, other):
                calls.append("eq")
                return True

            def __ne__(self, other):
                calls.append("ne")
                return False

            __hash__ = str.__hash__

        for bad in (Evil(), SubStr("arrhenius")):
            self.assertEqual(err(req(model=bad)), P + "unsupported_model", type(bad).__name__)
        self.assertEqual(calls, [])

    def test_oversize_and_near_miss_refused_exact_accepted(self):
        for bad in ("arrhenius" + "x" * 10 ** 6, "x" * 129, "Arrhenius", "arrhenius ", "", None, 1, ["arrhenius"], b"arrhenius"):
            self.assertEqual(err(req(model=bad)), P + "unsupported_model", repr(bad)[:30])
        self.assertEqual(al.run(req(model="arrhenius"))["model"], "arrhenius")



class ClosingFieldRefusalPins(unittest.TestCase):
    def test_zero_level_temperature_exact_field(self):
        self.assertEqual(err(req(stress_levels=[lvl(t=0)])), P + "invalid_number:temperature_k")

    def test_negative_and_boolean_failures_exact_field(self):
        for failures in (-1, True, False):
            with self.subTest(failures=failures):
                self.assertEqual(err(req(stress_levels=[lvl(f=failures)])), P + "invalid_number:failures")

    def test_zero_units_exact_field(self):
        self.assertEqual(err(req(stress_levels=[lvl(n=0)])), P + "invalid_number:units_on_test")

class ClosingLevelOutputPins(unittest.TestCase):
    def test_exact_level_keys_and_supplied_values(self):
        out = al.run(req(stress_levels=[lvl(t=350, n=10, f=2)]))
        level = out["levels"][0]
        self.assertEqual(set(level), {"id", "temperature_k", "exponent", "acceleration_factor", "stress_relation", "device_hours", "failures", "units_on_test"})
        self.assertEqual(level["temperature_k"], "350")
        self.assertEqual(level["failures"], 2)
        self.assertEqual(level["units_on_test"], 10)

if __name__ == "__main__":
    unittest.main()
