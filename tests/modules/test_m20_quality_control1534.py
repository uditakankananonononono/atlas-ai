"""Row 1534 QUALC1534 tests. Hermetic, stdlib unittest, N/N+1 pins."""
import copy, importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/quality_control1534.py"
_spec = importlib.util.spec_from_file_location("quality_control1534", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["quality_control1534"] = m
_spec.loader.exec_module(m)


def meas(i, v):
    return {"id": i, "value": v}


def packet(**kw):
    d = {"unit": "mm", "lower_spec": "0", "upper_spec": "3", "measurements": [meas("a", "1"), meas("b", "2"), meas("c", "9")]}
    d.update(kw)
    return d


def run(p):
    return m.evaluate_spec_conformance(p)


def refusal(test, p):
    with test.assertRaises(ValueError) as cm:
        run(p)
    return str(cm.exception)


class Compute(unittest.TestCase):
    def test_basic(self):
        r = run(packet())
        self.assertEqual((r["total"], r["conforming"], r["nonconforming"]), (3, 2, 1))
        self.assertEqual(r["conforming_fraction"], {"numerator": 2, "denominator": 3, "decimal_floor_6": "0.666666"})
        self.assertEqual(r["nonconforming_items"], [{"id": "c", "value": "9.000000", "reason": "above_upper_spec"}])
        self.assertEqual(r["unit"], "mm")
        self.assertEqual(r["lower_spec"], "0.000000")
        self.assertEqual(r["upper_spec"], "3.000000")
        self.assertEqual((r["observed_min"], r["observed_max"]), ("1.000000", "9.000000"))

    def test_boundary_n_and_n_plus_1(self):
        r = run(packet(measurements=[meas("a", "0"), meas("b", "3"), meas("c", "-0.000001"), meas("d", "3.000001")]))
        status = {x["id"]: x["status"] for x in r["items"]}
        self.assertEqual(status, {"a": "conforming", "b": "conforming", "c": "nonconforming_below_lower_spec", "d": "nonconforming_above_upper_spec"})
        self.assertEqual([x["reason"] for x in r["nonconforming_items"]], ["below_lower_spec", "above_upper_spec"])
        self.assertEqual([x["id"] for x in r["nonconforming_items"]], ["c", "d"])

    def test_equal_specs_allowed(self):
        r = run(packet(lower_spec="2", upper_spec="2", measurements=[meas("a", "2"), meas("b", "2.000001")]))
        self.assertEqual((r["conforming"], r["nonconforming"]), (1, 1))

    def test_all_conforming_and_none(self):
        r = run(packet(measurements=[meas("a", "1")]))
        self.assertEqual(r["nonconforming_items"], [])
        self.assertEqual(r["conforming_fraction"], {"numerator": 1, "denominator": 1, "decimal_floor_6": "1.000000"})
        r = run(packet(measurements=[meas("a", "9")]))
        self.assertEqual(r["conforming_fraction"], {"numerator": 0, "denominator": 1, "decimal_floor_6": "0.000000"})

    def test_fraction_floor_not_round(self):
        ms = [meas("m%02d" % i, "1" if i < 2 else "9") for i in range(3)]
        self.assertEqual(run(packet(measurements=ms))["conforming_fraction"]["decimal_floor_6"], "0.666666")
        ms = [meas("m%d" % i, "1" if i < 1 else "9") for i in range(3)]
        self.assertEqual(run(packet(measurements=ms))["conforming_fraction"]["decimal_floor_6"], "0.333333")

    def test_negative_specs(self):
        r = run(packet(lower_spec="-3", upper_spec="-1", measurements=[meas("a", "-2"), meas("b", "-0.5"), meas("c", "-3.5")]))
        self.assertEqual([x["status"] for x in r["items"]],
                         ["conforming", "nonconforming_above_upper_spec", "nonconforming_below_lower_spec"])
        self.assertEqual(r["observed_min"], "-3.500000")
        self.assertEqual(r["observed_max"], "-0.500000")

    def test_sorted_by_id_deterministic_no_mutation(self):
        p = packet(measurements=[meas("c", "9"), meas("a", "1"), meas("b", "2")])
        before = copy.deepcopy(p)
        r1, r2 = run(p), run(p)
        self.assertEqual(r1, r2)
        self.assertEqual(p, before)
        self.assertEqual([x["id"] for x in r1["items"]], ["a", "b", "c"])

    def test_unit_echoed_per_input_and_item_values(self):
        for u in ("mm", "V", "K"):
            self.assertEqual(run(packet(unit=u))["unit"], u)
        self.assertEqual(run(packet())["items"], [{"id": "a", "value": "1.000000", "status": "conforming"},
                                                  {"id": "b", "value": "2.000000", "status": "conforming"},
                                                  {"id": "c", "value": "9.000000", "status": "nonconforming_above_upper_spec"}])

    def test_disposition_not_assigned(self):
        r = run(packet())
        self.assertEqual(r["disposition"], "none_assigned")
        self.assertIs(r["disposition_requires_approval"], True)
        self.assertIs(r["disposition_authority"], False)
        self.assertEqual(r["scope"], "declared_measurements_vs_declared_specs_bookkeeping_only")
        self.assertIn("approval", r["boundary"])
        low = repr(r).lower()
        for w in ("accepted", "rejected", "released", "scrap", "certified"):
            self.assertNotIn(w, low)


class Refusals(unittest.TestCase):
    def check(self, p, code):
        self.assertEqual(refusal(self, p), "QUALC1534:" + code)

    def test_packet(self):
        for bad in (None, [], "x", 3):
            self.check(bad, "invalid_packet")
        p = packet(); p["extra"] = 1
        self.check(p, "unknown_fields:packet")
        p = packet(); del p["unit"]
        self.check(p, "unknown_fields:packet")

    def test_unit(self):
        run(packet(unit="x" * 16))
        for bad in ("", " ", "x" * 17, None, 1, "m\nm"):
            self.check(packet(unit=bad), "invalid_text:unit")

    def test_specs(self):
        run(packet(lower_spec="-999999999999.999999", upper_spec="999999999999.999999"))
        for k in ("lower_spec", "upper_spec"):
            for bad in ("+1", "1e3", "1.", ".5", "1.0000001", "-1234567890123", "", " 1", "1 ", "\uff11", 1, 1.0, None, True):
                self.check(packet(**{k: bad}), "invalid_number:" + k)
        self.check(packet(lower_spec="3.000001", upper_spec="3"), "spec_order")
        self.check(packet(lower_spec="1", upper_spec="0"), "spec_order")

    def test_count(self):
        run(packet(measurements=[meas("m%d" % i, "1") for i in range(256)]))
        self.check(packet(measurements=[meas("m%d" % i, "1") for i in range(257)]), "invalid_count:measurements")
        self.check(packet(measurements=[]), "invalid_count:measurements")
        self.check(packet(measurements=(meas("a", "1"),)), "invalid_count:measurements")

    def test_count_cap_checked_before_any_other_parse(self):
        bad = packet(unit="", lower_spec="x", upper_spec="y", measurements=[meas("m%d" % i, "z") for i in range(257)])
        self.check(bad, "invalid_count:measurements")
        bad = packet(unit="", lower_spec="x", upper_spec="y", measurements=[])
        self.check(bad, "invalid_count:measurements")
        self.assertEqual(refusal(self, packet(unit="")), "QUALC1534:invalid_text:unit")

    def test_unit_is_label_only(self):
        r = run(packet(unit="degC"))
        self.assertEqual(r["unit"], "degC")
        self.assertEqual(r["observed_max"], "9.000000")   # no conversion applied
        self.assertNotIn("convert", r["boundary"].lower().replace("no conversion", ""))
        self.assertIn("unit is a label", r["boundary"].lower())

    def test_records(self):
        self.check(packet(measurements=["x"]), "invalid_record:measurements")
        r = meas("a", "1"); r["extra"] = 1
        self.check(packet(measurements=[r]), "invalid_fields:measurements")
        self.check(packet(measurements=[{"id": "a"}]), "invalid_fields:measurements")
        self.check(packet(measurements=[meas("a", "1"), meas("a", "2")]), "duplicate_id")

    def test_id_text(self):
        run(packet(measurements=[meas("A" * 128, "1")]))
        for bad in ("", "  ", "a" * 129, None, 3, "a\tb", "a\x7fb"):
            self.check(packet(measurements=[meas(bad, "1")]), "invalid_text:id")

    def test_value_numbers(self):
        run(packet(measurements=[meas("a", "-999999999999.999999")]))
        for bad in ("+1", "1e3", "-1.0000001", "-", "-1234567890123", "", 1, 1.0, None, "1\n", "nan", True):
            self.check(packet(measurements=[meas("a", bad)]), "invalid_number:value")

    def test_reason_never_echoes_input(self):
        secret = "SECRET-VALUE-XYZ"
        for p in (packet(unit=secret * 20), packet(lower_spec=secret), packet(measurements=[meas(secret * 20, "1")]),
                  packet(measurements=[meas("a", secret)])):
            self.assertNotIn(secret, refusal(self, p))

    def test_surface_and_offline(self):
        self.assertEqual([n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))
                          and getattr(getattr(m, n), "__module__", None) == "quality_control1534"], ["evaluate_spec_conformance"])
        src = _P.read_text()
        for banned in ("import socket", "import requests", "urllib", "subprocess", "import os", "open(", "float(", "engineering_1510_1559"):
            self.assertNotIn(banned, src)


class UnicodeText(unittest.TestCase):
    HIDDEN = ("\x85", "\u2028", "\u2029", "\u202e", "\u200b", "\ufeff", "\x7f", "\u200f", "\u202a", "\u2066", "\u2069", "\u200c", "\x00", "\x1f", "\u200e", "\u202d", "\u2067", "\u2068")
    ALLOWED = ("a b", "\u00e9", "\u00b5m", "\u4e2d\u6587", "\u00a0x", "\u2010x", "\u200a" + "x")

    def test_hidden_refused_on_unit_and_id(self):
        for ch in self.HIDDEN:
            self.assertEqual(refusal(self, packet(unit="a%sb" % ch)), "QUALC1534:invalid_text:unit")
            self.assertEqual(refusal(self, packet(measurements=[meas("a%sb" % ch, "1")])), "QUALC1534:invalid_text:id")
            self.assertNotIn(ch, refusal(self, packet(unit=ch)))

    def test_printable_non_ascii_and_spaces_allowed(self):
        for text in self.ALLOWED:
            r = run(packet(unit=text, measurements=[meas(text, "1")]))
            self.assertEqual(r["unit"], text)


if __name__ == "__main__":
    unittest.main()
