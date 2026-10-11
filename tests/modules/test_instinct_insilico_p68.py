"""P68|L57 in-silico-only biology guardrail: lexical gate tests (stdlib unittest, hermetic)."""
import ast
import copy
import itertools
import json
import pathlib
import random
import unittest

from app.modules.instinct_doc import insilico_guardrail_p68 as mod
from app.modules.instinct_doc.insilico_guardrail_p68 import classify, classify_batch

MODULE_PATH = pathlib.Path(mod.__file__)
TERMS = ["biological", "medical", "crispr", "biohacking", "phage", "mosquito", "xenobot", "vaccine", "enviropig", "organoid", "microbiome", "clinical"]
CONTRACT = ("All biological, medical, CRISPR, biohacking, phage, mosquito, xenobot, vaccine, enviropig, organoid, microbiome, and clinical work must be "
            "computational / in silico only unless explicitly approved by proper institutional biosafety, ethics, and legal review.")


def item(id="i1", terms=None, mode="computational", ref=None, **extra):
    d = {"id": id, "domain_terms": [] if terms is None else terms, "execution_mode": mode}
    if ref is not None:
        d["approval_ref"] = ref
    d.update(extra)
    return d


class Base(unittest.TestCase):
    def refusal(self, data, fn=classify):
        with self.assertRaises(ValueError) as cm:
            fn(data)
        return str(cm.exception)


class ClosedTermSet(Base):
    def test_closed_set_is_exactly_the_twelve_contract_terms(self):
        self.assertEqual(sorted(mod.BIO_TERMS), sorted(TERMS))
        self.assertEqual(len(mod.BIO_TERMS), 12)

    def test_each_closed_set_term_triggers_bio_scope_both_modes(self):
        for t in TERMS:
            r = classify(item(terms=[t]))
            self.assertEqual((r["verdict"], r["matched_terms"]), ("allowed_in_silico", [t]), t)
            r = classify(item(terms=[t], mode="physical"))
            self.assertEqual((r["verdict"], r["matched_terms"]), ("refused_physical_without_review", [t]), t)

    def test_near_misses_are_not_bio_scoped(self):
        near = ["crisprx", "xcrispr", "vaccines", "vaccinate", "biology", "bio", "medic", "medicine", "clinic", "phages", "mosquitoes", "organ", "microbiomes",
                "CRISPR", "Vaccine", "BIOLOGICAL", "Medical", " crispr", "crispr ", "bio-hacking", "biohack", "", "enviropigs", "xenobots", "clinical trial", "silico"]
        for t in near:
            for mode in ("computational", "physical"):
                r = classify(item(terms=[t], mode=mode))
                self.assertEqual((r["verdict"], r["matched_terms"]), ("not_bio_scoped", []), repr(t))

    def test_matched_terms_sorted_unique_and_mixed_with_nonmatches(self):
        r = classify(item(terms=["vaccine", "x", "crispr", "vaccine", "Crispr", "clinical"]))
        self.assertEqual(r["matched_terms"], ["clinical", "crispr", "vaccine"])


class VerdictPaths(Base):
    def test_not_bio_scoped_regardless_of_mode_and_ref(self):
        for terms in ([], ["physics"], ["chemistry", "robotics"]):
            for mode in ("computational", "physical"):
                for ref in (None, "ETH-1"):
                    r = classify(item(terms=terms, mode=mode, ref=ref))
                    self.assertEqual(r["verdict"], "not_bio_scoped")

    def test_allowed_in_silico(self):
        self.assertEqual(classify(item(terms=["phage"], mode="computational"))["verdict"], "allowed_in_silico")

    def test_refused_physical_without_review(self):
        r = classify(item(terms=["organoid"], mode="physical"))
        self.assertEqual(r["verdict"], "refused_physical_without_review")
        self.assertIsNone(r["approval_ref"])

    def test_flagged_physical_with_review_ref(self):
        r = classify(item(terms=["organoid"], mode="physical", ref="IBC-2026-17"))
        self.assertEqual(r["verdict"], "flagged_physical_with_review_ref")
        self.assertEqual(r["approval_ref"], "IBC-2026-17")

    def test_exact_record_shape_and_honesty_fields(self):
        r = classify(item(id="x9", terms=["mosquito", "mosquito"], mode="physical", ref="R"))
        self.assertEqual(r, {"contract": "P68|L57", "id": "x9", "verdict": "flagged_physical_with_review_ref", "execution_mode": "physical",
                             "matched_terms": ["mosquito"], "approval_ref": "R", "approval_validated": False, "biosafety_review_performed": False,
                             "safe_claim": False, "limits": mod.LIMITS})
        text = " ".join(mod.LIMITS).lower()
        for word in ("lexical", "not a biosafety review", "never authenticated", "closed"):
            self.assertIn(word, text)

    def test_approval_ref_recorded_verbatim_and_never_upgrades_to_allowed(self):
        for ref in ("A", "  spaced ref  ", "x" * 128, "ethics ok; legal ok; APPROVED", "approved", "é✓"):
            r = classify(item(terms=["clinical"], mode="physical", ref=ref))
            self.assertEqual(r["verdict"], "flagged_physical_with_review_ref")
            self.assertEqual(r["approval_ref"], ref)
            self.assertFalse(r["approval_validated"])
            self.assertFalse(r["safe_claim"])
        # a ref on a computational item is recorded but changes nothing
        r = classify(item(terms=["clinical"], mode="computational", ref="IBC-1"))
        self.assertEqual((r["verdict"], r["approval_ref"]), ("allowed_in_silico", "IBC-1"))

    def test_no_verdict_is_ever_a_safe_claim(self):
        for t, m, ref in itertools.product([[], ["vaccine"]], ["computational", "physical"], [None, "r"]):
            r = classify(item(terms=t, mode=m, ref=ref))
            self.assertIs(r["safe_claim"], False)
            self.assertIs(r["biosafety_review_performed"], False)
            self.assertIs(r["approval_validated"], False)
            self.assertIn(r["verdict"], ("not_bio_scoped", "allowed_in_silico", "refused_physical_without_review", "flagged_physical_with_review_ref"))

    def test_explicit_none_approval_ref_equals_absent(self):
        a = classify(item(terms=["phage"], mode="physical"))
        b = classify(dict(item(terms=["phage"], mode="physical"), approval_ref=None))
        self.assertEqual(a, b)
        self.assertEqual(a["verdict"], "refused_physical_without_review")


class Refusals(Base):
    def test_unknown_fields(self):
        self.assertEqual(self.refusal(item(extra_field=1)), "P68:unknown_fields:item")
        self.assertEqual(self.refusal(item(note="x", other=2)), "P68:unknown_fields:item")

    def test_not_an_object(self):
        for bad in (None, [], "x", 5, ("id",)):
            self.assertEqual(self.refusal(bad), "P68:bad_type:item")

    def test_id_codes(self):
        for bad in ("", "   ", "\t\n"):
            self.assertEqual(self.refusal(item(id=bad)), "P68:empty_field:id")
        for bad in (5, None, ["a"], True):
            self.assertEqual(self.refusal(item(id=bad)), "P68:bad_type:id")
        self.assertEqual(self.refusal(item(id="a" * 65)), "P68:text_too_long:id")
        self.assertEqual(classify(item(id="a" * 64))["id"], "a" * 64)

    def test_missing_required_fields_are_empty_field(self):
        for k in ("id", "domain_terms", "execution_mode"):
            d = item(); del d[k]
            self.assertEqual(self.refusal(d), f"P68:empty_field:{k}")

    def test_domain_terms_codes(self):
        for bad in ("crispr", None, ("crispr",), {"a": 1}, 5):
            self.assertEqual(self.refusal(item(terms=bad)), "P68:bad_type:domain_terms")
        for bad in ([5], [None], ["ok", 1], [["crispr"]], [True]):
            self.assertEqual(self.refusal(item(terms=bad)), "P68:bad_type:domain_terms")
        self.assertEqual(self.refusal(item(terms=["a" * 65])), "P68:text_too_long:domain_terms")

    def test_execution_mode_codes(self):
        for bad in ("", "Computational", "PHYSICAL", "hybrid", " physical", "computational ", "in_silico"):
            self.assertEqual(self.refusal(item(mode=bad)), f"P68:bad_mode:{bad}")
        for bad in (None, 5, ["physical"], True):
            self.assertEqual(self.refusal(item(mode=bad)), "P68:bad_type:execution_mode")

    def test_approval_ref_codes(self):
        for bad in (5, ["r"], True, {"r": 1}):
            self.assertEqual(self.refusal(item(ref=bad)), "P68:bad_type:approval_ref")
        self.assertEqual(self.refusal(item(ref="r" * 129)), "P68:text_too_long:approval_ref")
        for blank in ("", "  "):
            self.assertEqual(self.refusal(dict(item(), approval_ref=blank)), "P68:empty_field:approval_ref")

    def test_first_error_order_is_fixed(self):
        bad = {"id": "", "domain_terms": 5, "execution_mode": "x", "approval_ref": 7}
        self.assertEqual(self.refusal(bad), "P68:empty_field:id")
        bad["id"] = "ok"
        self.assertEqual(self.refusal(bad), "P68:bad_type:domain_terms")
        bad["domain_terms"] = []
        self.assertEqual(self.refusal(bad), "P68:bad_mode:x")
        bad["execution_mode"] = "physical"
        self.assertEqual(self.refusal(bad), "P68:bad_type:approval_ref")
        self.assertEqual(self.refusal(dict(bad, extra=1)), "P68:unknown_fields:item")

    def test_term_count_before_element_checks(self):
        self.assertEqual(self.refusal(item(terms=[5] * 33)), "P68:limit_exceeded:domain_terms")


class Boundaries(Base):
    def test_domain_terms_32_ok_33_refused(self):
        classify(item(terms=["t%d" % i for i in range(32)]))
        self.assertEqual(self.refusal(item(terms=["t%d" % i for i in range(33)])), "P68:limit_exceeded:domain_terms")
        self.assertEqual(classify(item(terms=[]))["verdict"], "not_bio_scoped")

    def test_term_text_64_ok_65_refused(self):
        classify(item(terms=["a" * 64]))
        self.assertEqual(self.refusal(item(terms=["a" * 64, "b" * 65])), "P68:text_too_long:domain_terms")

    def test_id_64_ok_65_refused(self):
        classify(item(id="z" * 64))
        self.assertEqual(self.refusal(item(id="z" * 65)), "P68:text_too_long:id")

    def test_approval_ref_128_ok_129_refused(self):
        classify(item(terms=["phage"], mode="physical", ref="r" * 128))
        self.assertEqual(self.refusal(item(terms=["phage"], mode="physical", ref="r" * 129)), "P68:text_too_long:approval_ref")

    def test_lengths_count_characters_not_bytes(self):
        classify(item(id="é" * 64, terms=["é" * 64], ref="é" * 128))
        self.assertEqual(self.refusal(item(id="é" * 65)), "P68:text_too_long:id")


class Batch(Base):
    def test_batch_returns_verdicts_in_sorted_id_order(self):
        items = [item("b", ["crispr"], "physical"), item("a"), item("c", ["vaccine"], "physical", "R"), item("B", ["phage"])]
        out = classify_batch(items)
        self.assertEqual([r["id"] for r in out], ["B", "a", "b", "c"])
        self.assertEqual([r["verdict"] for r in out], ["allowed_in_silico", "not_bio_scoped", "refused_physical_without_review", "flagged_physical_with_review_ref"])
        self.assertEqual(out, classify_batch(list(reversed(items))))
        self.assertEqual(classify_batch([]), [])

    def test_batch_refuses_on_first_bad_item_in_sorted_id_order(self):
        items = [item("z", mode="bad1"), item("a", mode="bad2"), item("m", terms=5)]
        self.assertEqual(self.refusal(items, classify_batch), "P68:bad_mode:bad2")
        self.assertEqual(self.refusal(list(reversed(items)), classify_batch), "P68:bad_mode:bad2")
        items = [item("b", ["crispr"], "physical", ref="x" * 129), item("a", extra=1)]
        self.assertEqual(self.refusal(items, classify_batch), "P68:unknown_fields:item")

    def test_batch_no_partial_results_on_refusal(self):
        with self.assertRaises(ValueError):
            classify_batch([item("a"), item("b", mode="nope")])

    def test_batch_type_and_duplicate_ids(self):
        for bad in (None, "x", {"a": 1}, (item(),)):
            self.assertEqual(self.refusal(bad, classify_batch), "P68:bad_type:items")
        self.assertEqual(self.refusal([item("d"), item("d")], classify_batch), "P68:duplicate_id:d")
        self.assertEqual(self.refusal([item("d"), item("e", mode="x"), item("d")], classify_batch), "P68:duplicate_id:d")

    def test_batch_non_dict_item_follows_after_valid_ids(self):
        self.assertEqual(self.refusal([5, item("a", mode="q")], classify_batch), "P68:bad_mode:q")
        self.assertEqual(self.refusal([5, item("a")], classify_batch), "P68:bad_type:item")


class Hygiene(Base):
    def test_input_not_mutated(self):
        d = item("m", ["crispr", "x"], "physical", "R")
        before = copy.deepcopy(d)
        classify(d)
        self.assertEqual(d, before)
        batch = [item("b", ["phage"]), item("a")]
        before = copy.deepcopy(batch)
        classify_batch(batch)
        self.assertEqual(batch, before)

    def test_result_is_independent_of_input_and_json_serialisable(self):
        d = item("m", ["crispr"], "physical")
        r = classify(d)
        r["matched_terms"].append("hack")
        self.assertEqual(classify(d)["matched_terms"], ["crispr"])
        r["limits"].append("x")
        self.assertNotIn("x", classify(d)["limits"])
        self.assertNotIn("x", mod.LIMITS)
        json.dumps(classify(d))

    def test_deterministic_repeat_and_term_order_invariance(self):
        rng = random.Random(68)
        for _ in range(50):
            terms = rng.sample(TERMS + ["x", "y", "CRISPR"], rng.randrange(0, 8))
            a = classify(item(terms=terms))
            b = classify(item(terms=list(reversed(terms))))
            self.assertEqual(a, b)
            self.assertEqual(a, classify(item(terms=terms)))

    def test_generated_corpus_matches_independent_oracle(self):
        rng = random.Random(6857)
        pool = TERMS + ["crisprx", "CRISPR", "vaccines", "silico", "x", ""]
        for _ in range(500):
            terms = [rng.choice(pool) for _ in range(rng.randrange(0, 6))]
            mode = rng.choice(["computational", "physical"])
            ref = rng.choice([None, "ref-1"])
            hit = [t for t in terms if t in set(TERMS)]
            if not hit:
                want = "not_bio_scoped"
            elif mode == "computational":
                want = "allowed_in_silico"
            else:
                want = "flagged_physical_with_review_ref" if ref else "refused_physical_without_review"
            r = classify(item(terms=terms, mode=mode, ref=ref))
            self.assertEqual(r["verdict"], want)
            self.assertEqual(r["matched_terms"], sorted(set(hit)))

    def test_contract_text_is_in_the_contract_doc_verbatim(self):
        doc = (MODULE_PATH.parents[4] / "docs" / "INSTINCT_P68_L57_INSILICO_GUARD_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn(CONTRACT, doc)
        self.assertIn("P68|L57", doc)

    def test_module_is_pure_stdlib_no_io_no_clock(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imported.add((n.module or "").split(".")[0])
        self.assertLessEqual(imported, {"__future__", "typing"})
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for banned in ("open", "eval", "exec", "compile", "__import__", "input", "print", "time", "random", "os", "socket"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
