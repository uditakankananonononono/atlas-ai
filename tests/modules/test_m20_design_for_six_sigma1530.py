import unittest

from app.modules.m20_general_cognitive_worker import design_for_six_sigma1530 as dfs

P = "DFSS1530:"


def spec(**k):
    s = {"unit": "mm", "lower": 9, "target": 10, "upper": 11}
    s.update(k)
    return s


def req(**k):
    r = {"dmadv_phase": "measure",
         "ctqs": [{"id": "q1", "name": "width", "specification": spec()}, {"id": "q2", "name": "feel"}],
         "verification_plan": [{"id": "v1", "ctq_id": "q1", "method": "caliper study"}]}
    r.update(k)
    return r


def err(**k):
    try:
        dfs.run(req(**k))
    except ValueError as e:
        return str(e)
    raise AssertionError("no refusal")


class Behaviour(unittest.TestCase):
    def test_lists_and_flags(self):
        out = dfs.run(req())
        self.assertEqual(out["open_ctq_ids"], ["q2"])
        self.assertEqual(out["unverified_ctq_ids"], ["q2"])
        self.assertEqual(out["plan_items_by_ctq"], {"q1": 1, "q2": 0})
        self.assertEqual((out["phase"], out["phase_index"]), ("measure", 1))
        self.assertEqual(out["phase_gate_notes"], [])
        self.assertIs(out["statistical_validation_claimed"], False)
        self.assertIs(out["sigma_level_computed"], False)
        self.assertEqual(out["summary"], {"ctq_count": 2, "open_count": 1, "unverified_count": 1, "plan_item_count": 1})

    def test_phase_indexes(self):
        for i, ph in enumerate(("define", "measure", "analyze", "design", "verify")):
            self.assertEqual(dfs.run(req(dmadv_phase=ph))["phase_index"], i)
        self.assertEqual(err(dmadv_phase="improve"), P + "invalid_phase")
        self.assertEqual(err(dmadv_phase=None), P + "invalid_phase")
        self.assertEqual(err(dmadv_phase="Define"), P + "invalid_phase")

    def test_gate_notes(self):
        self.assertEqual(dfs.run(req(dmadv_phase="analyze"))["phase_gate_notes"], [])
        self.assertEqual(dfs.run(req(dmadv_phase="design"))["phase_gate_notes"], ["open_ctq_at_design_or_verify"])
        self.assertEqual(dfs.run(req(dmadv_phase="verify"))["phase_gate_notes"],
                         ["open_ctq_at_design_or_verify", "unverified_ctq_at_verify"])
        closed = req(dmadv_phase="verify", ctqs=[{"id": "q1", "name": "w", "specification": spec()}])
        self.assertEqual(dfs.run(closed)["phase_gate_notes"], [])
        unver = req(dmadv_phase="verify", ctqs=[{"id": "q1", "name": "w", "specification": spec()}], verification_plan=[])
        self.assertEqual(dfs.run(unver)["phase_gate_notes"], ["unverified_ctq_at_verify"])
        design_unver = req(dmadv_phase="design", ctqs=[{"id": "q1", "name": "w", "specification": spec()}], verification_plan=[])
        self.assertEqual(dfs.run(design_unver)["phase_gate_notes"], [])

    def test_spec_bound_combinations(self):
        for s in ({"unit": "mm", "lower": 1}, {"unit": "mm", "target": 1}, {"unit": "mm", "upper": 1},
                  {"unit": "mm", "lower": 1, "upper": 1}, {"unit": "mm", "lower": 1, "target": 1, "upper": 1}):
            dfs.run(req(ctqs=[{"id": "q", "name": "n", "specification": s}], verification_plan=[]))

    def test_plan_counts(self):
        plan = [{"id": "v1", "ctq_id": "q1", "method": "m"}, {"id": "v2", "ctq_id": "q1", "method": "m"}, {"id": "v3", "ctq_id": "q2", "method": "m"}]
        out = dfs.run(req(verification_plan=plan))
        self.assertEqual(out["plan_items_by_ctq"], {"q1": 2, "q2": 1})
        self.assertEqual(out["unverified_ctq_ids"], [])

    def test_order_kept(self):
        out = dfs.run(req(ctqs=[{"id": "z", "name": "n"}, {"id": "a", "name": "n"}], verification_plan=[]))
        self.assertEqual(out["open_ctq_ids"], ["z", "a"])
        self.assertEqual(out["unverified_ctq_ids"], ["z", "a"])


class Refusals(unittest.TestCase):
    def test_request_and_text(self):
        with self.assertRaises(ValueError) as cm:
            dfs.run([])
        self.assertEqual(str(cm.exception), P + "invalid_request")
        self.assertEqual(err(zzz=1), P + "unknown_key")
        self.assertEqual(err(ctqs=[{"id": "q", "name": ""}]), P + "invalid_text:name")
        dfs.run(req(ctqs=[{"id": "q", "name": "x" * 128}], verification_plan=[]))
        self.assertEqual(err(ctqs=[{"id": "q", "name": "x" * 129}]), P + "invalid_text:name")
        self.assertEqual(err(verification_plan=[{"id": "v", "ctq_id": "q1", "method": ""}]), P + "invalid_text:method")

    def test_counts_n_and_n_plus_1(self):
        cs = [{"id": "q%d" % i, "name": "n"} for i in range(64)]
        dfs.run(req(ctqs=cs, verification_plan=[]))
        self.assertEqual(err(ctqs=cs + [{"id": "q64", "name": "n"}], verification_plan=[]), P + "invalid_count:ctqs")
        self.assertEqual(err(ctqs=[], verification_plan=[]), P + "invalid_count:ctqs")
        pl = [{"id": "v%d" % i, "ctq_id": "q1", "method": "m"} for i in range(128)]
        dfs.run(req(verification_plan=pl))
        self.assertEqual(err(verification_plan=pl + [{"id": "v128", "ctq_id": "q1", "method": "m"}]), P + "invalid_count:verification_plan")

    def test_spec_rules(self):
        def e(s):
            return err(ctqs=[{"id": "q", "name": "n", "specification": s}], verification_plan=[])
        self.assertEqual(e({"unit": "mm"}), P + "specification_needs_bound")
        self.assertEqual(e({"lower": 1}), P + "invalid_text:unit")
        self.assertEqual(e({"unit": "mm", "lower": 2, "upper": 1}), P + "invalid_specification")
        self.assertEqual(e({"unit": "mm", "lower": 2, "target": 1}), P + "invalid_specification")
        self.assertEqual(e({"unit": "mm", "target": 3, "upper": 2}), P + "invalid_specification")
        self.assertEqual(e({"unit": "mm", "lower": "1"}), P + "invalid_number:lower")
        self.assertEqual(e({"unit": "mm", "lower": True}), P + "invalid_number:lower")
        self.assertEqual(e({"unit": "mm", "target": float("nan")}), P + "invalid_number:target")
        self.assertEqual(e({"unit": "mm", "upper": 10 ** 12 + 1}), P + "invalid_number:upper")
        self.assertEqual(e({"unit": "mm", "upper": 1, "z": 1}), P + "unknown_key")
        self.assertEqual(e([]), P + "invalid_item:specification")

    def test_refs_dups_shape(self):
        self.assertEqual(err(verification_plan=[{"id": "v", "ctq_id": "zz", "method": "m"}]), P + "unknown_ctq")
        self.assertEqual(err(ctqs=[{"id": "q", "name": "n"}, {"id": "q", "name": "n"}]), P + "duplicate_id:ctqs")
        self.assertEqual(err(verification_plan=[{"id": "v", "ctq_id": "q1", "method": "m"}] * 2), P + "duplicate_id:verification_plan")
        self.assertEqual(err(ctqs=[{"id": "", "name": "n"}]), P + "invalid_text:id")
        self.assertEqual(err(ctqs=[{"id": "q", "name": "n", "z": 1}]), P + "unknown_key")
        self.assertEqual(err(ctqs=[5]), P + "invalid_item:ctqs")
        self.assertEqual(err(verification_plan=[{"id": "v", "ctq_id": "q1", "method": "m", "z": 1}]), P + "unknown_key")

    def test_number_magnitude_and_float_accepted(self):
        def ok(s):
            dfs.run(req(ctqs=[{"id": "q", "name": "n", "specification": s}], verification_plan=[]))
        ok({"unit": "mm", "upper": 10 ** 12})
        ok({"unit": "mm", "lower": -10 ** 12})
        ok({"unit": "mm", "lower": 1.5, "upper": 2.5})


class UnicodeRule(unittest.TestCase):
    BAD = {"U+0085": "\u0085", "U+2028": "\u2028", "U+2029": "\u2029", "U+202E": "\u202e",
           "U+200B": "\u200b", "U+FEFF": "\ufeff", "DEL": "\x7f"}

    def _call(self, expr, value):
        return err(**eval("dict(%s)" % (expr % "VALUE"), {"VALUE": value}))

    def test_seven_pins_refused_naming_field_not_value(self):
        for expr, field in [("ctqs=[{'id': 'q', 'name': %s}], verification_plan=[]", 'name'), ("ctqs=[{'id': %s, 'name': 'n'}], verification_plan=[]", 'id')]:
            for label, ch in self.BAD.items():
                for value in ("a" + ch + "b", ch):
                    self.assertEqual(self._call(expr, value), P + "invalid_text:" + field, (field, label))

    def test_cap_then_unicode_and_allowed_text(self):
        for expr, field in [("ctqs=[{'id': 'q', 'name': %s}], verification_plan=[]", 'name'), ("ctqs=[{'id': %s, 'name': 'n'}], verification_plan=[]", 'id')]:
            self.assertEqual(self._call(expr, "x" * 128 + "\u200b"), P + "invalid_text:" + field)
            self.assertEqual(self._call(expr, "\u200b" + "x" * 128), P + "invalid_text:" + field)

    def test_ordinary_space_and_printable_non_ascii_not_refused_by_rule(self):
        for expr, field in [("ctqs=[{'id': 'q', 'name': %s}], verification_plan=[]", 'name'), ("ctqs=[{'id': %s, 'name': 'n'}], verification_plan=[]", 'id')]:
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
            self.assertEqual(err(ctqs=[{'id': 'q', 'name': 'n', 'specification': {'unit': 'mm', 'lower': BIG}}], verification_plan=[]), P + "invalid_number:lower")
            self.assertLess(time.perf_counter() - t0, 0.5)
        BIG = "9" * 10 ** 7
        self.assertEqual(err(ctqs=[{'id': 'q', 'name': 'n', 'specification': {'unit': 'mm', 'lower': BIG}}], verification_plan=[]), P + "invalid_number:lower")


    def test_guard_precedes_abs(self):
        def boom(_):
            raise AssertionError("abs reached before size guard")
        dfs.abs = boom
        try:
            BIG = 1 << (8 * 10 ** 6)
            self.assertIn("invalid_number", err(ctqs=[{'id': 'q', 'name': 'n', 'specification': {'unit': 'mm', 'lower': BIG}}], verification_plan=[]))
        finally:
            del dfs.abs


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
            dfs.run(request)
        except ValueError as e:
            return str(e)
        raise AssertionError("no refusal")

    def test_top_level_keys_n_and_n_plus_1(self):
        r = req()
        self.assertEqual(self._call(self._padded(r, 64)), P + "unknown_key")
        self.assertEqual(self._call(self._padded(r, 65)), P + "invalid_count:keys")

    def test_item_keys_n_and_n_plus_1(self):
        r = req()
        item = r["ctqs"][0]
        r["ctqs"][0] = self._padded(item, 64)
        self.assertEqual(self._call(r), P + "unknown_key")
        r = req()
        r["ctqs"][0] = self._padded(r["ctqs"][0], 65)
        self.assertEqual(self._call(r), P + "invalid_count:keys")

    def test_cap_before_iteration_set_not_reached(self):
        def boom(*a, **k):
            raise AssertionError("set() reached before key cap")
        dfs.set = boom
        try:
            huge = {("k%d" % i): 1 for i in range(10 ** 6)}
            self.assertEqual(self._call(huge), P + "invalid_count:keys")
        finally:
            del dfs.set

    def test_nested_specification_keys_n_and_n_plus_1(self):
        r = req()
        r["ctqs"][0]["specification"] = self._padded(r["ctqs"][0].get("specification") or {}, 65)
        self.assertEqual(self._call(r), P + "invalid_count:keys")


class BlankAndCollectionPins(unittest.TestCase):
    def test_q1_blank_text_names_field_per_field(self):
        self.assertEqual(err(ctqs=[{"id": "q", "name": " "}], verification_plan=[]), P + "invalid_text:name")
        self.assertEqual(err(ctqs=[{"id": "q", "name": "n", "specification": {"unit": " ", "lower": 1}}], verification_plan=[]),
                         P + "invalid_text:unit")
        self.assertEqual(err(verification_plan=[{"id": "v", "ctq_id": "q1", "method": " "}]), P + "invalid_text:method")

    def test_q1_blank_ctq_id_is_invalid_text_not_unknown_ctq(self):
        self.assertEqual(err(ctqs=[{"id": " ", "name": "n"}], verification_plan=[]), P + "invalid_text:id")
        self.assertEqual(err(ctqs=[{"id": " ", "name": "n"}]), P + "invalid_text:id")
        self.assertEqual(err(verification_plan=[{"id": "v", "ctq_id": " ", "method": "m"}]), P + "invalid_text:ctq_id")

    def test_q2_non_list_collections(self):
        for name in ("ctqs", "verification_plan"):
            for bad in (5, "ab", {}):
                self.assertEqual(err(**{name: bad}), P + "invalid_count:" + name, (name, bad))


if __name__ == "__main__":
    unittest.main()
