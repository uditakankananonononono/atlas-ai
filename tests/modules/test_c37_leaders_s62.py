"""S6.2 / c37.leaders - leaders-and-concepts integrator tests.

Loaded by file path (c37 has no package __init__; composition is the
integrator's). S62_MODULE_PATH overrides the module path for mutation runs.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(
    os.environ.get(
        "S62_MODULE_PATH",
        Path(__file__).resolve().parents[2]
        / "backend" / "app" / "modules" / "c37" / "leaders.py",
    )
)


def _load():
    spec = importlib.util.spec_from_file_location("c37_leaders_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


m = _load()

AS_OF = "2026-10-11"


def req(**overrides):
    base = {
        "as_of": AS_OF,
        "known_entities": [{"name": "Ada Lovelace", "type": "person"}],
        "passages": [
            {"id": "p1", "url": "https://example.com/a",
             "text": "Ada Lovelace wrote notes. Ada Lovelace corresponded."},
        ],
    }
    base.update(overrides)
    return base


def run(**overrides):
    return m.run(req(**overrides))


def names(out):
    return [(e["name"], e["type"]) for e in out["entities"]]


class Refusals(unittest.TestCase):
    def test_request_not_dict(self):
        with self.assertRaises(ValueError) as cm:
            m.run("nope")
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_BAD_TYPE:request")

    def test_missing_passages(self):
        with self.assertRaises(ValueError) as cm:
            m.run({"as_of": AS_OF})
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_BAD_TYPE:passages")

    def test_passages_not_list(self):
        with self.assertRaises(ValueError) as cm:
            m.run({"as_of": AS_OF, "passages": "x"})
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_BAD_TYPE:passages")

    def test_empty_passages_list(self):
        with self.assertRaises(ValueError) as cm:
            m.run({"as_of": AS_OF, "passages": []})
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_EMPTY")

    def test_all_passages_dropped_is_nosource(self):
        with self.assertRaises(ValueError) as cm:
            run(passages=[{"id": "p1", "url": "http://insecure.example", "text": "Ada Lovelace"},
                          {"id": "p2", "url": "https://example.com", "text": "   "}])
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_NOSOURCE")

    def test_blank_known_name(self):
        with self.assertRaises(ValueError) as cm:
            run(known_entities=[{"name": "  ", "type": "person"}])
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_BAD_TYPE:known_entities")

    def test_non_str_known_name(self):
        with self.assertRaises(ValueError) as cm:
            run(known_entities=[{"name": 5, "type": "person"}])
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_BAD_TYPE:known_entities")

    def test_unknown_entity_type(self):
        with self.assertRaises(ValueError) as cm:
            run(known_entities=[{"name": "Ada Lovelace", "type": "robot"}])
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_BAD_TYPE:known_entities")

    def test_unsourced_internal_invariant(self):
        with self.assertRaises(ValueError) as cm:
            m._build_record("X Y", "concept", "confirmed", [], AS_OF)
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_UNSOURCED")

    def test_focus_validated(self):
        with self.assertRaises(ValueError) as cm:
            run(focus="x" * 201)
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_TEXT_TOO_LONG:focus")
        with self.assertRaises(ValueError) as cm:
            run(focus=7)
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_BAD_TYPE:focus")

    def test_no_effect_paths_exposed(self):
        # pure-offline applicability: no public callable spends, sends, posts,
        # trades or creates accounts
        public = [n for n in dir(m) if not n.startswith("_")]
        for banned in ("spend", "send", "post", "trade", "account", "fetch", "request_http"):
            for n in public:
                self.assertNotIn(banned, n.lower())


class PassageGate(unittest.TestCase):
    def test_http_url_dropped_counted(self):
        out = run(passages=[{"id": "p1", "url": "http://example.com", "text": "Ada Lovelace"},
                            {"id": "p2", "url": "https://example.com", "text": "Ada Lovelace"}])
        self.assertEqual(out["coverage"]["dropped_by_reason"], {"no_https_url": 1, "empty_text": 0})
        self.assertEqual(out["coverage"]["passages_supplied"], 2)
        self.assertEqual(out["coverage"]["passages_used"], 1)

    def test_empty_host_dropped(self):
        out = run(passages=[{"id": "p1", "url": "https://", "text": "Ada Lovelace"},
                            {"id": "p2", "url": "https://example.com", "text": "Ada Lovelace"}])
        self.assertEqual(out["coverage"]["dropped_by_reason"]["no_https_url"], 1)

    def test_whitespace_url_dropped(self):
        out = run(passages=[{"id": "p1", "url": "https://exa mple.com", "text": "Ada Lovelace"},
                            {"id": "p2", "url": "https://example.com", "text": "Ada Lovelace"}])
        self.assertEqual(out["coverage"]["dropped_by_reason"]["no_https_url"], 1)

    def test_whitespace_text_dropped(self):
        out = run(passages=[{"id": "p1", "url": "https://example.com", "text": "  \n "},
                            {"id": "p2", "url": "https://example.com", "text": "Ada Lovelace"}])
        self.assertEqual(out["coverage"]["dropped_by_reason"], {"no_https_url": 0, "empty_text": 1})


class Matching(unittest.TestCase):
    def test_case_sensitive_exact(self):
        out = run(passages=[{"id": "p1", "url": "https://example.com", "text": "ada lovelace"}])
        self.assertEqual(out["entities"], [])
        self.assertEqual(out["coverage"]["known_not_found"], ["Ada Lovelace"])
        self.assertEqual(out["coverage"]["entities_found"], 0)

    def test_zero_entities_is_success(self):
        out = run(known_entities=[],
                  passages=[{"id": "p1", "url": "https://example.com", "text": "all lowercase here"}])
        self.assertEqual(out["entities"], [])
        self.assertEqual(out["prompts"], [])

    def test_unicode_known_entity_exact(self):
        out = run(known_entities=[{"name": "S\u00e9amus Heaney", "type": "person"}],
                  passages=[{"id": "p1", "url": "https://example.com", "text": "S\u00e9amus Heaney wrote."}])
        self.assertEqual(names(out), [("S\u00e9amus Heaney", "person")])

    def test_offsets_are_zero_based_code_points(self):
        out = run(passages=[{"id": "p1", "url": "https://example.com",
                             "text": "\u00e9! Ada Lovelace."}])
        ent = out["entities"][0]
        self.assertEqual(ent["mentions"][0]["offset"], 3)

    def test_mentions_two_passages(self):
        out = run(passages=[{"id": "p1", "url": "https://example.com", "text": "Ada Lovelace."},
                            {"id": "p2", "url": "https://example.com", "text": "Ada Lovelace."}])
        ent = out["entities"][0]
        self.assertEqual([(x["passage_id"], x["offset"]) for x in ent["mentions"]],
                         [("p1", 0), ("p2", 0)])

    def test_mentions_deduped(self):
        out = run(passages=[{"id": "p1", "url": "https://example.com",
                             "text": "Ada Lovelace. Ada Lovelace."}])
        ent = out["entities"][0]
        offs = [x["offset"] for x in ent["mentions"]]
        self.assertEqual(offs, [0, 14])
        self.assertEqual(len(offs), len(set(offs)))

    def test_snippet_window_and_clip(self):
        text = "x" * 100 + "Ada Lovelace" + "y" * 100
        out = run(passages=[{"id": "p1", "url": "https://example.com", "text": text}])
        snip = out["entities"][0]["mentions"][0]["snippet"]
        self.assertLessEqual(len(snip), 160)
        self.assertIn("Ada Lovelace", snip)
        self.assertEqual(snip, text[40:172])

    def test_first_seen_is_as_of(self):
        out = run()
        self.assertEqual(out["entities"][0]["first_seen"], AS_OF)


class Candidates(unittest.TestCase):
    def test_regex_candidate_flagged_unconfirmed(self):
        out = run(known_entities=[],
                  passages=[{"id": "p1", "url": "https://example.com", "text": "Met New Delhi yesterday."}])
        self.assertEqual([(e["name"], e["status"]) for e in out["entities"]],
                         [("Met New Delhi", "candidate_unconfirmed")])

    def test_single_token_and_acronym_not_candidates(self):
        out = run(known_entities=[],
                  passages=[{"id": "p1", "url": "https://example.com", "text": "AI and OpenAI and NASA today."}])
        self.assertEqual(out["entities"], [])

    def test_four_tokens_candidate_five_token_tail(self):
        out = run(known_entities=[],
                  passages=[{"id": "p1", "url": "https://example.com",
                             "text": "The Quick Brown Fox."}])
        self.assertEqual([e["name"] for e in out["entities"]], ["The Quick Brown Fox"])

    def test_non_ascii_not_a_candidate(self):
        out = run(known_entities=[],
                  passages=[{"id": "p1", "url": "https://example.com", "text": "S\u00e9amus Heaney wrote."}])
        self.assertEqual(out["entities"], [])

    def test_candidate_equal_to_known_name_not_duplicated(self):
        out = run()
        self.assertEqual(len(out["entities"]), 1)
        self.assertEqual(out["entities"][0]["status"], "confirmed")


class OverlapAndHomonyms(unittest.TestCase):
    def test_longest_known_wins(self):
        out = run(known_entities=[{"name": "New York", "type": "concept"},
                                  {"name": "New York City", "type": "concept"}],
                  passages=[{"id": "p1", "url": "https://example.com", "text": "New York City grew."}])
        self.assertEqual(names(out), [("New York City", "concept")])

    def test_known_beats_candidate_same_span(self):
        out = run(known_entities=[{"name": "Grace Hopper", "type": "person"}],
                  passages=[{"id": "p1", "url": "https://example.com", "text": "Grace Hopper spoke."}])
        self.assertEqual([(e["name"], e["status"]) for e in out["entities"]],
                         [("Grace Hopper", "confirmed")])

    def test_homonyms_separate_records(self):
        out = run(known_entities=[{"name": "Mercury", "type": "concept"},
                                  {"name": "Mercury", "type": "product"}],
                  passages=[{"id": "p1", "url": "https://example.com", "text": "Mercury rose."}])
        self.assertEqual(sorted(names(out)), [("Mercury", "concept"), ("Mercury", "product")])
        for e in out["entities"]:
            self.assertEqual(e["homonym_types"], ["concept", "product"])

    def test_no_homonym_field_when_single_type(self):
        out = run()
        self.assertNotIn("homonym_types", out["entities"][0])


class Prompts(unittest.TestCase):
    def test_t1_only_with_focus(self):
        out = run(focus="compilers")
        t1 = [p for p in out["prompts"] if p["template_id"] == "T1"]
        self.assertEqual(len(t1), 1)
        self.assertEqual(t1[0]["text"], "What would Ada Lovelace's approach look like applied to compilers?")
        self.assertEqual(set(t1[0]), {"entity", "template_id", "text", "label"})
        self.assertEqual(t1[0]["label"], "template_prompt")
        self.assertEqual(t1[0]["entity"], "Ada Lovelace")

    def test_no_focus_no_t1(self):
        out = run()
        self.assertEqual([p for p in out["prompts"] if p["template_id"] == "T1"], [])

    def test_t2_next_in_sorted_order_wrapping(self):
        out = run(known_entities=[{"name": "Ada Lovelace", "type": "person"},
                                  {"name": "Grace Hopper", "type": "person"}],
                  passages=[{"id": "p1", "url": "https://example.com",
                             "text": "Ada Lovelace and Grace Hopper."}])
        t2 = {p["entity"]: p["text"] for p in out["prompts"] if p["template_id"] == "T2"}
        self.assertEqual(t2["Ada Lovelace"], "How does Ada Lovelace compare with Grace Hopper?")
        self.assertEqual(t2["Grace Hopper"], "How does Grace Hopper compare with Ada Lovelace?")

    def test_t2_needs_two_entities(self):
        out = run()
        self.assertEqual([p for p in out["prompts"] if p["template_id"] == "T2"], [])

    def test_candidates_get_no_prompts(self):
        out = run(known_entities=[],
                  passages=[{"id": "p1", "url": "https://example.com", "text": "New Delhi and Old Delhi."}])
        self.assertEqual(out["prompts"], [])


class OutputShape(unittest.TestCase):
    def test_entity_schema_exact(self):
        out = run()
        self.assertEqual(set(out["entities"][0]),
                         {"name", "type", "status", "mentions", "first_seen"})
        self.assertEqual(set(out["entities"][0]["mentions"][0]), {"passage_id", "offset", "snippet"})

    def test_coverage_schema_exact(self):
        out = run()
        self.assertEqual(set(out["coverage"]), {"passages_supplied", "passages_used",
                                                "dropped_by_reason", "entities_found",
                                                "known_not_found"})

    def test_output_keys_exact(self):
        out = run()
        self.assertEqual(set(out), {"entities", "prompts", "coverage", "scope"})

    def test_scope_block(self):
        out = run()
        self.assertEqual(set(out["scope"]), {"implemented", "not_implemented", "data_source", "as_of"})
        self.assertEqual(out["scope"]["as_of"], AS_OF)

    def test_deterministic_byte_identical(self):
        a = json.dumps(run(), sort_keys=True)
        b = json.dumps(run(), sort_keys=True)
        self.assertEqual(a, b)


class ReviewPins(unittest.TestCase):
    def assert_refusal(self, reason, **kwargs):
        with self.assertRaises(ValueError) as cm:
            run(**kwargs)
        self.assertEqual(str(cm.exception), "INTEL_REFUSED_"+reason)

    def test_duplicate_passage_ids_refused_no_echo(self):
        self.assert_refusal("BAD_TYPE:passages", passages=[
            {"id":"same", "url":"https://example.org", "text":"Ada Lovelace first."},
            {"id":"same", "url":"https://example.org", "text":"Ada Lovelace second."}])

    def test_duplicate_known_exact_refused(self):
        self.assert_refusal("BAD_TYPE:known_entities", known_entities=[
            {"name":"Ada Lovelace","type":"person"}, {"name":"Ada Lovelace","type":"person"}])

    def test_known_name_limit_controls_and_boundary(self):
        self.assert_refusal("TEXT_TOO_LONG:name", known_entities=[{"name":"x"*257,"type":"person"}])
        self.assert_refusal("CONTROL_CHARS:name", known_entities=[{"name":"a\x1fb","type":"person"}])
        out=run(known_entities=[{"name":"x"*256,"type":"person"}], passages=[{"id":"p","url":"https://example.org","text":"x"*256}])
        self.assertEqual(out["entities"][0]["name"],"x"*256)

    def test_duplicates_follow_whole_list_validation(self):
        self.assert_refusal("CONTROL_CHARS:text", passages=[
            {"id":"dup","url":"https://example.org","text":"Ada Lovelace"},
            {"id":"dup","url":"https://example.org","text":"Ada Lovelace"},
            {"id":"third","url":"https://example.org","text":"bad\x00text"}])
        self.assert_refusal("CONTROL_CHARS:name", known_entities=[
            {"name":"A","type":"person"},{"name":"A","type":"person"},{"name":"B\x00","type":"person"}])

    def test_known_nonlist_and_row_nondict(self):
        for val in [False,True,{},"", "x",0]:
            with self.subTest(val=val):self.assert_refusal("BAD_TYPE:known_entities",known_entities=val)
        self.assert_refusal("BAD_TYPE:passages",passages=["not row"])
        self.assert_refusal("BAD_TYPE:known_entities",known_entities=["not row"])

    def test_offset_zero_snippet_exact(self):
        text="ada lovelace"+"x"*100
        out=run(known_entities=[{"name":"ada lovelace","type":"person"}],passages=[{"id":"p","url":"https://example.org","text":text}])
        self.assertEqual(out["entities"][0]["mentions"][0],{"passage_id":"p","offset":0,"snippet":text[:72]})

    def test_found_excluded_unknown_included(self):
        out=run(known_entities=[{"name":"Ada Lovelace","type":"person"},{"name":"absent","type":"company"}])
        self.assertEqual(out["coverage"]["known_not_found"],["absent"])

    def test_t2_three_entities(self):
        out=run(known_entities=[{"name":n,"type":"person"} for n in ["b","a","c"]],passages=[{"id":"p","url":"https://example.org","text":"a b c"}])
        self.assertEqual([(p["entity"],p["text"]) for p in out["prompts"]],[("a","How does a compare with b?"),("b","How does b compare with c?"),("c","How does c compare with a?")])

    def test_adjacent_spans_survive(self):
        out=run(known_entities=[{"name":"abc","type":"person"},{"name":"def","type":"company"}],passages=[{"id":"p","url":"https://example.org","text":"abcdef"}])
        self.assertEqual([(e["name"],e["mentions"][0]["offset"]) for e in out["entities"]],[("abc",0),("def",3)])

    def test_multiline_accepted_controls_refused(self):
        text="Ada Lovelace\n\tcontinued\rline"
        out=run(passages=[{"id":"p","url":"https://example.org","text":text}])
        self.assertEqual(out["entities"][0]["mentions"][0]["snippet"],text)
        self.assert_refusal("CONTROL_CHARS:text",passages=[{"id":"p","url":"https://example.org","text":"Ada Lovelace\x1f"}])

    def test_limits_and_types_exact(self):
        self.assert_refusal("TEXT_TOO_LONG:as_of",as_of="x"*65)
        self.assert_refusal("TEXT_TOO_LONG:text",passages=[{"id":"p","url":"https://example.org","text":"x"*100001}])
        self.assert_refusal("TEXT_TOO_LONG:id",passages=[{"id":"x"*257,"url":"https://example.org","text":"Ada Lovelace"}])
        self.assert_refusal("BAD_TYPE:passages",passages=[{"id":1,"url":"https://example.org","text":"Ada Lovelace"}])

    def test_candidate_type_and_scope_exact(self):
        out=run(known_entities=[],passages=[{"id":"p","url":"https://example.org","text":"New Delhi"}])
        self.assertEqual(out["entities"][0]["type"],"concept")
        self.assertEqual(out["scope"],{"implemented":["structured entity records from supplied passages with evidence spans","fixed-template idea prompts for confirmed entities"],"not_implemented":["knowledge graph","entity resolution beyond exact name match","judging who is a leader","live fetch","verified entity facts"],"data_source":"supplied-passages","as_of":AS_OF})

class AdditionalSurvivorPins(unittest.TestCase):
    def test_t2_labels(self):
        out=run(known_entities=[{"name":"a","type":"person"},{"name":"b","type":"person"}],passages=[{"id":"p","url":"https://example.org","text":"a b"}])
        for prompt in out["prompts"]:
            self.assertEqual(set(prompt),{"entity","template_id","text","label"})
            self.assertEqual(prompt["label"],"template_prompt")
    def test_overlapping_occurrences(self):
        out=run(known_entities=[{"name":"aa","type":"person"}],passages=[{"id":"p","url":"https://example.org","text":"aaa"}])
        self.assertEqual([m["offset"] for m in out["entities"][0]["mentions"]],[0,1])
    def test_snippet_exact_cap(self):
        out=run(known_entities=[{"name":"x"*200,"type":"person"}],passages=[{"id":"p","url":"https://example.org","text":"x"*200}])
        self.assertEqual(out["entities"][0]["mentions"][0]["snippet"],"x"*160)
    def test_overlap_length_not_start(self):
        out=run(known_entities=[{"name":"abcd","type":"person"},{"name":"cd","type":"product"}],passages=[{"id":"p","url":"https://example.org","text":"abcd"}])
        self.assertEqual(names(out),[("abcd","person")])
    def test_dropped_row_id_validation_precedes_duplicates(self):
        with self.assertRaises(ValueError) as cm:
            run(passages=[{"id":"dup","url":"https://example.org","text":"Ada Lovelace"},{"id":"dup","url":"http://example.org","text":"x"},{"id":"bad\x00","url":"http://example.org","text":"x"}])
        self.assertEqual(str(cm.exception),"INTEL_REFUSED_CONTROL_CHARS:id")

class FinalOverlapPin(unittest.TestCase):
    def test_adjacent_nonzero_start_not_length(self):
        out=run(known_entities=[{"name":"abc","type":"person"},{"name":"def","type":"company"}],passages=[{"id":"p","url":"https://example.org","text":"x abcdef"}])
        self.assertEqual([(e["name"],e["mentions"][0]["offset"]) for e in out["entities"]],[("abc",2),("def",5)])

class OptionalKnownListPins(unittest.TestCase):
    def test_explicit_none_same_as_empty(self):
        self.assertEqual(run(known_entities=None),run(known_entities=[]))
    def test_absent_same_as_empty(self):
        request=req();request.pop("known_entities")
        self.assertEqual(m.run(request),run(known_entities=[]))

class CandidateKnownAdjacencyPin(unittest.TestCase):
    def test_candidate_then_known_adjacent_spans_both_kept(self):
        out=run(known_entities=[{"name":"-X","type":"product"}],passages=[{"id":"p","url":"https://example.org","text":"Alice Smith-X ok"}])
        self.assertEqual([(e["name"],e["status"],e["mentions"][0]["offset"]) for e in out["entities"]],[("-X","confirmed",11),("Alice Smith","candidate_unconfirmed",0)])

class AuditBoundaryAndOrderPins(unittest.TestCase):
    def test_focus_cap_n_and_n_plus_one(self):
        out=run(focus="x"*200)
        self.assertEqual(out["prompts"][0]["text"],"What would Ada Lovelace's approach look like applied to "+"x"*200+"?")
        with self.assertRaises(ValueError) as cm:run(focus="x"*201)
        self.assertEqual(str(cm.exception),"INTEL_REFUSED_TEXT_TOO_LONG:focus")
    def test_text_cap_n_and_n_plus_one(self):
        for n in [100000,100001]:
            request=req(known_entities=[],passages=[{"id":"p","url":"https://example.org","text":"x"*n}])
            if n==100000:self.assertEqual(m.run(request)["coverage"]["passages_used"],1)
            else:
                with self.assertRaises(ValueError) as cm:m.run(request)
                self.assertEqual(str(cm.exception),"INTEL_REFUSED_TEXT_TOO_LONG:text")
    def test_id_cap_n_and_n_plus_one(self):
        out=run(passages=[{"id":"x"*256,"url":"https://example.org","text":"Ada Lovelace"}])
        self.assertEqual(out["entities"][0]["mentions"][0]["passage_id"],"x"*256)
        with self.assertRaises(ValueError) as cm:run(passages=[{"id":"x"*257,"url":"https://example.org","text":"Ada Lovelace"}])
        self.assertEqual(str(cm.exception),"INTEL_REFUSED_TEXT_TOO_LONG:id")
    def test_as_of_cap_n_and_n_plus_one(self):
        self.assertEqual(run(as_of="x"*64)["scope"]["as_of"],"x"*64)
        with self.assertRaises(ValueError) as cm:run(as_of="x"*65)
        self.assertEqual(str(cm.exception),"INTEL_REFUSED_TEXT_TOO_LONG:as_of")
    def test_candidate_begins_at_known_end(self):
        out=run(known_entities=[{"name":"!","type":"product"}],passages=[{"id":"p","url":"https://example.org","text":"!Alice Smith"}])
        self.assertEqual([(e["name"],e["mentions"][0]["offset"]) for e in out["entities"]],[("!",0),("Alice Smith",1)])
    def test_passage_order_precedes_smaller_offset(self):
        passages=[{"id":"a","text":"xxxx!"},{"id":"b","text":"!"}]
        hits=m._collect_matches(passages,[{"name":"!","type":"product"}])
        self.assertEqual([(h[0],h[1]) for h in hits],[("a",4),("b",0)])
    def test_start_order_and_longer_overlap(self):
        hits=m._collect_matches([{"id":"p","text":"abcdef"}],[{"name":"ab","type":"person"},{"name":"abcdef","type":"product"},{"name":"cdef","type":"company"}])
        self.assertEqual([(h[1],h[2],h[3]) for h in hits],[(0,6,"abcdef")])
    def test_url_control_characters_drop(self):
        for code in [0,31,32]:
            out=run(passages=[{"id":"bad","url":"https://example.org/"+chr(code),"text":"Ada Lovelace"},{"id":"ok","url":"https://example.org","text":"Ada Lovelace"}])
            self.assertEqual(out["coverage"]["dropped_by_reason"]["no_https_url"],1)

class DifferentOffsetOverlapPin(unittest.TestCase):
    def test_offset_before_length_in_same_passage(self):
        hits=m._collect_matches([{"id":"p","text":"abcdef"}],[{"name":"abc","type":"person"},{"name":"bcdef","type":"company"}])
        self.assertEqual([(h[1],h[2],h[3]) for h in hits],[(0,3,"abc")])

class UrlCharacterPolicyPins(unittest.TestCase):
    def test_ascii_c1_complete_range(self):
        for code in range(0xA0):
            with self.subTest(code=code):
                self.assertEqual(m._valid_url("https://example.org/"+chr(code)),33 <= code <= 126)
    def test_format_character_ranges_refused(self):
        codes=list(range(0x200B,0x2010))+list(range(0x202A,0x202F))+list(range(0x2066,0x206A))+[0xFEFF,0xA0,0x2028,0x2029]
        for code in codes:
            with self.subTest(code=code):
                self.assertFalse(m._valid_url("https://example.org/"+chr(code)))
    def test_other_url_unicode_not_blanket_refused(self):
        self.assertTrue(m._valid_url("https://example.org/café"))

class UrlAdjacentAllowedBoundaryPins(unittest.TestCase):
    def test_characters_just_outside_new_ranges_accepted(self):
        for code in [0xA1,0x2010,0x202F,0x206A]:
            # U+202F is whitespace and remains refused by the existing whitespace rule.
            with self.subTest(code=code):
                self.assertEqual(m._valid_url("https://example.org/"+chr(code)),code != 0x202F)

if __name__ == "__main__":
    unittest.main()
