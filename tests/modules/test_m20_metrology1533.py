"""Row 1533 METROL1533 tests. Hermetic, stdlib unittest, N/N+1 pins."""
import copy, importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/metrology1533.py"
_spec = importlib.util.spec_from_file_location("metrology1533", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["metrology1533"] = m
_spec.loader.exec_module(m)


def comp(i, u="3", c="1", kind="type_b", ref="cert-1"):
    return {"id": i, "standard_uncertainty": u, "sensitivity": c, "kind": kind, "source_ref": ref}


def packet(**kw):
    d = {"unit": "mm", "assumption": "uncorrelated_inputs", "coverage_factor": "2",
         "components": [comp("A", "3"), comp("B", "4")], "traceability_chain": ["lab ref 1", "national ref 2"]}
    d.update(kw)
    return d


def run(p):
    return m.compute_uncertainty_budget(p)


def refusal(test, p):
    with test.assertRaises(ValueError) as cm:
        run(p)
    return str(cm.exception)


class Compute(unittest.TestCase):
    def test_3_4_5_exact(self):
        r = run(packet())
        self.assertEqual(r["combined_standard_uncertainty"]["bounds"], ["5.000000", "5.000000"])
        self.assertEqual(r["combined_standard_uncertainty"]["squared"], "25.000000000000000000000000")
        self.assertEqual(r["expanded_uncertainty"]["bounds"], ["10.000000", "10.000000"])
        self.assertEqual(r["coverage_factor"], "2.000000")
        self.assertEqual(r["unit"], "mm")

    def test_non_square_bracket(self):
        r = run(packet(components=[comp("A", "1"), comp("B", "1")], coverage_factor="1"))
        self.assertEqual(r["combined_standard_uncertainty"]["bounds"], ["1.414213", "1.414214"])
        self.assertEqual(r["combined_standard_uncertainty"]["squared"], "2.000000000000000000000000")
        r = run(packet(components=[comp("A", "1"), comp("B", "1")], coverage_factor="2"))
        self.assertEqual(r["expanded_uncertainty"]["bounds"], ["2.828427", "2.828428"])

    def test_expanded_bounds_from_exact_square_not_rounded_root(self):
        # k=1.5, u_c=sqrt(2): U=2.1213203... ; direct bounds 2.121320/2.121321
        r = run(packet(components=[comp("A", "1"), comp("B", "1")], coverage_factor="1.5"))
        self.assertEqual(r["expanded_uncertainty"]["bounds"], ["2.121320", "2.121321"])

    def test_sensitivity_scales_and_sign_irrelevant(self):
        a = run(packet(components=[comp("A", "3", "2"), comp("B", "4", "-0.5")], coverage_factor="1"))
        self.assertEqual(a["contributions"][0]["contribution"], "6.000000000000")
        self.assertEqual(a["contributions"][1]["contribution"], "2.000000000000")
        self.assertEqual(a["combined_standard_uncertainty"]["squared"], "40.000000000000000000000000")
        b = run(packet(components=[comp("A", "3", "2"), comp("B", "4", "0.5")], coverage_factor="1"))
        self.assertEqual(a["combined_standard_uncertainty"], b["combined_standard_uncertainty"])

    def test_squared_is_exact_24_places(self):
        r = run(packet(components=[comp("A", "0.000001"), comp("B", "0.000002")], coverage_factor="1"))
        self.assertEqual(r["combined_standard_uncertainty"]["squared"], "0.000000000005000000000000")
        self.assertEqual(r["combined_standard_uncertainty"]["bounds"], ["0.000002", "0.000003"])

    def test_zero_uncertainty_allowed(self):
        r = run(packet(components=[comp("A", "0")]))
        self.assertEqual(r["combined_standard_uncertainty"]["bounds"], ["0.000000", "0.000000"])
        self.assertEqual(r["expanded_uncertainty"]["bounds"], ["0.000000", "0.000000"])

    def test_sorted_by_id_deterministic_no_mutation(self):
        p = packet(components=[comp("B", "4"), comp("A", "3")])
        before = copy.deepcopy(p)
        r1, r2 = run(p), run(p)
        self.assertEqual(r1, r2)
        self.assertEqual(p, before)
        self.assertEqual([c["id"] for c in r1["contributions"]], ["A", "B"])
        r1["traceability_chain"].append("x")
        self.assertEqual(p, before)

    def test_contribution_fields(self):
        c = run(packet())["contributions"][0]
        self.assertEqual(c, {"id": "A", "kind": "type_b", "source_ref": "cert-1", "standard_uncertainty": "3.000000",
                             "sensitivity": "1.000000", "contribution": "3.000000000000"})

    def test_traceability_echoed_not_verified(self):
        r = run(packet(traceability_chain=["z", "a", "z"]))
        self.assertEqual(r["traceability_chain"], ["z", "a", "z"])
        self.assertIs(r["traceability_verified"], False)
        self.assertIs(r["calibration_authority"], False)
        self.assertEqual(run(packet(traceability_chain=[]))["traceability_chain"], [])

    def test_scope_flags(self):
        r = run(packet())
        self.assertEqual(r["scope"], "declared_standard_uncertainties_arithmetic_only")
        self.assertIs(r["requires_metrologist_review"], True)
        self.assertIn("uncorrelated", r["statement"])
        self.assertIn("coverage probability", r["boundary"])
        low = repr(r).lower()
        for w in ("certified", "calibrated by", "compliant", "accredited"):
            self.assertNotIn(w, low.replace("not ", ""))


class Refusals(unittest.TestCase):
    def check(self, p, code):
        self.assertEqual(refusal(self, p), "METROL1533:" + code)

    def test_packet(self):
        for bad in (None, [], "x", 3):
            self.check(bad, "invalid_packet")
        p = packet(); p["extra"] = 1
        self.check(p, "unknown_fields:packet")
        p = packet(); del p["traceability_chain"]
        self.check(p, "unknown_fields:packet")

    def test_unit(self):
        run(packet(unit="x" * 16))
        for bad in ("", " ", "x" * 17, None, 1, "m\nm"):
            self.check(packet(unit=bad), "invalid_text:unit")

    def test_assumption(self):
        for bad in ("correlated", "", None, "uncorrelated_inputs "):
            self.check(packet(assumption=bad), "invalid_assumption")

    def test_coverage_factor(self):
        run(packet(coverage_factor="10"))
        run(packet(coverage_factor="0.000001"))
        for bad in ("0", "0.0", "10.000001", "11", "-1", 2, 2.0, None, "2e0", " 2", "2 "):
            self.check(packet(coverage_factor=bad), "invalid_coverage_factor")

    def test_count(self):
        run(packet(components=[comp("c%d" % i) for i in range(64)]))
        self.check(packet(components=[comp("c%d" % i) for i in range(65)]), "invalid_count:components")
        self.check(packet(components=[]), "invalid_count:components")
        self.check(packet(components=()), "invalid_count:components")

    def test_records(self):
        self.check(packet(components=["x"]), "invalid_record:components")
        r = comp("A"); r["extra"] = 1
        self.check(packet(components=[r]), "invalid_fields:components")
        r = comp("A"); del r["kind"]
        self.check(packet(components=[r]), "invalid_fields:components")
        self.check(packet(components=[comp("A"), comp("A")]), "duplicate_id")

    def test_kind(self):
        run(packet(components=[comp("A", kind="type_a")]))
        for bad in ("Type_A", "", None, "type_c"):
            self.check(packet(components=[comp("A", kind=bad)]), "invalid_kind")

    def test_text(self):
        run(packet(components=[comp("A" * 128, ref="r" * 128)]))
        for f in ("id", "ref"):
            for bad in ("", "  ", "a" * 129, None, 3, "a\tb", "a\x7fb"):
                c = comp("A") if f == "ref" else comp("A", ref="ok")
                if f == "id":
                    c["id"] = bad
                else:
                    c["source_ref"] = bad
                self.check(packet(components=[c]), "invalid_text:id" if f == "id" else "invalid_text:source_ref")

    def test_numbers(self):
        run(packet(components=[comp("A", "999999999999.999999", "-999999999999.999999")]))
        run(packet(components=[comp("A", "0.000001", "0")]))
        for bad in ("-1", "+1", "1e3", "1.", ".5", "1.0000001", "1234567890123", "", " 1", "1 ", "\uff11", 1, 1.0, None, True):
            self.check(packet(components=[comp("A", u=bad)]), "invalid_number:standard_uncertainty")
        for bad in ("+1", "1e3", "-1.0000001", "-", "-1234567890123", "", 1, None, "1\n"):
            self.check(packet(components=[comp("A", c=bad)]), "invalid_number:sensitivity")

    def test_trace_chain(self):
        run(packet(traceability_chain=["t%d" % i for i in range(16)]))
        self.check(packet(traceability_chain=["t%d" % i for i in range(17)]), "invalid_count:traceability_chain")
        self.check(packet(traceability_chain="abc"), "invalid_count:traceability_chain")
        self.check(packet(traceability_chain=None), "invalid_count:traceability_chain")
        for bad in ("", " ", "a" * 129, 3, None, "a\nb"):
            self.check(packet(traceability_chain=[bad]), "invalid_text:traceability_chain")
        run(packet(traceability_chain=["a" * 128]))

    def test_reason_never_echoes_input(self):
        secret = "SECRET-VALUE-XYZ"
        for p in (packet(unit=secret * 20), packet(coverage_factor=secret), packet(components=[comp(secret, u=secret)]),
                  packet(traceability_chain=[secret * 20])):
            self.assertNotIn(secret, refusal(self, p))

    def test_surface_and_offline(self):
        self.assertEqual([n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))
                          and getattr(getattr(m, n), "__module__", None) == "metrology1533"], ["compute_uncertainty_budget"])
        src = _P.read_text()
        for banned in ("import socket", "import requests", "urllib", "subprocess", "import os", "open(", "float(", "engineering_1510_1559"):
            self.assertNotIn(banned, src)


class SurvivorPins(unittest.TestCase):
    """Added after the first mutation run."""

    def test_negative_sensitivity_echoed_signed(self):
        c = run(packet(components=[comp("A", "3", "-0.5")]))["contributions"][0]
        self.assertEqual(c["sensitivity"], "-0.500000")
        self.assertEqual(c["contribution"], "1.500000000000")

    def test_coverage_factor_echoed_per_input(self):
        for k, shown in (("3", "3.000000"), ("0.5", "0.500000"), ("10", "10.000000")):
            self.assertEqual(run(packet(coverage_factor=k))["coverage_factor"], shown)

    def test_unit_echoed_per_input(self):
        for u in ("mm", "V", "K", "kg m-3"):
            self.assertEqual(run(packet(unit=u))["unit"], u)

    def test_coverage_factor_as_given_and_traceability_label(self):
        r = run(packet(coverage_factor="2.50"))
        self.assertEqual((r["coverage_factor"], r["coverage_factor_as_given"]), ("2.500000", "2.50"))
        self.assertEqual(r["traceability_status"], "echoed_not_verified")
        self.assertNotIn("confidence", repr(r).lower().replace("no coverage probability", ""))

    def test_oversize_control_text_refused_with_fixed_code(self):
        # order of cap vs content scan is not observable (same code); this pins only the fixed code
        for f in (lambda v: packet(unit=v), lambda v: packet(traceability_chain=[v]), lambda v: packet(components=[comp(v)])):
            self.assertIn("invalid_text", refusal(self, f("\t" * 200)))

    def test_kind_exact_set(self):
        self.assertEqual(m.KINDS, ("type_a", "type_b"))
        self.assertEqual(refusal(self, packet(components=[comp("A", kind="x")])), "METROL1533:invalid_kind")

    def test_components_must_be_list(self):
        self.assertEqual(refusal(self, packet(components=(comp("A"),))), "METROL1533:invalid_count:components")


class UnicodeText(unittest.TestCase):
    HIDDEN = ("\x85", "\u2028", "\u2029", "\u202e", "\u200b", "\ufeff", "\x7f", "\u200f", "\u202a", "\u2066", "\u2069", "\u200c", "\x00", "\x1f", "\u200e", "\u202d", "\u2067", "\u2068")
    ALLOWED = ("a b", "\u00e9", "\u00b5m", "\u4e2d\u6587", "\u00a0x", "\u2010x", "\u200a" + "x")

    def test_hidden_refused_on_unit_source_ref_id_and_chain(self):
        for ch in self.HIDDEN:
            self.assertEqual(refusal(self, packet(unit="a%sb" % ch)), "METROL1533:invalid_text:unit")
            self.assertEqual(refusal(self, packet(components=[comp("A", ref="a%sb" % ch)])), "METROL1533:invalid_text:source_ref")
            self.assertEqual(refusal(self, packet(components=[comp("a%sb" % ch)])), "METROL1533:invalid_text:id")
            self.assertEqual(refusal(self, packet(traceability_chain=["a%sb" % ch])), "METROL1533:invalid_text:traceability_chain")
            self.assertNotIn(ch, refusal(self, packet(unit=ch)))

    def test_printable_non_ascii_and_spaces_allowed(self):
        for text in self.ALLOWED:
            r = run(packet(unit=text, components=[comp(text, ref=text)], traceability_chain=[text]))
            self.assertEqual(r["traceability_chain"], [text])
            self.assertEqual(r["unit"], text)
            self.assertIs(r["traceability_verified"], False)


class CapFirst(unittest.TestCase):
    """The first operation after the isinstance check is the raw length check (no strip, regex or scan before it)."""
    BIG = 10 * 1024 * 1024
    PRE = "METROL1533:"

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
                m.compute_uncertainty_budget(packet(unit=big))
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
                        m._micro(bad, "invalid_coverage_factor", signed)
                    self.assertEqual(str(cm.exception), "METROL1533:invalid_coverage_factor")
        finally:
            for name, value in olds.items():
                setattr(m, name, value)

    def test_number_cap_equals_longest_valid_form(self):
        self.assertEqual(m.MAX_NUMBER_CHARS, len("-" + "9" * 12 + "." + "9" * 6))
        self.assertEqual(m._micro("-" + "9" * 12 + "." + "9" * 6, "invalid_coverage_factor", True), -999999999999999999)
        with self.assertRaises(ValueError):
            m._micro("-" + "9" * 12 + "." + "9" * 7, "invalid_coverage_factor", True)



if __name__ == "__main__":
    unittest.main()
