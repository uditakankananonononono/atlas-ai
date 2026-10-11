import unittest

from app.modules.m20_general_cognitive_worker import design_for_sustainability1529 as ds

P = "DESSUS1529:"


def imp(**kw):
    return {k: {"value": v, "unit": "kg" if k == "co2" else "L"} for k, v in kw.items()}


def req(**k):
    r = {"functional_unit": "one chair for 10 years", "system_boundary": "cradle to gate",
         "lifecycle_stages": [{"id": "make", "impacts": imp(co2=6, water=1)}, {"id": "use", "impacts": imp(co2=2, water=1)},
                              {"id": "end", "impacts": imp(co2=2)}]}
    r.update(k)
    return r


def err(**k):
    try:
        ds.run(req(**k))
    except ValueError as e:
        return str(e)
    raise AssertionError("no refusal")


class Behaviour(unittest.TestCase):
    def test_totals_shares_hotspots(self):
        out = ds.run(req())
        self.assertEqual(out["impact_totals"], {"co2": {"total": "10", "unit": "kg"}, "water": {"total": "2", "unit": "L"}})
        self.assertEqual(out["shares"]["co2"], {"end": "1/5", "make": "3/5", "use": "1/5"})
        self.assertEqual(out["shares"]["water"], {"make": "1/2", "use": "1/2"})
        self.assertEqual(out["hotspots"], {"co2": ["make"], "water": ["make", "use"]})
        self.assertIs(out["comparative_claim_review_required"], True)
        self.assertIs(out["lca_certification_claimed"], False)
        self.assertEqual(out["functional_unit"], "one chair for 10 years")
        self.assertEqual(out["system_boundary"], "cradle to gate")
        self.assertEqual(out["stage_count"], 3)

    def test_decimal_exactness(self):
        r = req(lifecycle_stages=[{"id": "a", "impacts": imp(co2=0.1)}, {"id": "b", "impacts": imp(co2=0.2)}])
        self.assertEqual(ds.run(r)["impact_totals"]["co2"]["total"], "0.3")
        self.assertEqual(ds.run(r)["shares"]["co2"], {"a": "1/3", "b": "2/3"})

    def test_zero_total_has_no_shares(self):
        r = req(lifecycle_stages=[{"id": "a", "impacts": imp(co2=5)}, {"id": "b", "impacts": imp(co2=-5)}])
        out = ds.run(r)
        self.assertEqual(out["impact_totals"]["co2"]["total"], "0")
        self.assertIsNone(out["shares"]["co2"])
        self.assertEqual(out["hotspots"]["co2"], ["a"])

    def test_negative_credit_allowed(self):
        r = req(lifecycle_stages=[{"id": "a", "impacts": imp(co2=10)}, {"id": "b", "impacts": imp(co2=-4)}])
        out = ds.run(r)
        self.assertEqual(out["impact_totals"]["co2"]["total"], "6")
        self.assertEqual(out["shares"]["co2"], {"a": "5/3", "b": "-2/3"})

    def test_stage_without_category_is_ok(self):
        out = ds.run(req(lifecycle_stages=[{"id": "a", "impacts": imp(co2=1, water=3)}, {"id": "b", "impacts": imp(co2=1)}]))
        self.assertEqual(out["shares"]["water"], {"a": "1"})
        self.assertEqual(out["hotspots"]["co2"], ["a", "b"])

    def test_empty_impacts_stage(self):
        out = ds.run(req(lifecycle_stages=[{"id": "a", "impacts": {}}]))
        self.assertEqual(out["impact_totals"], {})
        self.assertEqual(out["stage_count"], 1)


class Refusals(unittest.TestCase):
    def test_request_and_text(self):
        with self.assertRaises(ValueError) as cm:
            ds.run([])
        self.assertEqual(str(cm.exception), P + "invalid_request")
        self.assertEqual(err(zzz=1), P + "unknown_key")
        for f in ("functional_unit", "system_boundary"):
            self.assertEqual(err(**{f: ""}), P + "invalid_text:" + f)
            self.assertEqual(err(**{f: None}), P + "invalid_text:" + f)
            self.assertEqual(err(**{f: "x" * 129}), P + "invalid_text:" + f)
            ds.run(req(**{f: "x" * 128}))

    def test_counts_n_and_n_plus_1(self):
        st = [{"id": "s%d" % i, "impacts": imp(co2=1)} for i in range(32)]
        ds.run(req(lifecycle_stages=st))
        self.assertEqual(err(lifecycle_stages=st + [{"id": "s32", "impacts": imp(co2=1)}]), P + "invalid_count:lifecycle_stages")
        self.assertEqual(err(lifecycle_stages=[]), P + "invalid_count:lifecycle_stages")
        cats = {"c%d" % i: {"value": 1, "unit": "kg"} for i in range(16)}
        ds.run(req(lifecycle_stages=[{"id": "a", "impacts": cats}]))
        cats["c16"] = {"value": 1, "unit": "kg"}
        self.assertEqual(err(lifecycle_stages=[{"id": "a", "impacts": cats}]), P + "invalid_count:impacts")

    def test_units_and_numbers(self):
        a = {"id": "a", "impacts": {"co2": {"value": 1, "unit": "kg"}}}
        b = {"id": "b", "impacts": {"co2": {"value": 1, "unit": "g"}}}
        self.assertEqual(err(lifecycle_stages=[a, b]), P + "unit_mismatch")
        for bad in (True, "1", None, float("nan"), float("inf"), 10 ** 12 + 1):
            self.assertEqual(err(lifecycle_stages=[{"id": "a", "impacts": {"co2": {"value": bad, "unit": "kg"}}}]), P + "invalid_number:value", bad)
        ds.run(req(lifecycle_stages=[{"id": "a", "impacts": {"co2": {"value": 10 ** 12, "unit": "kg"}}}]))
        self.assertEqual(err(lifecycle_stages=[{"id": "a", "impacts": {"co2": {"value": 1, "unit": ""}}}]), P + "invalid_text:unit")
        self.assertEqual(err(lifecycle_stages=[{"id": "a", "impacts": {"": {"value": 1, "unit": "kg"}}}]), P + "invalid_text:category")
        self.assertEqual(err(lifecycle_stages=[{"id": "a", "impacts": {"co2": 5}}]), P + "invalid_item:impacts")
        self.assertEqual(err(lifecycle_stages=[{"id": "a", "impacts": {"co2": {"value": 1, "unit": "kg", "z": 1}}}]), P + "unknown_key")
        self.assertEqual(err(lifecycle_stages=[{"id": "a", "impacts": []}]), P + "invalid_item:impacts")

    def test_ids_and_shape(self):
        s = {"id": "a", "impacts": imp(co2=1)}
        self.assertEqual(err(lifecycle_stages=[s, dict(s)]), P + "duplicate_id:lifecycle_stages")
        self.assertEqual(err(lifecycle_stages=[{**s, "id": ""}]), P + "invalid_text:id")
        self.assertEqual(err(lifecycle_stages=[{**s, "z": 1}]), P + "unknown_key")
        self.assertEqual(err(lifecycle_stages=[5]), P + "invalid_item:lifecycle_stages")


class UnicodeRule(unittest.TestCase):
    BAD = {"U+0085": "\u0085", "U+2028": "\u2028", "U+2029": "\u2029", "U+202E": "\u202e",
           "U+200B": "\u200b", "U+FEFF": "\ufeff", "DEL": "\x7f"}

    def _call(self, expr, value):
        return err(**eval("dict(%s)" % (expr % "VALUE"), {"VALUE": value}))

    def test_seven_pins_refused_naming_field_not_value(self):
        for expr, field in [('functional_unit=%s', 'functional_unit'), ('system_boundary=%s', 'system_boundary')]:
            for label, ch in self.BAD.items():
                for value in ("a" + ch + "b", ch):
                    self.assertEqual(self._call(expr, value), P + "invalid_text:" + field, (field, label))

    def test_cap_then_unicode_and_allowed_text(self):
        for expr, field in [('functional_unit=%s', 'functional_unit'), ('system_boundary=%s', 'system_boundary')]:
            self.assertEqual(self._call(expr, "x" * 128 + "\u200b"), P + "invalid_text:" + field)
            self.assertEqual(self._call(expr, "\u200b" + "x" * 128), P + "invalid_text:" + field)

    def test_ordinary_space_and_printable_non_ascii_not_refused_by_rule(self):
        for expr, field in [('functional_unit=%s', 'functional_unit'), ('system_boundary=%s', 'system_boundary')]:
            for value in ("caf\u00e9 \u00fc\u4e2d", "a b", "\u00a0x"):
                try:
                    got = self._call(expr, value)
                except AssertionError:
                    continue
                self.assertNotEqual(got, P + "invalid_text:" + field, (field, value))


class OversizeNumber(unittest.TestCase):
    def test_huge_int_refused_fast_both_signs_and_str_refused(self):
        import time
        for big in (1 << (8 * 10 ** 7), -(1 << (8 * 10 ** 7))):
            BIG = big
            t0 = time.perf_counter()
            self.assertEqual(err(lifecycle_stages=[{'id': 'a', 'impacts': {'co2': {'value': BIG, 'unit': 'kg'}}}]), P + "invalid_number:value")
            self.assertLess(time.perf_counter() - t0, 0.5)
        BIG = "9" * 10 ** 7
        self.assertEqual(err(lifecycle_stages=[{'id': 'a', 'impacts': {'co2': {'value': BIG, 'unit': 'kg'}}}]), P + "invalid_number:value")


    def test_guard_precedes_abs(self):
        def boom(_):
            raise AssertionError("abs reached before size guard")
        ds.abs = boom
        try:
            BIG = 1 << (8 * 10 ** 6)
            self.assertIn("invalid_number", err(lifecycle_stages=[{'id': 'a', 'impacts': {'co2': {'value': BIG, 'unit': 'kg'}}}]))
        finally:
            del ds.abs


class KeyCaps(unittest.TestCase):
    """Dict key-count cap (author batch default 64) applied before any iteration or set construction."""

    def _padded(self, d, total):
        d = dict(d)
        i = 0
        while len(d) < total:
            d["zz%d" % i] = 1
            i += 1
        return d

    def _call(self, request):
        try:
            ds.run(request)
        except ValueError as e:
            return str(e)
        raise AssertionError("no refusal")

    def test_top_level_keys_n_and_n_plus_1(self):
        r = req()
        self.assertEqual(self._call(self._padded(r, 64)), P + "unknown_key")
        self.assertEqual(self._call(self._padded(r, 65)), P + "invalid_count:keys")

    def test_item_keys_n_and_n_plus_1(self):
        r = req()
        item = r["lifecycle_stages"][0]
        r["lifecycle_stages"][0] = self._padded(item, 64)
        self.assertEqual(self._call(r), P + "unknown_key")
        r = req()
        r["lifecycle_stages"][0] = self._padded(r["lifecycle_stages"][0], 65)
        self.assertEqual(self._call(r), P + "invalid_count:keys")

    def test_cap_before_iteration_set_not_reached(self):
        def boom(*a, **k):
            raise AssertionError("set() reached before key cap")
        ds.set = boom
        try:
            huge = {("k%d" % i): 1 for i in range(10 ** 6)}
            self.assertEqual(self._call(huge), P + "invalid_count:keys")
        finally:
            del ds.set


class ExactArithmetic(unittest.TestCase):
    CTXS = [None, dict(prec=2), dict(prec=28), dict(prec=100), dict(rounding="ROUND_DOWN"), dict(rounding="ROUND_UP"),
            dict(rounding="ROUND_HALF_UP"), dict(prec=3, traps=[])]

    @staticmethod
    def _state(c):
        return (c.prec, c.rounding, c.Emin, c.Emax, tuple(sorted(k.__name__ for k, v in c.traps.items() if v)),
                tuple(sorted(k.__name__ for k, v in c.flags.items() if v)))

    def _run_in(self, kw, request):
        import decimal
        old = decimal.getcontext()
        decimal.setcontext(decimal.Context(**kw) if kw else decimal.Context())
        try:
            before = self._state(decimal.getcontext())
            out = ds.run(request)
            self.assertEqual(before, self._state(decimal.getcontext()))
            return out
        finally:
            decimal.setcontext(old)

    def test_output_identical_across_ambient_contexts(self):
        rq = req(lifecycle_stages=[{"id": "a", "impacts": imp(co2=1.234)}, {"id": "b", "impacts": imp(co2=2.345)}])
        base = self._run_in(None, rq)
        self.assertEqual(base["impact_totals"]["co2"]["total"], "3.579")
        self.assertEqual(base["shares"]["co2"], {"a": "1234/3579", "b": "2345/3579"})
        for kw in self.CTXS:
            self.assertEqual(self._run_in(kw, rq), base, kw)

    def test_total_is_exact_beyond_28_and_64_digits(self):
        rq = req(lifecycle_stages=[{"id": "a", "impacts": imp(co2=100000000000)}, {"id": "b", "impacts": imp(co2=1e-60)}])
        want = "100000000000." + "0" * 59 + "1"
        for kw in self.CTXS:
            self.assertEqual(self._run_in(kw, rq)["impact_totals"]["co2"]["total"], want, kw)

    def test_total_render_forms(self):
        def tot(*vals):
            st = [{"id": "s%d" % i, "impacts": imp(co2=v)} for i, v in enumerate(vals)]
            return ds.run(req(lifecycle_stages=st))["impact_totals"]["co2"]["total"]
        self.assertEqual(tot(5.0, 0.5), "5.5")
        self.assertEqual(tot(2, 3), "5")
        self.assertEqual(tot(-1.5, 0.5), "-1")
        self.assertEqual(tot(-0.25, 0.125), "-0.125")
        self.assertEqual(tot(1.5, -1.5), "0")


if __name__ == "__main__":
    unittest.main()
