"""U29 child: S9.1 gaps G1-G5 (packet fields, verbatim response record, tickets, evidence-not-approval, scope block)."""
import pytest

from app.modules.m20_general_cognitive_worker.quote_audit_u29 import (
    QuoteAuditError, audit_unit, build_external_packet, quote_sha256, record_response, tickets_from_gaps,
)

Q = "check whether it adds every essence of my word into working code"
UNIT = {"unit_id": "U", "quote": Q, "quote_sha256": quote_sha256(Q),
        "essences": [{"id": "e1", "fragment": "working code", "requires": [{"kind": "file", "path": "a.py"}]}]}
SRC = {"a.py": "def f():\n    return 1\n"}


def _packet(**kw):
    rep = audit_unit(UNIT, SRC)
    return build_external_packet(UNIT, rep, {"a.py": SRC["a.py"]}, ["claude", "deepseek"], sources=SRC, **kw)


def test_packet_carries_code_summary_tests_limits():
    p = _packet(code_summary="f returns 1", tests=["tests/test_a.py::test_f"], limits=["structural only"])
    pl = p["payload"]
    assert pl["code_summary"] == "f returns 1" and pl["tests"] == ["tests/test_a.py::test_f"] and pl["limits"] == ["structural only"]


def test_packet_fields_default_to_empty_not_absent():
    pl = _packet()["payload"]
    assert pl["code_summary"] == "" and pl["tests"] == [] and pl["limits"] == []


@pytest.mark.parametrize("kw", [{"code_summary": 5}, {"tests": "x"}, {"tests": [1]}, {"limits": [None]}, {"limits": "x"}])
def test_packet_field_types_refused(kw):
    with pytest.raises(QuoteAuditError, match="^U29: "):
        _packet(**kw)


def test_credential_in_code_summary_refused():
    with pytest.raises(QuoteAuditError, match="^U29: "):
        _packet(code_summary="api_key = 'abcdefgh1234'")


def test_changing_summary_changes_packet_hash():
    assert _packet(code_summary="a")["packet_sha256"] != _packet(code_summary="b")["packet_sha256"]


def test_record_response_is_verbatim_and_not_approval():
    p = _packet()
    text = "  Gaps:\n- no tests\n\nVerdict: partial  \n"
    r = record_response(p, "claude", text, as_of="2026-10-11")
    assert r["response_text"] == text
    assert r["provider"] == "claude" and r["packet_sha256"] == p["packet_sha256"]
    assert r["status"] == "evidence_not_approval" and r["approval"] is False
    assert len(r["response_sha256"]) == 64 and r["as_of"] == "2026-10-11"


def test_record_response_hash_follows_text():
    p = _packet()
    a = record_response(p, "claude", "x", as_of="d")
    b = record_response(p, "claude", "y", as_of="d")
    assert a["response_sha256"] != b["response_sha256"]


@pytest.mark.parametrize("prov,text,as_of", [("chatgpt", "x", "d"), ("nobody", "x", "d"), ("claude", "", "d"),
                                              ("claude", 5, "d"), ("claude", "x", ""), ("claude", "x", None)])
def test_record_response_refusals(prov, text, as_of):
    with pytest.raises(QuoteAuditError, match="^U29: "):
        record_response(_packet(), prov, text, as_of=as_of)


def test_record_response_refuses_tampered_packet():
    p = _packet()
    p["payload"]["quote"] = "changed"
    with pytest.raises(QuoteAuditError, match="^U29: "):
        record_response(p, "claude", "x", as_of="d")


def test_tickets_from_gaps_one_per_gap_open():
    p = _packet()
    r = record_response(p, "claude", "resp", as_of="d")
    t = tickets_from_gaps(r, ["no tests", "no limits"])
    assert [x["gap"] for x in t] == ["no tests", "no limits"]
    assert all(x["status"] == "open" and x["unit_id"] == "U" and x["provider"] == "claude" for x in t)
    assert all(x["source_response_sha256"] == r["response_sha256"] for x in t)
    assert len({x["ticket_id"] for x in t}) == 2
    assert t == tickets_from_gaps(r, ["no tests", "no limits"])


def test_tickets_empty_gap_list_is_empty():
    assert tickets_from_gaps(record_response(_packet(), "claude", "r", as_of="d"), []) == []


@pytest.mark.parametrize("gaps", ["x", [1], [""], ["a", "a"], None])
def test_tickets_bad_gaps_refused(gaps):
    with pytest.raises(QuoteAuditError, match="^U29: "):
        tickets_from_gaps(record_response(_packet(), "claude", "r", as_of="d"), gaps)


def test_tickets_refuse_non_response():
    with pytest.raises(QuoteAuditError, match="^U29: "):
        tickets_from_gaps({"response_text": "x"}, ["g"])


def test_scope_block_on_report():
    rep = audit_unit(UNIT, SRC, as_of="2026-10-11")
    s = rep["scope"]
    assert s["implemented"] == ["e1"] and s["not_implemented"] == []
    assert s["data_source"] == "caller-supplied sources and test results" and s["as_of"] == "2026-10-11"


def test_scope_block_lists_non_evidenced():
    u = dict(UNIT, essences=[{"id": "e1", "fragment": "working code", "requires": [{"kind": "file", "path": "zz.py"}]}])
    s = audit_unit(u, SRC)["scope"]
    assert s["implemented"] == [] and s["not_implemented"] == ["e1"] and s["as_of"] is None


def test_scope_as_of_must_be_string_or_none():
    with pytest.raises(QuoteAuditError, match="^U29: "):
        audit_unit(UNIT, SRC, as_of=5)


@pytest.mark.parametrize("kw", [{"tests": ["api_key = 'abcdefgh1234'"]}, {"limits": ["password = 'hunter2hunter2'"]}])
def test_credential_in_tests_or_limits_refused(kw):
    with pytest.raises(QuoteAuditError, match="^U29: "):
        _packet(**kw)


def test_tickets_refuse_response_without_evidence_status():
    r = record_response(_packet(), "claude", "r", as_of="d")
    r["status"] = "approved"
    with pytest.raises(QuoteAuditError, match="^U29: "):
        tickets_from_gaps(r, ["g"])


def test_same_gap_from_different_responses_gets_different_ticket_ids():
    p = _packet()
    a = tickets_from_gaps(record_response(p, "claude", "one", as_of="d"), ["g"])[0]
    b = tickets_from_gaps(record_response(p, "claude", "two", as_of="d"), ["g"])[0]
    assert a["ticket_id"] != b["ticket_id"]


@pytest.mark.parametrize("bad", [None, "x", 5, [], {}, {"payload": {}}, {"packet_sha256": "x"}])
def test_record_response_refuses_non_packets(bad):
    with pytest.raises(QuoteAuditError, match="^U29: "):
        record_response(bad, "claude", "x", as_of="d")
