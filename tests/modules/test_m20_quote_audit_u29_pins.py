"""U29 repair pins (tests only, core unchanged): exact refusals and exact coverage the peer audit found unpinned."""
import pytest

from app.modules.m20_general_cognitive_worker.quote_audit_u29 import (
    QuoteAuditError, audit_unit, build_external_packet, quote_sha256, record_response, tickets_from_gaps,
)


def _unit(quote="abc def", essences=None, sha=None):
    return {"unit_id": "U", "quote": quote, "quote_sha256": sha if sha is not None else quote_sha256(quote) if isinstance(quote, str) else "x",
            "essences": essences if essences is not None else [{"id": "e1", "fragment": "abc", "requires": [{"kind": "file", "path": "a.py"}]}]}


def test_empty_quote_with_matching_sha_refused():
    with pytest.raises(QuoteAuditError, match="quote must be a non-empty string"):
        audit_unit(_unit(quote="", essences=[{"id": "e", "fragment": "x", "requires": []}]), {})


@pytest.mark.parametrize("q", [5, None, ["abc"], b"abc"])
def test_non_string_quote_refused_cleanly(q):
    with pytest.raises(QuoteAuditError, match="quote must be a non-empty string"):
        audit_unit(_unit(quote=q, sha=quote_sha256("abc")), {})


@pytest.mark.parametrize("eid", ["", 5, None])
def test_empty_or_non_string_essence_id_refused(eid):
    u = _unit(essences=[{"id": eid, "fragment": "abc", "requires": []}])
    with pytest.raises(QuoteAuditError, match="non-empty string id"):
        audit_unit(u, {})


@pytest.mark.parametrize("frag", ["", 5, None])
def test_empty_or_non_string_fragment_refused(frag):
    u = _unit(essences=[{"id": "e1", "fragment": frag, "requires": []}])
    with pytest.raises(QuoteAuditError, match="fragment is not an exact substring"):
        audit_unit(u, {})


@pytest.mark.parametrize("check", [
    {"kind": "file", "path": ""}, {"kind": "file", "path": 5}, {"kind": "file"},
    {"kind": "symbol", "path": "a.py", "name": ""}, {"kind": "symbol", "path": "a.py", "name": 5},
    {"kind": "test", "path": "a.py", "name": ""}, {"kind": "text", "path": "a.py", "contains": ""},
    {"kind": "text", "path": "a.py", "contains": 5}])
def test_empty_or_non_string_check_field_refused(check):
    u = _unit(essences=[{"id": "e1", "fragment": "abc", "requires": [check]}])
    with pytest.raises(QuoteAuditError, match="requires '"):
        audit_unit(u, {"a.py": "x = 1\n"})


def test_overlapping_fragment_occurrences_cover_exactly():
    q = "aaa"
    u = _unit(quote=q, essences=[{"id": "e1", "fragment": "aa", "requires": [{"kind": "file", "path": "a.py"}]}])
    rep = audit_unit(u, {"a.py": ""})
    assert rep["unmapped_quote_words"] == []


def test_non_overlapping_gap_still_reported_unmapped():
    q = "aaa b"
    u = _unit(quote=q, essences=[{"id": "e1", "fragment": "aa", "requires": [{"kind": "file", "path": "a.py"}]}])
    assert audit_unit(u, {"a.py": ""})["unmapped_quote_words"] == ["b"]


_SRC = {"a.py": "x = 1\n"}


def _build(excerpts, sources):
    u = _unit()
    rep = audit_unit(u, _SRC)
    return build_external_packet(u, rep, excerpts, ["claude"], sources=sources)


@pytest.mark.parametrize("bad", [None, [], "x", 5, [("a.py", "x")]])
def test_non_dict_excerpts_refused_cleanly_with_valid_sources(bad):
    with pytest.raises(QuoteAuditError, match="excerpts and sources must be objects"):
        _build(bad, _SRC)


@pytest.mark.parametrize("bad", [None, [], "x", 5, [("a.py", "x")]])
def test_non_dict_sources_refused_cleanly_with_valid_excerpts(bad):
    with pytest.raises(QuoteAuditError, match="excerpts and sources must be objects"):
        _build({"a.py": "x = 1"}, bad)


def test_ticket_id_is_exactly_16_lowercase_hex():
    p = _build({"a.py": "x = 1"}, _SRC)
    r = record_response(p, "claude", "resp", as_of="d")
    tid = tickets_from_gaps(r, ["g"])[0]["ticket_id"]
    assert len(tid) == 16 and all(c in "0123456789abcdef" for c in tid)
