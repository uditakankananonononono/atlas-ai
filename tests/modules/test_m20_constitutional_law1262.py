"""Row 1262 Constitutional Law: hermetic stdlib tests for caller-supplied bookkeeping."""
import tracemalloc
import unicodedata
import pytest
from backend.app.modules.m20_general_cognitive_worker import constitutional_law1262 as m

BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel must verify "
            "jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.")
BANNED = ("best better optimal optimum recommend rank winner winning robust improve superior "
          "ideal preferred highest select choose").split()
AUTH = {"id": "A1", "citation": "Example v. Example, 1 Ex. 1", "jurisdiction": "XX", "source_url": "https://example.org/a"}


def base(**kw):
    d = {"jurisdiction": "XX", "as_of": "2026-01-15", "authorities": [dict(AUTH)],
         "elements": [
             {"element": "state_action", "kind": "sourced_fact", "text": "Agency denied permit", "source_id": "A1"},
             {"element": "right", "kind": "assertion", "text": "Claimed speech right"},
             {"element": "scrutiny_level", "kind": "assertion", "text": "caller labels it strict"},
             {"element": "governmental_interest", "kind": "analysis", "text": "Stated safety interest"},
             {"element": "tailoring", "kind": "analysis", "text": "Caller notes narrow means"}]}
    d.update(kw)
    return d


def refused(data, code):
    with pytest.raises(m.ConstitutionalRefusal) as e:
        m.map_constitutional_scrutiny(data)
    assert str(e.value) == "CONSTI1262:" + code
    return e


def walk(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk(v)
    else:
        yield x


def test_happy_path_shape_and_no_conclusion():
    r = m.map_constitutional_scrutiny(base())
    assert r["status"] == "constitutional_bookkeeping_only"
    assert r["legal_conclusion"] is None and r["authority_independently_verified"] is False
    assert r["boundary"] == BOUNDARY and r["missing_elements"] == []
    assert r["elements"]["state_action"]["entries"][0]["kind"] == "sourced_fact"
    assert r["elements"]["state_action"]["entries"][0]["source_linked"] is True
    assert r["elements"]["right"]["entries"][0]["source_linked"] is False


def test_missing_elements_listed_in_fixed_order():
    d = base(elements=base()["elements"][:2])
    assert m.map_constitutional_scrutiny(d)["missing_elements"] == ["scrutiny_level", "governmental_interest", "tailoring"]


def test_output_has_no_banned_words_and_no_decision_words():
    r = m.map_constitutional_scrutiny(base())
    own = [w for w in walk(r) if isinstance(w, str) and w not in {e["text"] for e in base()["elements"]}]
    for s in own:
        for b in BANNED:
            assert b not in s.casefold(), (b, s)


def test_dates():
    refused(base(as_of="soon"), "DATE")
    refused(base(as_of="2026-1-5"), "DATE")
    refused(base(as_of="2026-02-30"), "DATE")
    refused(base(as_of=20260115), "TYPE")
    refused(base(as_of="\uff12026-01-15"), "DATE")  # non-ASCII digit
    assert m.map_constitutional_scrutiny(base(as_of="2026-02-28"))["as_of"] == "2026-02-28"


def test_type_and_shape_refusals():
    with pytest.raises(m.ConstitutionalRefusal) as e:
        m.map_constitutional_scrutiny([])
    assert str(e.value) == "CONSTI1262:SHAPE"
    refused(base(jurisdiction=5), "TYPE")
    refused(base(elements="x"), "SHAPE")
    refused(base(elements=[1]), "SHAPE")
    refused(base(authorities="x"), "SHAPE")
    refused(base(extra=1), "KEYS")
    refused(base(authorities=[]), "COUNT_MIN")
    refused(base(elements=[]), "COUNT_MIN")


def test_enums_and_source_rules():
    e = base(); e["elements"][0]["element"] = "verdict"; refused(e, "ENUM")
    e = base(); e["elements"][0]["kind"] = "ruling"; refused(e, "ENUM")
    e = base(); del e["elements"][0]["source_id"]; refused(e, "SOURCE_REQUIRED")
    e = base(); e["elements"][0]["source_id"] = "ZZ"; refused(e, "SOURCE_UNKNOWN")
    e = base(); e["elements"][1]["extra"] = 1; refused(e, "KEYS")
    e = base(authorities=[dict(AUTH), dict(AUTH)]); refused(e, "DUP")
    e = base(); e["authorities"][0]["jurisdiction"] = "YY"
    r = m.map_constitutional_scrutiny(e)
    assert r["jurisdiction_mismatch_source_ids"] == ["A1"]
    e = base(); del e["authorities"][0]["citation"]; refused(e, "KEYS")


def test_authority_url_scheme():
    e = base(); e["authorities"][0]["source_url"] = "file:///tmp/x"; refused(e, "URL")
    e = base(); e["authorities"][0]["source_url"] = "https://"; refused(e, "URL")


def test_counts_cap_before_parse():
    el = base()["elements"]
    refused(base(elements=el * 5), "COUNT_MAX")  # 25 > 20
    assert len(m.map_constitutional_scrutiny(base(elements=el * 4))["elements"]["right"]["entries"]) == 4
    # junk entries are never parsed once the count cap trips
    refused(base(elements=[object()] * (m.MAX_ITEMS + 1)), "COUNT_MAX")
    refused(base(authorities=[object()] * (m.MAX_ITEMS + 1)), "COUNT_MAX")


def test_text_cap_first_and_unicode():
    e = base(); e["elements"][1]["text"] = "a" * m.MAX_TEXT
    m.map_constitutional_scrutiny(e)
    e["elements"][1]["text"] = "a" * (m.MAX_TEXT + 1); refused(e, "TEXT_LONG")
    e["elements"][1]["text"] = " " * m.MAX_TEXT + "x"; refused(e, "TEXT_LONG")  # raw length, not stripped
    e["elements"][1]["text"] = "   "; refused(e, "TEXT_EMPTY")
    for ch in ["\x00", "\x7f", "\u2028", "\u2029", "\u200b", "\u200f", "\u202a", "\u202e", "\u2066", "\u2069", "\ufeff", "\n"]:
        e["elements"][1]["text"] = "ab" + ch + "cd"; refused(e, "TEXT_HIDDEN")
    refused(base(jurisdiction="X" * (m.MAX_TEXT + 1)), "TEXT_LONG")


def test_big_string_refused_without_allocation():
    big = "a" * (10 * 1024 * 1024)
    e = base(); e["elements"][1]["text"] = big
    tracemalloc.start()
    with pytest.raises(m.ConstitutionalRefusal):
        m.map_constitutional_scrutiny(e)
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert peak < 100000


def test_length_check_precedes_scan(monkeypatch):
    called = []
    monkeypatch.setattr(m, "_hidden", lambda s: called.append(s) or False)
    with pytest.raises(m.ConstitutionalRefusal):
        m._text("a" * (m.MAX_TEXT + 1), "f")
    assert called == []


def test_refusal_never_echoes_input():
    e = base(); e["elements"][0]["source_id"] = "SECRETVALUE"
    err = refused(e, "SOURCE_UNKNOWN")
    assert "SECRETVALUE" not in str(err.value)


def test_input_not_mutated_and_deterministic():
    d = base(); import copy; c = copy.deepcopy(d)
    r1 = m.map_constitutional_scrutiny(d); r2 = m.map_constitutional_scrutiny(d)
    assert d == c and r1 == r2


def test_boundary_and_scope_constants():
    assert m.BOUNDARY == BOUNDARY
    assert m.PREFIX == "CONSTI1262:"


def test_url_scheme_with_host_refused():
    for u in ("file://host/x", "ftp://host/x", "javascript://host/x"):
        e = base(); e["authorities"][0]["source_url"] = u; refused(e, "URL")


def test_cf_category_fully_refused_with_explicit_pins():
    for ch in ["\u00ad", "\u2060", "\u061c", "\u180e", "\u2061", "\u2064", "\u206a", "\u206f", "\ufff9", "\ufffb", "\U000e0001", "\U000e0020"]:
        assert unicodedata.category(ch) == "Cf" or ch == "\u180e", repr(ch)
        e = base(); e["elements"][1]["text"] = "ab" + ch + "cd"
        if unicodedata.category(ch) == "Cf":
            refused(e, "TEXT_HIDDEN")


def test_zs_accepted_and_no_surrogate_refusal_added():
    e = base(); e["elements"][1]["text"] = "a\u00a0b\u2003c"
    assert m.map_constitutional_scrutiny(e)["elements"]["right"]["entries"][0]["text"] == "a\u00a0b\u2003c"
    e["elements"][1]["text"] = "a\ud800b"  # Cs: disclosed residual, no new refusal
    m.map_constitutional_scrutiny(e)


class _D(dict):
    pass


class _L(list):
    pass


class _S(str):
    pass


def test_key_count_before_set_construction(monkeypatch):
    import builtins
    calls = []
    monkeypatch.setattr(m, "set", lambda *a: calls.append(len(a[0]) if a else 0) or builtins.set(*a), raising=False)
    refused({str(i): 1 for i in range(m.MAX_KEYS + 1)}, "COUNT_MAX")
    e = base(); e["authorities"] = [{str(i): 1 for i in range(m.MAX_KEYS + 1)}]; refused(e, "COUNT_MAX")
    e = base(); e["elements"] = [{str(i): 1 for i in range(m.MAX_KEYS + 1)}]; refused(e, "COUNT_MAX")
    # no set was ever built over an over-cap container
    assert all(n <= m.MAX_KEYS for n in calls) and m.MAX_KEYS == 64


def test_strict_builtin_types_subclasses_refused():
    refused(_D(base()), "SHAPE")
    e = base(); e["authorities"] = [_D(AUTH)]; refused(e, "SHAPE")
    e = base(); e["elements"] = [_D(base()["elements"][0])]; refused(e, "SHAPE")
    refused(base(elements=_L(base()["elements"])), "SHAPE")
    refused(base(authorities=_L([dict(AUTH)])), "SHAPE")
    refused(base(jurisdiction=_S("XX")), "TYPE")
    e = base(); e["elements"][1]["text"] = _S("ok"); refused(e, "TYPE")
    e = base(); e["elements"][1]["kind"] = _S("assertion"); refused(e, "TYPE")


def test_edge_control_and_separator_not_stripped_away():
    for ch in ["\n", "\t", "\x85", "\u2028", "\u2029", "\r", "\x0b", "\x0c"]:
        for pat in (ch + "ok", "ok" + ch):
            e = base(); e["elements"][1]["text"] = pat; refused(e, "TEXT_HIDDEN")
            e = base(); e["jurisdiction"] = pat; refused(e, "TEXT_HIDDEN")
    e = base(); e["elements"][1]["text"] = "  ok  "  # Zs edge spaces still trimmed
    assert m.map_constitutional_scrutiny(e)["elements"]["right"]["entries"][0]["text"] == "ok"


def test_screen_runs_on_raw_after_cap_before_strip(monkeypatch):
    seen = []
    real = m._hidden
    monkeypatch.setattr(m, "_hidden", lambda s: seen.append(s) or real(s))
    m._text("  ab  ", "f")
    assert seen == ["  ab  "]


def test_date_exact_raw_length_ten_first(monkeypatch):
    for bad in (" 2026-01-15", "2026-01-15 ", "2026-01-15\n", "2026-01-1", "x" * 11):
        refused(base(as_of=bad), "DATE")
    seen = []
    monkeypatch.setattr(m, "_DATE", type("R", (), {"fullmatch": staticmethod(lambda s: seen.append(s) or None)})())
    refused(base(as_of="a" * 11), "DATE")
    assert seen == []  # regex never reached for wrong raw length
    monkeypatch.undo()
    big = "2" * (10 * 1024 * 1024)
    tracemalloc.start()
    with pytest.raises(m.ConstitutionalRefusal):
        m.map_constitutional_scrutiny(base(as_of=big))
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert peak < 100000


def test_dict_keys_strict_str_after_count_before_allowlist():
    class K(str):
        pass
    d = base(); d[1] = 1; refused(d, "KEYS")
    d = base(); d[K("extra")] = 1; refused(d, "KEYS")
    e = base(); e["authorities"][0][2] = "x"; refused(e, "KEYS")
    e = base(); e["elements"][0][None] = "x"; refused(e, "KEYS")
    # count is still first: over-cap dict with a non-str key reports COUNT_MAX
    big = {i: 1 for i in range(m.MAX_KEYS + 1)}
    refused(big, "COUNT_MAX")


def test_nonstr_key_refused_before_any_set_construction(monkeypatch):
    import builtins
    calls = []
    monkeypatch.setattr(m, "set", lambda *a: calls.append(a) or builtins.set(*a), raising=False)
    refused({1: 1, "jurisdiction": "XX"}, "KEYS")
    assert calls == []


def test_str_subclass_key_with_allowed_name_refused():
    class K(str):
        pass
    d = base(); d[K("jurisdiction")] = d.pop("jurisdiction"); refused(d, "KEYS")
    e = base(); a = e["authorities"][0]; a[K("id")] = a.pop("id"); refused(e, "KEYS")
    e = base(); el = e["elements"][0]; el[K("text")] = el.pop("text"); refused(e, "KEYS")


# ---- closing pins (boundaries, week-date refusal, http scheme, exact output shape)

def test_max_text_500_accepted_501_refused():
    assert m.map_constitutional_scrutiny(base(jurisdiction="x" * 500))["jurisdiction"] == "x" * 500
    refused(base(jurisdiction="x" * 501), "TEXT_LONG")


def test_max_items_20_accepted_21_refused_authorities_and_elements():
    auths = []
    for i in range(20):
        a = dict(AUTH)
        a["id"] = f"A{i}"
        auths.append(a)
    assert len(m.map_constitutional_scrutiny(base(authorities=auths))["authorities"]) == 20
    a21 = dict(AUTH)
    a21["id"] = "A20"
    refused(base(authorities=auths + [a21]), "COUNT_MAX")
    elems = [dict(e) for e in base()["elements"]] * 4
    assert len(elems) == 20
    r = m.map_constitutional_scrutiny(base(elements=elems))
    assert sum(g["count"] for g in r["elements"].values()) == 20
    refused(base(elements=elems + [dict(elems[0])]), "COUNT_MAX")


def test_key_count_boundary_64_refuses_keys_65_refuses_count_max():
    d = base()
    for i in range(60):
        d[f"extra{i}"] = "x"
    assert len(d) == 64
    refused(d, "KEYS")
    d["extra60"] = "x"
    assert len(d) == 65
    refused(d, "COUNT_MAX")


def test_iso_week_date_refused():
    # valid fromisoformat week date on 3.12, exact length 10: the one input that
    # separates the length-10 + fullmatch gate from a plain fromisoformat call
    refused(base(as_of="2026-W01-1"), "DATE")


def test_http_scheme_source_url_accepted():
    a = dict(AUTH)
    a["source_url"] = "http://e.com/x"
    r = m.map_constitutional_scrutiny(base(authorities=[a]))
    assert r["authorities"][0]["source_url"] == "http://e.com/x"


def test_minimal_request_full_output_exact():
    d = {"jurisdiction": "  Example State  ", "as_of": "2026-01-02",
         "authorities": [{"id": "A1", "citation": "Example v. Sample, 1 Ex. 1",
                          "jurisdiction": "Example State", "source_url": "http://e.com/x"}],
         "elements": [
             {"element": "right", "kind": "sourced_fact", "text": "Permit denial recorded",
              "source_id": "A1"},
             {"element": "state_action", "kind": "assertion", "text": "Agency acted"}]}
    r = m.map_constitutional_scrutiny(d)
    assert r == {
        "status": "constitutional_bookkeeping_only",
        "jurisdiction": "Example State",
        "as_of": "2026-01-02",
        "elements": {
            "state_action": {"count": 1, "entries": [
                {"kind": "assertion", "text": "Agency acted",
                 "source_id": None, "source_linked": False}]},
            "right": {"count": 1, "entries": [
                {"kind": "sourced_fact", "text": "Permit denial recorded",
                 "source_id": "A1", "source_linked": True}]},
            "scrutiny_level": {"count": 0, "entries": []},
            "governmental_interest": {"count": 0, "entries": []},
            "tailoring": {"count": 0, "entries": []}},
        "missing_elements": ["scrutiny_level", "governmental_interest", "tailoring"],
        "jurisdiction_mismatch_source_ids": [],
        "authorities": [{"id": "A1", "citation": "Example v. Sample, 1 Ex. 1",
                         "jurisdiction": "Example State", "source_url": "http://e.com/x"}],
        "legal_conclusion": None,
        "authority_independently_verified": False,
        "filing_or_external_effect": False,
        "boundary": BOUNDARY,
    }
