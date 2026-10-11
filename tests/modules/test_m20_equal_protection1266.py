"""Row 1266 Equal Protection: bounded five-element bookkeeping over caller data.

Hermetic stdlib tests. The module is loaded by file path so no web stack is needed.
Sample data is synthetic: no real names, ids or matters.
"""
import importlib.util
from pathlib import Path

import pytest

_PATH = (Path(__file__).resolve().parents[2] / "backend" / "app" / "modules"
         / "m20_general_cognitive_worker" / "equal_protection1266.py")
_spec = importlib.util.spec_from_file_location("equal_protection1266", _PATH)
ep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ep)
map_equal_protection = ep.map_equal_protection

BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel must verify "
            "jurisdiction, currency, citations, facts, duties, deadlines and strategy before use. "
            "This unit organizes caller-supplied equal-protection elements (classification, "
            "comparator, intent, scrutiny tier, fit) and the authority references cited for each. "
            "It selects no scrutiny tier, assesses no merits, decides no discrimination claim, "
            "verifies no authority or fact, and files or sends nothing.")


def auth(i="a1", **kw):
    d = {"id": i, "citation": "Example v. Sample, 1 Ex. 1", "jurisdiction": "XX-Federal",
         "effective_date": "2020-01-01", "last_checked_at": "2026-10-01"}
    d.update(kw)
    return d


def payload(**over):
    p = {
        "jurisdiction": "XX-Federal", "as_of": "2026-10-01",
        "authorities": [auth("a1"), auth("a2")],
        "classification": {"basis": "age band", "kind": "facial", "source_ids": ["a1"]},
        "comparator": {"treated_group": "group red", "treated_treatment": "denied permit",
                       "comparator_group": "group blue", "comparator_treatment": "granted permit",
                       "similarly_situated_assertion": "same application class",
                       "source_ids": ["a1"]},
        "intent": {"items": [{"kind": "stated_purpose", "text": "stated aim in preamble",
                              "source_ids": ["a2"]},
                             {"kind": "disparate_impact_data", "text": "approval rate gap table",
                              "source_ids": ["a1", "a2"]}]},
        "scrutiny": {"tier_supplied_by_counsel": "intermediate", "source_ids": ["a2"]},
        "fit": {"interest": "stated safety interest", "means": "age cutoff rule", "source_ids": ["a1"]},
    }
    p.update(over)
    return p


def refuse(p, message):
    with pytest.raises(ValueError) as ei:
        map_equal_protection(p)
    assert str(ei.value) == "EQUALP1266: " + message


# ------------------------------------------------------------ happy path

def test_complete_payload_exact_envelope():
    r = map_equal_protection(payload())
    assert r["row"] == 1266 and r["unit"] == "equal_protection_element_map"
    assert r["jurisdiction"] == "XX-Federal" and r["as_of"] == "2026-10-01"
    assert r["elements"]["classification"] == {
        "status": "supplied", "supplied": {"basis": "age band", "kind": "facial"},
        "source_ids": ["a1"], "unresolved_source_ids": []}
    assert r["elements"]["comparator"]["status"] == "supplied"
    assert r["elements"]["comparator"]["supplied"]["similarly_situated_assertion"] == "same application class"
    assert r["elements"]["intent"]["status"] == "supplied"
    assert r["elements"]["intent"]["kinds_present"] == ["disparate_impact_data", "stated_purpose"]
    assert r["elements"]["intent"]["source_ids"] == ["a1", "a2"]
    assert r["elements"]["scrutiny"]["supplied"] == {"tier_supplied_by_counsel": "intermediate"}
    assert r["elements"]["fit"]["supplied"] == {"interest": "stated safety interest", "means": "age cutoff rule"}
    assert [a["id"] for a in r["authorities"]] == ["a1", "a2"]
    assert r["authorities"][0] == {"id": "a1", "citation": "Example v. Sample, 1 Ex. 1",
        "jurisdiction": "XX-Federal", "jurisdiction_match": True, "effective_date": "2020-01-01",
        "last_checked_at": "2026-10-01", "stale": False, "not_yet_effective": False}
    assert r["open_items"] == [] and r["ready_for_counsel_review"] is True
    for flag in ("claim_decided", "scrutiny_selected_by_unit", "merits_assessed",
                 "authorities_verified", "filed_or_sent"):
        assert r[flag] is False
    assert r["requires_licensed_counsel"] is True
    assert r["boundary"] == BOUNDARY


def test_prefix_and_standing_boundary_constants():
    assert ep.PREFIX == "EQUALP1266"
    assert ep.STANDING_BOUNDARY == ("Legal work product for review, not legal advice. Licensed counsel "
        "must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.")


def test_input_not_mutated_and_deterministic():
    p = payload()
    import copy
    before = copy.deepcopy(p)
    assert map_equal_protection(p) == map_equal_protection(p)
    assert p == before


# ------------------------------------------------------------ missing / flagged elements

def test_absent_elements_are_missing_and_listed_in_fixed_order():
    p = payload()
    for k in ("classification", "comparator", "intent", "scrutiny", "fit"):
        del p[k]
    r = map_equal_protection(p)
    assert [r["elements"][k]["status"] for k in ("classification", "comparator", "intent", "scrutiny", "fit")] == ["missing"] * 5
    assert r["open_items"] == ["classification:missing", "comparator:missing", "intent:missing",
                               "scrutiny:missing", "fit:missing"]
    assert r["ready_for_counsel_review"] is False
    assert r["elements"]["classification"] == {"status": "missing", "supplied": None,
                                               "source_ids": [], "unresolved_source_ids": []}


def test_none_counts_as_absent():
    r = map_equal_protection(payload(scrutiny=None))
    assert r["elements"]["scrutiny"]["status"] == "missing"
    assert r["open_items"] == ["scrutiny:missing"]


def test_unsourced_element_flagged():
    p = payload()
    p["fit"]["source_ids"] = []
    r = map_equal_protection(p)
    assert r["elements"]["fit"]["status"] == "unsourced"
    assert r["open_items"] == ["fit:unsourced"]


def test_unresolved_source_id_flagged_and_listed():
    p = payload()
    p["classification"]["source_ids"] = ["a1", "ghost"]
    r = map_equal_protection(p)
    e = r["elements"]["classification"]
    assert e["status"] == "unresolved_sources" and e["unresolved_source_ids"] == ["ghost"]
    assert r["open_items"] == ["classification:unresolved_source:ghost"]


def test_jurisdiction_mismatch_flagged_per_element_and_authority():
    p = payload(authorities=[auth("a1", jurisdiction="YY-State"), auth("a2")])
    r = map_equal_protection(p)
    assert r["authorities"][0]["jurisdiction_match"] is False
    items = r["open_items"]
    assert "classification:jurisdiction_mismatch:a1" in items
    assert "comparator:jurisdiction_mismatch:a1" in items
    assert "fit:jurisdiction_mismatch:a1" in items
    assert not any(i.startswith("scrutiny:") for i in items)
    assert r["elements"]["classification"]["status"] == "supplied"  # status is about sourcing only


def test_stale_boundary_last_checked_vs_as_of():
    eq = map_equal_protection(payload(authorities=[auth("a1", last_checked_at="2026-10-01"), auth("a2")]))
    older = map_equal_protection(payload(authorities=[auth("a1", last_checked_at="2026-09-30"), auth("a2")]))
    assert eq["authorities"][0]["stale"] is False
    assert older["authorities"][0]["stale"] is True
    assert older["open_items"] == ["authority:a1:stale"]


def test_not_yet_effective_boundary():
    eq = map_equal_protection(payload(authorities=[auth("a1", effective_date="2026-10-01"), auth("a2")]))
    later = map_equal_protection(payload(authorities=[auth("a1", effective_date="2026-10-02"), auth("a2")]))
    assert eq["authorities"][0]["not_yet_effective"] is False
    assert later["authorities"][0]["not_yet_effective"] is True
    assert later["open_items"] == ["authority:a1:not_yet_effective"]


def test_authority_flags_follow_element_flags_in_order():
    p = payload(authorities=[auth("a1", last_checked_at="2026-01-01"), auth("a2")])
    p["fit"]["source_ids"] = []
    assert map_equal_protection(p)["open_items"] == ["fit:unsourced", "authority:a1:stale"]


def test_intent_aggregates_unresolved_and_unsourced_items():
    p = payload()
    p["intent"]["items"][0]["source_ids"] = []
    r = map_equal_protection(p)
    assert r["elements"]["intent"]["status"] == "unsourced"
    assert r["elements"]["intent"]["items"][0]["status"] == "unsourced"
    assert r["elements"]["intent"]["items"][1]["status"] == "supplied"
    p["intent"]["items"][0]["source_ids"] = ["ghost"]
    r = map_equal_protection(p)
    assert r["elements"]["intent"]["status"] == "unresolved_sources"
    assert r["elements"]["intent"]["unresolved_source_ids"] == ["ghost"]


def test_comparator_without_similarly_situated_assertion_is_open_item():
    p = payload()
    del p["comparator"]["similarly_situated_assertion"]
    r = map_equal_protection(p)
    assert r["elements"]["comparator"]["supplied"]["similarly_situated_assertion"] is None
    assert r["open_items"] == ["comparator:similarly_situated_assertion_missing"]


def test_tier_is_recorded_not_chosen_for_every_value():
    for tier in ("strict", "intermediate", "rational_basis"):
        p = payload()
        p["scrutiny"]["tier_supplied_by_counsel"] = tier
        r = map_equal_protection(p)
        assert r["elements"]["scrutiny"]["supplied"]["tier_supplied_by_counsel"] == tier
        assert r["scrutiny_selected_by_unit"] is False


# ------------------------------------------------------------ refusals

def test_payload_must_be_object():
    for bad in (None, [], "x", 3):
        refuse(bad, "payload requires an object")


@pytest.mark.parametrize("name", ["verdict", "conclusion", "outcome", "likely_outcome",
                                  "prediction", "merits", "ruling", "advice"])
def test_conclusion_seeking_field_refused(name):
    refuse(payload(**{name: "x"}), f"field '{name}' asks for a conclusion; this unit decides no claim")


def test_unknown_fields_refused_at_every_level():
    refuse(payload(extra=1), "unknown field in payload")
    p = payload(); p["classification"]["zzz"] = 1
    refuse(p, "unknown field in classification")
    p = payload(); p["authorities"][0]["zzz"] = 1
    refuse(p, "unknown field in authorities[0]")
    p = payload(); p["intent"]["items"][0]["zzz"] = 1
    refuse(p, "unknown field in intent.items[0]")
    p = payload(); p["intent"]["zzz"] = 1
    refuse(p, "unknown field in intent")


def test_jurisdiction_and_as_of_validation():
    refuse(payload(jurisdiction=""), "jurisdiction requires non-empty text of at most 2000 characters")
    refuse(payload(jurisdiction=5), "jurisdiction requires non-empty text of at most 2000 characters")
    p = payload(); del p["jurisdiction"]
    refuse(p, "jurisdiction requires non-empty text of at most 2000 characters")
    for bad in ("2026-13-01", "20261001", "2026-1-01", "x", 20261001, "2026-10-01T00:00"):
        refuse(payload(as_of=bad), "as_of requires an ISO date YYYY-MM-DD")


def test_authorities_list_bounds_n_and_n_plus_1():
    ok = [auth(f"a{i}") for i in range(64)]
    p = payload(authorities=ok)
    p["classification"]["source_ids"] = ["a0"]
    assert map_equal_protection(p)["authorities"][63]["id"] == "a63"
    refuse(payload(authorities=[auth(f"a{i}") for i in range(65)]),
           "authorities requires a list of 1..64 records")
    refuse(payload(authorities=[]), "authorities requires a list of 1..64 records")
    refuse(payload(authorities="x"), "authorities requires a list of 1..64 records")


def test_authority_record_validation():
    refuse(payload(authorities=["x"]), "authorities[0] requires an object")
    refuse(payload(authorities=[auth("a1"), auth("a1")]), "duplicate authority id")
    refuse(payload(authorities=[auth("a1", citation="")]),
           "authorities[0].citation requires non-empty text of at most 2000 characters")
    refuse(payload(authorities=[auth("a1", effective_date="2020/01/01")]),
           "authorities[0].effective_date requires an ISO date YYYY-MM-DD")
    refuse(payload(authorities=[auth("a1"), auth("a2", last_checked_at="no")]),
           "authorities[1].last_checked_at requires an ISO date YYYY-MM-DD")
    d = auth("a1"); del d["jurisdiction"]
    refuse(payload(authorities=[d]), "authorities[0].jurisdiction requires non-empty text of at most 2000 characters")


def test_text_length_n_and_n_plus_1():
    p = payload(); p["fit"]["interest"] = "x" * 2000
    assert map_equal_protection(p)["elements"]["fit"]["supplied"]["interest"] == "x" * 2000
    p["fit"]["interest"] = "x" * 2001
    refuse(p, "fit.interest requires non-empty text of at most 2000 characters")
    p["fit"]["interest"] = "   "
    refuse(p, "fit.interest requires non-empty text of at most 2000 characters")


def test_source_ids_bounds_and_shape():
    ids = [f"a{i}" for i in range(8)]
    p = payload(authorities=[auth(i) for i in ids])
    p["fit"]["source_ids"] = ids
    assert map_equal_protection(p)["elements"]["fit"]["source_ids"] == ids
    p["fit"]["source_ids"] = ids + ["a8"]
    refuse(p, "fit.source_ids requires a list of at most 8 unique non-empty text ids")
    for bad in (["a1", "a1"], [""], [3], "a1", None):
        q = payload(); q["fit"]["source_ids"] = bad
        refuse(q, "fit.source_ids requires a list of at most 8 unique non-empty text ids")
    q = payload(); del q["fit"]["source_ids"]
    refuse(q, "fit.source_ids requires a list of at most 8 unique non-empty text ids")


def test_element_must_be_object():
    for name in ("classification", "comparator", "intent", "scrutiny", "fit"):
        refuse(payload(**{name: "x"}), f"{name} requires an object")


def test_enum_validation():
    p = payload(); p["classification"]["kind"] = "other"
    refuse(p, "classification.kind must be one of facial, applied, unspecified")
    p = payload(); p["scrutiny"]["tier_supplied_by_counsel"] = "heightened"
    refuse(p, "scrutiny.tier_supplied_by_counsel must be one of strict, intermediate, rational_basis")
    p = payload(); p["intent"]["items"][0]["kind"] = "guess"
    refuse(p, "intent.items[0].kind must be one of facial_text, stated_purpose, "
              "disparate_impact_data, historical_background, procedural_departure")


def test_intent_items_bounds_n_and_n_plus_1():
    item = {"kind": "facial_text", "text": "t", "source_ids": ["a1"]}
    p = payload(); p["intent"]["items"] = [dict(item) for _ in range(32)]
    assert len(map_equal_protection(p)["elements"]["intent"]["items"]) == 32
    p["intent"]["items"] = [dict(item) for _ in range(33)]
    refuse(p, "intent.items requires a list of 1..32 records")
    p["intent"]["items"] = []
    refuse(p, "intent.items requires a list of 1..32 records")
    p["intent"] = {}
    refuse(p, "intent.items requires a list of 1..32 records")
    p["intent"]["items"] = ["x"]
    refuse(p, "intent.items[0] requires an object")


def test_refusal_prefix_is_exact_on_every_refusal():
    for bad in (None, payload(as_of="x"), payload(extra=1), payload(authorities=[])):
        with pytest.raises(ValueError) as ei:
            map_equal_protection(bad)
        assert str(ei.value).startswith("EQUALP1266: ")


def test_bool_is_not_text_or_date():
    refuse(payload(jurisdiction=True), "jurisdiction requires non-empty text of at most 2000 characters")
    p = payload(); p["classification"]["basis"] = False
    refuse(p, "classification.basis requires non-empty text of at most 2000 characters")


def test_output_never_carries_a_conclusion_key():
    r = map_equal_protection(payload())
    assert not {"verdict", "conclusion", "outcome", "prediction", "legal_conclusion"} & set(r)


def test_intent_mixed_unsourced_and_unresolved_reports_unresolved_first():
    p = payload()
    p["intent"]["items"][0]["source_ids"] = []
    p["intent"]["items"][1]["source_ids"] = ["ghost"]
    r = map_equal_protection(p)
    assert r["elements"]["intent"]["status"] == "unresolved_sources"
    assert r["open_items"] == ["intent:unresolved_source:ghost"]


# ------------------------------------------------ hardening policy pins (repair 1)
import sys
import unicodedata

CAT = "contains a control, format or line/paragraph-separator character"
BAD_CHARS = {
    "Cc": ["\x00", "\x07", "\n", "\t", "\r", "\x7f", "\x85"],
    "Cf": ["\u00ad", "\u2060", "\u200b", "\u200e", "\ufeff", "\u202e", "\u061c"],
    "Zl": ["\u2028"], "Zp": ["\u2029"],
}
ALL_BAD = [c for chars in BAD_CHARS.values() for c in chars]


def test_bad_char_table_is_in_the_categories_claimed():
    for cat, chars in BAD_CHARS.items():
        assert all(unicodedata.category(c) == cat for c in chars)


def _with_text(path, value):
    p = payload()
    if path == "jurisdiction":
        p["jurisdiction"] = value
        p["authorities"] = [auth("a1", jurisdiction=value), auth("a2")]
    elif path == "classification.basis":
        p["classification"]["basis"] = value
    elif path == "fit.interest":
        p["fit"]["interest"] = value
    elif path == "authorities[0].citation":
        p["authorities"][0]["citation"] = value
    elif path == "authorities[0].id":
        p["authorities"][0]["id"] = value
    elif path == "intent.items[0].text":
        p["intent"]["items"][0]["text"] = value
    elif path == "comparator.similarly_situated_assertion":
        p["comparator"]["similarly_situated_assertion"] = value
    return p


PATHS = ["jurisdiction", "classification.basis", "fit.interest", "authorities[0].citation",
         "authorities[0].id", "intent.items[0].text", "comparator.similarly_situated_assertion"]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("ch", ALL_BAD)
def test_cc_cf_zl_zp_refused_in_every_echoed_text_field(path, ch):
    field = path
    refuse(_with_text(path, "ab" + ch + "cd"), f"{field} {CAT}")
    refuse(_with_text(path, ch), f"{field} {CAT}")  # category screen precedes the emptiness check


def test_explicit_soft_hyphen_and_word_joiner_pins():
    assert unicodedata.category("\u00ad") == "Cf" and unicodedata.category("\u2060") == "Cf"
    refuse(_with_text("fit.interest", "a\u00adb"), f"fit.interest {CAT}")
    refuse(_with_text("fit.interest", "a\u2060b"), f"fit.interest {CAT}")


def test_every_cf_codepoint_refused():
    cf = [cp for cp in range(sys.maxunicode + 1) if unicodedata.category(chr(cp)) == "Cf"]
    assert len(cf) >= 100
    for cp in cf:
        with pytest.raises(ValueError) as ei:
            map_equal_protection(_with_text("fit.interest", "a" + chr(cp) + "b"))
        assert str(ei.value) == f"EQUALP1266: fit.interest {CAT}", hex(cp)


@pytest.mark.parametrize("ch", ["\u00a0", "\u3000", " ", "\u2003", "\u202f"])
def test_zs_spaces_accepted(ch):
    assert unicodedata.category(ch) == "Zs"
    v = "ab" + ch + "cd"
    assert map_equal_protection(_with_text("fit.interest", v))["elements"]["fit"]["supplied"]["interest"] == v


def test_lone_surrogate_not_newly_refused_disclosed_residual():
    v = "a\ud800b"
    assert unicodedata.category("\ud800") == "Cs"
    assert map_equal_protection(_with_text("fit.interest", v))["elements"]["fit"]["supplied"]["interest"] == v


def test_raw_length_checked_before_strip_and_before_unicode_scan():
    refuse(_with_text("fit.interest", "x" * 2000 + "\x07"), "fit.interest requires non-empty text of at most 2000 characters")
    refuse(_with_text("fit.interest", "x" * 1999 + "\x07"), f"fit.interest {CAT}")
    refuse(_with_text("fit.interest", "  " + "x" * 2000),
           "fit.interest requires non-empty text of at most 2000 characters")
    refuse(_with_text("fit.interest", " " * 3000 + "\x07"),
           "fit.interest requires non-empty text of at most 2000 characters")


def test_whitespace_only_still_refused_as_empty():
    refuse(_with_text("fit.interest", "\u00a0 \u3000"), "fit.interest requires non-empty text of at most 2000 characters")


def test_source_ids_screened_for_length_and_characters():
    for bad in ("a" * 2001, "a\nb", "a\u200bb", "a\u2028"):
        p = payload(); p["fit"]["source_ids"] = [bad]
        refuse(p, "fit.source_ids requires a list of at most 8 unique non-empty text ids")
    p = payload(authorities=[auth("a" * 2000), auth("a2")]); p["fit"]["source_ids"] = ["a" * 2000]
    assert map_equal_protection(p)["elements"]["fit"]["status"] == "supplied"


def test_date_rejects_trailing_newline_and_long_strings():
    refuse(payload(as_of="2026-10-01\n"), "as_of requires an ISO date YYYY-MM-DD")
    refuse(payload(as_of="2026-10-01" + "0" * 100000), "as_of requires an ISO date YYYY-MM-DD")


def test_container_key_counts_checked_before_iteration():
    big = {f"k{i}": 1 for i in range(200000)}
    refuse(big, "payload has too many fields (at most 16)")
    p = payload(); p["classification"] = {f"k{i}": 1 for i in range(200000)}
    refuse(p, "classification has too many fields (at most 11)")
    p = payload(); p["authorities"][0] = {f"k{i}": 1 for i in range(200000)}
    refuse(p, "authorities[0] has too many fields (at most 13)")
    p = payload(); p["intent"]["items"][0] = {f"k{i}": 1 for i in range(200000)}
    refuse(p, "intent.items[0] has too many fields (at most 11)")


def test_key_count_boundary_n_and_n_plus_1():
    ok = payload(); ok["classification"].update({f"z{i}": 1 for i in range(8)})  # 3 + 8 = 11
    refuse(ok, "unknown field in classification")
    over = payload(); over["classification"].update({f"z{i}": 1 for i in range(9)})  # 12
    refuse(over, "classification has too many fields (at most 11)")
    p16 = {f"k{i}": 1 for i in range(16)}
    refuse(p16, "unknown field in payload")
    refuse({f"k{i}": 1 for i in range(17)}, "payload has too many fields (at most 16)")


def test_unknown_key_is_never_echoed():
    for key in ("plain", "a" * 64, "a" * 65, "bad\nkey", "bad\u200bkey", "secret-looking-value"):
        r = None
        with pytest.raises(ValueError) as ei:
            map_equal_protection(payload(**{key: 1}))
        assert str(ei.value) == "EQUALP1266: unknown field in payload"
        assert key not in str(ei.value)
    p = payload(); p[7] = 1
    refuse(p, "unknown field in payload")


def test_payload_count_cap_precedes_conclusion_key_scan():
    big = {f"k{i}": 1 for i in range(200000)}
    big["verdict"] = "x"
    refuse(big, "payload has too many fields (at most 16)")
    ok = {f"k{i}": 1 for i in range(15)}
    ok["verdict"] = "x"  # 16 keys: within the cap, so the conclusion-field refusal applies
    refuse(ok, "field 'verdict' asks for a conclusion; this unit decides no claim")


# ------------------------------------------------ strict builtin types (repair 2)
class S(str):
    pass


class D(dict):
    pass


class L(list):
    pass


TXT = "requires non-empty text of at most 2000 characters"
SRC = "requires a list of at most 8 unique non-empty text ids"


def test_str_subclass_refused_everywhere_text_date_enum_source_id():
    refuse(payload(jurisdiction=S("XX-Federal")), f"jurisdiction {TXT}")
    refuse(payload(as_of=S("2026-10-01")), "as_of requires an ISO date YYYY-MM-DD")
    p = payload(); p["classification"]["basis"] = S("age band")
    refuse(p, f"classification.basis {TXT}")
    p = payload(); p["classification"]["kind"] = S("facial")
    refuse(p, "classification.kind must be one of facial, applied, unspecified")
    p = payload(); p["scrutiny"]["tier_supplied_by_counsel"] = S("strict")
    refuse(p, "scrutiny.tier_supplied_by_counsel must be one of strict, intermediate, rational_basis")
    p = payload(); p["intent"]["items"][0]["kind"] = S("facial_text")
    refuse(p, "intent.items[0].kind must be one of facial_text, stated_purpose, "
              "disparate_impact_data, historical_background, procedural_departure")
    p = payload(); p["fit"]["source_ids"] = [S("a1")]
    refuse(p, f"fit.source_ids {SRC}")
    p = payload(authorities=[auth(S("a1")), auth("a2")])
    refuse(p, f"authorities[0].id {TXT}")
    p = payload(); p["authorities"][0]["effective_date"] = S("2020-01-01")
    refuse(p, "authorities[0].effective_date requires an ISO date YYYY-MM-DD")


def test_dict_subclass_refused_at_every_object_level():
    refuse(D(payload()), "payload requires an object")
    for name in ("classification", "comparator", "intent", "scrutiny", "fit"):
        p = payload(); p[name] = D(p[name])
        refuse(p, f"{name} requires an object")
    p = payload(); p["authorities"][0] = D(p["authorities"][0])
    refuse(p, "authorities[0] requires an object")
    p = payload(); p["intent"]["items"][0] = D(p["intent"]["items"][0])
    refuse(p, "intent.items[0] requires an object")


def test_list_subclass_refused_at_every_list_level():
    refuse(payload(authorities=L([auth("a1"), auth("a2")])), "authorities requires a list of 1..64 records")
    p = payload(); p["intent"]["items"] = L(p["intent"]["items"])
    refuse(p, "intent.items requires a list of 1..32 records")
    p = payload(); p["fit"]["source_ids"] = L(["a1"])
    refuse(p, f"fit.source_ids {SRC}")


def test_non_builtin_scalars_refused():
    refuse(payload(jurisdiction=b"XX"), f"jurisdiction {TXT}")
    refuse(payload(authorities=({"id": "a"},)), "authorities requires a list of 1..64 records")
    p = payload(); p["classification"]["source_ids"] = ("a1",)
    refuse(p, f"classification.source_ids {SRC}")


def test_every_refusal_reason_is_fixed_no_caller_value_echo():
    secret = "SECRET-CALLER-VALUE-123"
    cases = [
        payload(authorities=[auth(secret), auth(secret)]),
        payload(**{secret: 1}),
        payload(jurisdiction=secret + "\u200b"),
        payload(as_of=secret),
        payload(authorities=[auth("a1", effective_date=secret), auth("a2")]),
    ]
    p = payload(); p["classification"]["kind"] = secret; cases.append(p)
    p = payload(); p["scrutiny"]["tier_supplied_by_counsel"] = secret; cases.append(p)
    p = payload(); p["intent"]["items"][0]["kind"] = secret; cases.append(p)
    p = payload(); p["fit"]["source_ids"] = [secret, secret]; cases.append(p)
    p = payload(); p["classification"][secret] = 1; cases.append(p)
    for c in cases:
        with pytest.raises(ValueError) as ei:
            map_equal_protection(c)
        assert secret not in str(ei.value) and str(ei.value).startswith("EQUALP1266: ")


# ------------------------------------------------ repair 3: enum raw cap, strict key type
def test_str_subclass_key_refused_even_when_it_equals_an_allowed_name():
    p = payload(); p["classification"] = {S("basis"): "age band", "kind": "facial", "source_ids": ["a1"]}
    refuse(p, "unknown field in classification")
    p = payload(); p["authorities"][0] = {S("id"): "a1", "citation": "c", "jurisdiction": "XX-Federal",
                                         "effective_date": "2020-01-01", "last_checked_at": "2026-10-01"}
    refuse(p, "unknown field in authorities[0]")
    p = payload(); p["intent"]["items"][0] = {S("kind"): "facial_text", "text": "t", "source_ids": []}
    refuse(p, "unknown field in intent.items[0]")
    p = payload(); p[S("fit")] = p.pop("fit")
    refuse(p, "unknown field in payload")


def test_str_subclass_conclusion_key_is_not_matched_by_name():
    p = payload(); p[S("verdict")] = "x"
    refuse(p, "unknown field in payload")
    refuse(payload(verdict="x"), "field 'verdict' asks for a conclusion; this unit decides no claim")


def test_enum_value_over_raw_cap_refused_with_the_enum_reason():
    for v in ("strict" * 1000, "x" * 10_000_000):
        p = payload(); p["scrutiny"]["tier_supplied_by_counsel"] = v
        refuse(p, "scrutiny.tier_supplied_by_counsel must be one of strict, intermediate, rational_basis")
    p = payload(); p["scrutiny"]["tier_supplied_by_counsel"] = "rational_basis"
    assert map_equal_protection(p)["elements"]["scrutiny"]["supplied"]["tier_supplied_by_counsel"] == "rational_basis"


# ------------------------------------------------ closing pins (auditor-5 gate; tests-only, runtime unchanged)

class _StrSub(str):
    pass


def test_week_calendar_dates_refused_on_all_date_fields():
    # '2026-W01-1' is a valid ISO week date (datetime.date.fromisoformat accepts it on
    # 3.11+); the shape gate (len 10 + strict digit regex) must refuse it on every field.
    refuse(payload(as_of="2026-W01-1"), "as_of requires an ISO date YYYY-MM-DD")
    refuse(payload(authorities=[auth("a1", effective_date="2026-W01-1"), auth("a2")]),
           "authorities[0].effective_date requires an ISO date YYYY-MM-DD")
    refuse(payload(authorities=[auth("a1", last_checked_at="2026-W01-1"), auth("a2")]),
           "authorities[0].last_checked_at requires an ISO date YYYY-MM-DD")


def test_payload_dict_subclass_refused():
    class DictSub(dict):
        pass
    refuse(DictSub(payload()), "payload requires an object")
    p = payload(); p["verdict"] = "likely allowed"
    # the root exact-type guard fires before the conclusion-field screen: under an
    # isinstance mutant the verdict-key path would raise the conclusion refusal instead
    refuse(DictSub(p), "payload requires an object")


def test_jurisdiction_mismatch_catches_case_variants():
    # match is exact string equality: a lower/upper-case variant still flags the element
    for variant in ("xx-federal", "XX-FEDERAL"):
        p = payload(authorities=[auth("a1", jurisdiction=variant), auth("a2")])
        r = map_equal_protection(p)
        assert r["authorities"][0]["jurisdiction_match"] is False
        assert "classification:jurisdiction_mismatch:a1" in r["open_items"]


_COMP_TEXT_FIELDS = ("treated_group", "treated_treatment", "comparator_group", "comparator_treatment")


def test_comparator_text_fields_refuse_bad_values():
    for f in _COMP_TEXT_FIELDS:
        base = f"comparator.{f}"
        p = payload(); p["comparator"][f] = "   "
        refuse(p, base + " requires non-empty text of at most 2000 characters")
        p = payload(); p["comparator"][f] = "ok\x01bad"
        refuse(p, base + " " + CAT)
        p = payload(); p["comparator"][f] = "x" * 2001
        refuse(p, base + " requires non-empty text of at most 2000 characters")
        p = payload(); p["comparator"][f] = 5
        refuse(p, base + " requires non-empty text of at most 2000 characters")
        p = payload(); p["comparator"][f] = _StrSub("valid text")
        refuse(p, base + " requires non-empty text of at most 2000 characters")


def test_fit_means_refuses_bad_values_like_fit_interest():
    base = "fit.means"
    p = payload(); p["fit"]["means"] = "   "
    refuse(p, base + " requires non-empty text of at most 2000 characters")
    p = payload(); p["fit"]["means"] = "ok\x01bad"
    refuse(p, base + " " + CAT)
    p = payload(); p["fit"]["means"] = "x" * 2001
    refuse(p, base + " requires non-empty text of at most 2000 characters")
    p = payload(); p["fit"]["means"] = 5
    refuse(p, base + " requires non-empty text of at most 2000 characters")
    p = payload(); p["fit"]["means"] = _StrSub("valid text")
    refuse(p, base + " requires non-empty text of at most 2000 characters")


def test_intent_aggregation_dedups_and_sorts_across_items():
    p = payload(authorities=[auth("a1"), auth("a2"), auth("a3", jurisdiction="YY-State")])
    p["intent"]["items"] = [
        {"kind": "stated_purpose", "text": "first note", "source_ids": ["u9", "a3"]},
        {"kind": "facial_text", "text": "second note", "source_ids": ["u9", "a3"]},
    ]
    r = map_equal_protection(p)
    e = r["elements"]["intent"]
    assert e["status"] == "unresolved_sources"
    assert e["unresolved_source_ids"] == ["u9"]
    assert e["source_ids"] == ["a3", "u9"]
    assert e["kinds_present"] == ["facial_text", "stated_purpose"]
    items = r["open_items"]
    assert items.count("intent:unresolved_source:u9") == 1
    assert items.count("intent:jurisdiction_mismatch:a3") == 1
    assert items == ["intent:unresolved_source:u9", "intent:jurisdiction_mismatch:a3"]


def test_returned_source_ids_do_not_alias_caller_lists():
    p = payload()
    cls_ids = p["classification"]["source_ids"]
    item_ids = p["intent"]["items"][0]["source_ids"]
    r = map_equal_protection(p)
    r["elements"]["classification"]["source_ids"].append("evil")
    r["elements"]["intent"]["items"][0]["source_ids"].append("evil")
    assert cls_ids == ["a1"] and item_ids == ["a2"]
