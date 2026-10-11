import unicodedata
import unittest

from app.modules.m20_general_cognitive_worker import design_for_manufacturing1527 as dfm

P = "DESMAN1527:"


def feat(fid="f1", **vals):
    return {"id": fid, "values": {k: {"value": v, "unit": "mm"} for k, v in vals.items()}}


def req(**k):
    r = {"process": "injection moulding",
         "process_constraints": [{"id": "wall", "field": "wall_thickness", "unit": "mm", "min": 2, "max": 10}],
         "features": [feat(wall_thickness=5)]}
    r.update(k)
    return r


def err(**k):
    try:
        dfm.run(req(**k))
    except ValueError as e:
        return str(e)
    raise AssertionError("no refusal")


def check(v, **c):
    cons = {"id": "wall", "field": "w", "unit": "mm", **c}
    return dfm.run(req(process_constraints=[cons], features=[feat(w=v)]))["feature_checks"][0]


class Behaviour(unittest.TestCase):
    def test_pass(self):
        out = dfm.run(req())
        self.assertEqual(out["feature_checks"], [{"feature_id": "f1", "violations": [], "missing_constraint_ids": []}])
        self.assertEqual(out["disposition"], "bookkeeping_only")
        self.assertIs(out["process_planning_claimed"], False)
        self.assertEqual(out["summary"], {"feature_count": 1, "constraint_count": 1, "violation_count": 0, "missing_count": 0,
                                           "features_with_violations_count": 0, "features_with_missing_count": 0,
                                           "features_without_findings_count": 1})

    def test_boundaries_n_and_n_plus_1(self):
        lo = dict(min=2, max=10)
        self.assertEqual(check(2, **lo)["violations"], [])
        self.assertEqual(check(10, **lo)["violations"], [])
        v = check(1.99, **lo)["violations"][0]
        self.assertEqual((v["kind"], v["bound"], v["margin"], v["constraint_id"], v["value"]), ("below_min", "2", "0.01", "wall", "1.99"))
        v = check(10.01, **lo)["violations"][0]
        self.assertEqual((v["kind"], v["bound"], v["margin"]), ("above_max", "10", "0.01"))
        self.assertEqual(check(0, min=0)["violations"], [])
        self.assertEqual(check(-0.5, min=0)["violations"][0]["margin"], "0.5")
        self.assertEqual(check(100, max=100)["violations"], [])
        self.assertEqual(len(check(101, max=100)["violations"]), 1)

    def test_only_one_bound(self):
        self.assertEqual(check(1000, min=2)["violations"], [])
        self.assertEqual(check(-1000, max=2)["violations"], [])

    def test_min_equals_max(self):
        self.assertEqual(check(3, min=3, max=3)["violations"], [])
        self.assertEqual(len(check(3.1, min=3, max=3)["violations"]), 1)
        self.assertEqual(len(check(2.9, min=3, max=3)["violations"]), 1)

    def test_missing_field_is_not_a_pass(self):
        out = dfm.run(req(features=[{"id": "f1", "values": {}}]))
        self.assertEqual(out["feature_checks"][0]["missing_constraint_ids"], ["wall"])
        self.assertEqual(out["summary"]["missing_count"], 1)
        self.assertEqual(out["summary"]["features_with_missing_count"], 1)
        self.assertEqual(out["summary"]["features_without_findings_count"], 0)

    def test_multiple_constraints_and_features(self):
        cons = [{"id": "c1", "field": "a", "unit": "mm", "min": 1}, {"id": "c2", "field": "b", "unit": "mm", "max": 5}]
        feats = [feat("f1", a=0, b=9), feat("f2", a=1, b=5), {"id": "f3", "values": {"a": {"value": 2, "unit": "mm"}}}]
        out = dfm.run(req(process_constraints=cons, features=feats))
        self.assertEqual([[v["constraint_id"] for v in c["violations"]] for c in out["feature_checks"]], [["c1", "c2"], [], []])
        self.assertEqual(out["feature_checks"][2]["missing_constraint_ids"], ["c2"])
        self.assertEqual(out["summary"], {"feature_count": 3, "constraint_count": 2, "violation_count": 2, "missing_count": 1,
                                           "features_with_violations_count": 1, "features_with_missing_count": 1,
                                           "features_without_findings_count": 1})

    def test_numeric_forms(self):
        self.assertEqual(check(10 ** 12, max=10 ** 12)["violations"], [])
        self.assertEqual(check(0.1 + 0.2, max=0.3)["violations"][0]["kind"], "above_max")


class Refusals(unittest.TestCase):
    def test_request(self):
        with self.assertRaises(ValueError) as cm:
            dfm.run([])
        self.assertEqual(str(cm.exception), P + "invalid_request")
        self.assertEqual(err(zzz=1), P + "unknown_key")
        self.assertEqual(err(process=""), P + "invalid_text:process")
        dfm.run(req(process="x" * 128))
        self.assertEqual(err(process="x" * 129), P + "invalid_text:process")

    def test_counts_n_and_n_plus_1(self):
        cons = [{"id": "c%d" % i, "field": "a", "unit": "mm", "min": 0} for i in range(64)]
        dfm.run(req(process_constraints=cons))
        self.assertEqual(err(process_constraints=cons + [{"id": "c64", "field": "a", "unit": "mm", "min": 0}]), P + "invalid_count:process_constraints")
        self.assertEqual(err(process_constraints=[]), P + "invalid_count:process_constraints")
        fs = [feat("f%d" % i, wall_thickness=5) for i in range(64)]
        dfm.run(req(features=fs))
        self.assertEqual(err(features=fs + [feat("f64", wall_thickness=5)]), P + "invalid_count:features")
        self.assertEqual(err(features=[]), P + "invalid_count:features")
        vals = {"v%d" % i: {"value": 1, "unit": "mm"} for i in range(32)}
        dfm.run(req(features=[{"id": "f", "values": vals}]))
        vals["v32"] = {"value": 1, "unit": "mm"}
        self.assertEqual(err(features=[{"id": "f", "values": vals}]), P + "invalid_count:values")

    def test_constraint_rules(self):
        base = {"id": "c", "field": "a", "unit": "mm"}
        self.assertEqual(err(process_constraints=[base]), P + "constraint_needs_bound")
        self.assertEqual(err(process_constraints=[{**base, "min": 5, "max": 4}]), P + "invalid_bounds")
        self.assertEqual(err(process_constraints=[{**base, "min": "1"}]), P + "invalid_number:min")
        self.assertEqual(err(process_constraints=[{**base, "min": True}]), P + "invalid_number:min")
        self.assertEqual(err(process_constraints=[{**base, "min": float("nan")}]), P + "invalid_number:min")
        self.assertEqual(err(process_constraints=[{**base, "max": 10 ** 12 + 1}]), P + "invalid_number:max")
        self.assertEqual(err(process_constraints=[{**base, "min": 0}, {**base, "min": 0}]), P + "duplicate_id:process_constraints")
        self.assertEqual(err(process_constraints=[{**base, "min": 0, "z": 1}]), P + "unknown_key")
        self.assertEqual(err(process_constraints=[{**base, "min": 0, "unit": ""}]), P + "invalid_text:unit")

    def test_value_rules(self):
        self.assertEqual(err(features=[{"id": "f", "values": {"wall_thickness": {"value": 5, "unit": "cm"}}}]), P + "unit_mismatch")
        self.assertEqual(err(features=[{"id": "f", "values": {"wall_thickness": {"value": "5", "unit": "mm"}}}]), P + "invalid_number:value")
        self.assertEqual(err(features=[{"id": "f", "values": {"wall_thickness": 5}}]), P + "invalid_item:values")
        self.assertEqual(err(features=[{"id": "f", "values": {"wall_thickness": {"value": 5, "unit": "mm", "z": 1}}}]), P + "unknown_key")
        self.assertEqual(err(features=[{"id": "f", "values": []}]), P + "invalid_item:values")
        self.assertEqual(err(features=[{"id": "f", "values": {}}, {"id": "f", "values": {}}]), P + "duplicate_id:features")
        self.assertEqual(err(features=[{"id": "f", "values": {}, "z": 1}]), P + "unknown_key")
        self.assertEqual(err(features=[5]), P + "invalid_item:features")


class ReviewPins(unittest.TestCase):
    def test_process_and_ids_accept_letter_x(self):
        out = dfm.run(req(process="CNC-X", process_constraints=[{"id": "X", "field": "w", "unit": "mm", "min": 1}],
                          features=[{"id": "X", "values": {"w": {"value": 5, "unit": "mm"}}}]))
        self.assertEqual(out["process"], "CNC-X")
        self.assertEqual(out["feature_checks"][0]["feature_id"], "X")

    def test_negative_fraction_value_rendering(self):
        v = check(-0.5, min=0)["violations"][0]
        self.assertEqual((v["kind"], v["value"], v["bound"], v["margin"]), ("below_min", "-0.5", "0", "0.5"))

    def test_zero_value_and_zero_bound_render_as_zero(self):
        v = check(0, min=1)["violations"][0]
        self.assertEqual((v["value"], v["bound"], v["margin"]), ("0", "1", "1"))
        v = check(-1, min=0)["violations"][0]
        self.assertEqual((v["value"], v["bound"], v["margin"]), ("-1", "0", "1"))
        v = check(1, max=0)["violations"][0]
        self.assertEqual((v["kind"], v["value"], v["bound"], v["margin"]), ("above_max", "1", "0", "1"))

    def test_bad_text_names_the_right_field(self):
        bad = ("", " ", "a\u200bb", "a\x00b")
        for b in bad:
            self.assertEqual(err(process_constraints=[{"id": b, "field": "w", "unit": "mm", "min": 1}]), P + "invalid_text:id", repr(b))
            self.assertEqual(err(process_constraints=[{"id": "c", "field": b, "unit": "mm", "min": 1}]), P + "invalid_text:field", repr(b))
            self.assertEqual(err(features=[{"id": b, "values": {}}]), P + "invalid_text:id", repr(b))
            self.assertEqual(err(features=[{"id": "f", "values": {"wall_thickness": {"value": 5, "unit": b}}}]), P + "invalid_text:unit", repr(b))
            self.assertEqual(err(process=b), P + "invalid_text:process", repr(b))


_CF = [chr(i) for i in range(0x110000) if unicodedata.category(chr(i)) == "Cf"]


class FullCfRefusal(unittest.TestCase):
    def test_named_code_points_are_cf(self):
        for ch in ("\u00ad", "\u2060", "\u061c", "\ufff9", "\U000e0001"):
            self.assertIn(ch, _CF)

    def test_every_cf_character_refused_in_every_echoed_text_field(self):
        for ch in _CF + ["\x00", "\x7f", "\x85", "\u2028", "\u2029"]:
            w = "a" + ch + "b"
            self.assertEqual(err(process=w), P + "invalid_text:process", hex(ord(ch)))
            self.assertEqual(err(process_constraints=[{"id": w, "field": "f", "unit": "mm", "min": 1}]), P + "invalid_text:id", hex(ord(ch)))
            self.assertEqual(err(process_constraints=[{"id": "c", "field": w, "unit": "mm", "min": 1}]), P + "invalid_text:field", hex(ord(ch)))
            self.assertEqual(err(process_constraints=[{"id": "c", "field": "f", "unit": w, "min": 1}]), P + "invalid_text:unit", hex(ord(ch)))
            self.assertEqual(err(features=[{"id": w, "values": {}}]), P + "invalid_text:id", hex(ord(ch)))
            self.assertEqual(err(features=[{"id": "f", "values": {w: {"value": 1, "unit": "mm"}}}]), P + "invalid_text:field", hex(ord(ch)))
            self.assertEqual(err(features=[{"id": "f", "values": {"wall_thickness": {"value": 1, "unit": w}}}]), P + "invalid_text:unit", hex(ord(ch)))

    def test_zs_and_printable_still_accepted(self):
        for ch in ("\u00a0", "\u2003", "\u3000", " ", "\u00e9", "\u4e2d"):
            self.assertEqual(dfm.run(req(process="a" + ch + "b"))["process"], "a" + ch + "b")


class SpyKey(str):
    """str subclass whose hash/eq calls are counted. Mechanics (grounded by running): building a dict with this key
    calls __hash__ during construction; set(d) on an exact dict reuses stored hashes, but the later set difference and
    any dict lookup call __eq__. So the counters are reset AFTER the input is built and must stay 0 when the type check
    refuses first. This does not prove anything about hashing done while the caller builds the input."""
    calls = []

    def __hash__(self):
        SpyKey.calls.append("hash")
        return str.__hash__(self)

    def __eq__(self, other):
        SpyKey.calls.append("eq")
        return str.__eq__(self, other)


def _shapes(key):
    cons = {"id": "c", "field": "f", "unit": "mm", "min": 1}
    feat_ = {"id": "f", "values": {"f": {"value": 1, "unit": "mm"}}}
    root = {"process": "p", "process_constraints": [cons], "features": [feat_]}
    return {
        "root": {**{k: v for k, v in root.items() if k != "process"}, key("process"): "p"},
        "constraint": {**root, "process_constraints": [{**{k: v for k, v in cons.items() if k != "id"}, key("id"): "c"}]},
        "feature": {**root, "features": [{**{k: v for k, v in feat_.items() if k != "id"}, key("id"): "f"}]},
        "cell": {**root, "features": [{"id": "f", "values": {"f": {**{"unit": "mm"}, key("value"): 1}}}]},
    }


class KeyTypeFirst(unittest.TestCase):
    def test_exact_str_keys_still_accepted(self):
        for name, r in _shapes(str).items():
            self.assertEqual(dfm.run(r)["process"], "p", name)

    def test_str_subclass_key_refused_at_every_shape_before_any_comparison(self):
        for name, r in _shapes(SpyKey).items():
            SpyKey.calls.clear()
            with self.assertRaises(ValueError) as cm:
                dfm.run(r)
            self.assertEqual(str(cm.exception), P + "unknown_key", name)
            self.assertEqual(SpyKey.calls, [], name)

    def test_non_str_keys_refused_at_every_shape(self):
        for name, r in _shapes(lambda k: 5).items():
            self.assertEqual(self._r(r), P + "unknown_key", name)

    def _r(self, r):
        try:
            dfm.run(r)
        except ValueError as e:
            return str(e)
        raise AssertionError("no refusal")

    def test_count_cap_still_first_with_subclass_keys(self):
        big = {SpyKey("k%d" % i): 1 for i in range(65)}
        SpyKey.calls.clear()
        self.assertEqual(self._r(big), P + "invalid_count:keys")
        self.assertEqual(SpyKey.calls, [])


class UnicodeRule(unittest.TestCase):
    BAD = {"U+0085": "\u0085", "U+2028": "\u2028", "U+2029": "\u2029", "U+202E": "\u202e",
           "U+200B": "\u200b", "U+FEFF": "\ufeff", "DEL": "\x7f"}

    def _call(self, expr, value):
        return err(**eval("dict(%s)" % (expr % "VALUE"), {"VALUE": value}))

    def test_seven_pins_refused_naming_field_not_value(self):
        for expr, field in [('process=%s', 'process'), ("process_constraints=[{'id': 'wall', 'field': 'wall_thickness', 'unit': %s, 'min': 2, 'max': 10}]", 'unit')]:
            for label, ch in self.BAD.items():
                for value in ("a" + ch + "b", ch):
                    self.assertEqual(self._call(expr, value), P + "invalid_text:" + field, (field, label))

    def test_cap_then_unicode_and_allowed_text(self):
        for expr, field in [('process=%s', 'process'), ("process_constraints=[{'id': 'wall', 'field': 'wall_thickness', 'unit': %s, 'min': 2, 'max': 10}]", 'unit')]:
            self.assertEqual(self._call(expr, "x" * 128 + "\u200b"), P + "invalid_text:" + field)
            self.assertEqual(self._call(expr, "\u200b" + "x" * 128), P + "invalid_text:" + field)

    def test_ordinary_space_and_printable_non_ascii_not_refused_by_rule(self):
        for expr, field in [('process=%s', 'process'), ("process_constraints=[{'id': 'wall', 'field': 'wall_thickness', 'unit': %s, 'min': 2, 'max': 10}]", 'unit')]:
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
            self.assertEqual(err(process_constraints=[{'id': 'wall', 'field': 'wall_thickness', 'unit': 'mm', 'min': BIG, 'max': 10}]), P + "invalid_number:min")
            self.assertLess(time.perf_counter() - t0, 0.5)
        BIG = "9" * 10 ** 7
        self.assertEqual(err(process_constraints=[{'id': 'wall', 'field': 'wall_thickness', 'unit': 'mm', 'min': BIG, 'max': 10}]), P + "invalid_number:min")


    def test_guard_precedes_abs(self):
        def boom(_):
            raise AssertionError("abs reached before size guard")
        dfm.abs = boom
        try:
            BIG = 1 << (8 * 10 ** 6)
            self.assertIn("invalid_number", err(process_constraints=[{'id': 'wall', 'field': 'wall_thickness', 'unit': 'mm', 'min': BIG, 'max': 10}]))
        finally:
            del dfm.abs


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
            dfm.run(request)
        except ValueError as e:
            return str(e)
        raise AssertionError("no refusal")

    def test_top_level_keys_n_and_n_plus_1(self):
        r = req()
        self.assertEqual(self._call(self._padded(r, 64)), P + "unknown_key")
        self.assertEqual(self._call(self._padded(r, 65)), P + "invalid_count:keys")

    def test_item_keys_n_and_n_plus_1(self):
        r = req()
        item = r["process_constraints"][0]
        r["process_constraints"][0] = self._padded(item, 64)
        self.assertEqual(self._call(r), P + "unknown_key")
        r = req()
        r["process_constraints"][0] = self._padded(r["process_constraints"][0], 65)
        self.assertEqual(self._call(r), P + "invalid_count:keys")

    def test_cap_before_iteration_set_not_reached(self):
        def boom(*a, **k):
            raise AssertionError("set() reached before key cap")
        dfm.set = boom
        try:
            huge = {("k%d" % i): 1 for i in range(10 ** 6)}
            self.assertEqual(self._call(huge), P + "invalid_count:keys")
        finally:
            del dfm.set


class ValueKeys(unittest.TestCase):
    def test_values_keys_are_checked_text(self):
        cell = {"value": 5, "unit": "mm"}
        for bad in (1, None, (1, 2), "", "k" * 129, "a\u202eb", "a\nb", 1.5, b"x"):
            self.assertEqual(err(features=[{"id": "f", "values": {bad: cell, "wall_thickness": cell}}]), P + "invalid_text:field", repr(bad)[:20])
        dfm.run(req(features=[{"id": "f", "values": {"k" * 128: cell, "caf\u00e9 x": cell}}]))
        self.assertEqual(err(features=[{"id": "f", "values": {"k" * 129: cell}}]), P + "invalid_text:field")


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
            out = dfm.run(request)
            self.assertEqual(before, self._state(decimal.getcontext()))
            return out
        finally:
            decimal.setcontext(old)

    def _rq(self, lo, hi, v):
        return req(process_constraints=[{"id": "wall", "field": "wall_thickness", "unit": "mm", "min": lo, "max": hi}],
                   features=[feat(wall_thickness=v)])

    def test_output_identical_across_ambient_contexts_and_exact(self):
        rq = self._rq(2.345, 3.1234567, 1.234)
        base = self._run_in(None, rq)
        v = base["feature_checks"][0]["violations"][0]
        self.assertEqual((v["value"], v["bound"], v["margin"]), ("1.234", "2.345", "1.111"))
        for kw in self.CTXS:
            self.assertEqual(self._run_in(kw, rq), base, kw)
        rq = self._rq(2.345, 3.1234567, 3.3456789)
        base = self._run_in(None, rq)
        v = base["feature_checks"][0]["violations"][0]
        self.assertEqual((v["value"], v["bound"], v["margin"]), ("3.3456789", "3.1234567", "0.2222222"))
        for kw in self.CTXS:
            self.assertEqual(self._run_in(kw, rq), base, kw)

    def test_margin_exact_beyond_64_digits(self):
        rq = self._rq(10 ** 11, 10 ** 12, 1e-60)
        want = "99999999999." + "9" * 60
        for kw in self.CTXS:
            self.assertEqual(self._run_in(kw, rq)["feature_checks"][0]["violations"][0]["margin"], want, kw)

    def test_value_equals_bound_exact_in_all_contexts(self):
        for lo, hi in ((2.345, 2.345), (0.1, 0.3), (1e-60, 1e-60)):
            for v in (lo, hi):
                for kw in self.CTXS:
                    out = self._run_in(kw, self._rq(lo, hi, v))
                    self.assertEqual(out["feature_checks"][0]["violations"], [], (lo, hi, v, kw))


class Bookkeeping(unittest.TestCase):
    def _mixed(self):
        cons = [{"id": "c1", "field": "a", "unit": "mm", "min": 1}, {"id": "c2", "field": "b", "unit": "mm", "max": 5}]
        feats = [feat("f1", a=2, b=3), feat("f2", a=0, b=3), feat("f3", a=2), feat("f4", a=0)]
        return dfm.run(req(process_constraints=cons, features=feats))

    def test_mixed_fixture_counts_and_union(self):
        s = self._mixed()["summary"]
        self.assertEqual(s, {"feature_count": 4, "constraint_count": 2, "violation_count": 2, "missing_count": 2,
                             "features_with_violations_count": 2, "features_with_missing_count": 2,
                             "features_without_findings_count": 1})

    def test_missing_only_feature_is_not_without_findings(self):
        cons = [{"id": "c1", "field": "a", "unit": "mm", "min": 1}]
        s = dfm.run(req(process_constraints=cons, features=[{"id": "f", "values": {}}]))["summary"]
        self.assertEqual((s["features_with_missing_count"], s["features_with_violations_count"], s["features_without_findings_count"]), (1, 0, 0))

    def test_keyset_disposition_and_no_manufacturable_string_anywhere(self):
        out = self._mixed()
        self.assertEqual(sorted(out), ["disposition", "feature_checks", "process", "process_planning_claimed", "summary"])
        self.assertEqual(out["disposition"], "bookkeeping_only")
        self.assertIs(out["process_planning_claimed"], False)
        self.assertEqual(sorted(out["summary"]), ["constraint_count", "feature_count", "features_with_missing_count",
                                                  "features_with_violations_count", "features_without_findings_count",
                                                  "missing_count", "violation_count"])
        self.assertEqual(sorted(out["feature_checks"][0]), ["feature_id", "missing_constraint_ids", "violations"])
        self.assertNotIn("manufacturable", repr(out).lower())


if __name__ == "__main__":
    unittest.main()
