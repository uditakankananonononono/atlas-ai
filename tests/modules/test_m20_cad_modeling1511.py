"""Row 1511 CAD Modeling: bounded exact supplied feature-tree evaluation.

Stdlib only. The module under test is loaded by file path so these tests do not
need the web framework that the package __init__ imports.
"""
import hashlib
import importlib.util
import json
import os
import random
import unittest

_CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend", "app",
                     "modules", "m20_general_cognitive_worker", "cad_modeling1511.py")


def load():
    spec = importlib.util.spec_from_file_location("cad_modeling1511_under_test", _CORE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = load()
PREFIX = "CADMOD1511:"


def feat(fid, references=None, parameters=None):
    d = {"id": fid}
    if references is not None:
        d["references"] = references
    if parameters is not None:
        d["parameters"] = parameters
    return d


def fixture():
    # sketch <- cut <- pattern; "boss" has a forward reference to "plane" (declared
    # later) and "fillet" self-references; "dup-ref" repeats a reference.
    return {"features": [feat("sketch"),
                         feat("cut", ["sketch"], ["depth"]),
                         feat("pattern", ["cut", "sketch", "cut"]),
                         feat("boss", ["plane"]),
                         feat("fillet", ["fillet"]),
                         feat("plane")],
            "parameters": {"depth": "10 mm", "angle": "30 deg", "unused": "0"}}


def refusal(data):
    try:
        M.evaluate_feature_tree(data)
    except M.CadModelingRefusal as exc:
        return exc
    raise AssertionError("expected CadModelingRefusal for %r" % (data,))


def oracle(data):
    """Independent order-based reference evaluation over the validated declaration."""
    seen = set()
    errors = []
    for f in data["features"]:
        for ref in f.get("references") or []:
            if ref == f["id"]:
                errors.append((f["id"], "self_reference", ref))
            elif ref not in seen:
                errors.append((f["id"], "forward_reference", ref))
        seen.add(f["id"])
    return errors


class TestKnownAnswer(unittest.TestCase):
    def test_evaluation(self):
        r = M.evaluate_feature_tree(fixture())
        self.assertEqual(r["row"], 1511)
        self.assertEqual(r["capability"], "CAD Modeling")
        self.assertEqual(r["scope"], "supplied_feature_tree_evaluation")
        self.assertEqual(r["status"], "evaluation_complete")
        rows = r["feature_rows"]
        self.assertEqual([row["id"] for row in rows],
                         ["sketch", "cut", "pattern", "boss", "fillet", "plane"])  # input (tree) order
        self.assertEqual(rows[1]["references"], ["sketch"])
        self.assertEqual(rows[2]["references"], ["cut", "sketch"])  # deduped, first occurrence
        self.assertEqual(rows[1]["parameters"], ["depth"])
        errors = r["reference_errors"]
        self.assertEqual([(e["feature"], e["kind"], e["reference"]) for e in errors],
                         [("boss", "forward_reference", "plane"),
                          ("fillet", "self_reference", "fillet")])
        self.assertIs(r["regeneration_ready"], False)
        self.assertIsNone(r["regeneration_order"])
        s = r["summary"]
        self.assertEqual(s["feature_count"], 6)
        self.assertEqual(s["error_count"], 2)
        self.assertEqual(s["parameters_declared"], ["angle", "depth", "unused"])
        self.assertEqual(s["parameters_used"], ["depth"])
        self.assertEqual(s["parameters_unreferenced"], ["angle", "unused"])
        self.assertEqual([t["feature_id"] for t in r["input_trace"]],
                         ["sketch", "cut", "pattern", "boss", "fillet", "plane"])

    def test_clean_tree_regeneration_order(self):
        data = {"features": [feat("sketch"), feat("cut", ["sketch"]),
                             feat("pattern", ["cut", "sketch"]), feat("plane")]}
        r = M.evaluate_feature_tree(data)
        self.assertIs(r["regeneration_ready"], True)
        self.assertEqual(r["reference_errors"], [])
        # Exact deterministic topological order, lexicographic tie-break.
        self.assertEqual(r["regeneration_order"], ["plane", "sketch", "cut", "pattern"])

    def test_full_receipt_boundary_and_provenance(self):
        data = fixture()
        r = M.evaluate_feature_tree(data)
        self.assertEqual(set(r), {"row", "capability", "scope", "status", "feature_rows",
                                  "reference_errors", "regeneration_order", "regeneration_ready",
                                  "summary", "input_trace", "parameters", "provenance",
                                  "boundary", "human_review_required"})
        normalized = {"features": [{"id": f["id"],
                                    **({"references": list(dict.fromkeys(f["references"]))} if "references" in f else {}),
                                    **({"parameters": list(dict.fromkeys(f["parameters"]))} if "parameters" in f else {})}
                                   for f in data["features"]],
                      "parameters": data["parameters"]}
        canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        self.assertEqual(r["provenance"]["input_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertIs(r["provenance"]["declarations_not_geometry"], True)
        self.assertIs(r["provenance"]["geometry_kernel_executed"], False)
        self.assertIs(r["provenance"]["regeneration_performed"], False)
        self.assertIs(r["boundary"]["requires_engineer_review"], True)
        self.assertIs(r["boundary"]["not_a_released_model"], True)
        self.assertIs(r["boundary"]["no_machinery_control"], True)
        self.assertIs(r["human_review_required"], True)
        self.assertEqual(r["parameters"], {"depth": "10 mm", "angle": "30 deg", "unused": "0"})


class TestRefusals(unittest.TestCase):
    def test_non_object(self):
        exc = refusal("nope")
        self.assertEqual((exc.code, str(exc)),
                         (PREFIX + "invalid_input", PREFIX + "invalid_input: input must be an object"))

    def test_features_shape(self):
        exc = refusal({"features": "nope"})
        self.assertEqual(str(exc), PREFIX + "invalid_input: features must be a list of 1..64 feature objects")
        exc = refusal({"features": []})
        self.assertEqual(str(exc), PREFIX + "invalid_input: features must be a list of 1..64 feature objects")
        exc = refusal({"features": [42]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: features[0] must be an object")

    def test_id_problems(self):
        exc = refusal({"features": [feat("")]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: features[0].id requires a non-empty string")
        exc = refusal({"features": [feat("a"), feat("a")]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: duplicate id in features")

    def test_unknown_reference(self):
        exc = refusal({"features": [feat("a", ["ghost"])]})
        self.assertEqual(exc.code, PREFIX + "unknown_reference")
        self.assertEqual(str(exc), PREFIX + "unknown_reference: unknown feature reference at features[0].references")

    def test_unknown_parameter(self):
        exc = refusal({"features": [feat("a", [], ["ghost"])]})
        self.assertEqual(exc.code, PREFIX + "unknown_parameter")
        self.assertEqual(str(exc), PREFIX + "unknown_parameter: unknown parameter reference at features[0].parameters")

    def test_shape_details(self):
        exc = refusal({"features": [feat("a", "sketch")]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: features[0].references must be a list of feature ids")
        exc = refusal({"features": [feat("a", [], "depth")]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: features[0].parameters must be a list of parameter names")
        exc = refusal({"features": [feat("a")], "parameters": ["depth"]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: parameters must be an object of string values")
        exc = refusal({"features": [feat("a")], "parameters": {"d": 5}})
        self.assertEqual(str(exc), PREFIX + "invalid_input: parameters must be an object of string values")
        exc = refusal({"features": [feat("a")], "surprise": 1})
        self.assertEqual(str(exc), PREFIX + "unknown_key: unknown key at input")


class TestBounds(unittest.TestCase):
    def test_feature_count_64_65(self):
        ok = {"features": [feat(f"f{i}") for i in range(64)]}
        self.assertEqual(M.evaluate_feature_tree(ok)["summary"]["feature_count"], 64)
        exc = refusal({"features": [feat(f"f{i}") for i in range(65)]})
        self.assertEqual((exc.code, str(exc)),
                         (PREFIX + "resource_limit", PREFIX + "resource_limit: features count 65 exceeds limit 64"))

    def test_reference_count_64_65(self):
        # Limit counts the declared list before dedup. 64 features total: top
        # references the other 63 plus itself (self-reference is a finding, not a
        # refusal), hitting exactly 64 declared references.
        base = [feat(f"b{i}") for i in range(63)]
        ok = base + [feat("top", [f"b{i}" for i in range(63)] + ["top"])]
        r = M.evaluate_feature_tree({"features": ok})
        row = r["feature_rows"][-1]
        self.assertEqual(len(row["references"]), 64)
        self.assertIn(("top", "self_reference", "top"),
                      [(e["feature"], e["kind"], e["reference"]) for e in r["reference_errors"]])
        exc = refusal({"features": base + [feat("top", [f"b{i}" for i in range(63)] + ["top", "top"])]})
        self.assertEqual(str(exc), PREFIX + "resource_limit: features[63].references count 65 exceeds limit 64")

    def test_parameter_count_32_33(self):
        # FINAL author table: MAX_PARAMETERS = 32 shared (global keys AND per-feature entries).
        base = {"features": [feat("a")]}
        ok = dict(base, parameters={f"p{k}": "v" for k in range(32)})
        self.assertEqual(len(M.evaluate_feature_tree(ok)["parameters"]), 32)
        exc = refusal(dict(base, parameters={f"p{k}": "v" for k in range(33)}))
        self.assertEqual(str(exc), PREFIX + "resource_limit: parameters count 33 exceeds limit 32")

    def test_id_length_128_129(self):
        self.assertEqual(M.evaluate_feature_tree({"features": [feat("f" * 128)]})["summary"]["feature_count"], 1)
        exc = refusal({"features": [feat("f" * 129)]})
        self.assertEqual(str(exc), PREFIX + "resource_limit: features[0].id is 129 characters, limit is 128")


class TestSemantics(unittest.TestCase):
    def test_forward_reference_is_order_semantic(self):
        # Tree order is semantic (cluster parity): moving the referenced feature earlier
        # clears the finding.
        forward = {"features": [feat("a", ["b"]), feat("b")]}
        r1 = M.evaluate_feature_tree(forward)
        self.assertEqual([(e["feature"], e["kind"]) for e in r1["reference_errors"]],
                         [("a", "forward_reference")])
        backward = {"features": [feat("b"), feat("a", ["b"])]}
        r2 = M.evaluate_feature_tree(backward)
        self.assertEqual(r2["reference_errors"], [])
        self.assertIs(r2["regeneration_ready"], True)
        self.assertNotEqual(r1["provenance"], r2["provenance"])

    def test_determinism_byte_identical(self):
        data = fixture()
        r1 = M.evaluate_feature_tree(data)
        r2 = M.evaluate_feature_tree(json.loads(json.dumps(data)))
        self.assertEqual(r1, r2)
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))

    def test_oracle_corpus(self):
        rng = random.Random(1511)
        for case in range(150):
            n = rng.randrange(1, 12)
            ids = [f"f{k}" for k in range(n)]
            feats = []
            for k, i in enumerate(ids):
                refs = [d for d in ids if rng.random() < 0.15]
                feats.append(feat(i, refs))
            data = {"features": feats}
            r = M.evaluate_feature_tree(data)
            exp = oracle(data)
            got = [(e["feature"], e["kind"], e["reference"]) for e in r["reference_errors"]]
            self.assertEqual(got, exp, case)
            self.assertIs(r["regeneration_ready"], not exp, case)
            if not exp:
                order = r["regeneration_order"]
                self.assertEqual(sorted(order), sorted(ids), case)
                pos = {x: k for k, x in enumerate(ids)}
                for k, f in enumerate(feats):
                    for ref in f["references"] or []:
                        if ref != f["id"] and pos[ref] < k:
                            self.assertLess(order.index(ref), order.index(f["id"]), case)


if __name__ == "__main__":
    unittest.main()
