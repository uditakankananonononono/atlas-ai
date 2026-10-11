"""Row 1260 Sentencing Guidelines: bounded declared legal-support bookkeeping.

Hermetic stdlib tests; the module is loaded by file path. The unit maps
caller-supplied guideline edition, offense characteristics, adjustments and
departures; it never computes a sentence or a guideline range outcome."""
import importlib.util
import unittest
from pathlib import Path

MOD_PATH = (Path(__file__).resolve().parent.parent.parent
            / "backend/app/modules/m20_general_cognitive_worker/sentencing_guidelines1260.py")
spec = importlib.util.spec_from_file_location("sentencing_guidelines1260", MOD_PATH)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
PREFIX = "SENTEN1260:"


def item(text, basis="assertion", source_ref=None):
    d = {"text": text, "basis": basis}
    if source_ref is not None:
        d["source_ref"] = source_ref
    return d


def payload(**over):
    base = {"guideline_edition": "2023",
            "offense_characteristics": [item("amount stated in the referral", "sourced_fact", "exhibit-a"),
                                        item("role alleged by counsel")],
            "adjustments": [item("acceptance argued", "analysis")],
            "departures": [],
            "jurisdiction": "example-state",
            "as_of": "2026-01-15",
            "provenance": "intake memo bundle"}
    base.update(over)
    return base


def refusal(data):
    try:
        M.map_guideline_inputs(data)
    except M.SentencingGuidelinesRefusal as exc:
        return exc
    raise AssertionError("expected refusal")


class TestKnownAnswer(unittest.TestCase):
    def test_mapping_and_separation(self):
        r = M.map_guideline_inputs(payload())
        self.assertEqual(r["row"], 1260)
        self.assertEqual(r["capability"], "Sentencing Guidelines")
        self.assertEqual(r["scope"], "supplied_guideline_input_mapping")
        self.assertEqual(r["status"], "mapping_complete")
        self.assertEqual(r["guideline_edition"], "2023")
        gm = r["guideline_map"]
        self.assertEqual([x["text"] for x in gm["offense_characteristics"]],
                         ["amount stated in the referral", "role alleged by counsel"])
        self.assertEqual(gm["offense_characteristics"][0]["basis"], "sourced_fact")
        self.assertEqual(gm["offense_characteristics"][0]["source_ref"], "exhibit-a")
        self.assertEqual(gm["adjustments"][0]["basis"], "analysis")
        self.assertEqual(gm["departures"], [])
        self.assertEqual(r["separation"], {"sourced_facts": 1, "assertions": 1, "analysis": 1})
        self.assertEqual(r["jurisdiction"], "example-state")
        self.assertEqual(r["as_of"], "2026-01-15")
        self.assertEqual(r["provenance_label"], "intake memo bundle")

    def test_never_computes_sentence_or_range(self):
        r = M.map_guideline_inputs(payload())
        self.assertIs(r["flags"]["sentence_computed"], False)
        self.assertIs(r["flags"]["guideline_range_computed"], False)
        self.assertIs(r["flags"]["legal_advice"], False)
        self.assertIs(r["flags"]["filing_or_contact"], False)
        self.assertIs(r["provenance"]["edition_verified"], False)
        self.assertIs(r["provenance"]["assertions_verified"], False)
        self.assertIs(r["provenance"]["sources_verified"], False)
        self.assertIs(r["boundary"]["not_legal_advice"], True)
        self.assertIs(r["boundary"]["requires_licensed_counsel"], True)
        self.assertIn("not legal advice", r["boundary"]["text"])
        self.assertIs(r["human_review_required"], True)

    def test_determinism_and_hash_scope(self):
        r1 = M.map_guideline_inputs(payload())
        r2 = M.map_guideline_inputs(payload())
        self.assertEqual(r1, r2)
        self.assertEqual(r1["provenance"]["hash_scope"], "validated_fields")
        self.assertEqual(len(r1["provenance"]["input_sha256"]), 64)


class TestRefusals(unittest.TestCase):
    def test_non_object(self):
        exc = refusal([1])
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        self.assertEqual(exc.detail, {})

    def test_edition_required_and_nonempty(self):
        exc = refusal(payload(guideline_edition=None))
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal(payload(guideline_edition=""))
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_unknown_top_key_generic(self):
        exc = refusal(payload(surprise=1))
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        self.assertNotIn("surprise", str(exc))

    def test_list_shape_and_exact_types(self):
        class L(list):
            pass

        exc = refusal(payload(adjustments="acceptance"))
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal(payload(adjustments=(item("x"),)))
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal(payload(adjustments=L([item("x")])))
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal(payload(adjustments=["x"]))
        self.assertEqual(exc.code, PREFIX + "invalid_input")

        class D(dict):
            pass

        exc = refusal(D(guideline_edition="2023"))  # dict subclass refused
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal(payload(adjustments=[D(text="x", basis="assertion")]))  # item subclass refused
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_item_unknown_key_generic(self):
        exc = refusal(payload(adjustments=[{"text": "x", "basis": "assertion", "extra": 1}]))
        self.assertEqual(exc.code, PREFIX + "unknown_key")
        self.assertNotIn("extra", str(exc))

    def test_basis_enum(self):
        exc = refusal(payload(adjustments=[item("x", "fact")]))
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        for ok in ("sourced_fact", "assertion", "analysis"):
            M.map_guideline_inputs(payload(adjustments=[item("x", ok)]))

    def test_as_of_iso(self):
        exc = refusal(payload(as_of="15/01/2026"))
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        M.map_guideline_inputs(payload(as_of=None))

    def test_refusal_detail_empty(self):
        self.assertEqual(refusal([1]).detail, {})


class TestBounds(unittest.TestCase):
    def test_edition_64_65(self):
        M.map_guideline_inputs(payload(guideline_edition="e" * 64))
        exc = refusal(payload(guideline_edition="e" * 65))
        self.assertEqual(exc.code, PREFIX + "resource_limit")

    def test_text_256_257(self):
        M.map_guideline_inputs(payload(adjustments=[item("t" * 256)]))
        exc = refusal(payload(adjustments=[item("t" * 257)]))
        self.assertEqual(exc.code, PREFIX + "resource_limit")

    def test_items_64_65(self):
        M.map_guideline_inputs(payload(adjustments=[item(f"a{i}") for i in range(64)]))
        exc = refusal(payload(adjustments=[item(f"a{i}") for i in range(65)]))
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertIn("65", str(exc))

    def test_count_cap_before_element_scan(self):
        exc = refusal(payload(adjustments=[42] + [item(f"a{i}") for i in range(64)]))
        self.assertEqual(exc.code, PREFIX + "resource_limit")

    def test_length_cap_before_unicode(self):
        exc = refusal(payload(adjustments=[item("t" * 256 + "\u202e")]))
        self.assertEqual(exc.code, PREFIX + "resource_limit")


class TestUnicodeAndAggregate(unittest.TestCase):
    def test_disallowed_chars(self):
        for bad in ("a\u202e", "a\u200b", "a\x01", "a\x7f", "a\ufeff"):
            exc = refusal(payload(adjustments=[item(bad)]))
            self.assertEqual(exc.code, PREFIX + "invalid_input")
            self.assertIn("disallowed character", str(exc))

    def test_printable_non_ascii_allowed(self):
        M.map_guideline_inputs(payload(adjustments=[item("café argument")]))


class TestIsolation(unittest.TestCase):
    def test_caller_mutation_after_call_does_not_change_receipt(self):
        data = payload()
        r = M.map_guideline_inputs(data)
        data["adjustments"][0]["text"] = "MUTATED"
        data["guideline_edition"] = "MUTATED"
        self.assertEqual(r["guideline_map"]["adjustments"][0]["text"], "acceptance argued")
        self.assertEqual(r["guideline_edition"], "2023")

    def test_receipt_mutation_does_not_alias_caller(self):
        data = payload()
        r = M.map_guideline_inputs(data)
        r["guideline_map"]["adjustments"][0]["text"] = "MUT"
        r["guideline_map"]["departures"].append({"text": "MUT"})
        self.assertEqual(data["adjustments"][0]["text"], "acceptance argued")
        self.assertEqual(data["departures"], [])


if __name__ == "__main__":
    unittest.main()


class TestBatteryResiduals(unittest.TestCase):
    """Pins added after the first battery round (masked/gap survivors)."""

    def test_separation_counts_asymmetric(self):
        data = payload(offense_characteristics=[item("f1", "sourced_fact", "r1"),
                                                item("f2", "sourced_fact", "r2"),
                                                item("a1", "assertion")],
                       adjustments=[], departures=[])
        self.assertEqual(M.map_guideline_inputs(data)["separation"],
                         {"sourced_facts": 2, "assertions": 1, "analysis": 0})

    def test_jurisdiction_128_129(self):
        M.map_guideline_inputs(payload(jurisdiction="j" * 128))
        exc = refusal(payload(jurisdiction="j" * 129))
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertIn("129", str(exc))

    def test_source_ref_256_257(self):
        M.map_guideline_inputs(payload(adjustments=[item("x", "sourced_fact", "r" * 256)]))
        exc = refusal(payload(adjustments=[item("x", "sourced_fact", "r" * 257)]))
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        self.assertIn("257", str(exc))

    def test_hash_present_keys(self):
        h_absent = M.map_guideline_inputs(payload())["provenance"]["input_sha256"]
        dropped = payload()
        del dropped["departures"]
        h_dropped = M.map_guideline_inputs(dropped)["provenance"]["input_sha256"]
        self.assertNotEqual(h_absent, h_dropped)  # explicit-empty vs absent is visible


class TestUnicodePolicyCf(unittest.TestCase):
    """Full Cf category refused, Zs accepted, Cs residual kept (validation policy)."""

    def test_u00ad_soft_hyphen_refused(self):
        exc = refusal(payload(guideline_edition="2023­ed"))
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        exc = refusal(payload(adjustments=[item("a­b", "assertion")]))
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_u2060_word_joiner_refused(self):
        exc = refusal(payload(guideline_edition="2023⁠ed"))
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_full_cf_category_refused(self):
        for ch in ("؀", "﻿", "​", "‮"):
            exc = refusal(payload(adjustments=[item("x" + ch, "assertion")]))
            self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_zs_spaces_accepted(self):
        data = payload(guideline_edition="2023 ed", adjustments=[item("a b", "assertion")])
        receipt = M.map_guideline_inputs(data)
        self.assertEqual(receipt["guideline_edition"], "2023 ed")

    def test_cs_surrogate_residual_kept(self):
        # Disclosed residual: unpaired surrogates (Cs) are NOT refused.
        receipt = M.map_guideline_inputs(payload(adjustments=[item("x\ud800y", "assertion")]))
        self.assertEqual(receipt["separation"]["assertions"], 2)  # payload default adds 1


class TestStrictStrAndAsOfOrder(unittest.TestCase):
    """Exact str type (type(x) is str) and as_of raw cap before the regex."""

    def test_str_subclass_refused_everywhere(self):
        class S(str):
            pass

        for mutate in (
            lambda d: d.update(guideline_edition=S("2023")),
            lambda d: d.update(adjustments=[item(S("x"), "assertion")]),
            lambda d: d.update(adjustments=[item("x", "sourced_fact", S("r1"))]),
            lambda d: d.update(jurisdiction=S("in")),
            lambda d: d.update(provenance=S("p")),
            lambda d: d.update(as_of=S("2026-10-11")),
        ):
            data = payload()
            mutate(data)
            exc = refusal(data)
            self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_as_of_raw_cap_before_regex(self):
        # 11 chars that also fail the ISO regex: the raw length cap fires first.
        exc = refusal(payload(as_of="20230101123"))
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        # exactly 10 chars, bad format: regex refusal as before
        exc = refusal(payload(as_of="2026/10/11"))
        self.assertEqual(exc.code, PREFIX + "invalid_input")


class TestBasisAndKeyTypes(unittest.TestCase):
    """Basis: exact str, raw cap before membership. Keys: exact str only."""

    def test_basis_str_subclass_refused(self):
        class S(str):
            pass

        exc = refusal(payload(adjustments=[item("x", S("assertion"))]))
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_basis_raw_cap_before_membership(self):
        # 13+ chars (over the longest basis, 12): raw cap fires first.
        exc = refusal(payload(adjustments=[item("x", "z" * 13)]))
        self.assertEqual(exc.code, PREFIX + "resource_limit")
        # within cap, unknown basis: membership refusal
        exc = refusal(payload(adjustments=[item("x", "opinion")]))
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_str_subclass_key_refused_root_and_item(self):
        class S(str):
            pass

        data = payload()
        data[S("jurisdiction")] = data.pop("jurisdiction")  # allowed name, subclass key
        exc = refusal(data)
        self.assertEqual(exc.code, PREFIX + "invalid_input")
        sub_item = {S("text"): "x", "basis": "assertion"}
        exc = refusal(payload(adjustments=[sub_item]))
        self.assertEqual(exc.code, PREFIX + "invalid_input")

    def test_no_set_construction_over_caller_keys(self):
        # Exact-str key enforcement makes runtime spying on caller keys
        # impossible (subclass keys are refused at the door, pinned above), so
        # this pin is a static source scan: the module never calls set(...).
        import pathlib
        src = pathlib.Path(M.__file__).read_text()
        self.assertNotIn("set(", src)


class TestReviewPins(unittest.TestCase):
    """Final-gate pins: guard ordering, exact canonical SHA goldens."""

    GOLDENS = {
        "baseline": "95d3d439c64b118908b0be84baad2b534cb27ad54d15df12f8d79a985c444e52",
        "juris_one": "a755468fab7c2ae7391b72923bc1c6137d9bbb6a1d1c8f7c9197838c0e254046",
        "juris_none": "7513a7cfbe02c5cab6e8aab4ab511eb6227e611bd3ee7f53069b7e836ad93de8",
        "asof": "38beb68de2d5d277dbb5172305503035fc7acc043e4483aed5b966c584c9e64c",
        "asof_none": "5ac71bc8716ae29b0ae0202972bdf34edcb303b74ba5267f12c45dde99ff343c",
        "prov": "75fabea129d990b1ba1ed11b7ac5156765c6dcb85eb550f43c42dd0475a7c200",
        "prov_none": "59522b98910fb46ef5f58d8b7ead2b74e294638a85d808a99c5c58cf66323246",
        "adj_item": "37a9208c2b67d93c43b0208929791e3db2f35d101389ec32b9665df897b5baf9",
        "adj_empty": "939059d252739c5a7bcf49e370e8289c4b27c389a7377aa03018c9e5bdccdf0e",
    }

    def sha(self, data):
        return M.map_guideline_inputs(data)["provenance"]["input_sha256"]

    def test_root_overcap_int_key_hits_count_guard_first(self):
        data = {1: None, "guideline_edition": "x"}
        data.update({f"bad{i}": None for i in range(6)})  # 8 keys > 7, int key present
        exc = refusal(data)
        self.assertEqual(exc.code, PREFIX + "unknown_key")  # count guard, not key-type

    def test_item_overcap_int_key_hits_count_guard_first(self):
        bad_item = {1: None, "text": "a", "basis": "analysis", "source_ref": "x"}  # 4 > 3
        exc = refusal(payload(adjustments=[bad_item]))
        self.assertEqual(exc.code, PREFIX + "unknown_key")  # count guard, not key-type

    def test_unknown_top_key_undercap_allowlist(self):
        exc = refusal({"guideline_edition": "x", "unknown": 1})
        self.assertEqual(exc.code, PREFIX + "unknown_key")

    def test_exact_canonical_sha_golden(self):
        self.assertEqual(self.sha({"guideline_edition": "2023"}), self.GOLDENS["baseline"])

    def test_optional_membership_flips_exact(self):
        base = {"guideline_edition": "2023"}
        for name, nname, key, val in (("juris_one", "juris_none", "jurisdiction", "one"),
                                      ("asof", "asof_none", "as_of", "2026-01-15"),
                                      ("prov", "prov_none", "provenance", "memo")):
            d = dict(base)
            d[key] = val
            self.assertEqual(self.sha(d), self.GOLDENS[name])
            d[key] = None  # present-None is a different membership state than absent
            self.assertEqual(self.sha(d), self.GOLDENS[nname])
            self.assertNotEqual(self.GOLDENS[nname], self.GOLDENS["baseline"])

    def test_list_presence_flips_exact(self):
        self.assertEqual(self.sha({"guideline_edition": "2023",
                                   "adjustments": [{"text": "a", "basis": "analysis"}]}),
                         self.GOLDENS["adj_item"])
        self.assertEqual(self.sha({"guideline_edition": "2023", "adjustments": []}),
                         self.GOLDENS["adj_empty"])
        self.assertNotEqual(self.GOLDENS["adj_empty"], self.GOLDENS["baseline"])

    def test_sort_keys_true_exact_golden(self):
        import hashlib, json
        obj = {"guideline_edition": "2023", "adjustments": [{"text": "a", "basis": "analysis"}]}
        sorted_sha = hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        unsorted_sha = hashlib.sha256(json.dumps(obj, sort_keys=False, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(sorted_sha, self.GOLDENS["adj_item"])  # module uses sort_keys=True
        self.assertNotEqual(unsorted_sha, self.GOLDENS["adj_item"])
        self.assertEqual(self.sha(obj), sorted_sha)
