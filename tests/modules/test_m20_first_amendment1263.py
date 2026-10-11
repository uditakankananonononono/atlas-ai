"""Row 1263 First Amendment: hermetic stdlib tests (test-first; RED before the module existed)."""
import copy
import importlib.util
import pathlib
import pytest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/first_amendment1263.py"
_spec = importlib.util.spec_from_file_location("first_amendment1263", _P)
fa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fa)

AUTH = {"id": "a1", "citation_text": "Supplied citation text", "jurisdiction": "US-Federal", "effective_date": "2020-01-01"}


def item(i="i1", **kw):
    d = {"id": i, "speech": "political", "speaker": "private_individual", "forum": "traditional_public",
         "restriction": "content_based", "scrutiny_declared": "strict", "source_ids": ["a1"]}
    d.update(kw)
    return d


def payload(**kw):
    d = {"jurisdiction": "US-Federal", "as_of": "2026-01-01", "authorities": [dict(AUTH)], "items": [item()]}
    d.update(kw)
    return d


def refusal(p):
    with pytest.raises(ValueError) as e:
        fa.classify(p)
    return str(e.value)


def test_golden_output_and_never_decides():
    r = fa.classify(payload())
    assert r["row"] == 1263 and r["status"] == "caller_declared_classification_bookkeeping_only"
    assert r["constitutionality_decided"] is False and r["legal_conclusion"] is None
    assert r["filing_or_external_effect"] is False and r["authorities_independently_verified"] is False
    assert r["requires_licensed_counsel"] is True and r["review_state"] == "counsel_review_required"
    assert r["disclaimer"] == fa.BOUNDARY
    c = r["classified"][0]
    assert c["id"] == "i1" and c["speech"] == "political" and c["forum"] == "traditional_public"
    assert c["reference_scrutiny_label"] == "strict" and c["scrutiny_declared"] == "strict"
    assert c["scrutiny_matches_reference"] is True and c["unclassified_fields"] == [] and c["missing_source_ids"] == []
    assert r["counts"] == {"items": 1, "unclassified": 0, "scrutiny_mismatch": 0, "blocked_items": 0}


def test_boundary_text_verbatim():
    assert fa.BOUNDARY == ("Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, "
                           "currency, citations, facts, duties, deadlines and strategy before use.")


@pytest.mark.parametrize("restriction,label", [("content_based", "strict"), ("viewpoint_based", "strict"),
                                               ("content_neutral", "intermediate"), ("time_place_manner", "intermediate"),
                                               ("prior_restraint", "heavy_presumption_against"), ("compelled_speech", "exacting_or_strict")])
def test_reference_label_table(restriction, label):
    c = fa.classify(payload(items=[item(restriction=restriction, scrutiny_declared="none_declared")]))["classified"][0]
    assert c["reference_scrutiny_label"] == label


def test_scrutiny_mismatch_flagged_not_decided():
    r = fa.classify(payload(items=[item(scrutiny_declared="rational_basis")]))
    c = r["classified"][0]
    assert c["scrutiny_matches_reference"] is False and r["counts"]["scrutiny_mismatch"] == 1
    assert r["review_state"] == "blocked" and r["constitutionality_decided"] is False


def test_none_declared_is_not_a_mismatch():
    c = fa.classify(payload(items=[item(scrutiny_declared="none_declared")]))["classified"][0]
    assert c["scrutiny_matches_reference"] is None


def test_unknown_values_listed_as_unclassified():
    r = fa.classify(payload(items=[item(speech="unknown", forum="unknown", restriction="unknown")]))
    c = r["classified"][0]
    assert c["unclassified_fields"] == ["speech", "forum", "restriction"]
    assert c["reference_scrutiny_label"] is None and c["scrutiny_matches_reference"] is None
    assert r["counts"]["unclassified"] == 1 and r["review_state"] == "blocked"


def test_unknown_speaker_listed():
    c = fa.classify(payload(items=[item(speaker="unknown")]))["classified"][0]
    assert c["unclassified_fields"] == ["speaker"]


def test_missing_source_id_blocks():
    r = fa.classify(payload(items=[item(source_ids=["a1", "zz"])]))
    assert r["classified"][0]["missing_source_ids"] == ["zz"] and r["review_state"] == "blocked"


def test_jurisdiction_mismatch_and_post_as_of_flagged():
    a = dict(AUTH, jurisdiction="US-OtherState", effective_date="2027-01-01")
    r = fa.classify(payload(authorities=[a]))
    assert r["authority_flags"] == [{"id": "a1", "jurisdiction_mismatch": True, "effective_after_as_of": True,
                                     "independently_verified": False}]
    assert r["review_state"] == "blocked"


def test_effective_on_as_of_is_not_flagged():
    r = fa.classify(payload(authorities=[dict(AUTH, effective_date="2026-01-01")]))
    assert r["authority_flags"][0]["effective_after_as_of"] is False


def test_input_not_mutated_and_deterministic():
    p = payload(); q = copy.deepcopy(p)
    assert fa.classify(p) == fa.classify(p) and p == q


@pytest.mark.parametrize("bad,code", [
    (None, "BAD_TYPE:payload"), ([], "BAD_TYPE:payload"),
])
def test_payload_type(bad, code):
    assert refusal(bad) == "FIRSTA1263:" + code


@pytest.mark.parametrize("key", ["jurisdiction", "as_of", "authorities", "items"])
def test_missing_required_key(key):
    p = payload(); del p[key]
    assert refusal(p) == "FIRSTA1263:MISSING:" + key


def test_unknown_top_level_key():
    assert refusal(payload(extra=1)) == "FIRSTA1263:UNKNOWN_KEY"


@pytest.mark.parametrize("key,code", [("decide", "CONCLUSION_REFUSED"), ("constitutional", "CONCLUSION_REFUSED"),
                                      ("conclusion", "CONCLUSION_REFUSED"), ("file", "EXTERNAL_EFFECT_REFUSED"),
                                      ("serve", "EXTERNAL_EFFECT_REFUSED"), ("contact", "EXTERNAL_EFFECT_REFUSED"),
                                      ("send", "EXTERNAL_EFFECT_REFUSED"), ("spend", "EXTERNAL_EFFECT_REFUSED")])
def test_conclusion_and_effect_keys_refused_first(key, code):
    p = payload(); p[key] = True
    assert refusal(p) == "FIRSTA1263:" + code
    p[key] = False   # falsy still unknown key, but refusal order: guard only on truthy
    assert refusal(p) == "FIRSTA1263:UNKNOWN_KEY"


@pytest.mark.parametrize("field", ["jurisdiction"])
@pytest.mark.parametrize("val,code", [(5, "BAD_TYPE"), ("", "EMPTY"), ("  ", "EMPTY"), ("a\x00b", "CONTROL_CHARS"), ("x" * 257, "TEXT_TOO_LONG")])
def test_text_rules(field, val, code):
    assert refusal(payload(**{field: val})) == "FIRSTA1263:%s:%s" % (code, field)


def test_text_length_boundary_accepts_256():
    assert fa.classify(payload(jurisdiction="x" * 256, authorities=[dict(AUTH, jurisdiction="x" * 256)]))


@pytest.mark.parametrize("val", ["2026-13-01", "2026/01/01", "x", "2026-1-1"])
def test_as_of_must_be_iso(val):
    assert refusal(payload(as_of=val)) == "FIRSTA1263:BAD_DATE:as_of"


def test_authority_date_must_be_iso():
    assert refusal(payload(authorities=[dict(AUTH, effective_date="nope")])) == "FIRSTA1263:BAD_DATE:effective_date"


def test_authorities_required_nonempty_and_caps():
    assert refusal(payload(authorities=[])) == "FIRSTA1263:EMPTY:authorities"
    assert refusal(payload(authorities="x")) == "FIRSTA1263:BAD_TYPE:authorities"
    many = [dict(AUTH, id="a%d" % i) for i in range(32)]
    assert fa.classify(payload(authorities=many, items=[item(source_ids=["a0"])]))
    assert refusal(payload(authorities=many + [dict(AUTH, id="a32")])) == "FIRSTA1263:TOO_MANY:authorities"


def test_items_cap_and_empty():
    ok = [item("i%d" % i) for i in range(16)]
    assert fa.classify(payload(items=ok))["counts"]["items"] == 16
    assert refusal(payload(items=ok + [item("i16")])) == "FIRSTA1263:TOO_MANY:items"
    assert refusal(payload(items=[])) == "FIRSTA1263:EMPTY:items"
    assert refusal(payload(items="x")) == "FIRSTA1263:BAD_TYPE:items"


def test_source_ids_cap():
    ids = ["a1"] * 8
    assert fa.classify(payload(items=[item(source_ids=ids)]))
    assert refusal(payload(items=[item(source_ids=ids + ["a1"])])) == "FIRSTA1263:TOO_MANY:source_ids"
    assert refusal(payload(items=[item(source_ids=[])])) == "FIRSTA1263:EMPTY:source_ids"
    assert refusal(payload(items=[item(source_ids="a1")])) == "FIRSTA1263:BAD_TYPE:source_ids"
    assert refusal(payload(items=[item(source_ids=[3])])) == "FIRSTA1263:BAD_TYPE:source_id"


def test_duplicate_ids():
    assert refusal(payload(items=[item("i1"), item("i1")])) == "FIRSTA1263:DUPLICATE:item_id"
    assert refusal(payload(authorities=[dict(AUTH), dict(AUTH)])) == "FIRSTA1263:DUPLICATE:authority_id"


@pytest.mark.parametrize("field", ["speech", "speaker", "forum", "restriction", "scrutiny_declared"])
def test_vocabulary_enforced(field):
    assert refusal(payload(items=[item(**{field: "made_up"})])) == "FIRSTA1263:UNKNOWN_VALUE:" + field
    assert refusal(payload(items=[item(**{field: 3})])) == "FIRSTA1263:BAD_TYPE:" + field


@pytest.mark.parametrize("field", ["speech", "speaker", "forum", "restriction", "scrutiny_declared", "source_ids", "id"])
def test_item_required_fields(field):
    it = item(); del it[field]
    assert refusal(payload(items=[it])) == "FIRSTA1263:MISSING:" + field


def test_item_and_authority_shape():
    assert refusal(payload(items=["x"])) == "FIRSTA1263:BAD_TYPE:item"
    assert refusal(payload(authorities=["x"])) == "FIRSTA1263:BAD_TYPE:authority"
    assert refusal(payload(items=[item(zzz=1)])) == "FIRSTA1263:UNKNOWN_KEY"
    assert refusal(payload(authorities=[dict(AUTH, zzz=1)])) == "FIRSTA1263:UNKNOWN_KEY"
    a = dict(AUTH); del a["citation_text"]
    assert refusal(payload(authorities=[a])) == "FIRSTA1263:MISSING:citation_text"


def test_item_conclusion_key_refused():
    assert refusal(payload(items=[item(constitutional=True)])) == "FIRSTA1263:CONCLUSION_REFUSED"
    assert refusal(payload(items=[item(decide="yes")])) == "FIRSTA1263:CONCLUSION_REFUSED"


def test_constants_pinned():
    assert (fa.MAX_ITEMS, fa.MAX_AUTHORITIES, fa.MAX_SOURCE_IDS, fa.MAX_TEXT) == (16, 32, 8, 256)
    assert fa.PREFIX == "FIRSTA1263"
    assert fa.REFERENCE_LABELS == {"content_based": "strict", "viewpoint_based": "strict", "content_neutral": "intermediate",
                                   "time_place_manner": "intermediate", "prior_restraint": "heavy_presumption_against",
                                   "compelled_speech": "exacting_or_strict"}


def test_output_has_no_verdict_words():
    s = repr(fa.classify(payload())).lower()
    for w in ("unconstitutional", "violates", "is constitutional", "upheld", "struck down"):
        assert w not in s


# ---- retake pins for mutation survivors ----
def test_vocab_tables_pinned_exactly():
    assert fa.VOCAB == {
        "speech": ("political", "commercial", "expressive_conduct", "government_speech", "student",
                   "public_employee", "unprotected_category_asserted", "other", "unknown"),
        "speaker": ("private_individual", "media", "corporation", "public_employee", "student", "government", "unknown"),
        "forum": ("traditional_public", "designated_public", "limited_public", "nonpublic", "private", "unknown"),
        "restriction": ("content_based", "content_neutral", "viewpoint_based", "prior_restraint", "compelled_speech",
                        "time_place_manner", "unknown"),
        "scrutiny_declared": ("strict", "intermediate", "rational_basis", "exacting", "other_declared", "none_declared"),
    }


@pytest.mark.parametrize("field", ["speech", "speaker", "forum", "restriction", "scrutiny_declared"])
def test_every_vocab_value_accepted_and_echoed(field):
    for v in fa.VOCAB[field]:
        c = fa.classify(payload(items=[item(**{field: v})]))["classified"][0]
        assert c[field] == v


def test_label_match_table_pinned_and_all_pairs():
    assert fa._LABEL_MATCH == {"strict": ("strict",), "intermediate": ("intermediate",),
                               "heavy_presumption_against": ("strict", "other_declared"),
                               "exacting_or_strict": ("exacting", "strict")}
    for r, label in fa.REFERENCE_LABELS.items():
        for d in fa.VOCAB["scrutiny_declared"]:
            c = fa.classify(payload(items=[item(restriction=r, scrutiny_declared=d)]))["classified"][0]
            want = None if d == "none_declared" else d in fa._LABEL_MATCH[label]
            assert c["scrutiny_matches_reference"] is want


def test_full_classified_dict_and_top_fields():
    r = fa.classify(payload())
    assert r["jurisdiction"] == "US-Federal" and r["as_of"] == "2026-01-01"
    assert r["classified"][0] == {"id": "i1", "speech": "political", "speaker": "private_individual",
                                  "forum": "traditional_public", "restriction": "content_based",
                                  "scrutiny_declared": "strict", "reference_scrutiny_label": "strict",
                                  "scrutiny_matches_reference": True, "unclassified_fields": [], "missing_source_ids": []}
    assert set(r) == {"row", "status", "jurisdiction", "as_of", "classified", "authority_flags", "counts",
                      "review_state", "constitutionality_decided", "legal_conclusion", "filing_or_external_effect",
                      "authorities_independently_verified", "requires_licensed_counsel", "disclaimer"}


def test_blocked_items_counts_one_per_item():
    r = fa.classify(payload(items=[item("i1", speech="unknown", scrutiny_declared="rational_basis"), item("i2")]))
    assert r["counts"]["blocked_items"] == 1


def test_authority_problem_either_flag_alone_blocks():
    assert fa.classify(payload(authorities=[dict(AUTH, jurisdiction="X")]))["review_state"] == "blocked"
    assert fa.classify(payload(authorities=[dict(AUTH, effective_date="2027-01-01")]))["review_state"] == "blocked"
    assert fa.classify(payload())["review_state"] == "counsel_review_required"


def test_compact_iso_date_refused_and_names():
    assert refusal(payload(as_of="20260101")) == "FIRSTA1263:BAD_DATE:as_of"
    assert refusal(payload(authorities=[dict(AUTH, effective_date="20200101")])) == "FIRSTA1263:BAD_DATE:effective_date"


def test_del_char_refused_and_space_ok():
    assert refusal(payload(jurisdiction="a\x7fb")) == "FIRSTA1263:CONTROL_CHARS:jurisdiction"
    assert refusal(payload(jurisdiction="a\x1fb")) == "FIRSTA1263:CONTROL_CHARS:jurisdiction"
    assert fa.classify(payload(jurisdiction="a b", authorities=[dict(AUTH, jurisdiction="a b")]))


@pytest.mark.parametrize("field,name", [("id", "authority_id"), ("citation_text", "citation_text"), ("jurisdiction", "jurisdiction")])
@pytest.mark.parametrize("val,code", [(5, "BAD_TYPE"), ("", "EMPTY")])
def test_authority_text_names(field, name, val, code):
    assert refusal(payload(authorities=[dict(AUTH, **{field: val})])) == "FIRSTA1263:%s:%s" % (code, name)


@pytest.mark.parametrize("val,code", [(5, "BAD_TYPE"), ("", "EMPTY")])
def test_item_id_text_name(val, code):
    assert refusal(payload(items=[item(i=val)])) == "FIRSTA1263:%s:item_id" % code


# ---- settled text/container policy pins (repair) ----
import sys
import unicodedata


def _cf_all():
    return [chr(c) for c in range(sys.maxunicode + 1) if unicodedata.category(chr(c)) == "Cf"]


def test_every_cf_codepoint_refused_including_00ad_and_2060():
    cf = _cf_all()
    assert "\u00ad" in cf and "\u2060" in cf and len(cf) > 100
    for ch in cf:
        assert refusal(payload(jurisdiction="a" + ch + "b")) == "FIRSTA1263:CONTROL_CHARS:jurisdiction", hex(ord(ch))
    assert refusal(payload(jurisdiction="a\u00adb")) == "FIRSTA1263:CONTROL_CHARS:jurisdiction"
    assert refusal(payload(jurisdiction="a\u2060b")) == "FIRSTA1263:CONTROL_CHARS:jurisdiction"


@pytest.mark.parametrize("ch", ["\u2028", "\u2029", "\x85", "\x9f", "\x00", "\x7f"])
def test_zl_zp_cc_refused(ch):
    assert refusal(payload(jurisdiction="a" + ch + "b")) == "FIRSTA1263:CONTROL_CHARS:jurisdiction"


@pytest.mark.parametrize("ch", ["\u00a0", "\u2003", "\u3000", " "])
def test_zs_accepted_inside_text(ch):
    j = "a" + ch + "b"
    assert fa.classify(payload(jurisdiction=j, authorities=[dict(AUTH, jurisdiction=j)]))["jurisdiction"] == j


def test_surrogate_not_newly_refused_disclosed_residual():
    j = "a\ud800b"
    assert fa.classify(payload(jurisdiction=j, authorities=[dict(AUTH, jurisdiction=j)]))["jurisdiction"] == j


def test_raw_length_cap_before_strip_and_unicode():
    assert refusal(payload(jurisdiction=" " * 257)) == "FIRSTA1263:TEXT_TOO_LONG:jurisdiction"
    assert refusal(payload(jurisdiction="\u200b" * 257)) == "FIRSTA1263:TEXT_TOO_LONG:jurisdiction"
    assert refusal(payload(jurisdiction=" " * 256)) == "FIRSTA1263:EMPTY:jurisdiction"


def test_key_count_cap():
    big = {"k%d" % i: 1 for i in range(fa.MAX_KEYS + 1)}
    assert refusal(big) == "FIRSTA1263:TOO_MANY:keys"
    assert refusal(payload(items=[dict(big)])) == "FIRSTA1263:TOO_MANY:keys"
    assert refusal(payload(authorities=[dict(big)])) == "FIRSTA1263:TOO_MANY:keys"
    assert fa.MAX_KEYS == 16
    ok = dict(payload()); ok.update({"x%d" % i: 0 for i in range(fa.MAX_KEYS - 4)})
    assert refusal(ok) == "FIRSTA1263:UNKNOWN_KEY"


def test_list_len_cap_before_item_work():
    assert refusal(payload(items=[1] * 17)) == "FIRSTA1263:TOO_MANY:items"
    assert refusal(payload(authorities=[1] * 33)) == "FIRSTA1263:TOO_MANY:authorities"
    assert refusal(payload(items=[item(source_ids=["a"] * 9)])) == "FIRSTA1263:TOO_MANY:source_ids"


class _D(dict):
    pass


class _L(list):
    pass


class _S(str):
    pass


def test_strict_builtin_types_dict():
    assert refusal(_D(payload())) == "FIRSTA1263:BAD_TYPE:payload"
    assert refusal(payload(items=[_D(item())])) == "FIRSTA1263:BAD_TYPE:item"
    assert refusal(payload(authorities=[_D(AUTH)])) == "FIRSTA1263:BAD_TYPE:authority"


def test_strict_builtin_types_list():
    assert refusal(payload(items=_L([item()]))) == "FIRSTA1263:BAD_TYPE:items"
    assert refusal(payload(authorities=_L([dict(AUTH)]))) == "FIRSTA1263:BAD_TYPE:authorities"
    assert refusal(payload(items=[item(source_ids=_L(["a1"]))])) == "FIRSTA1263:BAD_TYPE:source_ids"


def test_strict_builtin_types_str():
    assert refusal(payload(jurisdiction=_S("x"))) == "FIRSTA1263:BAD_TYPE:jurisdiction"
    assert refusal(payload(as_of=_S("2026-01-01"))) == "FIRSTA1263:BAD_TYPE:as_of"
    assert refusal(payload(items=[item(speech=_S("political"))])) == "FIRSTA1263:BAD_TYPE:speech"
    assert refusal(payload(items=[item(source_ids=[_S("a1")])])) == "FIRSTA1263:BAD_TYPE:source_id"


def test_no_caller_key_echoed_in_any_refusal():
    secret = "SECRETKEY_zq9"
    for p in (dict(payload(), **{secret: 1}), payload(items=[item(**{secret: 1})]),
              payload(authorities=[dict(AUTH, **{secret: 1})])):
        m = refusal(p)
        assert m == "FIRSTA1263:UNKNOWN_KEY" and secret not in m
    big = {secret + str(i): 1 for i in range(fa.MAX_KEYS + 1)}
    assert secret not in refusal(big)
    assert secret not in refusal(payload(items=[item(speech=secret)]))


# ---- hard-hold gap pins ----
@pytest.mark.parametrize("ch", ["\u00ad", "\u2060", "\u200b", "\x00", "\x1f", "\x7f", "\x85", "\u2028", "\u2029"])
def test_source_id_unicode_screen_on_success_path(ch):
    a = dict(AUTH, id="a" + ch + "1")
    assert refusal(payload(items=[item(source_ids=["a" + ch + "1"])])) == "FIRSTA1263:CONTROL_CHARS:source_id"
    assert refusal(payload(items=[item(source_ids=["zz" + ch])])) == "FIRSTA1263:CONTROL_CHARS:source_id"


def test_every_cf_in_source_id_refused():
    for ch in _cf_all():
        assert refusal(payload(items=[item(source_ids=["a" + ch])])) == "FIRSTA1263:CONTROL_CHARS:source_id", hex(ord(ch))


def test_source_id_raw_cap_and_blank():
    assert refusal(payload(items=[item(source_ids=["x" * 257])])) == "FIRSTA1263:TEXT_TOO_LONG:source_id"
    assert refusal(payload(items=[item(source_ids=[" " * 300])])) == "FIRSTA1263:TEXT_TOO_LONG:source_id"
    assert refusal(payload(items=[item(source_ids=["  "])])) == "FIRSTA1263:EMPTY:source_id"
    assert fa.classify(payload(items=[item(source_ids=["x" * 256])]))["classified"][0]["missing_source_ids"] == ["x" * 256]
    assert fa.classify(payload(items=[item(source_ids=["a\u00a0b"])]))["classified"][0]["missing_source_ids"] == ["a\u00a0b"]


@pytest.mark.parametrize("field", ["speech", "speaker", "forum", "restriction", "scrutiny_declared"])
def test_enum_raw_cap_before_membership(field):
    assert refusal(payload(items=[item(**{field: "x" * 257})])) == "FIRSTA1263:TEXT_TOO_LONG:" + field
    assert refusal(payload(items=[item(**{field: "x" * 256})])) == "FIRSTA1263:UNKNOWN_VALUE:" + field
    assert refusal(payload(items=[item(**{field: ""})])) == "FIRSTA1263:UNKNOWN_VALUE:" + field


class _K(str):
    pass


@pytest.mark.parametrize("bad", [1, None, (1, 2), 1.5, b"k", _K("extra"), _K("decide")])
def test_non_str_keys_refused_before_guard_without_typeerror(bad):
    assert refusal({bad: 1}) == "FIRSTA1263:BAD_TYPE:key"
    if bad != "decide":  # a str subclass equal to "decide" would collide with the plain key
        assert refusal(dict(payload(), **{"decide": True}) | {bad: 1}) == "FIRSTA1263:BAD_TYPE:key"
    d = {bad: True}
    assert refusal(d) == "FIRSTA1263:BAD_TYPE:key"
    assert refusal(payload(items=[dict(item()) | {bad: 1}])) == "FIRSTA1263:BAD_TYPE:key"
    assert refusal(payload(authorities=[dict(AUTH) | {bad: 1}])) == "FIRSTA1263:BAD_TYPE:key"


def test_strict_str_on_all_remaining_values():
    assert refusal(payload(items=[item(i=_S("i1"))])) == "FIRSTA1263:BAD_TYPE:item_id"
    assert refusal(payload(authorities=[dict(AUTH, id=_S("a1"))])) == "FIRSTA1263:BAD_TYPE:authority_id"
    assert refusal(payload(authorities=[dict(AUTH, citation_text=_S("c"))])) == "FIRSTA1263:BAD_TYPE:citation_text"
    assert refusal(payload(authorities=[dict(AUTH, jurisdiction=_S("US-Federal"))])) == "FIRSTA1263:BAD_TYPE:jurisdiction"
    assert refusal(payload(authorities=[dict(AUTH, effective_date=_S("2020-01-01"))])) == "FIRSTA1263:BAD_TYPE:effective_date"
    for f in ("speaker", "forum", "restriction", "scrutiny_declared"):
        assert refusal(payload(items=[item(**{f: _S("unknown")})])) == "FIRSTA1263:BAD_TYPE:" + f


# ---- date gate: exact type str, THEN exact raw length 10, THEN format/calendar ----
@pytest.mark.parametrize("name,mk", [
    ("as_of", lambda v: payload(as_of=v)),
    ("effective_date", lambda v: payload(authorities=[dict(AUTH, effective_date=v)])),
])
class TestDateGate:
    def test_type_first(self, name, mk):
        for bad in (20260101, None, b"2026-01-01", _S("2026-01-01")):
            assert refusal(mk(bad)) == "FIRSTA1263:BAD_TYPE:" + name

    def test_exact_length_ten_before_format(self, name, mk):
        for bad in ("", " ", "2026-01-0", "2026-01-011", "x" * 9, "x" * 11, "x" * 257, "x" * 100000,
                    "2026-01-01" + "\u200b", "\u200b2026-01-0", "\x00" * 10 + "1", " " * 300):
            assert refusal(mk(bad)) == "FIRSTA1263:BAD_DATE:" + name, repr(bad[:12])

    def test_length_ten_then_format_then_calendar(self, name, mk):
        for bad in ("2026/01/01", "abcd-ef-gh", "2026-13-01", "2026-02-30", "2025-02-29", "0000-01-01", "2026-00-10", "2026-W01-1"):
            assert refusal(mk(bad)) == "FIRSTA1263:BAD_DATE:" + name, bad

    def test_ascii_digits_only(self, name, mk):
        assert refusal(mk("\u0662\u0660\u0662\u0666-01-01")) == "FIRSTA1263:BAD_DATE:" + name
        assert refusal(mk("2026-\uff10\uff11-01")) == "FIRSTA1263:BAD_DATE:" + name
        assert refusal(mk("2026-01-01\n")) == "FIRSTA1263:BAD_DATE:" + name

    def test_valid_dates_pass(self, name, mk):
        assert fa.classify(mk("2024-02-29"))["row"] == 1263
        assert fa.classify(mk("2026-12-31"))["row"] == 1263


def test_date_length_gate_runs_before_text_rules():
    assert fa._MAX_DATE == 10
    # previously TEXT_TOO_LONG / EMPTY / CONTROL_CHARS; now one code, disclosed in the contract
    assert refusal(payload(as_of="x" * 257)) == "FIRSTA1263:BAD_DATE:as_of"
    assert refusal(payload(as_of="")) == "FIRSTA1263:BAD_DATE:as_of"
    assert refusal(payload(as_of="2026-01-0\x00")) == "FIRSTA1263:BAD_DATE:as_of"


# ---- execution-order pins: regex and calendar parse never entered unless exact str of length 10 ----
import types


class _Spy:
    def __init__(self, real):
        self.real, self.args = real, []

    @property
    def calls(self):
        return len(self.args)

    def match(self, s):
        self.args.append(s)
        return self.real.match(s)


@pytest.mark.parametrize("name,mk", [
    ("as_of", lambda v: payload(as_of=v)),
    ("effective_date", lambda v: payload(authorities=[dict(AUTH, effective_date=v)])),
])
def test_regex_and_calendar_never_entered_off_length(monkeypatch, name, mk):
    spy = _Spy(fa._ISO)
    cal = {"n": 0, "args": []}

    def fromiso(s):
        cal["n"] += 1
        cal["args"].append(s)
        return date_cls.fromisoformat(s)
    import datetime
    date_cls = datetime.date
    monkeypatch.setattr(fa, "_ISO", spy)
    monkeypatch.setattr(fa, "date", types.SimpleNamespace(fromisoformat=fromiso))
    for bad in ("x" * 9, "x" * 11, "x" * 257, "x" * 100000, "2026-01-0", "2026-01-011", "", " "):
        assert refusal(mk(bad)) == "FIRSTA1263:BAD_DATE:" + name
    for bad in (20260101, None, b"2026-01-01", _S("2026-01-01")):
        assert refusal(mk(bad)) == "FIRSTA1263:BAD_TYPE:" + name
    # the other (valid) date in the payload may be parsed; no off-length or non-str value ever is
    sink = {"x" * 9, "x" * 11, "x" * 257, "x" * 100000, "2026-01-0", "2026-01-011", "", " "}
    assert not (set(map(str, spy.args)) & sink) and not (set(map(str, cal["args"])) & sink)
    assert all(len(a) == 10 for a in spy.args) and all(len(a) == 10 for a in cal["args"])
    base_s, base_c = spy.calls, cal["n"]
    base_args = list(spy.args)
    # positive control: an exact 10-char str enters both
    assert fa.classify(mk("2026-01-01"))["row"] == 1263
    assert spy.calls > base_s and cal["n"] > base_c
    # a 10-char str failing the shape stops at the regex, never reaching the calendar parse
    assert refusal(mk("2026/01/01")) == "FIRSTA1263:BAD_DATE:" + name
    assert "2026/01/01" in spy.args and "2026/01/01" not in cal["args"]
