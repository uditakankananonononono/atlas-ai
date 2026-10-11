"""Row 1272 Treaties: hermetic stdlib tests (test-first; RED before the module existed)."""
import copy
import importlib.util
import pathlib
import pytest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/treaties1272.py"
_spec = importlib.util.spec_from_file_location("treaties1272", _P)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

AUTH = {"id": "a1", "citation_text": "Supplied citation text", "jurisdiction": "Declared-Jurisdiction",
        "effective_date": "2020-01-01"}
FIELDS = ['signature', 'ratification', 'reservation', 'entry_into_force', 'domestic_effect']


def item(i="i1", **kw):
    d = {"id": i, "signature": "signed", "ratification": "ratified", "reservation": "none", "entry_into_force": "in_force", "domestic_effect": "directly_applicable",  "source_ids": ["a1"]}
    d.update(kw)
    return d


def payload(**kw):
    d = {"jurisdiction": "Declared-Jurisdiction", "as_of": "2026-01-01",
         "authorities": [dict(AUTH)], "items": [item()]}
    d.update(kw)
    return d


def refusal(p):
    with pytest.raises(ValueError) as e:
        m.organize(p)
    return str(e.value)


def test_golden_output_and_never_decides():
    r = m.organize(payload())
    assert r["row"] == 1272 and r["status"] == "caller_declared_treaties_bookkeeping_only"
    assert r["treaty_status_decided"] is False and r["legal_conclusion"] is None
    assert r["filing_or_external_effect"] is False and r["authorities_independently_verified"] is False
    assert r["requires_licensed_counsel"] is True and r["review_state"] == "counsel_review_required"
    assert r["disclaimer"] == m.BOUNDARY
    c = r["classified"][0]
    assert c["id"] == "i1" and c["unclassified_fields"] == [] and c["missing_source_ids"] == []
    assert r["counts"] == {"items": 1, "unclassified": 0, "blocked_items": 0}
    assert set(r) == {"row", "status", "jurisdiction", "as_of", "classified", "authority_flags", "counts",
                      "review_state", "treaty_status_decided", "legal_conclusion", "filing_or_external_effect",
                      "authorities_independently_verified", "requires_licensed_counsel", "disclaimer"}


def test_full_classified_dict():
    c = m.organize(payload())["classified"][0]
    assert c == {'id': 'i1', 'signature': 'signed', 'ratification': 'ratified', 'reservation': 'none', 'entry_into_force': 'in_force', 'domestic_effect': 'directly_applicable', 'unclassified_fields': [], 'missing_source_ids': []}


def test_boundary_text_verbatim():
    assert m.BOUNDARY == ("Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, "
                          "currency, citations, facts, duties, deadlines and strategy before use.")


def test_vocab_tables_pinned_exactly():
    assert m.VOCAB == {
        "signature": ("signed", "not_signed", "accession", "succession", "unknown"),
        "ratification": ("ratified", "accepted", "approved", "not_ratified", "unknown"),
        "reservation": ("none", "declared_reservation", "declared_understanding", "objection_received", "unknown"),
        "entry_into_force": ("in_force", "not_in_force", "provisional_application", "disputed", "unknown"),
        "domestic_effect": ("directly_applicable", "implementing_legislation", "not_implemented", "disputed", "unknown"),
    }


@pytest.mark.parametrize("field", FIELDS)
def test_every_vocab_value_accepted_and_echoed(field):
    for v in m.VOCAB[field]:
        c = m.organize(payload(items=[item(**{field: v})]))["classified"][0]
        assert c[field] == v


def test_unknown_values_listed_as_unclassified():
    kw = {f: "unknown" for f in FIELDS}
    r = m.organize(payload(items=[item(**kw)]))
    c = r["classified"][0]
    assert c["unclassified_fields"] == FIELDS
    assert r["counts"]["unclassified"] == 1 and r["review_state"] == "blocked"
    assert r["treaty_status_decided"] is False


def test_missing_source_id_blocks():
    r = m.organize(payload(items=[item(source_ids=["a1", "zz"])]))
    assert r["classified"][0]["missing_source_ids"] == ["zz"] and r["review_state"] == "blocked"


def test_jurisdiction_mismatch_and_post_as_of_flagged_not_decided():
    a = dict(AUTH, jurisdiction="Other-Jurisdiction", effective_date="2027-01-01")
    r = m.organize(payload(authorities=[a]))
    assert r["authority_flags"] == [{"id": "a1", "jurisdiction_mismatch": True, "effective_after_as_of": True,
                                     "independently_verified": False}]
    assert r["review_state"] == "blocked" and r["treaty_status_decided"] is False


def test_effective_on_as_of_is_not_flagged():
    r = m.organize(payload(authorities=[dict(AUTH, effective_date="2026-01-01")]))
    assert r["authority_flags"][0]["effective_after_as_of"] is False


def test_input_not_mutated_and_deterministic():
    p = payload(); q = copy.deepcopy(p)
    assert m.organize(p) == m.organize(p) and p == q


@pytest.mark.parametrize("bad,code", [(None, "BAD_TYPE:payload"), ([], "BAD_TYPE:payload")])
def test_payload_type(bad, code):
    assert refusal(bad) == "TREAT1272:" + code


@pytest.mark.parametrize("key", ["jurisdiction", "as_of", "authorities", "items"])
def test_missing_required_key(key):
    p = payload(); del p[key]
    assert refusal(p) == "TREAT1272:MISSING:" + key


def test_unknown_top_level_key():
    assert refusal(payload(extra=1)) == "TREAT1272:UNKNOWN_KEY"


@pytest.mark.parametrize("key,code", [("decide", "CONCLUSION_REFUSED"), ("constitutional", "CONCLUSION_REFUSED"),
                                      ("conclusion", "CONCLUSION_REFUSED"), ("file", "EXTERNAL_EFFECT_REFUSED"),
                                      ("serve", "EXTERNAL_EFFECT_REFUSED"), ("contact", "EXTERNAL_EFFECT_REFUSED"),
                                      ("send", "EXTERNAL_EFFECT_REFUSED"), ("spend", "EXTERNAL_EFFECT_REFUSED")])
def test_conclusion_and_effect_keys_refused_first(key, code):
    p = payload(); p[key] = True
    assert refusal(p) == "TREAT1272:" + code
    p[key] = False
    assert refusal(p) == "TREAT1272:UNKNOWN_KEY"


@pytest.mark.parametrize("val,code", [(5, "BAD_TYPE"), ("", "EMPTY"), ("  ", "EMPTY"),
                                      ("a\x00b", "CONTROL_CHARS"), ("x" * 257, "TEXT_TOO_LONG")])
def test_text_rules(val, code):
    assert refusal(payload(jurisdiction=val)) == "TREAT1272:%s:jurisdiction" % code


def test_text_length_boundary_accepts_256():
    j = "x" * 256
    assert m.organize(payload(jurisdiction=j, authorities=[dict(AUTH, jurisdiction=j)]))


@pytest.mark.parametrize("val", ["2026-13-01", "2026/01/01", "x", "2026-1-1", "20260101"])
def test_as_of_must_be_iso(val):
    assert refusal(payload(as_of=val)) == "TREAT1272:BAD_DATE:as_of"


def test_authority_date_must_be_iso():
    assert refusal(payload(authorities=[dict(AUTH, effective_date="nope")])) == "TREAT1272:BAD_DATE:effective_date"
    assert refusal(payload(authorities=[dict(AUTH, effective_date=20200101)])) == "TREAT1272:BAD_TYPE:effective_date"


def test_authorities_required_nonempty_and_caps():
    assert refusal(payload(authorities=[])) == "TREAT1272:EMPTY:authorities"
    assert refusal(payload(authorities="x")) == "TREAT1272:BAD_TYPE:authorities"
    many = [dict(AUTH, id="a%d" % i) for i in range(32)]
    assert m.organize(payload(authorities=many, items=[item(source_ids=["a0"])]))
    assert refusal(payload(authorities=many + [dict(AUTH, id="a32")])) == "TREAT1272:TOO_MANY:authorities"


def test_items_cap_and_empty():
    ok = [item("i%d" % i) for i in range(16)]
    assert m.organize(payload(items=ok))["counts"]["items"] == 16
    assert refusal(payload(items=ok + [item("i16")])) == "TREAT1272:TOO_MANY:items"
    assert refusal(payload(items=[])) == "TREAT1272:EMPTY:items"
    assert refusal(payload(items="x")) == "TREAT1272:BAD_TYPE:items"


def test_source_ids_cap():
    ids = ["a1"] * 8
    assert m.organize(payload(items=[item(source_ids=ids)]))
    assert refusal(payload(items=[item(source_ids=ids + ["a1"])])) == "TREAT1272:TOO_MANY:source_ids"
    assert refusal(payload(items=[item(source_ids=[])])) == "TREAT1272:EMPTY:source_ids"
    assert refusal(payload(items=[item(source_ids=[3])])) == "TREAT1272:BAD_TYPE:source_id"


def test_duplicate_ids():
    assert refusal(payload(items=[item("i1"), item("i1")])) == "TREAT1272:DUPLICATE:item_id"
    assert refusal(payload(authorities=[dict(AUTH), dict(AUTH)])) == "TREAT1272:DUPLICATE:authority_id"


@pytest.mark.parametrize("field", FIELDS)
def test_vocabulary_enforced(field):
    assert refusal(payload(items=[item(**{field: "made_up"})])) == "TREAT1272:UNKNOWN_VALUE:" + field
    assert refusal(payload(items=[item(**{field: 3})])) == "TREAT1272:BAD_TYPE:" + field
    assert refusal(payload(items=[item(**{field: "x" * 257})])) == "TREAT1272:TEXT_TOO_LONG:" + field


@pytest.mark.parametrize("field", FIELDS + ["source_ids", "id"])
def test_item_required_fields(field):
    it = item(); del it[field]
    assert refusal(payload(items=[it])) == "TREAT1272:MISSING:" + field


def test_item_and_authority_shape():
    assert refusal(payload(items=["x"])) == "TREAT1272:BAD_TYPE:item"
    assert refusal(payload(authorities=["x"])) == "TREAT1272:BAD_TYPE:authority"
    assert refusal(payload(items=[item(zzz=1)])) == "TREAT1272:UNKNOWN_KEY"
    assert refusal(payload(authorities=[dict(AUTH, zzz=1)])) == "TREAT1272:UNKNOWN_KEY"
    a = dict(AUTH); del a["citation_text"]
    assert refusal(payload(authorities=[a])) == "TREAT1272:MISSING:citation_text"


def test_item_conclusion_key_refused():
    assert refusal(payload(items=[item(constitutional=True)])) == "TREAT1272:CONCLUSION_REFUSED"
    assert refusal(payload(items=[item(decide="yes")])) == "TREAT1272:CONCLUSION_REFUSED"


def test_constants_pinned():
    assert (m.MAX_ITEMS, m.MAX_AUTHORITIES, m.MAX_SOURCE_IDS, m.MAX_TEXT, m.MAX_KEYS) == (16, 32, 8, 256, 16)
    assert m.PREFIX == "TREAT1272"


def test_output_has_no_verdict_words():
    s = repr(m.organize(payload())).lower()
    for w in ('treaty is void', 'validly terminated', 'breached the treaty'):
        assert w not in s


def test_key_count_cap():
    big = {"k%d" % i: 1 for i in range(m.MAX_KEYS + 1)}
    assert refusal(big) == "TREAT1272:TOO_MANY:keys"
    assert refusal(payload(items=[dict(big)])) == "TREAT1272:TOO_MANY:keys"
    ok = dict(payload()); ok.update({"x%d" % i: 0 for i in range(m.MAX_KEYS - 4)})
    assert refusal(ok) == "TREAT1272:UNKNOWN_KEY"


def test_list_len_cap_before_item_work():
    assert refusal(payload(items=[1] * 17)) == "TREAT1272:TOO_MANY:items"
    assert refusal(payload(authorities=[1] * 33)) == "TREAT1272:TOO_MANY:authorities"
    assert refusal(payload(items=[item(source_ids=["a"] * 9)])) == "TREAT1272:TOO_MANY:source_ids"


class _D(dict):
    pass


class _L(list):
    pass


class _S(str):
    pass


def test_strict_builtin_types():
    assert refusal(_D(payload())) == "TREAT1272:BAD_TYPE:payload"
    assert refusal(payload(items=[_D(item())])) == "TREAT1272:BAD_TYPE:item"
    assert refusal(payload(authorities=[_D(AUTH)])) == "TREAT1272:BAD_TYPE:authority"
    assert refusal(payload(items=_L([item()]))) == "TREAT1272:BAD_TYPE:items"
    assert refusal(payload(jurisdiction=_S("x"))) == "TREAT1272:BAD_TYPE:jurisdiction"
    assert refusal(payload(items=[item(**{FIELDS[0]: _S(m.VOCAB[FIELDS[0]][0])})])) == "TREAT1272:BAD_TYPE:" + FIELDS[0]
    assert refusal(payload(items=[item(source_ids=[_S("a1")])])) == "TREAT1272:BAD_TYPE:source_id"
    assert refusal(payload(as_of=_S("2026-01-01"))) == "TREAT1272:BAD_TYPE:as_of"


def test_no_caller_key_echoed_in_any_refusal():
    secret = "SECRETKEY_zq9"
    for p in (dict(payload(), **{secret: 1}), payload(items=[item(**{secret: 1})]),
              payload(authorities=[dict(AUTH, **{secret: 1})])):
        msg = refusal(p)
        assert msg == "TREAT1272:UNKNOWN_KEY" and secret not in msg
    assert secret not in refusal(payload(items=[item(**{FIELDS[0]: secret})]))


@pytest.mark.parametrize("ch", ["\u00ad", "\u2060", "\u200b", "\x00", "\x1f", "\x7f", "\x85", "\u2028", "\u2029"])
def test_control_and_format_chars_refused(ch):
    assert refusal(payload(jurisdiction="a" + ch + "b")) == "TREAT1272:CONTROL_CHARS:jurisdiction"
    assert refusal(payload(items=[item(source_ids=["a" + ch])])) == "TREAT1272:CONTROL_CHARS:source_id"


@pytest.mark.parametrize("ch", ["\u00a0", "\u2003", "\u3000", " "])
def test_zs_accepted_inside_text(ch):
    j = "a" + ch + "b"
    assert m.organize(payload(jurisdiction=j, authorities=[dict(AUTH, jurisdiction=j)]))["jurisdiction"] == j


def test_surrogate_not_newly_refused_disclosed_residual():
    j = "a\ud800b"
    assert m.organize(payload(jurisdiction=j, authorities=[dict(AUTH, jurisdiction=j)]))["jurisdiction"] == j


def test_raw_length_cap_before_strip_and_unicode():
    assert refusal(payload(jurisdiction=" " * 257)) == "TREAT1272:TEXT_TOO_LONG:jurisdiction"
    assert refusal(payload(jurisdiction="\u200b" * 257)) == "TREAT1272:TEXT_TOO_LONG:jurisdiction"
    assert refusal(payload(jurisdiction=" " * 256)) == "TREAT1272:EMPTY:jurisdiction"


def test_date_gate_order():
    assert m._MAX_DATE == 10
    assert refusal(payload(as_of="x" * 257)) == "TREAT1272:BAD_DATE:as_of"
    assert refusal(payload(as_of="")) == "TREAT1272:BAD_DATE:as_of"
    assert refusal(payload(as_of="\u0662\u0660\u0662\u0666-01-01")) == "TREAT1272:BAD_DATE:as_of"


def test_non_str_keys_refused_before_guard():
    assert refusal({1: True}) == "TREAT1272:BAD_TYPE:key"
    assert refusal({"decide": True, 1: 0}) == "TREAT1272:BAD_TYPE:key"
    assert refusal(payload(items=[dict(item()) | {1: 0}])) == "TREAT1272:BAD_TYPE:key"

@pytest.mark.parametrize("field,mk", [
    ("as_of", lambda v: payload(as_of=v)),
    ("effective_date", lambda v: payload(authorities=[dict(AUTH, effective_date=v)])),
])
def test_week_date_form_refused_bad_date(field, mk):
    # ISO regex gap pin: a 10-char week-date shape never reaches the calendar parse
    assert refusal(mk("2026-W01-1")) == "TREAT1272:BAD_DATE:" + field


def test_jurisdiction_compare_case_variant_still_flags():
    a = dict(AUTH, jurisdiction="declared-jurisdiction")
    r = m.organize(payload(authorities=[a]))
    assert r["authority_flags"][0]["jurisdiction_mismatch"] is True
    assert r["review_state"] == "blocked"


@pytest.mark.parametrize("field", FIELDS)
def test_padded_vocab_value_is_unknown_value(field):
    padded = " " + m.VOCAB[field][0]
    assert refusal(payload(items=[item(**{field: padded})])) == "TREAT1272:UNKNOWN_VALUE:" + field


def test_duplicate_missing_source_ids_deduped_once_in_order():
    r = m.organize(payload(items=[item(source_ids=["zz", "zz", "yy", "zz"])]))
    assert r["classified"][0]["missing_source_ids"] == ["zz", "yy"]
    assert r["review_state"] == "blocked"


def test_review_state_blocked_by_jurisdiction_mismatch_alone():
    r = m.organize(payload(authorities=[dict(AUTH, jurisdiction="Other-Jurisdiction")]))
    assert r["authority_flags"][0] == {"id": "a1", "jurisdiction_mismatch": True,
                                       "effective_after_as_of": False, "independently_verified": False}
    assert r["review_state"] == "blocked"


def test_review_state_blocked_by_effective_after_as_of_alone():
    r = m.organize(payload(authorities=[dict(AUTH, effective_date="2027-01-01")]))
    assert r["authority_flags"][0] == {"id": "a1", "jurisdiction_mismatch": False,
                                       "effective_after_as_of": True, "independently_verified": False}
    assert r["review_state"] == "blocked"


@pytest.mark.parametrize("field,mk", [
    ("citation_text", lambda v: payload(authorities=[dict(AUTH, citation_text=v)])),
    ("jurisdiction", lambda v: payload(authorities=[dict(AUTH, jurisdiction=v)])),
    ("authority_id", lambda v: payload(authorities=[dict(AUTH, id=v)])),
    ("item_id", lambda v: payload(items=[item(i=v)])),
])
@pytest.mark.parametrize("val,code", [("", "EMPTY"), ("  ", "EMPTY"), ("x" * 257, "TEXT_TOO_LONG"),
                                      ("a\x00b", "CONTROL_CHARS"), (5, "BAD_TYPE"), ([1], "BAD_TYPE")])
def test_named_text_fields_refuse(field, mk, val, code):
    assert refusal(mk(val)) == "TREAT1272:%s:%s" % (code, field)
