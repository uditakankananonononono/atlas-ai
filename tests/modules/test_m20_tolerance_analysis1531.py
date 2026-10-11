"""Row 1531 TOLER1531 tests. Hermetic, stdlib unittest, N/N+1 pins."""
import copy, importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/tolerance_analysis1531.py"
_spec = importlib.util.spec_from_file_location("tolerance_analysis1531", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["tolerance_analysis1531"] = m
_spec.loader.exec_module(m)


def comp(i, sign=1, nominal="1", plus="0", minus="0", ref="drawing-A"):
    return {"id": i, "sign": sign, "nominal": nominal, "plus": plus, "minus": minus, "source_ref": ref}


def packet(**kw):
    d = {"unit": "mm", "assumption": "rss_independent",
         "components": [comp("A", 1, "10", "0.1", "0.2"), comp("B", -1, "4", "0.05", "0.15"), comp("C", 1, "3", "0.02", "0.04")]}
    d.update(kw)
    return d


def refusal(test, p):
    with test.assertRaises(ValueError) as cm:
        m.analyze_tolerance_stack(p)
    return str(cm.exception)


class Compute(unittest.TestCase):
    def test_exact_stack(self):
        r = m.analyze_tolerance_stack(packet())
        self.assertEqual(r["unit"], "mm")
        self.assertEqual(r["nominal_stack"], "9.000000")
        wc = r["worst_case"]
        self.assertEqual((wc["upper_deviation"], wc["lower_deviation"]), ("0.270000", "0.290000"))
        self.assertEqual((wc["max"], wc["min"]), ("9.270000", "8.710000"))
        self.assertEqual(r["contributions"], [
            {"id": "A", "signed_nominal": "10.000000", "upper": "0.100000", "lower": "0.200000", "source_ref": "drawing-A"},
            {"id": "B", "signed_nominal": "-4.000000", "upper": "0.150000", "lower": "0.050000", "source_ref": "drawing-A"},
            {"id": "C", "signed_nominal": "3.000000", "upper": "0.020000", "lower": "0.040000", "source_ref": "drawing-A"}])

    def test_rss_bounds_exact(self):
        r = m.analyze_tolerance_stack(packet())["rss"]
        self.assertEqual(r["assumption"], "rss_independent")
        self.assertEqual(r["upper_deviation_squared"], "0.032900000000")
        self.assertEqual(r["lower_deviation_squared"], "0.044100000000")
        self.assertEqual(r["upper_deviation_bounds"], ["0.181383", "0.181384"])  # not a perfect square: bracket
        self.assertEqual(r["lower_deviation_bounds"], ["0.210000", "0.210000"])   # perfect square: exact
        self.assertEqual((r["max_bounds"][0], r["max_bounds"][1]), ("9.181383", "9.181384"))
        self.assertEqual((r["min_bounds"][0], r["min_bounds"][1]), ("8.790000", "8.790000"))
        self.assertIn("independent", r["statement"])

    def test_classic_3_4_5(self):
        p = packet(components=[comp("a", 1, "2", "0.3", "0.3"), comp("b", 1, "3", "0.4", "0.4")])
        r = m.analyze_tolerance_stack(p)
        self.assertEqual(r["nominal_stack"], "5.000000")
        self.assertEqual(r["worst_case"]["upper_deviation"], "0.700000")
        self.assertEqual(r["rss"]["upper_deviation_bounds"], ["0.500000", "0.500000"])

    def test_sign_flips_swap_sides(self):
        a = m.analyze_tolerance_stack(packet(components=[comp("a", 1, "5", "0.5", "0.1")]))
        b = m.analyze_tolerance_stack(packet(components=[comp("a", -1, "5", "0.5", "0.1")]))
        self.assertEqual((a["worst_case"]["upper_deviation"], a["worst_case"]["lower_deviation"]), ("0.500000", "0.100000"))
        self.assertEqual((b["worst_case"]["upper_deviation"], b["worst_case"]["lower_deviation"]), ("0.100000", "0.500000"))
        self.assertEqual(b["nominal_stack"], "-5.000000")

    def test_worst_case_only_has_no_rss(self):
        r = m.analyze_tolerance_stack(packet(assumption="worst_case_only"))
        self.assertIsNone(r["rss"])
        self.assertIsNone(r["limits_check"])

    def test_limits_n_and_n_plus_1(self):
        base = packet(assumption="worst_case_only")
        def chk(lo, hi):
            return m.analyze_tolerance_stack(dict(base, limits={"min": lo, "max": hi}))["limits_check"]
        self.assertTrue(chk("8.710000", "9.270000")["worst_case_within_limits"])   # exactly at both limits
        self.assertFalse(chk("8.710001", "9.270000")["worst_case_within_limits"])  # min limit N+1 micro
        self.assertFalse(chk("8.710000", "9.269999")["worst_case_within_limits"])  # max limit N-1 micro
        self.assertEqual(chk("8", "10"), {"min": "8.000000", "max": "10.000000", "worst_case_within_limits": True, "rss_within_limits": None})

    def test_limits_rss_outward_bracket(self):
        p = packet(limits={"min": "8.79", "max": "9.181384"})
        self.assertTrue(m.analyze_tolerance_stack(p)["limits_check"]["rss_within_limits"])
        p = packet(limits={"min": "8.79", "max": "9.181383"})  # upper end of the outward RSS bracket (9.181384) is above max 9.181383
        self.assertFalse(m.analyze_tolerance_stack(p)["limits_check"]["rss_within_limits"])
        p = packet(limits={"min": "8.790001", "max": "9.5"})
        self.assertFalse(m.analyze_tolerance_stack(p)["limits_check"]["rss_within_limits"])

    def test_symmetric_rss_outward_rounding_pin(self):
        p = packet(components=[comp("A", 1, "5", "1", "1"), comp("B", 1, "5", "1", "1")])
        r = m.analyze_tolerance_stack(p)["rss"]
        self.assertEqual(r["upper_deviation_squared"], "2.000000000000")
        self.assertEqual(r["upper_deviation_bounds"], ["1.414213", "1.414214"])
        self.assertEqual(r["lower_deviation_bounds"], ["1.414213", "1.414214"])
        self.assertEqual(r["max_bounds"], ["11.414213", "11.414214"])
        self.assertEqual(r["min_bounds"], ["8.585786", "8.585787"])
        p["limits"] = {"min": "8.585786", "max": "11.414214"}   # outward ends exactly on the limits
        self.assertTrue(m.analyze_tolerance_stack(p)["limits_check"]["rss_within_limits"])
        p["limits"] = {"min": "8.585787", "max": "11.414214"}
        self.assertFalse(m.analyze_tolerance_stack(p)["limits_check"]["rss_within_limits"])
        p["limits"] = {"min": "8.585786", "max": "11.414213"}
        self.assertFalse(m.analyze_tolerance_stack(p)["limits_check"]["rss_within_limits"])

    def test_asymmetric_rss_directions_independent_fixture(self):
        p = packet(components=[comp("A", 1, "10", "0.3", "0.1"), comp("B", 1, "5", "0.4", "0.2")])
        r = m.analyze_tolerance_stack(p)["rss"]
        self.assertEqual(r["upper_deviation_bounds"], ["0.500000", "0.500000"])   # sqrt(0.09+0.16)
        self.assertEqual(r["lower_deviation_bounds"], ["0.223606", "0.223607"])   # sqrt(0.01+0.04)
        self.assertEqual(r["max_bounds"], ["15.500000", "15.500000"])
        self.assertEqual(r["min_bounds"], ["14.776393", "14.776394"])

    def test_distribution_assumption_string(self):
        r = m.analyze_tolerance_stack(packet())["rss"]
        self.assertEqual(r["distribution_assumption"], "independent components, RSS leg only")
        self.assertIsNone(m.analyze_tolerance_stack(packet(assumption="worst_case_only"))["rss"])

    def test_sorted_by_id_and_determinism_no_mutation(self):
        p = packet(); old = copy.deepcopy(p)
        p["components"].reverse()
        a = m.analyze_tolerance_stack(p); self.assertEqual([c["id"] for c in a["contributions"]], ["A", "B", "C"])
        self.assertEqual(a, m.analyze_tolerance_stack(copy.deepcopy(p)))
        p["components"].reverse(); self.assertEqual(p, old)
        a["contributions"][0]["id"] = "x"; self.assertEqual(p, old)

    def test_decimal_grammar_accepts(self):
        for ok in ("0", "-0", "1", "-1", "123456789012", "-123456789012", "0.000001", "1.5", "999999999999.999999"):
            m.analyze_tolerance_stack(packet(components=[comp("a", 1, ok)]))
        for ok in ("0", "0.000001", "123456789012.999999"):
            m.analyze_tolerance_stack(packet(components=[comp("a", 1, "1", ok, ok)]))

    def test_scope_and_boundary(self):
        r = m.analyze_tolerance_stack(packet())
        self.assertEqual(r["scope"], "linear_1d_declared_values_only")
        self.assertIs(r["physically_verified"], False)
        self.assertTrue(r["requires_engineer_review"])
        self.assertIn("not", r["boundary"].lower())


class Refusals(unittest.TestCase):
    def check(self, p, code):
        self.assertEqual(refusal(self, p), "TOLER1531:" + code)

    def test_packet(self):
        for bad in (None, [], "x", 3):
            self.check(bad, "invalid_packet")
        p = packet(); p["extra"] = 1; self.check(p, "unknown_fields:packet")
        p = packet(); del p["assumption"]; self.check(p, "unknown_fields:packet")
        p = packet(); del p["components"]; self.check(p, "unknown_fields:packet")

    def test_unit_and_assumption(self):
        for u in ("mm", "cm", "m", "inch"):
            m.analyze_tolerance_stack(packet(unit=u))
        for bad in ("MM", "ft", "", None, 5, " mm"):
            self.check(packet(unit=bad), "unsupported_unit")
        for bad in ("RSS", "rss", "", None, "worst_case_only ", 3):
            self.check(packet(assumption=bad), "invalid_assumption")

    def test_count_n_and_n_plus_1(self):
        m.analyze_tolerance_stack(packet(components=[comp("c%02d" % i) for i in range(64)]))
        self.check(packet(components=[comp("c%02d" % i) for i in range(65)]), "invalid_count:components")
        m.analyze_tolerance_stack(packet(components=[comp("a")]))
        self.check(packet(components=[]), "invalid_count:components")
        for bad in (None, "x", {}, ()):
            self.check(packet(components=bad), "invalid_count:components")

    def test_records(self):
        self.check(packet(components=["x"]), "invalid_record:components")
        c = comp("a"); c["extra"] = 1; self.check(packet(components=[c]), "invalid_fields:components")
        c = comp("a"); del c["minus"]; self.check(packet(components=[c]), "invalid_fields:components")
        self.check(packet(components=[comp("a"), comp("a")]), "duplicate_id")

    def test_text_n_and_n_plus_1(self):
        m.analyze_tolerance_stack(packet(components=[comp("a" * 128, ref="r" * 128)]))
        self.check(packet(components=[comp("a" * 129)]), "invalid_text:id")
        self.check(packet(components=[comp("a", ref="r" * 129)]), "invalid_text:source_ref")
        for bad in ("", "  ", 5, None, "a\nb", "a\x7fb"):
            self.check(packet(components=[comp(bad)]), "invalid_text:id")
            self.check(packet(components=[comp("a", ref=bad)]), "invalid_text:source_ref")

    def test_sign(self):
        for bad in (0, 2, -2, True, 1.0, "1", None):
            self.check(packet(components=[comp("a", sign=bad)]), "invalid_sign")

    def test_numbers(self):
        bad_nominal = ("", " 1", "1 ", "1\n", "+1", "1.", ".5", "1e3", "1.0000001", "1234567890123", "--1", "-", "\u0661", "0x10", 1, 1.5, None, True)
        for bad in bad_nominal:
            self.check(packet(components=[comp("a", 1, bad)]), "invalid_number:nominal")
        bad_tol = bad_nominal + ("-1", "-0", "-0.5")
        for bad in bad_tol:
            self.check(packet(components=[comp("a", 1, "1", bad, "0")]), "invalid_number:plus")
            self.check(packet(components=[comp("a", 1, "1", "0", bad)]), "invalid_number:minus")

    def test_limits(self):
        for bad in ("x", [], {"min": "1"}, {"min": "1", "max": "2", "x": 1}, None):
            self.check(packet(limits=bad), "invalid_limits")
        self.check(packet(limits={"min": "2", "max": "1"}), "limits_order")
        m.analyze_tolerance_stack(packet(limits={"min": "1", "max": "1"}))
        self.check(packet(limits={"min": "1e3", "max": "2"}), "invalid_number:limits")
        self.check(packet(limits={"min": 1, "max": "2"}), "invalid_number:limits")

    def test_reason_never_echoes_input(self):
        msg = refusal(self, packet(components=[comp("SECRETID\x00")]))
        self.assertNotIn("SECRETID", msg)
        self.assertEqual(msg, "TOLER1531:invalid_text:id")


class Surface(unittest.TestCase):
    def test_surface_and_offline(self):
        names = sorted(n for n in dir(m) if callable(getattr(m, n)) and not n.startswith("_")
                       and getattr(m, n).__module__ == "tolerance_analysis1531")
        self.assertEqual(names, ["analyze_tolerance_stack"])
        src = _P.read_text()
        for bad in ("import requests", "import urllib", "import socket", "import httpx", "subprocess", "open(", "random", "time.", "float(", "engineering_1510_1559", "datum_stack1532"):
            self.assertNotIn(bad, src, bad)

    def test_no_certification_claims(self):
        blob = repr(m.analyze_tolerance_stack(packet())).lower()
        for bad in ("certified", "approved", "released", "passes inspection", "safe"):
            self.assertNotIn(bad, blob)


class UnicodeText(unittest.TestCase):
    HIDDEN = ("\x85", "\u2028", "\u2029", "\u202e", "\u200b", "\ufeff", "\x7f", "\u200f", "\u202a", "\u2066", "\u2069", "\u200c", "\x00", "\x1f", "\u200e", "\u202d", "\u2067", "\u2068")
    ALLOWED = ("a b", "\u00e9", "\u00b5m", "\u4e2d\u6587", "\u00a0x", "\u2010x", "\u200a" + "x")

    def test_hidden_refused_on_id_and_source_ref(self):
        for ch in self.HIDDEN:
            self.assertEqual(refusal(self, packet(components=[comp("a%sb" % ch)])), "TOLER1531:invalid_text:id")
            self.assertEqual(refusal(self, packet(components=[comp("A", ref="a%sb" % ch)])), "TOLER1531:invalid_text:source_ref")
            self.assertNotIn(ch, refusal(self, packet(components=[comp(ch)])))

    def test_printable_non_ascii_and_spaces_allowed(self):
        for text in self.ALLOWED:
            r = m.analyze_tolerance_stack(packet(components=[comp(text, ref=text)]))
            self.assertEqual(r["contributions"][0]["source_ref"], text)


class CapFirst(unittest.TestCase):
    """The first operation after the isinstance check is the raw length check (no strip, regex or scan before it)."""
    BIG = 10 * 1024 * 1024
    PRE = "TOLER1531:"

    def _peak(self, fn):
        import tracemalloc
        tracemalloc.start()
        try:
            fn()
            return tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

    def test_text_raw_cap_n_and_n_plus_1(self):
        self.assertEqual(m._text("a" * m.MAX_TEXT, "id"), "a" * m.MAX_TEXT)
        for bad in ("a" * (m.MAX_TEXT + 1), " " + "a" * m.MAX_TEXT, "a" * m.MAX_TEXT + " "):   # raw length, not stripped length
            with self.assertRaises(ValueError) as cm:
                m._text(bad, "id")
            self.assertEqual(str(cm.exception), self.PRE + "invalid_text:id")

    def test_text_10mb_refused_without_strip_allocation(self):
        big = " a" + "b" * self.BIG       # strip() of this would allocate about 10 MB
        def call():
            with self.assertRaises(ValueError) as cm:
                m._text(big, "id")
            self.assertEqual(str(cm.exception), self.PRE + "invalid_text:id")
        self.assertLess(self._peak(call), 100000)

    def test_text_oversize_refused_before_any_scan(self):
        def boom(char):
            raise AssertionError("scanned an oversize value")
        old = m._hidden
        m._hidden = boom
        try:
            with self.assertRaises(ValueError):
                m._text("a" * (m.MAX_TEXT + 1), "id")
        finally:
            m._hidden = old

    def test_text_oversize_through_public_entry(self):
        big = " a" + "b" * self.BIG
        def call():
            with self.assertRaises(ValueError) as cm:
                m.analyze_tolerance_stack(packet(components=[dict(comp("A"), id=big)]))
            self.assertTrue(str(cm.exception).startswith(self.PRE + "invalid_text:"))
        self.assertLess(self._peak(call), 100000)

    def test_number_cap_n_and_n_plus_1_and_10mb_before_regex(self):
        class Spy:
            def fullmatch(self, text):
                raise AssertionError("regex ran on an oversize value")
        olds = {name: getattr(m, name) for name in ("_SIGNED", "_UNSIGNED") if hasattr(m, name)}
        for name in olds:
            setattr(m, name, Spy())
        try:
            for bad in ("1" * (m.MAX_NUMBER_CHARS + 1), "1" * self.BIG, " " + "1" * m.MAX_NUMBER_CHARS):
                for signed in [True, False]:
                    with self.assertRaises(ValueError) as cm:
                        m._micro(bad, "f", signed)
                    self.assertEqual(str(cm.exception), "TOLER1531:invalid_number:f")
        finally:
            for name, value in olds.items():
                setattr(m, name, value)

    def test_number_cap_equals_longest_valid_form(self):
        self.assertEqual(m.MAX_NUMBER_CHARS, len("-" + "9" * 12 + "." + "9" * 6))
        self.assertEqual(m._micro("-" + "9" * 12 + "." + "9" * 6, "f", True), -999999999999999999)
        with self.assertRaises(ValueError):
            m._micro("-" + "9" * 12 + "." + "9" * 7, "f", True)



if __name__ == "__main__":
    unittest.main()


class SurvivorPins(unittest.TestCase):
    """Added after the first mutation run (three real survivors)."""

    def test_unit_echoed_per_input(self):
        for u in ("mm", "cm", "m", "inch"):
            self.assertEqual(m.analyze_tolerance_stack(packet(unit=u))["unit"], u)

    def test_negative_nominal_and_limits_change_result(self):
        p = packet(components=[comp("A", 1, "-5", "0.1", "0.1"), comp("B", 1, "2", "0", "0")], assumption="worst_case_only")
        self.assertEqual(m.analyze_tolerance_stack(p)["nominal_stack"], "-3.000000")
        p["limits"] = {"min": "-3.2", "max": "-2.8"}
        self.assertTrue(m.analyze_tolerance_stack(p)["limits_check"]["worst_case_within_limits"])
        p["limits"] = {"min": "3.2", "max": "3.8"}
        self.assertFalse(m.analyze_tolerance_stack(p)["limits_check"]["worst_case_within_limits"])

    def test_assumption_exact_set(self):
        self.assertEqual(m.ASSUMPTIONS, ("worst_case_only", "rss_independent"))
        self.assertEqual(refusal(self, packet(assumption="x")), "TOLER1531:invalid_assumption")
