import unittest

from app.modules.m20_general_cognitive_worker import design_for_assembly1528 as dfa

P = "DESASS1528:"


def part(pid, mv=False, mat=False, svc=False):
    return {"id": pid, "moves_relative": mv, "different_material_required": mat, "service_removal_required": svc}


def req(**k):
    r = {"parts": [part("base", mv=True), part("screw"), part("cover", svc=True), part("label")],
         "assembly_steps": [{"id": "s1", "part_ids": ["base", "cover"]}, {"id": "s2", "part_ids": ["screw"]}]}
    r.update(k)
    return r


def err(**k):
    try:
        dfa.run(req(**k))
    except ValueError as e:
        return str(e)
    raise AssertionError("no refusal")


class Behaviour(unittest.TestCase):
    def test_counts_and_fractions(self):
        out = dfa.run(req())
        self.assertEqual(out["part_count"], 4)
        self.assertEqual(out["theoretical_minimum_parts"], 2)
        self.assertEqual(out["essential_part_ids"], ["base", "cover"])
        self.assertEqual(out["combination_candidates"], ["screw", "label"])
        self.assertEqual(out["reduction_fraction"], "1/2")
        self.assertEqual(out["efficiency_ratio"], "1/2")
        self.assertEqual(out["parts_without_step"], ["label"])
        self.assertEqual(out["step_count"], 2)
        self.assertIs(out["assembly_time_or_cost_claimed"], False)

    def test_each_criterion_alone_makes_essential(self):
        for kw in ({"mv": True}, {"mat": True}, {"svc": True}):
            out = dfa.run({"parts": [part("a", **kw), part("b")], "assembly_steps": []})
            self.assertEqual(out["essential_part_ids"], ["a"], kw)
            self.assertEqual(out["combination_candidates"], ["b"])

    def test_all_essential_and_none_essential(self):
        out = dfa.run({"parts": [part("a", mv=True), part("b", mat=True)], "assembly_steps": []})
        self.assertEqual((out["reduction_fraction"], out["efficiency_ratio"], out["combination_candidates"]), ("0", "1", []))
        out = dfa.run({"parts": [part("a"), part("b"), part("c")], "assembly_steps": []})
        self.assertEqual((out["theoretical_minimum_parts"], out["reduction_fraction"], out["efficiency_ratio"]), (0, "1", "0"))

    def test_fraction_lowest_terms(self):
        parts = [part("a", mv=True)] + [part("p%d" % i) for i in range(5)]
        out = dfa.run({"parts": parts, "assembly_steps": []})
        self.assertEqual((out["reduction_fraction"], out["efficiency_ratio"]), ("5/6", "1/6"))
        parts = [part("a", mv=True), part("b", mv=True), part("c", mv=True), part("d")]
        out = dfa.run({"parts": parts, "assembly_steps": []})
        self.assertEqual((out["reduction_fraction"], out["efficiency_ratio"]), ("1/4", "3/4"))

    def test_identical_parts_are_not_conflated(self):
        # the part list is by id; two parts with equal flags are both counted
        out = dfa.run({"parts": [part("a", mv=True), part("b", mv=True)], "assembly_steps": []})
        self.assertEqual(out["theoretical_minimum_parts"], 2)

    def test_step_coverage(self):
        out = dfa.run(req(assembly_steps=[]))
        self.assertEqual(out["parts_without_step"], ["base", "cover", "label", "screw"])
        self.assertEqual(out["step_count"], 0)


class Refusals(unittest.TestCase):
    def test_request(self):
        with self.assertRaises(ValueError) as cm:
            dfa.run([])
        self.assertEqual(str(cm.exception), P + "invalid_request")
        self.assertEqual(err(zzz=1), P + "unknown_key")

    def test_counts_n_and_n_plus_1(self):
        ps = [part("p%d" % i) for i in range(128)]
        dfa.run(req(parts=ps, assembly_steps=[]))
        self.assertEqual(err(parts=ps + [part("p128")], assembly_steps=[]), P + "invalid_count:parts")
        self.assertEqual(err(parts=[], assembly_steps=[]), P + "invalid_count:parts")
        steps = [{"id": "s%d" % i, "part_ids": ["base"]} for i in range(128)]
        dfa.run(req(assembly_steps=steps))
        self.assertEqual(err(assembly_steps=steps + [{"id": "s128", "part_ids": ["base"]}]), P + "invalid_count:assembly_steps")
        ids = ["base"] * 32
        dfa.run(req(assembly_steps=[{"id": "s", "part_ids": ids}]))
        self.assertEqual(err(assembly_steps=[{"id": "s", "part_ids": ids + ["base"]}]), P + "invalid_count:part_ids")
        self.assertEqual(err(assembly_steps=[{"id": "s", "part_ids": []}]), P + "invalid_count:part_ids")

    def test_flags_must_be_real_booleans(self):
        for key in ("moves_relative", "different_material_required", "service_removal_required"):
            for bad in (1, 0, "yes", None):
                p = part("x")
                p[key] = bad
                self.assertEqual(err(parts=[p], assembly_steps=[]), P + "invalid_bool:" + key, (key, bad))
            p = part("x")
            del p[key]
            self.assertEqual(err(parts=[p], assembly_steps=[]), P + "invalid_bool:" + key)

    def test_ids_refs_dups(self):
        self.assertEqual(err(parts=[part("a"), part("a")], assembly_steps=[]), P + "duplicate_id:parts")
        self.assertEqual(err(assembly_steps=[{"id": "s", "part_ids": ["nope"]}]), P + "unknown_part")
        self.assertEqual(err(assembly_steps=[{"id": "s", "part_ids": ["base"]}, {"id": "s", "part_ids": ["base"]}]), P + "duplicate_id:assembly_steps")
        self.assertEqual(err(parts=[part("")], assembly_steps=[]), P + "invalid_text:id")
        dfa.run(req(parts=[part("x" * 128)], assembly_steps=[]))
        self.assertEqual(err(parts=[part("x" * 129)], assembly_steps=[]), P + "invalid_text:id")
        self.assertEqual(err(assembly_steps=[{"id": "s", "part_ids": [5]}]), P + "invalid_text:part_ids")
        self.assertEqual(err(parts=[{**part("a"), "z": 1}], assembly_steps=[]), P + "unknown_key")
        self.assertEqual(err(parts=[5]), P + "invalid_item:parts")
        self.assertEqual(err(assembly_steps=[{"id": "s", "part_ids": "base"}]), P + "invalid_count:part_ids")


class UnicodeRule(unittest.TestCase):
    BAD = {"U+0085": "\u0085", "U+2028": "\u2028", "U+2029": "\u2029", "U+202E": "\u202e",
           "U+200B": "\u200b", "U+FEFF": "\ufeff", "DEL": "\x7f"}

    def _call(self, expr, value):
        return err(**eval("dict(%s)" % (expr % "VALUE"), {"VALUE": value}))

    def test_seven_pins_refused_naming_field_not_value(self):
        for expr, field in [("assembly_steps=[{'id': %s, 'part_ids': ['base']}]", 'id')]:
            for label, ch in self.BAD.items():
                for value in ("a" + ch + "b", ch):
                    self.assertEqual(self._call(expr, value), P + "invalid_text:" + field, (field, label))

    def test_cap_then_unicode_and_allowed_text(self):
        for expr, field in [("assembly_steps=[{'id': %s, 'part_ids': ['base']}]", 'id')]:
            self.assertEqual(self._call(expr, "x" * 128 + "\u200b"), P + "invalid_text:" + field)
            self.assertEqual(self._call(expr, "\u200b" + "x" * 128), P + "invalid_text:" + field)

    def test_ordinary_space_and_printable_non_ascii_not_refused_by_rule(self):
        for expr, field in [("assembly_steps=[{'id': %s, 'part_ids': ['base']}]", 'id')]:
            for value in ("caf\u00e9 \u00fc\u4e2d", "a b", "\u00a0x"):
                try:
                    got = self._call(expr, value)
                except AssertionError:
                    continue
                self.assertNotEqual(got, P + "invalid_text:" + field, (field, value))


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
            dfa.run(request)
        except ValueError as e:
            return str(e)
        raise AssertionError("no refusal")

    def test_top_level_keys_n_and_n_plus_1(self):
        r = req()
        self.assertEqual(self._call(self._padded(r, 64)), P + "unknown_key")
        self.assertEqual(self._call(self._padded(r, 65)), P + "invalid_count:keys")

    def test_item_keys_n_and_n_plus_1(self):
        r = req()
        item = r["parts"][0]
        r["parts"][0] = self._padded(item, 64)
        self.assertEqual(self._call(r), P + "unknown_key")
        r = req()
        r["parts"][0] = self._padded(r["parts"][0], 65)
        self.assertEqual(self._call(r), P + "invalid_count:keys")

    def test_cap_before_iteration_set_not_reached(self):
        def boom(*a, **k):
            raise AssertionError("set() reached before key cap")
        dfa.set = boom
        try:
            huge = {("k%d" % i): 1 for i in range(10 ** 6)}
            self.assertEqual(self._call(huge), P + "invalid_count:keys")
        finally:
            del dfa.set


if __name__ == "__main__":
    unittest.main()
