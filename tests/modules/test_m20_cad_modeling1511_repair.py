"""Row 1511 CAD Modeling v3 repair pins: batch-rule validation order, FINAL
parameter caps, generic reasons, no-alias receipts, normalized canonical hash."""
import importlib.util
import json
import unittest

spec = importlib.util.spec_from_file_location(
    "cad_modeling1511_v3",
    "backend/app/modules/m20_general_cognitive_worker/cad_modeling1511.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
PREFIX = "CADMOD1511:"


def refusal(data):
    try:
        M.evaluate_feature_tree(data)
    except M.CadModelingRefusal as exc:
        return exc
    raise AssertionError("expected refusal")


class TestExactTypes(unittest.TestCase):
    def test_top_and_collections(self):
        class D(dict):
            pass

        class L(list):
            pass

        exc = refusal(D(features=[{"id": "a"}]))
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"features": L([{"id": "a"}])})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"features": ({"id": "a"},)})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"features": [D(id="a")]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"features": [{"id": "a", "references": ("b",)}]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"features": [{"id": "a", "references": L(["b"])}]})  # list subclass refused
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"features": [{"id": "a", "parameters": {"p": 1}}]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"features": [{"id": "a", "parameters": L(["p"])}]})  # list subclass refused
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"features": [{"id": "a"}], "parameters": [("p", "v")]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"features": [{"id": "a"}], "parameters": D(p="v")})  # dict subclass refused
        self.assertEqual(exc.code, PREFIX + "invalid_input")


class TestCountCapsBeforeIteration(unittest.TestCase):
    def test_shared_max_parameters_32(self):
        self.assertEqual(M.MAX_PARAMETERS, 32)
        base = {"features": [{"id": "a"}]}
        ok = dict(base, parameters={f"p{k}": "v" for k in range(32)})
        self.assertEqual(len(M.evaluate_feature_tree(ok)["parameters"]), 32)
        exc = refusal(dict(base, parameters={f"p{k}": "v" for k in range(33)}))
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertIn("32", str(exc))
        feat = {"id": "a", "parameters": [f"p{k}" for k in range(32)]}
        params = {f"p{k}": "v" for k in range(32)}
        M.evaluate_feature_tree({"features": [feat], "parameters": params})
        feat33 = {"id": "a", "parameters": [f"p{k}" for k in range(33)]}
        exc = refusal({"features": [feat33], "parameters": params})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertIn("32", str(exc))

    def test_features_and_refs_caps(self):
        exc = refusal({"features": [{"id": f"f{i}"} for i in range(65)]})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        exc = refusal({"features": [{"id": "a", "references": [f"r{i}" for i in range(65)]}]})
        self.assertEqual(exc.code, PREFIX + "resource_limit")

    def test_key_count_caps(self):
        exc = refusal({"features": [{"id": "a"}], "parameters": {}, "surprise": 1})
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        self.assertNotIn("surprise", str(exc))
        exc = refusal({"features": [{"id": "a", "references": [], "parameters": [], "extra": 1}]})
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        self.assertNotIn("extra", str(exc))


class TestParamStrings(unittest.TestCase):
    def test_key_raw_cap_32_first(self):
        params = {"k" * 32: "v"}
        M.evaluate_feature_tree({"features": [{"id": "a"}], "parameters": params})
        exc = refusal({"features": [{"id": "a"}], "parameters": {"k" * 33: "v"}})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertIn("parameters key", str(exc))
        self.assertIn("33", str(exc))

    def test_value_cap_32(self):
        params = {"p": "v" * 33}
        exc = refusal({"features": [{"id": "a"}], "parameters": params})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertIn("parameters value", str(exc))


class TestGenericReasons(unittest.TestCase):
    def test_no_echo(self):
        exc = refusal({"features": [{"id": "dup"}, {"id": "dup"}]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: duplicate id in features")
        exc = refusal({"features": [{"id": "a", "references": ["ghost"]}]})
        self.assertEqual(str(exc), PREFIX + "unknown_reference: unknown feature reference at features[0].references")
        self.assertNotIn("ghost", str(exc))
        exc = refusal({"features": [{"id": "a", "parameters": ["ghost"]}]})
        self.assertEqual(str(exc), PREFIX + "unknown_parameter: unknown parameter reference at features[0].parameters")
        self.assertNotIn("ghost", str(exc))


class TestReceiptAndHash(unittest.TestCase):
    def test_no_alias(self):
        data = {"features": [{"id": "a", "references": ["b"]}, {"id": "b"}],
                "parameters": {"p": "v"}}
        r = M.evaluate_feature_tree(data)
        data["features"][0]["references"].append("MUTATED")
        data["parameters"]["p"] = "MUTATED"
        self.assertEqual(r["feature_rows"][0]["references"], ["b"])
        self.assertEqual(r["parameters"], {"p": "v"})

    def test_canonical_hash_normalization(self):
        # dup refs deduped; absent optionals dropped from the hashed canonical
        with_dups = {"features": [{"id": "b"}, {"id": "a", "references": ["b", "b"]}]}
        without_dups = {"features": [{"id": "b"}, {"id": "a", "references": ["b"]}]}
        h1 = M.evaluate_feature_tree(with_dups)["provenance"]["input_sha256"]
        h2 = M.evaluate_feature_tree(without_dups)["provenance"]["input_sha256"]
        self.assertEqual(h1, h2)
        with_absent = {"features": [{"id": "b"}]}
        with_empty = {"features": [{"id": "b", "references": []}]}
        h3 = M.evaluate_feature_tree(with_absent)["provenance"]["input_sha256"]
        h4 = M.evaluate_feature_tree(with_empty)["provenance"]["input_sha256"]
        self.assertNotEqual(h3, h4)  # present-vs-absent is visible; normalization is dedup-only


if __name__ == "__main__":
    unittest.main()


class TestAggregateLeaves(unittest.TestCase):
    """Aggregate string-leaf budget: 200000 across every validated string leaf.
    24 packed features stay under, 25 trip it - and a removed check lets 25 pass."""

    def _pack(self, n):
        # n features, each id 128 chars, each referencing all n declared ids:
        # leaves = n * 128 * (1 + n); 39 -> 199680 (passes), 40 -> 209920 (refuses)
        ids = [f"f{i}".ljust(128, "x") for i in range(n)]
        feats = [{"id": ids[i], "references": ids} for i in range(n)]
        return {"features": feats}

    def test_boundary_39_40(self):
        r = M.evaluate_feature_tree(self._pack(39))
        self.assertEqual(r["summary"]["feature_count"], 39)
        exc = refusal(self._pack(40))
        self.assertEqual(exc.code, PREFIX + "oversize")


class TestSevenProbePins(unittest.TestCase):
    """Pins for the seven 80-operator AST survivors (runtime already refuses;
    these were missing tests). Each mutant verified killed by tool."""

    def test_unicode_guard_and_or_operands(self):
        # guard -> False AND or->and both let a lone listed-CF char through
        for bad in ("a\u202e", "a\u200b", "a\x01", "a\x7f", "a\u2028", "a\u2029", "a\ufeff"):
            exc = refusal({"features": [{"id": bad}]})
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("disallowed character", str(exc))

    def test_unicode_printable_non_ascii_allowed(self):
        for ok in ("café", "日本語", "naïve-2"):
            self.assertEqual(M.evaluate_feature_tree({"features": [{"id": ok}]})["summary"]["feature_count"], 1)

    def test_refs_element_type(self):
        for bad in ([1], ["fine", 1], [None], [True]):
            exc = refusal({"features": [{"id": "a", "references": bad}]})
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("references must be a list of feature ids", str(exc))

    def test_params_element_type(self):
        for bad in ([1], ["fine", 1], [None]):
            exc = refusal({"features": [{"id": "a", "parameters": bad}]})
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("parameters must be a list of parameter names", str(exc))

    def test_global_param_key_type(self):
        for bad in ({1: "v"}, {None: "v"}, {True: "v"}):
            exc = refusal({"features": [{"id": "a"}], "parameters": bad})
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("parameters must be an object of string values", str(exc))

    def test_refusal_detail_is_empty_dict_not_none(self):
        for data in ({"features": []},
                     {"features": [{"id": "a", "extra": 1}]},
                     {"features": [{"id": "a"}, {"id": "a"}]}):
            exc = refusal(data)
            self.assertEqual(exc.detail, {})
            self.assertIsNotNone(exc.detail)

    def test_nested_allowlist_unknown_key(self):
        # 2-key and 3-key (at-cap) feature objects with an unknown key refuse;
        # the reason never carries the caller key
        for feat in ({"id": "a", "extra": 1},
                     {"id": "a", "references": [], "extra": 1}):
            exc = refusal({"features": [feat]})
            self.assertEqual(exc.code, PREFIX + "unknown_key")
            self.assertNotIn("extra", str(exc))


class TestRestoredV2Coverage(unittest.TestCase):
    """Restorations from the deleted v2 repair classes, adapted to v3 contracts."""

    def test_length_cap_before_unicode_check(self):
        # 33-char key whose 33rd char is disallowed: cap (resource_limit) fires first
        exc = refusal({"features": [{"id": "a"}], "parameters": {"k" * 32 + "\u202e": "v"}})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        # 129-char id with a disallowed final char: cap fires first
        exc = refusal({"features": [{"id": "f" * 128 + "\u202e"}]})
        self.assertEqual(exc.code, PREFIX + "resource_limit")

    def test_reference_length_128_129(self):
        # 128-char undeclared ref passes the length gate and reaches unknown_reference
        exc = refusal({"features": [{"id": "a", "references": ["r" * 128]}]})
        self.assertEqual(exc.code, PREFIX + "unknown_reference")
        exc = refusal({"features": [{"id": "a", "references": ["r" * 129]}]})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertIn("129", str(exc))

    def test_count_before_dedup_boundaries(self):
        # per-feature params: cap counts the DECLARED list before dedup -
        # 32 declared with a duplicate (31 distinct) passes and dedups;
        # 33 declared refuses even when only 32 are distinct
        names32 = [f"p{k}" for k in range(32)]
        params = {n: "v" for n in names32}
        r = M.evaluate_feature_tree({"features": [{"id": "a", "parameters": names32[:31] + [names32[0]]}],  # 32 declared, 31 distinct
                                     "parameters": params})
        self.assertEqual(r["feature_rows"][0]["parameters"], names32[:31])
        exc = refusal({"features": [{"id": "a", "parameters": names32 + [names32[0]]}],
                       "parameters": params})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        # references: 65 declared refuse even with a duplicate (64 distinct)
        ids = [f"f{i}" for i in range(64)]
        feats = [{"id": i} for i in ids]
        feats[0]["references"] = ids + [ids[1]]
        exc = refusal({"features": feats})
        self.assertEqual(exc.code, PREFIX + "resource_limit")

    def test_receipt_mutation_does_not_alias_caller(self):
        data = {"features": [{"id": "b"}, {"id": "a", "references": ["b"]}],
                "parameters": {"p": "v"}}
        r = M.evaluate_feature_tree(data)
        r["feature_rows"][1]["references"].append("MUT")
        r["parameters"]["p"] = "MUT"
        r["summary"]["parameters_declared"].append("MUT")
        self.assertEqual(data["features"][1]["references"], ["b"])
        self.assertEqual(data["parameters"], {"p": "v"})

    def test_echoes_are_not_the_callers_objects(self):
        refs = ["b"]
        data = {"features": [{"id": "b"}, {"id": "a", "references": refs}]}
        r = M.evaluate_feature_tree(data)
        self.assertIsNot(r["feature_rows"][1]["references"], refs)
        self.assertIsNot(r["parameters"], data.get("parameters"))

    def test_hash_reflects_input_at_call_time(self):
        data = {"features": [{"id": "b"}, {"id": "c"}, {"id": "a", "references": ["b"]}]}
        h1 = M.evaluate_feature_tree(data)["provenance"]["input_sha256"]
        data["features"][2]["references"] = ["c"]  # change to a different declared ref
        r2 = M.evaluate_feature_tree(data)
        self.assertNotEqual(r2["provenance"]["input_sha256"], h1)

    def test_oversized_unknown_key_refused_reason_has_no_key(self):
        big = "k" * 10000
        exc = refusal({"features": [{"id": "a"}], big: 1})
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        self.assertNotIn(big, str(exc))
        self.assertLess(len(str(exc)), 200)

    def test_non_json_leaves_refused_before_hash(self):
        for bad in ({"features": [{"id": 42}]},
                    {"features": [{"id": "a"}], "parameters": {"p": 42}}):
            exc = refusal(bad)
            self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_aggregate_oversize_names_field_class(self):
        ids = [f"f{i}".ljust(128, "x") for i in range(40)]
        feats = [{"id": ids[i], "references": ids} for i in range(40)]
        exc = refusal({"features": feats})
        self.assertEqual(exc.code, PREFIX + "oversize")
        self.assertIn("field class: features", str(exc))

    def test_count_cap_before_element_scan(self):
        # over-cap refs list with a bad first element: count cap fires first
        exc = refusal({"features": [{"id": "a", "references": [42] + ["r"] * 64}]})
        self.assertEqual(exc.code, PREFIX + "resource_limit")


class TestExactAggregateThreshold(unittest.TestCase):
    """EXACT threshold proof: 200000 validated string leaves pass, 200001 refuse.
    24 features x (128-char id + 64 refs x 128) = 199680 leaves; global parameter
    pairs add len(key)+len(value) each (<= 64). 199680 + 5x(32+32) = 200000 exactly;
    one further 1-char key with an empty value = 200001."""

    def _payload(self, extra_pair):
        ids = [f"f{i}".ljust(128, "x") for i in range(24)]
        refs64 = (ids * 3)[:64]  # 64 declared refs per feature (dups ok pre-dedup)
        feats = [{"id": ids[i], "references": refs64} for i in range(24)]
        params = {f"k{k}".ljust(32, "k"): "v" * 32 for k in range(5)}  # 5 x 64 = 320
        if extra_pair:
            params["q"] = ""  # +1 leaf -> 200001
        return {"features": feats, "parameters": params}

    def test_exactly_200000_passes(self):
        r = M.evaluate_feature_tree(self._payload(False))
        self.assertEqual(r["summary"]["feature_count"], 24)

    def test_exactly_200001_refuses(self):
        exc = refusal(self._payload(True))
        self.assertEqual(exc.code, PREFIX + "oversize")
        self.assertIn("200000", str(exc))


class TestFeatureParamNameThresholds(unittest.TestCase):
    """Per-feature parameter NAME caps/Unicode - the feature-list field, not the
    global dict key (different code path, different owner string)."""

    def test_name_32_passes_33_refuses(self):
        n32 = "n" * 32
        n33 = "n" * 33
        M.evaluate_feature_tree({"features": [{"id": "a", "parameters": [n32]}],
                                 "parameters": {n32: "v"}})
        # the 33-char name can never be declared (global keys cap at 32); the NAME
        # cap fires during feature validation, before any cross-reference check
        exc = refusal({"features": [{"id": "a", "parameters": [n33]}],
                       "parameters": {n32: "v"}})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertIn("parameters name", str(exc))
        self.assertIn("33", str(exc))

    def test_name_unicode_rejected_and_printable_allowed(self):
        for bad in ("n\u202e", "n\u200b", "n\x01", "n\x7f", "n\u2028", "n\ufeff"):
            exc = refusal({"features": [{"id": "a", "parameters": [bad]}],
                           "parameters": {bad: "v"}})
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("disallowed character", str(exc))
        for ok in ("café", "日本語"):
            M.evaluate_feature_tree({"features": [{"id": "a", "parameters": [ok]}],
                                     "parameters": {ok: "v"}})

    def test_name_length_cap_before_unicode(self):
        # 33-char name ending in a disallowed char: cap (resource_limit) fires first
        exc = refusal({"features": [{"id": "a", "parameters": ["n" * 32 + "\u202e"]}],
                       "parameters": {}})
        self.assertEqual(exc.code, PREFIX + "resource_limit")


class TestNonJsonLeafMatrix(unittest.TestCase):
    """Ordinary non-JSON leaves (set/bytes/NaN/dict/int/bool/None) across
    references elements, global parameter keys and global parameter values.
    Every case is a row refusal (invalid_input), never a raw TypeError.
    Not claimed equivalent to any old coverage - it is the current matrix."""

    def test_reference_elements(self):
        for bad in ({1}, b"b", float("nan"), {"k": 1}, 42, True, None):
            exc = refusal({"features": [{"id": "a", "references": [bad]}]})
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("references must be a list of feature ids", str(exc))

    def test_global_param_keys(self):
        # a set or dict can never ARRIVE as a dict key (unhashable in Python);
        # the expressible non-string keys are bytes/NaN/int/bool/None
        for bad in (b"k", float("nan"), 1, True, None):
            exc = refusal({"features": [{"id": "a"}], "parameters": {bad: "v"}})
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("parameters must be an object of string values", str(exc))

    def test_global_param_values(self):
        for bad in ({1}, b"v", float("nan"), {"k": 1}, 42, True, None, ["v"]):
            exc = refusal({"features": [{"id": "a"}], "parameters": {"p": bad}})
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("parameters must be an object of string values", str(exc))

    def test_feature_param_name_elements(self):
        for bad in ({1}, b"n", float("nan"), {"k": 1}, 42, None):
            exc = refusal({"features": [{"id": "a", "parameters": [bad]}]})
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("parameters must be a list of parameter names", str(exc))
