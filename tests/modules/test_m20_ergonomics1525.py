import unittest

from app.modules.m20_general_cognitive_worker import ergonomics1525 as eg

P = "ERGONO1525:"


def req(**k):
    r = {"task": "lift box", "exposures": [{"id": "x1", "kind": "force", "value": 20, "unit": "N", "limit": 25}],
         "anthropometric": [], "controls": [], "assessment_instrument": None, "score": None}
    r.update(k)
    return r


def err(**k):
    try:
        eg.run(req(**k))
    except ValueError as e:
        return str(e)
    raise AssertionError("no refusal")


INST = {"name": "RULA", "version": "2000", "source_citation": "caller-supplied citation"}


class Behaviour(unittest.TestCase):
    def test_limit_pins_n_and_n_plus_1(self):
        def x(v):
            return eg.run(req(exposures=[{"id": "a", "kind": "k", "value": v, "unit": "N", "limit": 25}]))["exposures"][0]
        self.assertIs(x(24.99)["exceeds_supplied_limit"], False)
        self.assertIs(x(25)["exceeds_supplied_limit"], False)
        self.assertIs(x(25.01)["exceeds_supplied_limit"], True)
        self.assertEqual(x(20)["margin"], "5")
        self.assertEqual(x(25.5)["margin"], "-0.5")
        self.assertEqual(x(0.1)["margin"], "24.9")

    def test_no_limit_means_not_assessed(self):
        out = eg.run(req(exposures=[{"id": "a", "kind": "k", "value": 5, "unit": "N"}]))["exposures"][0]
        self.assertIsNone(out["exceeds_supplied_limit"])
        self.assertIsNone(out["margin"])

    def test_flags_and_no_score_authority(self):
        out = eg.run(req())
        self.assertIs(out["interpretation_requires_qualified_reviewer"], True)
        self.assertIs(out["scoring_authority"], False)
        self.assertIsNone(out["computed_score"])
        self.assertIsNone(out["supplied_score"])
        self.assertEqual(out["summary"], {"exposure_count": 1, "exceeding_ids": [], "unassessed_ids": []})

    def test_summary_lists(self):
        ex = [{"id": "b", "kind": "k", "value": 9, "unit": "N", "limit": 5}, {"id": "a", "kind": "k", "value": 1, "unit": "N"},
              {"id": "c", "kind": "k", "value": 1, "unit": "N", "limit": 5}, {"id": "d", "kind": "k", "value": 9, "unit": "N", "limit": 5}]
        s = eg.run(req(exposures=ex))["summary"]
        self.assertEqual(s, {"exposure_count": 4, "exceeding_ids": ["b", "d"], "unassessed_ids": ["a"]})

    def test_score_requires_instrument_and_scale(self):
        sc = {"value": 5, "scale_min": 1, "scale_max": 7}
        self.assertEqual(err(score=sc), P + "score_without_instrument")
        out = eg.run(req(score=sc, assessment_instrument=INST))
        self.assertEqual(out["supplied_score"], {"value": 5, "scale_min": 1, "scale_max": 7})
        self.assertEqual(out["assessment_instrument"], INST)
        for v in (1, 7):
            eg.run(req(score={"value": v, "scale_min": 1, "scale_max": 7}, assessment_instrument=INST))
        for v in (0.99, 7.01):
            self.assertEqual(err(score={"value": v, "scale_min": 1, "scale_max": 7}, assessment_instrument=INST), P + "score_out_of_scale")
        self.assertEqual(err(score={"value": 1, "scale_min": 7, "scale_max": 1}, assessment_instrument=INST), P + "invalid_scale")
        eg.run(req(score={"value": 3, "scale_min": 3, "scale_max": 3}, assessment_instrument=INST))
        for miss in ("name", "version", "source_citation"):
            bad = {k: v for k, v in INST.items() if k != miss}
            self.assertEqual(err(score=sc, assessment_instrument=bad), P + "invalid_text:" + miss)
        self.assertEqual(err(assessment_instrument={**INST, "x": 1}), P + "unknown_key")
        self.assertEqual(err(assessment_instrument={}), P + "invalid_text:name")
        self.assertEqual(err(assessment_instrument=[]), P + "invalid_item:assessment_instrument")
        self.assertEqual(err(score=[]), P + "invalid_item:score")
        self.assertEqual(err(score={"value": 1, "scale_min": 0, "scale_max": 2, "z": 1}, assessment_instrument=INST), P + "unknown_key")

    def test_anthropometric_coverage(self):
        a = [{"dimension": "stature", "percentile": 5, "value": 150, "unit": "cm"},
             {"dimension": "stature", "percentile": 95, "value": 185, "unit": "cm"},
             {"dimension": "reach", "percentile": 50, "value": 70, "unit": "cm"},
             {"dimension": "reach", "percentile": 5, "value": 60, "unit": "cm"}]
        out = eg.run(req(anthropometric=a))["anthropometric"]
        self.assertEqual([d["dimension"] for d in out], ["reach", "stature"])
        self.assertEqual(out[0]["percentiles"], [5, 50])
        self.assertIs(out[0]["spans_p5_p95"], False)
        self.assertIs(out[1]["spans_p5_p95"], True)
        self.assertEqual(out[1]["unit"], "cm")
        edge = [{"dimension": "d", "percentile": 6, "value": 1, "unit": "cm"}, {"dimension": "d", "percentile": 94, "value": 2, "unit": "cm"}]
        self.assertIs(eg.run(req(anthropometric=edge))["anthropometric"][0]["spans_p5_p95"], False)
        edge2 = [{"dimension": "d", "percentile": 5, "value": 1, "unit": "cm"}, {"dimension": "d", "percentile": 94, "value": 2, "unit": "cm"}]
        self.assertIs(eg.run(req(anthropometric=edge2))["anthropometric"][0]["spans_p5_p95"], False)
        edge3 = [{"dimension": "d", "percentile": 6, "value": 1, "unit": "cm"}, {"dimension": "d", "percentile": 95, "value": 2, "unit": "cm"}]
        self.assertIs(eg.run(req(anthropometric=edge3))["anthropometric"][0]["spans_p5_p95"], False)

    def test_controls_echoed(self):
        out = eg.run(req(controls=[{"id": "c", "description": "lift aid"}]))
        self.assertEqual(out["controls"], [{"id": "c", "description": "lift aid"}])


class Refusals(unittest.TestCase):
    def test_request(self):
        for bad in ([], None, "x"):
            with self.assertRaises(ValueError) as cm:
                eg.run(bad)
            self.assertEqual(str(cm.exception), P + "invalid_request")
        self.assertEqual(err(zzz=1), P + "unknown_key")
        self.assertEqual(err(task=""), P + "invalid_text:task")
        self.assertEqual(err(task="x" * 129), P + "invalid_text:task")
        eg.run(req(task="x" * 128))

    def test_counts_n_and_n_plus_1(self):
        ex = [{"id": "e%d" % i, "kind": "k", "value": 1, "unit": "N"} for i in range(64)]
        eg.run(req(exposures=ex))
        self.assertEqual(err(exposures=ex + [{"id": "e64", "kind": "k", "value": 1, "unit": "N"}]), P + "invalid_count:exposures")
        self.assertEqual(err(exposures=[]), P + "invalid_count:exposures")
        an = [{"dimension": "d%d" % i, "percentile": 50, "value": 1, "unit": "cm"} for i in range(128)]
        eg.run(req(anthropometric=an))
        self.assertEqual(err(anthropometric=an + [{"dimension": "d128", "percentile": 50, "value": 1, "unit": "cm"}]), P + "invalid_count:anthropometric")
        ct = [{"id": "c%d" % i, "description": "d"} for i in range(64)]
        eg.run(req(controls=ct))
        self.assertEqual(err(controls=ct + [{"id": "c64", "description": "d"}]), P + "invalid_count:controls")

    def test_numbers(self):
        def ex(**k):
            return [{"id": "a", "kind": "k", "value": 1, "unit": "N", **k}]
        for bad in (True, "1", None, float("nan"), float("inf"), 10 ** 12 + 1):
            self.assertEqual(err(exposures=ex(value=bad)), P + "invalid_number:value", bad)
        eg.run(req(exposures=ex(value=10 ** 12)))
        eg.run(req(exposures=ex(value=-10 ** 12)))
        self.assertEqual(err(exposures=ex(limit="5")), P + "invalid_number:limit")
        self.assertEqual(err(exposures=ex(duration_s=-1)), P + "invalid_number:duration_s")
        eg.run(req(exposures=ex(duration_s=0)))
        self.assertEqual(err(exposures=ex(duration_s=1.5)), P + "invalid_number:duration_s")
        eg.run(req(exposures=ex(duration_s=10 ** 12)))
        self.assertEqual(err(exposures=ex(duration_s=10 ** 12 + 1)), P + "invalid_number:duration_s")

    def test_percentile_pins(self):
        def a(p):
            return [{"dimension": "d", "percentile": p, "value": 1, "unit": "cm"}]
        for ok in (1, 99):
            eg.run(req(anthropometric=a(ok)))
        for bad in (0, 100, True, 5.0, "5"):
            self.assertEqual(err(anthropometric=a(bad)), P + "invalid_percentile", bad)

    def test_duplicates_and_units(self):
        e = {"id": "a", "kind": "k", "value": 1, "unit": "N"}
        self.assertEqual(err(exposures=[e, dict(e)]), P + "duplicate_id:exposures")
        c = {"id": "c", "description": "d"}
        self.assertEqual(err(controls=[c, dict(c)]), P + "duplicate_id:controls")
        a1 = {"dimension": "d", "percentile": 5, "value": 1, "unit": "cm"}
        self.assertEqual(err(anthropometric=[a1, dict(a1)]), P + "duplicate_percentile")
        self.assertEqual(err(anthropometric=[a1, {**a1, "percentile": 6, "unit": "mm"}]), P + "unit_mismatch")
        self.assertEqual(err(exposures=[{**e, "unit": ""}]), P + "invalid_text:unit")
        self.assertEqual(err(exposures=[{**e, "zzz": 1}]), P + "unknown_key")
        self.assertEqual(err(exposures=[5]), P + "invalid_item:exposures")


class UnicodeRule(unittest.TestCase):
    BAD = {"U+0085": "\u0085", "U+2028": "\u2028", "U+2029": "\u2029", "U+202E": "\u202e",
           "U+200B": "\u200b", "U+FEFF": "\ufeff", "DEL": "\x7f"}

    def _call(self, expr, value):
        return err(**eval("dict(%s)" % (expr % "VALUE"), {"VALUE": value}))

    def test_seven_pins_refused_naming_field_not_value(self):
        for expr, field in [('task=%s', 'task'), ("exposures=[{'id': 'x1', 'kind': 'force', 'value': 20, 'unit': %s}]", 'unit')]:
            for label, ch in self.BAD.items():
                for value in ("a" + ch + "b", ch):
                    self.assertEqual(self._call(expr, value), P + "invalid_text:" + field, (field, label))

    def test_cap_then_unicode_and_allowed_text(self):
        for expr, field in [('task=%s', 'task'), ("exposures=[{'id': 'x1', 'kind': 'force', 'value': 20, 'unit': %s}]", 'unit')]:
            self.assertEqual(self._call(expr, "x" * 128 + "\u200b"), P + "invalid_text:" + field)
            self.assertEqual(self._call(expr, "\u200b" + "x" * 128), P + "invalid_text:" + field)

    def test_ordinary_space_and_printable_non_ascii_not_refused_by_rule(self):
        for expr, field in [('task=%s', 'task'), ("exposures=[{'id': 'x1', 'kind': 'force', 'value': 20, 'unit': %s}]", 'unit')]:
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
            self.assertEqual(err(exposures=[{'id': 'x1', 'kind': 'force', 'value': BIG, 'unit': 'N'}]), P + "invalid_number:value")
            self.assertLess(time.perf_counter() - t0, 0.5)
        BIG = "9" * 10 ** 7
        self.assertEqual(err(exposures=[{'id': 'x1', 'kind': 'force', 'value': BIG, 'unit': 'N'}]), P + "invalid_number:value")


    def test_guard_precedes_abs(self):
        def boom(_):
            raise AssertionError("abs reached before size guard")
        eg.abs = boom
        try:
            BIG = 1 << (8 * 10 ** 6)
            self.assertIn("invalid_number", err(exposures=[{'id': 'x1', 'kind': 'force', 'value': BIG, 'unit': 'N'}]))
        finally:
            del eg.abs


class AmbientDecimalContext(unittest.TestCase):
    CTXS = [("default", None), ("prec2", dict(prec=2)), ("prec28", dict(prec=28)), ("prec100", dict(prec=100)),
            ("down", dict(rounding="ROUND_DOWN")), ("up", dict(rounding="ROUND_UP")),
            ("half_up", dict(rounding="ROUND_HALF_UP")), ("traps_cleared", dict(prec=3, traps=[]))]

    @staticmethod
    def _ctx(kw):
        import decimal
        if kw is None:
            return decimal.Context()
        return decimal.Context(**kw)

    @staticmethod
    def _state(c):
        return (c.prec, c.rounding, c.Emin, c.Emax, c.clamp, c.capitals,
                tuple(sorted(k.__name__ for k, v in c.traps.items() if v)),
                tuple(sorted(k.__name__ for k, v in c.flags.items() if v)))

    def _run_in(self, kw, request):
        import decimal
        old = decimal.getcontext()
        decimal.setcontext(self._ctx(kw))
        try:
            before = self._state(decimal.getcontext())
            out = eg.run(request)
            after = self._state(decimal.getcontext())
            self.assertEqual(before, after)
            return out
        finally:
            decimal.setcontext(old)

    def test_output_identical_across_ambient_contexts(self):
        rq = req(exposures=[{"id": "x", "kind": "k", "value": 1.234, "unit": "N", "limit": 2.345}])
        base = self._run_in(None, rq)
        self.assertEqual(base["exposures"][0]["margin"], "1.111")
        for name, kw in self.CTXS:
            self.assertEqual(self._run_in(kw, rq), base, name)

    def test_derived_values_round_to_64_significant_digits_half_even(self):
        import decimal
        rq = req(exposures=[{"id": "x", "kind": "k", "value": 100000000000, "unit": "N", "limit": 1e-60}])
        oracle = decimal.Context(prec=64, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999)
        exact = decimal.Decimal(str(1e-60)) - decimal.Decimal(100000000000)
        want = format(oracle.normalize(oracle.plus(exact)), "f")
        self.assertGreater(len(decimal.Decimal(str(1e-60)).as_tuple().digits) + 71, 64)
        for name, kw in self.CTXS:
            self.assertEqual(self._run_in(kw, rq)["exposures"][0]["margin"], want, name)

    def test_fixed_context_parameters_inside_run(self):
        import decimal
        seen = []
        real = eg._run
        def spy(request):
            c = decimal.getcontext()
            seen.append((c.prec, c.rounding, c.Emin, c.Emax, c.clamp, c.capitals,
                         sorted(k.__name__ for k, v in c.traps.items() if v), [k for k, v in c.flags.items() if v]))
            return real(request)
        eg._run = spy
        try:
            for kw in self.CTXS:
                self._run_in(kw[1], req())
        finally:
            eg._run = real
        want = (64, decimal.ROUND_HALF_EVEN, -999999, 999999, 0, 1, ["DivisionByZero", "InvalidOperation", "Overflow", "Underflow"], [])
        self.assertEqual(len(seen), len(self.CTXS))
        for got in seen:
            self.assertEqual(got, want)

    def test_precision_is_exactly_64_digits(self):
        import decimal
        lim, val = -1.2345678901234567e-45, 123456789012.34567
        exact = decimal.Context(prec=400).subtract(decimal.Decimal(str(lim)), decimal.Decimal(str(val)))
        self.assertGreater(len(exact.as_tuple().digits), 66)
        out = {}
        for p in (63, 64, 65):
            c = decimal.Context(prec=p, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999)
            out[p] = format(c.normalize(c.plus(exact)), "f")
        self.assertEqual(len({out[63], out[64], out[65]}), 3)
        rq = req(exposures=[{"id": "x", "kind": "k", "value": val, "unit": "N", "limit": lim}])
        for name, kw in self.CTXS:
            self.assertEqual(self._run_in(kw, rq)["exposures"][0]["margin"], out[64], name)

    def test_arithmetic_overflow_refused_with_prefix_code_and_no_raw_exception(self):
        import decimal
        real = eg._num
        huge = decimal.Decimal("9E+999999")
        def fake(value, field):
            return huge if field == "limit" else -huge
        eg._num = fake
        try:
            for name, kw in self.CTXS:
                try:
                    self._run_in(kw, req(exposures=[{"id": "x", "kind": "k", "value": 1, "unit": "N", "limit": 1}]))
                except ValueError as e:
                    self.assertEqual(str(e), P + "arithmetic", name)
                else:
                    raise AssertionError("no refusal " + name)
        finally:
            eg._num = real

    def test_score_and_anthro_paths_also_context_independent(self):
        rq = req(score={"value": 1.5, "scale_min": 0, "scale_max": 3.25}, assessment_instrument={"name": "n", "version": "1", "source_citation": "c"})
        base = self._run_in(None, rq)
        for name, kw in self.CTXS:
            self.assertEqual(self._run_in(kw, rq), base, name)


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
            eg.run(request)
        except ValueError as e:
            return str(e)
        raise AssertionError("no refusal")

    def test_top_level_keys_n_and_n_plus_1(self):
        r = req()
        self.assertEqual(self._call(self._padded(r, 64)), P + "unknown_key")
        self.assertEqual(self._call(self._padded(r, 65)), P + "invalid_count:keys")

    def test_item_keys_n_and_n_plus_1(self):
        r = req()
        item = r["exposures"][0]
        r["exposures"][0] = self._padded(item, 64)
        self.assertEqual(self._call(r), P + "unknown_key")
        r = req()
        r["exposures"][0] = self._padded(r["exposures"][0], 65)
        self.assertEqual(self._call(r), P + "invalid_count:keys")

    def test_cap_before_iteration_set_not_reached(self):
        def boom(*a, **k):
            raise AssertionError("set() reached before key cap")
        eg.set = boom
        try:
            huge = {("k%d" % i): 1 for i in range(10 ** 6)}
            self.assertEqual(self._call(huge), P + "invalid_count:keys")
        finally:
            del eg.set


class FieldTypePins(unittest.TestCase):
    def test_p1_blank_task(self):
        self.assertEqual(err(task=" "), P + "invalid_text:task")

    def test_p2_non_list_collections(self):
        for name in ("exposures", "anthropometric", "controls"):
            for bad in (5, "ab", {}):
                self.assertEqual(err(**{name: bad}), P + "invalid_count:" + name, (name, bad))

    def test_p3_exposure_kind(self):
        for bad in (5, "a\nb"):
            self.assertEqual(err(exposures=[{"id": "x", "kind": bad, "value": 1, "unit": "N"}]), P + "invalid_text:kind", bad)

    def test_p4_anthropometric_value(self):
        for bad in ("x", 10 ** 13):
            self.assertEqual(err(anthropometric=[{"dimension": "d", "percentile": 5, "value": bad, "unit": "mm"}]),
                             P + "invalid_number:value", bad)

    def test_p5_control_description(self):
        self.assertEqual(err(controls=[{"id": "c", "description": 5}]), P + "invalid_text:description")


if __name__ == "__main__":
    unittest.main()
