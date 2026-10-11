import unittest

from app.modules.m20_general_cognitive_worker import industrial_design1526 as idg

P = "INDUST1526:"


def req(**k):
    r = {"criteria": [{"id": "cost", "weight": 3}, {"id": "look", "weight": 1}],
         "concepts": [{"id": "A", "name": "Alpha", "scores": {"cost": 5, "look": 9}},
                      {"id": "B", "name": "Beta", "scores": {"cost": 8, "look": 2}}],
         "user_needs": [{"id": "n1", "text": "easy to hold"}], "prototype_evidence": []}
    r.update(k)
    return r


def err(**k):
    try:
        idg.run(req(**k))
    except ValueError as e:
        return str(e)
    raise AssertionError("no refusal")


class Behaviour(unittest.TestCase):
    def test_weighted_totals_and_rank(self):
        out = idg.run(req())
        self.assertEqual([c["id"] for c in out["ranking"]], ["B", "A"])
        self.assertEqual({c["id"]: c["weighted_total"] for c in out["ranking"]}, {"A": 24, "B": 26})
        self.assertEqual(out["max_possible_total"], 40)
        self.assertEqual(out["ranking"][0]["fraction_of_max"], "13/20")
        self.assertEqual(out["ranking"][1]["fraction_of_max"], "3/5")
        self.assertEqual(out["ranking"][0]["rank"], 1)

    def test_ties_share_rank_and_are_flagged(self):
        r = req(concepts=[{"id": "B", "name": "b", "scores": {"cost": 5, "look": 5}},
                          {"id": "A", "name": "a", "scores": {"cost": 5, "look": 5}},
                          {"id": "C", "name": "c", "scores": {"cost": 0, "look": 0}}])
        out = idg.run(r)
        self.assertEqual([(c["id"], c["rank"], c["tied_with"]) for c in out["ranking"]],
                         [("A", 1, ["B"]), ("B", 1, ["A"]), ("C", 3, [])])
        self.assertIs(out["tie_at_top"], True)
        self.assertIs(idg.run(req())["tie_at_top"], False)

    def test_no_decision_no_release(self):
        out = idg.run(req())
        self.assertIsNone(out["selected_concept"])
        self.assertIs(out["selection_requires_human_decision"], True)
        self.assertIs(out["release_ready"], False)
        self.assertIs(out["manufacturing_claims"], False)

    def test_prototype_evidence_refs(self):
        out = idg.run(req(prototype_evidence=[{"id": "p1", "concept_id": "A"}, {"id": "p2", "concept_id": "A"}]))
        self.assertEqual(out["prototype_evidence_counts"], {"A": 2, "B": 0})
        self.assertEqual(err(prototype_evidence=[{"id": "p1", "concept_id": "Z"}]), P + "unknown_concept")
        self.assertEqual(err(prototype_evidence=[{"id": "p1", "concept_id": "A"}, {"id": "p1", "concept_id": "A"}]), P + "duplicate_id:prototype_evidence")

    def test_score_and_weight_pins(self):
        for s in (0, 10):
            idg.run(req(concepts=[{"id": "A", "name": "a", "scores": {"cost": s, "look": s}}]))
        for s in (-1, 11, True, 5.0, "5", None):
            self.assertEqual(err(concepts=[{"id": "A", "name": "a", "scores": {"cost": s, "look": 1}}]), P + "invalid_score", s)
        for w in (1, 100):
            idg.run(req(criteria=[{"id": "cost", "weight": w}, {"id": "look", "weight": 1}]))
        for w in (0, 101, True, 1.5, "2"):
            self.assertEqual(err(criteria=[{"id": "cost", "weight": w}, {"id": "look", "weight": 1}]), P + "invalid_weight", w)

    def test_missing_and_extra_scores(self):
        self.assertEqual(err(concepts=[{"id": "A", "name": "a", "scores": {"cost": 1}}]), P + "missing_score")
        self.assertEqual(err(concepts=[{"id": "A", "name": "a", "scores": {"cost": 1, "look": 1, "zzz": 1}}]), P + "unknown_criterion")
        self.assertEqual(err(concepts=[{"id": "A", "name": "a", "scores": []}]), P + "invalid_item:scores")

    def test_counts_n_and_n_plus_1(self):
        crit = [{"id": "c%d" % i, "weight": 1} for i in range(16)]
        conc = [{"id": "k1", "name": "n", "scores": {c["id"]: 1 for c in crit}}]
        idg.run(req(criteria=crit, concepts=conc))
        self.assertEqual(err(criteria=crit + [{"id": "c16", "weight": 1}], concepts=conc), P + "invalid_count:criteria")
        self.assertEqual(err(criteria=[], concepts=conc), P + "invalid_count:criteria")
        many = [{"id": "k%d" % i, "name": "n", "scores": {"cost": 1, "look": 1}} for i in range(32)]
        idg.run(req(concepts=many))
        self.assertEqual(err(concepts=many + [{"id": "k32", "name": "n", "scores": {"cost": 1, "look": 1}}]), P + "invalid_count:concepts")
        self.assertEqual(err(concepts=[]), P + "invalid_count:concepts")
        needs = [{"id": "n%d" % i, "text": "t"} for i in range(64)]
        idg.run(req(user_needs=needs))
        self.assertEqual(err(user_needs=needs + [{"id": "n64", "text": "t"}]), P + "invalid_count:user_needs")
        ev = [{"id": "p%d" % i, "concept_id": "A"} for i in range(64)]
        idg.run(req(prototype_evidence=ev))
        self.assertEqual(err(prototype_evidence=ev + [{"id": "p64", "concept_id": "A"}]), P + "invalid_count:prototype_evidence")

    def test_text_dups_unknown(self):
        self.assertEqual(err(criteria=[{"id": "a", "weight": 1}, {"id": "a", "weight": 1}]), P + "duplicate_id:criteria")
        self.assertEqual(err(concepts=[{"id": "A", "name": "a", "scores": {"cost": 1, "look": 1}}] * 2), P + "duplicate_id:concepts")
        self.assertEqual(err(user_needs=[{"id": "n", "text": "t"}] * 2), P + "duplicate_id:user_needs")
        self.assertEqual(err(user_needs=[{"id": "n", "text": ""}]), P + "invalid_text:text")
        self.assertEqual(err(concepts=[{"id": "A", "name": "", "scores": {"cost": 1, "look": 1}}]), P + "invalid_text:name")
        idg.run(req(user_needs=[{"id": "n", "text": "x" * 128}]))
        self.assertEqual(err(user_needs=[{"id": "n", "text": "x" * 129}]), P + "invalid_text:text")
        self.assertEqual(err(zzz=1), P + "unknown_key")
        self.assertEqual(err(criteria=[{"id": "a", "weight": 1, "z": 1}]), P + "unknown_key")
        with self.assertRaises(ValueError) as cm:
            idg.run([])
        self.assertEqual(str(cm.exception), P + "invalid_request")

    def test_non_dict_item_and_empty_needs(self):
        self.assertEqual(err(criteria=["x"]), P + "invalid_item:criteria")
        self.assertEqual(err(user_needs=[5]), P + "invalid_item:user_needs")
        self.assertEqual(idg.run(req(user_needs=[]))["ranking"][0]["id"], "B")


class UnicodeRule(unittest.TestCase):
    BAD = {"U+0085": "\u0085", "U+2028": "\u2028", "U+2029": "\u2029", "U+202E": "\u202e",
           "U+200B": "\u200b", "U+FEFF": "\ufeff", "DEL": "\x7f"}

    def _call(self, expr, value):
        return err(**eval("dict(%s)" % (expr % "VALUE"), {"VALUE": value}))

    def test_seven_pins_refused_naming_field_not_value(self):
        for expr, field in [("user_needs=[{'id': 'n1', 'text': %s}]", 'text'), ("user_needs=[{'id': %s, 'text': 't'}]", 'id')]:
            for label, ch in self.BAD.items():
                for value in ("a" + ch + "b", ch):
                    self.assertEqual(self._call(expr, value), P + "invalid_text:" + field, (field, label))

    def test_cap_then_unicode_and_allowed_text(self):
        for expr, field in [("user_needs=[{'id': 'n1', 'text': %s}]", 'text'), ("user_needs=[{'id': %s, 'text': 't'}]", 'id')]:
            self.assertEqual(self._call(expr, "x" * 128 + "\u200b"), P + "invalid_text:" + field)
            self.assertEqual(self._call(expr, "\u200b" + "x" * 128), P + "invalid_text:" + field)

    def test_ordinary_space_and_printable_non_ascii_not_refused_by_rule(self):
        for expr, field in [("user_needs=[{'id': 'n1', 'text': %s}]", 'text'), ("user_needs=[{'id': %s, 'text': 't'}]", 'id')]:
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
            idg.run(request)
        except ValueError as e:
            return str(e)
        raise AssertionError("no refusal")

    def test_top_level_keys_n_and_n_plus_1(self):
        r = req()
        self.assertEqual(self._call(self._padded(r, 64)), P + "unknown_key")
        self.assertEqual(self._call(self._padded(r, 65)), P + "invalid_count:keys")

    def test_item_keys_n_and_n_plus_1(self):
        r = req()
        item = r["criteria"][0]
        r["criteria"][0] = self._padded(item, 64)
        self.assertEqual(self._call(r), P + "unknown_key")
        r = req()
        r["criteria"][0] = self._padded(r["criteria"][0], 65)
        self.assertEqual(self._call(r), P + "invalid_count:keys")

    def test_cap_before_iteration_set_not_reached(self):
        def boom(*a, **k):
            raise AssertionError("set() reached before key cap")
        idg.set = boom
        try:
            huge = {("k%d" % i): 1 for i in range(10 ** 6)}
            self.assertEqual(self._call(huge), P + "invalid_count:keys")
        finally:
            del idg.set

    def test_nested_scores_keys_n_and_n_plus_1(self):
        r = req()
        r["concepts"][0]["scores"] = self._padded(r["concepts"][0].get("scores") or {}, 65)
        self.assertEqual(self._call(r), P + "invalid_count:keys")


class ConceptIdType(unittest.TestCase):
    def test_non_string_concept_id_refused_before_hashing(self):
        for bad in ([1], {"a": 1}, 5, None, True, 1.5, (1,), "", "x" * 129, "a\u202eb"):
            self.assertEqual(err(prototype_evidence=[{"id": "e", "concept_id": bad}]), P + "invalid_text:concept_id", repr(bad)[:20])
        self.assertEqual(err(prototype_evidence=[{"id": "e", "concept_id": "zzz"}]), P + "unknown_concept")
        self.assertEqual(idg.run(req(prototype_evidence=[{"id": "e", "concept_id": "A"}]))["ranking"][0]["id"] in ("A", "B"), True)


if __name__ == "__main__":
    unittest.main()
