import json
import unittest

from app.modules.m20_general_cognitive_worker import human_factors_engineering1524 as hf

P = "HUMANF1524:"


def err(**kw):
    req_kw = kw
    with_req = req_kw.pop("_req", None)
    try:
        hf.run(with_req if with_req is not None else globals()["req"](**req_kw))
    except ValueError as e:
        return str(e)
    raise AssertionError("no refusal")


def uerr(sev=3, lik=3, mit=None, **extra):
    e = {"id": "e1", "description": "d", "severity": sev, "likelihood": lik, "mitigation_ids": mit or []}
    e.update(extra)
    return e


def task(tid="t1", errors=None, **extra):
    t = {"id": tid, "name": "Task", "safety_consequence": False, "use_errors": [uerr()] if errors is None else errors}
    t.update(extra)
    return t


def req(**k):
    r = {"users": [{"id": "u1", "role": "operator"}], "tasks": [task()], "mitigations": [{"id": "m1", "description": "guard"}],
         "validation_participants": []}
    r.update(k)
    return r


class Basic(unittest.TestCase):
    def test_shape_and_flags(self):
        out = hf.run(req())
        self.assertIs(out["unvalidated"], True)
        self.assertIs(out["usability_study_claimed"], False)
        self.assertEqual(out["summary"], {"task_count": 1, "error_count": 1, "max_risk_index": 9,
                                          "unmitigated_high_ids": [], "validation_participant_count": 0})
        e = out["tasks"][0]["use_errors"][0]
        self.assertEqual((e["risk_index"], e["band"], e["mitigated"]), (9, "medium", False))

    def test_band_edges_and_product(self):
        def idx(s, l):
            e = hf.run(req(tasks=[task(errors=[uerr(s, l)])]))["tasks"][0]["use_errors"][0]
            return e["risk_index"], e["band"]
        self.assertEqual(idx(5, 1), (5, "low"))
        self.assertEqual(idx(4, 2), (8, "medium"))
        self.assertEqual(idx(3, 2), (6, "low"))
        self.assertEqual(idx(5, 2), (10, "medium"))
        self.assertEqual(idx(3, 4), (12, "medium"))
        self.assertEqual(idx(5, 3), (15, "high"))
        self.assertEqual(idx(4, 3), (12, "medium"))
        self.assertEqual(idx(2, 5), (10, "medium"))
        # 14 is not reachable with 1..5 factors; 16 is high, 12 medium
        self.assertEqual(idx(4, 4), (16, "high"))
        self.assertEqual(idx(1, 4), (4, "low"))

    def test_mitigation_marks_and_unmitigated_high(self):
        t = [task("t1", [uerr(5, 5, ["m1"]), uerr(5, 3), uerr(1, 1)], safety_consequence=True)]
        t[0]["use_errors"][0]["id"] = "a"
        t[0]["use_errors"][1]["id"] = "b"
        t[0]["use_errors"][2]["id"] = "c"
        out = hf.run(req(tasks=t))
        self.assertEqual([e["id"] for e in out["tasks"][0]["use_errors"]], ["a", "b", "c"])
        self.assertEqual([e["mitigated"] for e in out["tasks"][0]["use_errors"]], [True, False, False])
        self.assertEqual(out["summary"]["unmitigated_high_ids"], ["t1/b"])
        self.assertIs(out["tasks"][0]["critical"], True)
        self.assertEqual(out["summary"]["max_risk_index"], 25)

    def test_errors_sorted_by_risk_desc_then_id(self):
        errs = [uerr(1, 1, id="z"), uerr(5, 5, id="y"), uerr(5, 5, id="x"), uerr(2, 2, id="w")]
        out = hf.run(req(tasks=[task(errors=errs)]))
        self.assertEqual([e["id"] for e in out["tasks"][0]["use_errors"]], ["x", "y", "w", "z"])

    def test_task_order_kept(self):
        out = hf.run(req(tasks=[task("b"), task("a")]))
        self.assertEqual([t["id"] for t in out["tasks"]], ["b", "a"])

    def test_empty_errors_allowed(self):
        out = hf.run(req(tasks=[task(errors=[])]))
        self.assertEqual(out["summary"]["max_risk_index"], 0)
        self.assertEqual(out["tasks"][0]["use_errors"], [])

    def test_validation_participants_counted_but_study_not_claimed(self):
        out = hf.run(req(validation_participants=[{"id": "p1"}, {"id": "p2"}]))
        self.assertEqual(out["summary"]["validation_participant_count"], 2)
        self.assertIs(out["unvalidated"], True)
        self.assertIs(out["usability_study_claimed"], False)

    def test_deterministic_and_input_not_mutated(self):
        r = req()
        before = json.dumps(r, sort_keys=True)
        a = hf.run(r)
        self.assertEqual(json.dumps(r, sort_keys=True), before)
        self.assertEqual(a, hf.run(req()))


class Refusals(unittest.TestCase):
    def test_request_and_keys(self):
        self.assertEqual(err(_req=[]), P + "invalid_request")
        self.assertEqual(err(_req=req(zzz=1)), P + "unknown_key")
        r = req(); del r["tasks"]
        self.assertEqual(err(_req=r), P + "invalid_count:tasks")
        r = req(); del r["users"]
        self.assertEqual(hf.run(r)["summary"]["task_count"], 1)

    def test_counts_n_and_n_plus_1(self):
        tasks = [task("t%d" % i, []) for i in range(64)]
        self.assertEqual(hf.run(req(tasks=tasks))["summary"]["task_count"], 64)
        self.assertEqual(err(tasks=tasks + [task("t64", [])]), P + "invalid_count:tasks")
        self.assertEqual(err(tasks=[]), P + "invalid_count:tasks")
        users = [{"id": "u%d" % i, "role": "r"} for i in range(64)]
        self.assertEqual(hf.run(req(users=users))["summary"]["task_count"], 1)
        self.assertEqual(err(users=users + [{"id": "u64", "role": "r"}]), P + "invalid_count:users")
        mits = [{"id": "m%d" % i, "description": "d"} for i in range(128)]
        hf.run(req(mitigations=mits))
        self.assertEqual(err(mitigations=mits + [{"id": "m128", "description": "d"}]), P + "invalid_count:mitigations")
        errs = [uerr(id="e%d" % i) for i in range(32)]
        hf.run(req(tasks=[task(errors=errs)]))
        self.assertEqual(err(tasks=[task(errors=errs + [uerr(id="e32")])]), P + "invalid_count:use_errors")
        mids = ["m1"] * 16
        hf.run(req(tasks=[task(errors=[uerr(mit=mids)])]))
        self.assertEqual(err(tasks=[task(errors=[uerr(mit=mids + ["m1"])])]), P + "invalid_count:mitigation_ids")
        parts = [{"id": "p%d" % i} for i in range(64)]
        hf.run(req(validation_participants=parts))
        self.assertEqual(err(validation_participants=parts + [{"id": "p64"}]), P + "invalid_count:validation_participants")

    def test_empty_mitigations_allowed_and_unknown_ref_refused(self):
        out = hf.run(req(mitigations=[], tasks=[task(errors=[uerr()])]))
        self.assertEqual(out["summary"]["error_count"], 1)
        self.assertEqual(err(mitigations=[], tasks=[task(errors=[uerr(mit=["m1"])])]), P + "unknown_mitigation")

    def test_scale_pins(self):
        for bad in (0, 6, -1, True, 2.0, "3", None):
            self.assertEqual(err(tasks=[task(errors=[uerr(sev=bad)])]), P + "invalid_scale:severity", bad)
            self.assertEqual(err(tasks=[task(errors=[uerr(lik=bad)])]), P + "invalid_scale:likelihood", bad)
        for ok in (1, 5):
            hf.run(req(tasks=[task(errors=[uerr(sev=ok, lik=ok)])]))

    def test_text_and_id_pins(self):
        hf.run(req(tasks=[task("x" * 128)]))
        self.assertEqual(err(tasks=[task("x" * 129)]), P + "invalid_text:id")
        for bad in ("", " ", 5, None):
            self.assertEqual(err(tasks=[task(bad)]), P + "invalid_text:id")
        self.assertEqual(err(tasks=[task(name="")]), P + "invalid_text:name")
        self.assertEqual(err(tasks=[task(errors=[uerr(description="")])]), P + "invalid_text:description")
        self.assertEqual(err(users=[{"id": "u", "role": ""}]), P + "invalid_text:role")
        self.assertEqual(err(mitigations=[{"id": "m", "description": ""}]), P + "invalid_text:description")

    def test_duplicates_and_references(self):
        self.assertEqual(err(tasks=[task("a"), task("a")]), P + "duplicate_id:tasks")
        self.assertEqual(err(users=[{"id": "u", "role": "r"}, {"id": "u", "role": "r"}]), P + "duplicate_id:users")
        self.assertEqual(err(mitigations=[{"id": "m", "description": "d"}, {"id": "m", "description": "d"}]),
                         P + "duplicate_id:mitigations")
        self.assertEqual(err(tasks=[task(errors=[uerr(id="e"), uerr(id="e")])]), P + "duplicate_id:use_errors")
        hf.run(req(tasks=[task("a", [uerr(id="e")]), task("b", [uerr(id="e")])]))  # per-task scope
        self.assertEqual(err(tasks=[task(errors=[uerr(mit=["nope"])])]), P + "unknown_mitigation")
        self.assertEqual(err(validation_participants=[{"id": "p"}, {"id": "p"}]), P + "duplicate_id:validation_participants")

    def test_types(self):
        self.assertEqual(err(tasks="x"), P + "invalid_count:tasks")
        self.assertEqual(err(tasks=[5]), P + "invalid_item:tasks")
        self.assertEqual(err(tasks=[task(safety_consequence="yes")]), P + "invalid_bool:safety_consequence")
        self.assertEqual(err(tasks=[task(errors=[5])]), P + "invalid_item:use_errors")
        self.assertEqual(err(tasks=[task(errors=[uerr(mit="m1")])]), P + "invalid_count:mitigation_ids")
        self.assertEqual(err(tasks=[task(errors=[uerr(mit=[5])])]), P + "invalid_text:mitigation_ids")
        self.assertEqual(err(tasks=[task(extra_field=1)]), P + "unknown_key")
        self.assertEqual(err(tasks=[task(errors=[uerr(extra_field=1)])]), P + "unknown_key")
        self.assertEqual(err(users=[{"id": "u", "role": "r", "x": 1}]), P + "unknown_key")

    def test_no_request_text_in_refusal(self):
        secret = "SECRET-VALUE-123"
        for r in (req(tasks=[task(secret + "\x00")]), req(zzz=secret), req(tasks=[task(errors=[uerr(mit=[secret])])])):
            try:
                hf.run(r)
            except ValueError as e:
                self.assertNotIn(secret, str(e))
                self.assertTrue(str(e).startswith(P))


class UnicodeRule(unittest.TestCase):
    BAD = {"U+0085": "\u0085", "U+2028": "\u2028", "U+2029": "\u2029", "U+202E": "\u202e",
           "U+200B": "\u200b", "U+FEFF": "\ufeff", "DEL": "\x7f"}

    def _call(self, expr, value):
        return err(**eval("dict(%s)" % (expr % "VALUE"), {"VALUE": value}))

    def test_seven_pins_refused_naming_field_not_value(self):
        for expr, field in [("users=[{'id': 'u1', 'role': %s}]", 'role'), ("users=[{'id': %s, 'role': 'r'}]", 'id')]:
            for label, ch in self.BAD.items():
                for value in ("a" + ch + "b", ch):
                    self.assertEqual(self._call(expr, value), P + "invalid_text:" + field, (field, label))

    def test_cap_then_unicode_and_allowed_text(self):
        for expr, field in [("users=[{'id': 'u1', 'role': %s}]", 'role'), ("users=[{'id': %s, 'role': 'r'}]", 'id')]:
            self.assertEqual(self._call(expr, "x" * 128 + "\u200b"), P + "invalid_text:" + field)
            self.assertEqual(self._call(expr, "\u200b" + "x" * 128), P + "invalid_text:" + field)

    def test_ordinary_space_and_printable_non_ascii_not_refused_by_rule(self):
        for expr, field in [("users=[{'id': 'u1', 'role': %s}]", 'role'), ("users=[{'id': %s, 'role': 'r'}]", 'id')]:
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
            hf.run(request)
        except ValueError as e:
            return str(e)
        raise AssertionError("no refusal")

    def test_top_level_keys_n_and_n_plus_1(self):
        r = req()
        self.assertEqual(self._call(self._padded(r, 64)), P + "unknown_key")
        self.assertEqual(self._call(self._padded(r, 65)), P + "invalid_count:keys")

    def test_item_keys_n_and_n_plus_1(self):
        r = req()
        item = r["users"][0]
        r["users"][0] = self._padded(item, 64)
        self.assertEqual(self._call(r), P + "unknown_key")
        r = req()
        r["users"][0] = self._padded(r["users"][0], 65)
        self.assertEqual(self._call(r), P + "invalid_count:keys")

    def test_cap_before_iteration_set_not_reached(self):
        def boom(*a, **k):
            raise AssertionError("set() reached before key cap")
        hf.set = boom
        try:
            huge = {("k%d" % i): 1 for i in range(10 ** 6)}
            self.assertEqual(self._call(huge), P + "invalid_count:keys")
        finally:
            del hf.set


if __name__ == "__main__":
    unittest.main()
