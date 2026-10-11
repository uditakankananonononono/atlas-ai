"""Row 1510 Mechanical Design: bounded exact design-review matrix over supplied declarations.

Stdlib only. The module under test is loaded by file path so these tests do not
need the web framework that the package __init__ imports.
"""
import copy
import hashlib
import importlib.util
import itertools
import json
import os
import random
import unittest

_CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend", "app",
                     "modules", "m20_general_cognitive_worker", "mechanical_design1510.py")


def load():
    spec = importlib.util.spec_from_file_location("mechanical_design1510_under_test", _CORE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = load()
PREFIX = "MECHAN1510:"


def req(rid, method=None, acceptance=None, load_cases=None):
    d = {"id": rid}
    if method is not None:
        d["verification_method"] = method
    if acceptance is not None:
        d["acceptance"] = acceptance
    if load_cases is not None:
        d["load_cases"] = load_cases
    return d


def fixture():
    # r1 fully declared and references both load cases; r2 missing acceptance;
    # r3 missing both; L3 declared but unreferenced.
    return {"requirements": [req("r1", "analysis", "stress < yield", ["L2", "L1", "L2"]),
                             req("r2", "test"),
                             req("r3")],
            "load_cases": [{"id": "L1"}, {"id": "L2", "description": "gust"}, {"id": "L3"}],
            "interfaces": ["mount-a", "mount-a".replace("a", "b")],
            "units": {"stress": "MPa"},
            "assumptions": ["static equilibrium"],
            "source_refs": ["caller-doc-7"]}



def canon(data):
    """Expected v3 provenance basis: validated values, keys present in input,
    requirement load_cases deduped in first-seen order (module normalization)."""
    out = {}
    if "requirements" in data:
        reqs = []
        for raw in data["requirements"]:
            entry = {"id": raw["id"]}
            if "verification_method" in raw:
                entry["verification_method"] = raw["verification_method"] or None
            if "acceptance" in raw:
                entry["acceptance"] = raw["acceptance"] or None
            if "load_cases" in raw:
                entry["load_cases"] = list(dict.fromkeys(raw["load_cases"]))
            reqs.append(entry)
        out["requirements"] = reqs
    for key in ("load_cases", "interfaces", "units", "assumptions", "source_refs"):
        if key in data:
            out[key] = data[key]
    return out


def canon_sha(data):
    return hashlib.sha256(json.dumps(canon(data), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def refusal(data):
    try:
        M.evaluate_design_review(data)
    except M.MechanicalDesignRefusal as exc:
        return exc
    raise AssertionError("expected MechanicalDesignRefusal for %r" % (data,))


def oracle(data):
    """Independent coverage evaluation over the already-validated declaration."""
    by_id = {}
    covered, uncovered = {}, []
    referenced = set()
    for r in data["requirements"]:
        by_id[r["id"]] = r
        method = r.get("verification_method") or None
        acceptance = r.get("acceptance") or None
        ok = bool(method) and bool(acceptance)
        covered[r["id"]] = ok
        if not ok:
            uncovered.append(r["id"])
        for lc in r.get("load_cases") or []:
            referenced.add(lc)
    declared = [lc["id"] for lc in data.get("load_cases") or []]
    return {"covered_map": covered,
            "uncovered": sorted(uncovered),
            "referenced": sorted(referenced),
            "unreferenced": sorted(set(declared) - referenced)}


class TestKnownAnswer(unittest.TestCase):
    def test_matrix_and_summary(self):
        r = M.evaluate_design_review(fixture())
        self.assertEqual(r["row"], 1510)
        self.assertEqual(r["capability"], "Mechanical Design")
        self.assertEqual(r["status"], "evaluation_complete")
        matrix = r["verification_matrix"]
        self.assertEqual([row["requirement_id"] for row in matrix], ["r1", "r2", "r3"])  # sorted by id
        self.assertEqual(matrix[0]["load_cases"], ["L2", "L1"])  # deduped, first-occurrence order
        self.assertEqual([(row["covered"]) for row in matrix], [True, False, False])
        self.assertEqual(matrix[0]["verification_method"], "analysis")
        self.assertEqual(matrix[0]["acceptance"], "stress < yield")
        self.assertIs(matrix[1]["verification_method"], "test")
        self.assertIsNone(matrix[1]["acceptance"])
        s = r["summary"]
        self.assertEqual(s["requirement_count"], 3)
        self.assertEqual(s["covered_count"], 1)
        self.assertEqual(s["uncovered_count"], 2)
        self.assertEqual(s["uncovered_requirement_ids"], ["r2", "r3"])
        self.assertEqual(s["declared_load_case_count"], 3)
        self.assertEqual(s["referenced_load_case_ids"], ["L1", "L2"])
        self.assertEqual(s["unreferenced_load_case_ids"], ["L3"])
        self.assertIs(s["requirements_complete"], False)
        self.assertEqual(r["interfaces"], ["mount-a", "mount-b"])
        self.assertEqual([t["requirement_id"] for t in r["input_trace"]], ["r1", "r2", "r3"])
        self.assertEqual([t["input_index"] for t in r["input_trace"]], [0, 1, 2])

    def test_full_receipt_boundary_and_provenance(self):
        data = fixture()
        r = M.evaluate_design_review(data)
        self.assertEqual(set(r), {"row", "capability", "scope", "status", "verification_matrix",
                                  "summary", "interfaces", "input_trace", "units", "assumptions",
                                  "source_refs", "provenance", "boundary", "human_review_required"})
        self.assertEqual(r["scope"], "supplied_design_review_matrix")
        prov = r["provenance"]
        self.assertEqual(prov["input_sha256"], canon_sha(data))
        self.assertIs(prov["declarations_not_measurements"], True)
        self.assertIs(prov["computed_not_physically_verified"], True)
        self.assertIs(prov["solver_or_cad_executed"], False)
        self.assertIs(prov["physical_test_performed"], False)
        b = r["boundary"]
        self.assertIs(b["requires_engineer_review"], True)
        self.assertIs(b["not_a_certified_design"], True)
        self.assertIs(b["no_machinery_control"], True)
        self.assertIs(r["human_review_required"], True)
        self.assertEqual(r["units"], {"stress": "MPa"})
        self.assertEqual(r["assumptions"], ["static equilibrium"])
        self.assertEqual(r["source_refs"], ["caller-doc-7"])


class TestRefusals(unittest.TestCase):
    def test_non_object(self):
        exc = refusal("nope")
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        self.assertEqual(str(exc), PREFIX + "invalid_input: input must be an object")

    def test_requirements_shape(self):
        exc = refusal({"requirements": "nope"})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        self.assertEqual(str(exc), PREFIX + "invalid_input: requirements must be a list of 1..64 requirement objects")
        exc = refusal({"requirements": []})
        self.assertEqual(str(exc), PREFIX + "invalid_input: requirements must be a list of 1..64 requirement objects")
        exc = refusal({"requirements": [42]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: requirements[0] must be an object")

    def test_id_problems(self):
        exc = refusal({"requirements": [req("")]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: requirements[0].id requires a non-empty string")
        exc = refusal({"requirements": [req("a"), req("a")]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: duplicate id in requirements")
        exc = refusal({"requirements": [{"id": 5}]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: requirements[0].id requires a non-empty string")

    def test_unknown_load_case_reference(self):
        exc = refusal({"requirements": [req("a", "m", "acc", ["ghost"])]})
        self.assertEqual(exc.code, PREFIX + "unknown_reference")
        self.assertEqual(str(exc), PREFIX + "unknown_reference: unknown load case reference at requirements[0].load_cases")

    def test_load_case_shape(self):
        exc = refusal({"requirements": [req("a")], "load_cases": [{"id": "L"}, {"id": "L"}]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: duplicate id in load_cases")
        exc = refusal({"requirements": [req("a")], "load_cases": [{"id": ""}]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: load_cases[0].id requires a non-empty string")
        exc = refusal({"requirements": [req("a", "m", 1)]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: requirements[0].acceptance must be a string when present")
        exc = refusal({"requirements": [req("a", 2, "acc")]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: requirements[0].verification_method must be a string when present")
        exc = refusal({"requirements": [req("a", "m", "acc", "L1")]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: requirements[0].load_cases must be a list of load case ids")
        exc = refusal({"requirements": [req("a")], "interfaces": ["x", "x"]})
        self.assertEqual(str(exc), PREFIX + "invalid_input: duplicate id in interfaces")

    def test_unknown_top_key(self):
        # Author ruling (repair): UNKNOWN-style code naming the parent, not invalid_input.
        exc = refusal({"requirements": [req("a")], "surprise": 1})
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        self.assertEqual(str(exc), PREFIX + "unknown_key: unknown key at input")


class TestBounds(unittest.TestCase):
    def test_requirement_count_64_65(self):
        ok = {"requirements": [req(f"r{i}") for i in range(64)]}
        r = M.evaluate_design_review(ok)
        self.assertEqual(r["summary"]["requirement_count"], 64)
        exc = refusal({"requirements": [req(f"r{i}") for i in range(65)]})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertEqual(str(exc), PREFIX + "resource_limit: requirements count 65 exceeds limit 64")

    def test_load_case_count_64_65(self):
        base = {"requirements": [req("a")]}
        ok = dict(base, load_cases=[{"id": f"L{i}"} for i in range(64)])
        r = M.evaluate_design_review(ok)
        self.assertEqual(r["summary"]["declared_load_case_count"], 64)
        exc = refusal(dict(base, load_cases=[{"id": f"L{i}"} for i in range(65)]))
        self.assertEqual(str(exc), PREFIX + "resource_limit: load_cases count 65 exceeds limit 64")

    def test_interface_count_64_65(self):
        base = {"requirements": [req("a")]}
        ok = dict(base, interfaces=[f"i{k}" for k in range(64)])
        self.assertEqual(len(M.evaluate_design_review(ok)["interfaces"]), 64)
        exc = refusal(dict(base, interfaces=[f"i{k}" for k in range(65)]))
        self.assertEqual(str(exc), PREFIX + "resource_limit: interfaces count 65 exceeds limit 64")

    def test_id_length_128_129(self):
        rid = "r" * 128
        r = M.evaluate_design_review({"requirements": [req(rid)]})
        self.assertEqual(r["summary"]["requirement_count"], 1)
        exc = refusal({"requirements": [req("r" * 129)]})
        self.assertEqual(str(exc), PREFIX + "resource_limit: requirements[0].id is 129 characters, limit is 128")
        lid = "L" * 129
        exc = refusal({"requirements": [req("a")], "load_cases": [{"id": lid}]})
        self.assertEqual(str(exc), PREFIX + "resource_limit: load_cases[0].id is 129 characters, limit is 128")

    def test_text_length_1024_1025(self):
        ok = {"requirements": [req("a", "m" * 1024, "acc")]}
        self.assertEqual(M.evaluate_design_review(ok)["summary"]["covered_count"], 1)
        exc = refusal({"requirements": [req("a", "m" * 1025, "acc")]})
        self.assertEqual(str(exc), PREFIX + "resource_limit: requirements[0].verification_method is 1025 characters, limit is 1024")
        exc = refusal({"requirements": [req("a", "m", "a" * 1025)]})
        self.assertEqual(str(exc), PREFIX + "resource_limit: requirements[0].acceptance is 1025 characters, limit is 1024")


class TestSemantics(unittest.TestCase):
    def test_empty_string_counts_as_not_provided(self):
        # Cluster parity: empty method/acceptance string leaves the requirement uncovered.
        r = M.evaluate_design_review({"requirements": [req("a", "", "acc"), req("b", "m", "")]})
        self.assertEqual(r["summary"]["uncovered_requirement_ids"], ["a", "b"])
        self.assertIsNone(r["verification_matrix"][0]["verification_method"])
        self.assertIsNone(r["verification_matrix"][1]["acceptance"])

    def test_zero_load_cases_and_interfaces_defaults(self):
        r = M.evaluate_design_review({"requirements": [req("a", "m", "acc")]})
        self.assertEqual(r["summary"]["declared_load_case_count"], 0)
        self.assertEqual(r["summary"]["referenced_load_case_ids"], [])
        self.assertEqual(r["interfaces"], [])
        self.assertIs(r["summary"]["requirements_complete"], True)

    def test_permutation_independence_and_trace_order(self):
        data = fixture()
        base = M.evaluate_design_review(data)
        for perm in itertools.permutations(data["requirements"]):
            out = M.evaluate_design_review(dict(data, requirements=list(perm)))
            self.assertEqual(out["verification_matrix"], base["verification_matrix"])
            self.assertEqual(out["summary"], base["summary"])
            prov = dict(out["provenance"]); prov.pop("input_sha256")
            expected_prov = dict(base["provenance"]); expected_prov.pop("input_sha256")
            self.assertEqual(prov, expected_prov)
            self.assertEqual(out["provenance"]["input_sha256"], canon_sha(dict(data, requirements=list(perm))))
            self.assertEqual([t["requirement_id"] for t in out["input_trace"]],
                             [r["id"] for r in perm])

    def test_determinism_byte_identical(self):
        data = fixture()
        r1 = M.evaluate_design_review(data)
        r2 = M.evaluate_design_review(json.loads(json.dumps(data)))
        self.assertEqual(r1, r2)
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))

    def test_oracle_corpus(self):
        rng = random.Random(1510)
        for case in range(150):
            n = rng.randrange(1, 12)
            m = rng.randrange(0, 6)
            lcs = [f"L{k}" for k in range(m)]
            reqs = []
            for k in range(n):
                method = rng.choice([None, "", "analysis", "test", "inspection"])
                acc = rng.choice([None, "", "pass", "within tolerance"])
                chosen = [x for x in lcs if rng.random() < 0.4]
                reqs.append(req(f"r{k}", method, acc, chosen))
            data = {"requirements": reqs, "load_cases": [{"id": x} for x in lcs]}
            r = M.evaluate_design_review(data)
            exp = oracle(data)
            got = {row["requirement_id"]: row["covered"] for row in r["verification_matrix"]}
            self.assertEqual(got, exp["covered_map"], case)
            self.assertEqual(r["summary"]["uncovered_requirement_ids"], exp["uncovered"], case)
            self.assertEqual(r["summary"]["referenced_load_case_ids"], exp["referenced"], case)
            self.assertEqual(r["summary"]["unreferenced_load_case_ids"], exp["unreferenced"], case)
            self.assertIs(r["summary"]["requirements_complete"], not exp["uncovered"], case)


class TestMutationIsolation(unittest.TestCase):
    """Repair pins (peer re-audit NEEDSREPAIR): receipt echoes must not alias the
    caller's mutable structures, and receipt mutation must not reach the caller."""

    ECHO_KEYS = ("units", "interfaces", "assumptions", "source_refs")

    def test_caller_mutation_after_call_does_not_change_receipt(self):
        data = fixture()
        r = M.evaluate_design_review(data)
        snapshot = copy.deepcopy(r)
        data["units"]["stress"] = "furlong"
        data["units"]["injected"] = "x"
        data["interfaces"].append("injected")
        data["assumptions"].append("injected")
        data["source_refs"].append("injected")
        self.assertEqual(r, snapshot)
        for key in self.ECHO_KEYS:
            self.assertEqual(r[key], snapshot[key])

    def test_receipt_mutation_does_not_alias_caller(self):
        data = fixture()
        original = copy.deepcopy(data)
        r = M.evaluate_design_review(data)
        r["units"]["stress"] = "furlong"
        r["interfaces"].append("injected")
        r["assumptions"].append("injected")
        r["source_refs"].append("injected")
        self.assertEqual(data["units"], original["units"])
        self.assertEqual(data["interfaces"], original["interfaces"])
        self.assertEqual(data["assumptions"], original["assumptions"])
        self.assertEqual(data["source_refs"], original["source_refs"])
        # A second call over the unmodified caller input matches the first receipt.
        r2 = M.evaluate_design_review(data)
        self.assertEqual({k: r2[k] for k in self.ECHO_KEYS}, {k: original[k] for k in self.ECHO_KEYS})

    def test_echoes_are_not_the_callers_objects(self):
        data = fixture()
        r = M.evaluate_design_review(data)
        self.assertIsNot(r["units"], data["units"])
        self.assertIsNot(r["interfaces"], data["interfaces"])
        self.assertIsNot(r["assumptions"], data["assumptions"])
        self.assertIsNot(r["source_refs"], data["source_refs"])

    def test_hash_reflects_input_at_call_time(self):
        data = fixture()
        r = M.evaluate_design_review(data)
        self.assertEqual(r["provenance"]["input_sha256"], canon_sha(data))
        data["interfaces"].append("post-hoc")
        r2 = M.evaluate_design_review(data)
        self.assertNotEqual(r2["provenance"]["input_sha256"], r["provenance"]["input_sha256"])
        self.assertEqual(r["interfaces"], ["mount-a", "mount-b"])


class TestGuardPins(unittest.TestCase):
    """Repair pins for the peer re-audit survivors (12 guard/boolop mutants).
    Each subtest names the mapped operator it kills."""

    def base(self):
        return fixture()

    def test_str_list_shape_and_count_guards(self):
        # R1510-07 / R1510-24 (shape guard, or->and)
        for key in ("assumptions", "source_refs"):
            with self.subTest(key=key, case="non-list"):
                d = self.base(); d[key] = "somestring"
                self.assertEqual(str(refusal(d)), PREFIX + f"invalid_input: {key} must be a list of strings")
            with self.subTest(key=key, case="non-str-item"):
                d = self.base(); d[key] = ["ok", 1]
                self.assertEqual(str(refusal(d)), PREFIX + f"invalid_input: {key} must be a list of strings")
            # R1510-08 (count guard)
            with self.subTest(key=key, case="count-64"):
                d = self.base(); d[key] = [f"a{i}" for i in range(64)]
                self.assertEqual(len(M.evaluate_design_review(d)[key]), 64)
            with self.subTest(key=key, case="count-65"):
                d = self.base(); d[key] = [f"a{i}" for i in range(65)]
                self.assertEqual(str(refusal(d)), PREFIX + f"resource_limit: {key} count 65 exceeds limit 64")

    def test_load_cases_list_and_item_guards(self):
        # R1510-11 (list guard)
        for bad in ("x", {"id": "L1"}, 5):
            with self.subTest(case=repr(bad)):
                d = self.base(); d["load_cases"] = bad
                self.assertEqual(str(refusal(d)), PREFIX + "invalid_input: load_cases must be a list of load case objects")
        # R1510-33 (item dict guard)
        d = self.base(); d["load_cases"] = ["L1"]
        self.assertEqual(str(refusal(d)), PREFIX + "invalid_input: load_cases[0] must be an object")

    def test_interfaces_shape_and_nonempty_guards(self):
        # R1510-13 / R1510-35 (shape guard, or->and)
        for bad in ("ab", ["a", 1], [None]):
            with self.subTest(case=repr(bad)):
                d = self.base(); d["interfaces"] = bad
                self.assertEqual(str(refusal(d)), PREFIX + "invalid_input: interfaces must be a list of non-empty interface ids")
        # R1510-63 (inner or->and: empty string slips through)
        d = self.base(); d["interfaces"] = ["ok", ""]
        self.assertEqual(str(refusal(d)), PREFIX + "invalid_input: interfaces must be a list of non-empty interface ids")

    def test_units_shape_and_item_guards(self):
        # R1510-16 / R1510-38 / R1510-64
        for bad in ("s", ["k"], {"k": 1}, {1: "v"}, {"k": None}):
            with self.subTest(case=repr(bad)):
                d = self.base(); d["units"] = bad
                self.assertEqual(str(refusal(d)), PREFIX + "invalid_input: units must be an object of string unit labels")
        d = self.base(); d["units"] = {"stress": "MPa", "length": "mm"}
        self.assertEqual(M.evaluate_design_review(d)["units"], {"stress": "MPa", "length": "mm"})

    def test_refusal_detail_is_empty_dict_not_none(self):
        # R1510-39 (detail or {})
        exc = refusal(self.base() | {"requirements": []})
        self.assertEqual(exc.detail, {})
        self.assertIsInstance(exc.detail, dict)


class TestAuthorBounds(unittest.TestCase):
    """Pins for the repair author rulings: per-field bounds, pre-dedup ref cap,
    aggregate string-leaf budget. Caps apply before dedup, allocation, parse, hash."""

    def test_interface_id_length_128_129(self):
        d = fixture(); d["interfaces"] = ["i" * 128]
        self.assertEqual(M.evaluate_design_review(d)["interfaces"], ["i" * 128])
        d["interfaces"] = ["i" * 129]
        self.assertEqual(str(refusal(d)), PREFIX + "resource_limit: interfaces[0] id is 129 characters, limit is 128")

    def test_load_ref_length_128_129(self):
        ok = "r" * 128
        d = {"requirements": [req("a", load_cases=[ok])], "load_cases": [{"id": ok}]}
        self.assertEqual(M.evaluate_design_review(d)["summary"]["referenced_load_case_ids"], [ok])
        d2 = {"requirements": [req("a", load_cases=["r" * 129])], "load_cases": []}
        self.assertEqual(str(refusal(d2)), PREFIX + "resource_limit: requirements[0].load_cases ref is 129 characters, limit is 128")

    def test_refs_count_64_65_before_dedup(self):
        d = {"requirements": [req("a", load_cases=[f"L{i}" for i in range(64)])],
             "load_cases": [{"id": f"L{i}"} for i in range(64)]}
        self.assertEqual(M.evaluate_design_review(d)["summary"]["referenced_load_case_ids"][:2], ["L0", "L1"])
        # 65 entries that dedup to 1 still refuse: the cap precedes dedup/allocation.
        d2 = {"requirements": [req("a", load_cases=["L0"] * 65)], "load_cases": [{"id": "L0"}]}
        self.assertEqual(str(refusal(d2)), PREFIX + "resource_limit: requirements[0].load_cases count 65 exceeds limit 64")

    def test_units_key_count_32_33(self):
        d = fixture(); d["units"] = {f"k{i}": "v" for i in range(32)}
        self.assertEqual(len(M.evaluate_design_review(d)["units"]), 32)
        d["units"] = {f"k{i}": "v" for i in range(33)}
        self.assertEqual(str(refusal(d)), PREFIX + "resource_limit: units count 33 exceeds limit 32")

    def test_units_key_value_length_32_33(self):
        d = fixture(); d["units"] = {"k" * 32: "v"}
        self.assertEqual(M.evaluate_design_review(d)["units"], {"k" * 32: "v"})
        d["units"] = {"k" * 33: "v"}
        self.assertEqual(str(refusal(d)), PREFIX + "resource_limit: units key is 33 characters, limit is 32")
        d["units"] = {"k": "v" * 33}
        self.assertEqual(str(refusal(d)), PREFIX + "resource_limit: units value is 33 characters, limit is 32")
        d["units"] = {"k": "v" * 32}
        self.assertEqual(M.evaluate_design_review(d)["units"], {"k": "v" * 32})

    def test_list_item_length_500_501(self):
        for key in ("assumptions", "source_refs"):
            with self.subTest(key=key):
                d = fixture(); d[key] = ["x" * 500]
                self.assertEqual(M.evaluate_design_review(d)[key], ["x" * 500])
                d[key] = ["x" * 501]
                self.assertEqual(str(refusal(d)), PREFIX + f"resource_limit: {key}[0] is 501 characters, limit is 500")

    @staticmethod
    def _leaf_total(dd):
        t = sum(len(r["id"]) + len(r.get("verification_method") or "") + len(r.get("acceptance") or "")
                + sum(map(len, r.get("load_cases") or [])) for r in dd["requirements"])
        t += sum(len(lc["id"]) + len(lc.get("description") or "") for lc in dd.get("load_cases") or [])
        t += sum(map(len, dd.get("interfaces") or []))
        t += sum(len(k) + len(v) for k, v in (dd.get("units") or {}).items())
        t += sum(map(len, dd.get("assumptions") or [])) + sum(map(len, dd.get("source_refs") or []))
        return t

    def test_aggregate_200000_200001_names_field_class(self):
        lcs = [{"id": f"L{i:02d}"} for i in range(64)]
        refs = [lc["id"] for lc in lcs]
        d = {"requirements": [req(f"r{i:02d}", "m" * 1024, "a" * 1024, refs) for i in range(64)],
             "load_cases": lcs,
             "interfaces": [f"i{i:0125d}" for i in range(64)],
             "units": {f"k{i:029d}": "v" * 32 for i in range(32)},
             "assumptions": ["a" * 499] + ["a" * 500] * 63,
             "source_refs": ["s" * 500] * 64}
        total = self._leaf_total(d)
        srefs = d["source_refs"]
        while total - 500 >= 200000:
            srefs.pop()
            total -= 500
        pad = 200000 - (total - 500)
        self.assertTrue(1 <= pad <= 500)
        srefs[-1] = "s" * pad
        self.assertEqual(self._leaf_total(d), 200000)
        self.assertEqual(M.evaluate_design_review(d)["summary"]["requirement_count"], 64)
        d["assumptions"][0] = "a" * 500  # +1 char, still within the per-item cap
        self.assertEqual(self._leaf_total(d), 200001)
        exc = refusal(d)
        self.assertEqual(exc.code, PREFIX + "oversize")
        self.assertEqual(str(exc), PREFIX + "oversize: aggregate string leaves exceed limit 200000 (field class: source_refs)")
        self.assertNotIn("aaa", str(exc))  # never the value


    def test_oversized_string_refused_fast_without_processing(self):
        # Uniform cap-first rule: length check is the first operation after the
        # isinstance check; a 10 MB string refuses by resource_limit immediately
        # (no strip/copy/regex allocation exists anywhere in the helper chain).
        import time
        d = {"requirements": [req("a", "m" * 10_000_000)]}
        t0 = time.monotonic()
        exc = refusal(d)
        self.assertLess(time.monotonic() - t0, 2.0)
        self.assertEqual(str(exc), PREFIX + "resource_limit: requirements[0].verification_method is 10000000 characters, limit is 1024")


class TestStrictShapeAndUnicode(unittest.TestCase):
    """Repair pins: strict nested allowlist, non-JSON leaves refused before hashing,
    Unicode rule (length cap first, then Unicode check; field named, never value)."""

    def test_unknown_nested_keys_name_parent(self):
        d = fixture(); d["requirements"][0]["surprise"] = 1
        self.assertEqual(str(refusal(d)), PREFIX + "unknown_key: unknown key at requirements[0]")
        d = fixture(); d["load_cases"][0]["surprise"] = 1
        self.assertEqual(str(refusal(d)), PREFIX + "unknown_key: unknown key at load_cases[0]")

    def test_oversized_unknown_key_refused_fast_reason_has_no_key(self):
        # Author-confirmed ruling: a 10 MB unknown key refuses immediately and the
        # reason never contains the key.
        import time
        d = {"requirements": [req("a")], "k" * 10_000_000: 1}
        t0 = time.monotonic()
        exc = refusal(d)
        self.assertLess(time.monotonic() - t0, 2.0)
        self.assertEqual(str(exc), PREFIX + "unknown_key: unknown key at input")
        self.assertNotIn("kkkk", str(exc))

    def test_hash_never_covers_unvalidated_fields(self):
        # An unknown key holding a JSON-unserializable value is refused before any
        # json.dumps; no hash is computed over unvalidated content.
        exc = refusal({"requirements": [req("a")], "surprise": {1, 2}})
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        d = fixture(); d["requirements"][0]["surprise"] = float("nan")
        self.assertEqual(refusal(d).code, PREFIX + "unknown_key")

    def test_non_json_leaves_refused_before_hash(self):
        for bad in ({"a", "b"}, b"bytes", float("nan"), float("inf"), {"nested": 1}, object()):
            with self.subTest(case=type(bad).__name__):
                d = {"requirements": [req("a", bad)]}
                exc = refusal(d)
                self.assertEqual(str(exc), PREFIX + "invalid_input: requirements[0].verification_method must be a string when present")

    UNICODE_CASES = ["\u0085", "\u2028", "\u2029", "\u202E", "\u200B", "\uFEFF", "\u007F"]

    def test_unicode_rejected_chars_on_id_and_text(self):
        for ch in self.UNICODE_CASES:
            with self.subTest(char=f"U+{ord(ch):04X}"):
                d = {"requirements": [req("a" + ch)]}
                exc = refusal(d)
                self.assertEqual(exc.code, PREFIX + "invalid_input")
                self.assertEqual(str(exc), PREFIX + "invalid_input: requirements[0].id contains a disallowed character: "
                                 "no Unicode control, line/paragraph separator or bidi/format characters")
                self.assertNotIn(ch, str(exc))  # field named, never the value
                d2 = {"requirements": [req("a", "analysis" + ch)]}
                self.assertEqual(refusal(d2).code, PREFIX + "invalid_input")

    def test_unicode_printable_non_ascii_allowed(self):
        d = {"requirements": [req("r-é−α", "analyse é", "critère − ok")]}
        r = M.evaluate_design_review(d)
        self.assertEqual(r["summary"]["requirement_count"], 1)
        d2 = {"requirements": [req("a")], "units": {"contrainte é": "MPa"}, "assumptions": ["hypothèse é"]}
        self.assertEqual(M.evaluate_design_review(d2)["units"], {"contrainte é": "MPa"})

    def test_length_cap_before_unicode_check(self):
        # A 129-char id containing a bad char at position 128 refuses with the
        # length cap, not the Unicode message (cap first).
        d = {"requirements": [req("a" * 128 + "\u200B")]}
        self.assertEqual(refusal(d).code, PREFIX + "resource_limit")


if __name__ == "__main__":
    unittest.main()


class TestV3ResourceOrder(unittest.TestCase):
    """v3 pins: count/type caps before any iteration or allocation; no incoming
    copy; generic field-only reasons with no caller key/value/id/ref/unit content."""

    class Bomb:
        def __deepcopy__(self, memo):
            raise RuntimeError("raw throw from custom __deepcopy__")

    class IterBombList(list):
        def __iter__(self):
            raise RuntimeError("iterated before the count cap")

    class IterBombDict(dict):
        def items(self):
            raise RuntimeError("iterated before the count cap")
        def keys(self):
            raise RuntimeError("iterated before the count cap")
        def __iter__(self):
            raise RuntimeError("iterated before the count cap")

    def test_custom_object_refused_cleanly(self):
        # no incoming deepcopy exists, so a hostile __deepcopy__ never runs
        exc = refusal(self.Bomb())
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"requirements": [{"id": "r1"}], "units": {"a": self.Bomb()}})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"requirements": [{"id": "r1"}], "assumptions": [self.Bomb()]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_count_cap_before_iteration_refs(self):
        exc = refusal({"requirements": [req("r1", "m", "a", ["LC"] * 65)]})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        # exact type fires first: a list subclass is refused as wrong type
        exc = refusal({"requirements": [req("r1", "m", "a", self.IterBombList(["LC"] * 65))]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_count_cap_before_iteration_interfaces(self):
        exc = refusal({"requirements": [req("r1")],
                       "interfaces": ["i"] * 65})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        # exact type: a list subclass is refused as wrong type BEFORE len/iteration
        exc = refusal({"requirements": [req("r1")],
                       "interfaces": self.IterBombList(["i"] * 65)})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"requirements": [req("r1")],
                       "interfaces": ("i",)})
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_count_cap_before_iteration_units(self):
        u = self.IterBombDict({f"k{i}": "v" for i in range(33)})  # over the 32 cap
        exc = refusal({"requirements": [req("r1")], "units": u})
        self.assertEqual(exc.code, PREFIX + "invalid_input")  # exact type: subclass refused before len
        exc = refusal({"requirements": [req("r1")], "units": {f"k{i}": "v" for i in range(33)}})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        # count cap fires before ANY entry validation: first key has a control
        # char, but the count refusal must win
        u = {"k\x00ey": "v"}
        u.update({f"k{i}": "v" for i in range(33)})
        exc = refusal({"requirements": [req("r1")], "units": u})
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        exc = refusal({"requirements": [req("r1")], "units": [("k", "v")]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_count_cap_before_iteration_str_lists(self):
        for key in ("assumptions", "source_refs"):
            exc = refusal({"requirements": [req("r1")], key: ["x"] * 65})
            self.assertEqual(exc.code, PREFIX + "resource_limit", key)
            exc = refusal({"requirements": [req("r1")], key: self.IterBombList(["x"] * 65)})
            self.assertEqual(exc.code, PREFIX + "invalid_input", key)

    def test_count_cap_before_iteration_top_keys(self):
        d = {"requirements": [req("r1")]}
        for i in range(7):
            d[f"extra{i}"] = i  # 8 keys > 6 allowed
        exc = refusal(d)
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        # exact type fires first: a dict subclass is refused as wrong type
        exc = refusal(self.IterBombDict(d))
        self.assertEqual(exc.code, PREFIX + "invalid_input")


    def test_count_cap_before_iteration_nested_objects(self):
        raw = {"id": "r1", "verification_method": "m", "acceptance": "a",
               "load_cases": [], "extra": 1}  # 5 keys > 4 allowed
        exc = refusal({"requirements": [raw]})
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        lc = {"id": "L1", "description": "d", "extra": 1}  # 3 keys > 2 allowed
        exc = refusal({"requirements": [req("r1")], "load_cases": [lc]})
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        # exact type fires first: dict subclasses are refused as wrong type
        exc = refusal({"requirements": [self.IterBombDict(raw)]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"requirements": [req("r1")], "load_cases": [self.IterBombDict(lc)]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_no_echo_in_reasons(self):
        exc = refusal({"requirements": [req("secret-id"), req("secret-id")]})
        self.assertNotIn("secret-id", str(exc))
        exc = refusal({"requirements": [req("r1", "m", "a", ["ghost-ref"])]})
        self.assertNotIn("ghost-ref", str(exc))
        exc = refusal({"requirements": [req("r1")], "interfaces": ["if-dup", "if-dup"]})
        self.assertNotIn("if-dup", str(exc))
        exc = refusal({"requirements": [req("r1")], "units": {"secret-unit-key": "x" * 33}})
        self.assertNotIn("secret-unit-key", str(exc))
        exc = refusal({"requirements": [req("r1")], "secret-caller-key": 1})
        self.assertNotIn("secret-caller-key", str(exc))
        exc = refusal({"requirements": [req("r1")], "load_cases": [{"id": "dup-lc"}, {"id": "dup-lc"}]})
        self.assertNotIn("dup-lc", str(exc))

    def test_receipt_containers_are_fresh(self):
        data = fixture()
        out = M.evaluate_design_review(data)
        self.assertIsNot(out["interfaces"], data["interfaces"])
        self.assertIsNot(out["units"], data["units"])
        self.assertIsNot(out["assumptions"], data["assumptions"])
        self.assertIsNot(out["source_refs"], data["source_refs"])
        out["interfaces"].append("MUT")
        out["units"]["MUT"] = "MUT"
        out["assumptions"].append("MUT")
        out["verification_matrix"][0]["load_cases"].append("MUT")
        self.assertEqual(data["interfaces"], ["mount-a", "mount-b"])
        self.assertEqual(data["units"], {"stress": "MPa"})
        self.assertEqual(len(data["assumptions"]), 1)
        self.assertEqual(data["requirements"][0]["load_cases"], ["L2", "L1", "L2"])

    def test_caller_mutation_after_call_does_not_reach_receipt(self):
        data = fixture()
        out = M.evaluate_design_review(data)
        data["interfaces"].append("post")
        data["units"]["post"] = "post"
        data["requirements"][0]["load_cases"].append("post")
        self.assertEqual(out["interfaces"], ["mount-a", "mount-b"])
        self.assertEqual(out["units"], {"stress": "MPa"})
        self.assertEqual(out["verification_matrix"][0]["load_cases"], ["L2", "L1"])

    def test_hash_canonical_includes_only_present_keys(self):
        data = {"requirements": [{"id": "r1"}]}
        out = M.evaluate_design_review(data)
        self.assertEqual(out["provenance"]["input_sha256"], canon_sha(data))
        self.assertNotIn("units", canon(data))
        data2 = {"requirements": [{"id": "r1"}], "units": {}}
        out2 = M.evaluate_design_review(data2)
        self.assertEqual(out2["provenance"]["input_sha256"], canon_sha(data2))
        self.assertNotEqual(out["provenance"]["input_sha256"], out2["provenance"]["input_sha256"])

    class SpyList(list):
        calls = []
        def __len__(self):
            SpyList.calls.append("len")
            raise RuntimeError("len called on subclass")
        def __iter__(self):
            SpyList.calls.append("iter")
            raise RuntimeError("iter called on subclass")

    class SpyDict(dict):
        calls = []
        def __len__(self):
            SpyDict.calls.append("len")
            raise RuntimeError("len called on subclass")

    def test_exact_type_spies_never_called(self):
        # subclass or wrong-container inputs are refused by the type check;
        # len() and iteration are never reached (FINAL gate, spies)
        for key, bad in (("requirements", self.SpyList()), ("load_cases", self.SpyList()),
                         ("interfaces", self.SpyList()), ("assumptions", self.SpyList()),
                         ("source_refs", self.SpyList()), ("units", self.SpyDict())):
            self.SpyList.calls = []
            self.SpyDict.calls = []
            exc = refusal({"requirements": [req("r1")], key: bad})
            self.assertEqual(exc.code, PREFIX + "invalid_input", key)
            self.assertEqual(self.SpyList.calls + self.SpyDict.calls, [], key)
        # tuples and other wrong containers refuse the same way
        for key, bad in (("interfaces", ("i",)), ("assumptions", ("a",)),
                         ("units", [("k", "v")]), ("load_cases", ({"id": "L"},))):
            exc = refusal({"requirements": [req("r1")], key: bad})
            self.assertEqual(exc.code, PREFIX + "invalid_input", key)
        # nested: requirement object as dict subclass, refs as list subclass
        self.SpyList.calls = []
        self.SpyDict.calls = []
        exc = refusal({"requirements": [self.SpyDict({"id": "r1"})]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal({"requirements": [{"id": "r1", "load_cases": self.SpyList()}]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        self.assertEqual(self.SpyList.calls + self.SpyDict.calls, [])

    def test_count_cap_before_item_type_check_refs(self):
        # 65 refs with a non-string first element: the count cap must fire
        # BEFORE the element-type scan (battery residual M1510v3-01)
        refs = [123] + ["LC"] * 64
        exc = refusal({"requirements": [req("r1", "m", "a", refs)]})
        self.assertEqual(exc.code, PREFIX + "resource_limit")

    def test_refs_non_string_element_tagged(self):
        # deleting the refs string guard must not pass: without it a non-string
        # ref raises a RAW TypeError in len() (peer 70-op deletion probe)
        exc = refusal({"requirements": [{"id": "r1", "load_cases": [123]}]})
        self.assertEqual(str(exc),
                         PREFIX + "invalid_input: requirements[0].load_cases must be a list of load case ids")
        exc = refusal({"requirements": [{"id": "r1", "load_cases": [None, {}]}]})
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_nested_allowlist_not_masked_by_key_count_cap(self):
        # exactly-at-cap objects with one unknown key: the count cap cannot
        # catch these; the allowlist must (peer 70-op deletion probe)
        exc = refusal({"requirements": [{"id": "r1", "verification_method": "m",
                                         "acceptance": "a", "bogus": 1}]})
        self.assertEqual(str(exc), PREFIX + "unknown_key: unknown key at requirements[0]")
        exc = refusal({"requirements": [req("r1")],
                       "load_cases": [{"id": "L1", "bogus": 1}]})
        self.assertEqual(str(exc), PREFIX + "unknown_key: unknown key at load_cases[0]")

    def test_duplicate_refs_collapse_to_same_hash(self):
        # normalization: deduped refs hash identically (FINAL gate pin)
        d1 = {"requirements": [req("r1", "m", "a", ["L2", "L1", "L2"])],
              "load_cases": [{"id": "L1"}, {"id": "L2"}]}
        d2 = {"requirements": [req("r1", "m", "a", ["L2", "L1"])],
              "load_cases": [{"id": "L1"}, {"id": "L2"}]}
        h1 = M.evaluate_design_review(d1)["provenance"]["input_sha256"]
        h2 = M.evaluate_design_review(d2)["provenance"]["input_sha256"]
        self.assertEqual(h1, h2)
        # and empty-string optional normalizes to None in the canonical form
        d3 = {"requirements": [req("r1", "", "a")]}
        h3 = M.evaluate_design_review(d3)["provenance"]["input_sha256"]
        self.assertEqual(h3, canon_sha(d3))
        self.assertIsNone(canon(d3)["requirements"][0]["verification_method"])

    def test_two_calls_byte_identical(self):
        data = fixture()
        self.assertEqual(M.evaluate_design_review(data), M.evaluate_design_review(data))
