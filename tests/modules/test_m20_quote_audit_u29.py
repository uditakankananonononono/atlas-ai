"""U29: local quote-vs-code audit harness and external-review hooks (nothing is ever sent).

Units, quotes and sources here are invented for the tests.
"""
import copy
import hashlib

import pytest

from app.modules.m20_general_cognitive_worker.quote_audit_u29 import (
    PROVIDERS,
    QuoteAuditError,
    audit_unit,
    build_external_packet,
    quote_sha256,
    release_packet,
)

QUOTE = "Build a pitch writer that sends nothing without my approval"
SOURCES = {
    "pkg/pitch.py": "class PitchWriter:\n    def draft(self):\n        return 'x'\n\ndef require_approval():\n    return True\n",
    "tests/test_pitch.py": "def test_draft_is_text():\n    pass\n\ndef test_nothing_is_sent():\n    pass\n",
}
UNIT = {
    "unit_id": "T01",
    "quote": QUOTE,
    "quote_sha256": hashlib.sha256(QUOTE.encode()).hexdigest(),
    "essences": [
        {"id": "e1", "fragment": "pitch writer", "requires": [
            {"kind": "file", "path": "pkg/pitch.py"},
            {"kind": "symbol", "path": "pkg/pitch.py", "name": "PitchWriter"},
            {"kind": "test", "path": "tests/test_pitch.py", "name": "test_draft_is_text"}]},
        {"id": "e2", "fragment": "sends nothing without my approval", "requires": [
            {"kind": "symbol", "path": "pkg/pitch.py", "name": "require_approval"},
            {"kind": "test", "path": "tests/test_pitch.py", "name": "test_nothing_is_sent"},
            {"kind": "text", "path": "pkg/pitch.py", "contains": "return True"}]},
    ],
}
RESULTS = {"tests/test_pitch.py::test_draft_is_text": "passed", "tests/test_pitch.py::test_nothing_is_sent": "passed"}


def unit(**over):
    u = copy.deepcopy(UNIT)
    u.update(over)
    return u


def refusal(fn, *a, **kw):
    with pytest.raises(QuoteAuditError) as ei:
        fn(*a, **kw)
    assert str(ei.value).startswith("U29: ")
    return str(ei.value)


# --- audit ---------------------------------------------------------------------------------------------
def test_fully_evidenced_unit_reports_each_essence_as_evidenced_with_exact_fields():
    r = audit_unit(UNIT, SOURCES, RESULTS)
    assert r["unit_id"] == "T01" and r["quote_sha256"] == UNIT["quote_sha256"]
    assert [(e["id"], e["status"], e["problems"]) for e in r["essences"]] == [("e1", "evidenced", []), ("e2", "evidenced", [])]
    assert r["counts"] == {"evidenced": 2, "missing": 0, "test_failed": 0, "tests_not_run": 0}
    assert "percent" not in str(r).lower() and "score" not in r


def test_the_report_never_calls_the_unit_complete_and_says_what_it_did_not_do():
    r = audit_unit(UNIT, SOURCES, RESULTS)
    assert r["note"] == ("U29: structural evidence check against the quote; it did not run any test, read any meaning, "
                         "or judge whether the code does what the quote means.")


def test_unmapped_quote_text_is_listed_so_nothing_is_silently_dropped():
    r = audit_unit(UNIT, SOURCES, RESULTS)
    assert r["unmapped_quote_words"] == ["Build", "a", "that"]


def test_fully_mapped_quote_has_no_unmapped_words():
    u = unit(essences=[{"id": "all", "fragment": QUOTE, "requires": [{"kind": "file", "path": "pkg/pitch.py"}]}])
    assert audit_unit(u, SOURCES, RESULTS)["unmapped_quote_words"] == []


def test_missing_file_symbol_test_and_text_are_each_reported_with_exact_problem_text():
    u = unit(essences=[{"id": "m", "fragment": "pitch writer", "requires": [
        {"kind": "file", "path": "nope.py"},
        {"kind": "symbol", "path": "pkg/pitch.py", "name": "Nope"},
        {"kind": "test", "path": "tests/test_pitch.py", "name": "test_nope"},
        {"kind": "text", "path": "pkg/pitch.py", "contains": "zzz"}]}])
    e = audit_unit(u, SOURCES, RESULTS)["essences"][0]
    assert e["status"] == "missing"
    assert e["problems"] == ["file 'nope.py' not supplied",
                             "symbol 'Nope' not defined in 'pkg/pitch.py'",
                             "test 'test_nope' not found in 'tests/test_pitch.py'",
                             "text 'zzz' not found in 'pkg/pitch.py'"]


def test_symbol_in_a_file_that_is_not_supplied_is_a_file_problem_not_a_crash():
    u = unit(essences=[{"id": "m", "fragment": "pitch writer", "requires": [{"kind": "symbol", "path": "x.py", "name": "A"}]}])
    assert audit_unit(u, SOURCES, RESULTS)["essences"][0]["problems"] == ["file 'x.py' not supplied"]


def test_unparseable_source_is_reported_not_raised():
    u = unit(essences=[{"id": "m", "fragment": "pitch writer", "requires": [{"kind": "symbol", "path": "bad.py", "name": "A"}]}])
    e = audit_unit(u, {"bad.py": "def (:\n"}, RESULTS)["essences"][0]
    assert e["status"] == "missing" and e["problems"] == ["file 'bad.py' does not parse"]


def test_test_result_failed_is_reported_and_blocks_evidenced():
    res = dict(RESULTS); res["tests/test_pitch.py::test_nothing_is_sent"] = "failed"
    r = audit_unit(UNIT, SOURCES, res)
    assert [e["status"] for e in r["essences"]] == ["evidenced", "test_failed"]
    assert r["essences"][1]["problems"] == ["test 'tests/test_pitch.py::test_nothing_is_sent' result is 'failed'"]
    assert r["counts"] == {"evidenced": 1, "missing": 0, "test_failed": 1, "tests_not_run": 0}


def test_test_without_a_supplied_result_is_tests_not_run_never_evidenced():
    r = audit_unit(UNIT, SOURCES, {})
    assert [e["status"] for e in r["essences"]] == ["tests_not_run", "tests_not_run"]
    assert r["essences"][0]["problems"] == ["no result supplied for 'tests/test_pitch.py::test_draft_is_text'"]
    assert r["counts"]["tests_not_run"] == 2 and r["counts"]["evidenced"] == 0


def test_missing_outranks_failed_outranks_not_run():
    u = unit(essences=[{"id": "m", "fragment": "pitch writer", "requires": [
        {"kind": "file", "path": "nope.py"},
        {"kind": "test", "path": "tests/test_pitch.py", "name": "test_draft_is_text"}]}])
    assert audit_unit(u, SOURCES, {})["essences"][0]["status"] == "missing"


def test_an_essence_with_no_checks_is_missing_not_evidenced():
    u = unit(essences=[{"id": "m", "fragment": "pitch writer", "requires": []}])
    e = audit_unit(u, SOURCES, RESULTS)["essences"][0]
    assert e["status"] == "missing" and e["problems"] == ["no evidence checks declared"]


def test_audit_does_not_mutate_its_inputs():
    u, s, r = copy.deepcopy(UNIT), copy.deepcopy(SOURCES), copy.deepcopy(RESULTS)
    audit_unit(u, s, r)
    assert (u, s, r) == (UNIT, SOURCES, RESULTS)


# --- word-for-word quote ---------------------------------------------------------------------------------
def test_quote_hash_is_sha256_of_the_exact_utf8_text():
    assert quote_sha256(QUOTE) == hashlib.sha256(QUOTE.encode("utf-8")).hexdigest()


def test_quote_that_does_not_match_its_recorded_hash_is_refused():
    assert refusal(audit_unit, unit(quote=QUOTE + " "), SOURCES, RESULTS) == \
        "U29: quote does not match its recorded sha256 (the quote must be word for word)"


def test_fragment_must_be_an_exact_substring_of_the_quote():
    u = unit(essences=[{"id": "m", "fragment": "Pitch Writer", "requires": [{"kind": "file", "path": "pkg/pitch.py"}]}])
    assert refusal(audit_unit, u, SOURCES, RESULTS) == "U29: essence 'm' fragment is not an exact substring of the quote"


def test_recorded_hash_is_required():
    d = unit(); d.pop("quote_sha256")
    assert refusal(audit_unit, d, SOURCES, RESULTS) == "U29: unit key 'quote_sha256' is required"


# --- declaration validation ----------------------------------------------------------------------------
@pytest.mark.parametrize("key", ["unit_id", "quote", "essences"])
def test_required_unit_keys(key):
    d = unit(); d.pop(key)
    assert refusal(audit_unit, d, SOURCES, RESULTS) == f"U29: unit key '{key}' is required"


def test_unknown_unit_key_is_refused():
    assert refusal(audit_unit, unit(extra=1), SOURCES, RESULTS) == "U29: unknown unit key(s) ['extra']"


def test_unit_must_be_an_object_and_sources_an_object():
    assert refusal(audit_unit, [], SOURCES, RESULTS) == "U29: unit must be an object"
    assert refusal(audit_unit, UNIT, [], RESULTS) == "U29: sources must be an object of path to text"
    assert refusal(audit_unit, UNIT, {"a": 1}, RESULTS) == "U29: sources must be an object of path to text"
    assert refusal(audit_unit, UNIT, SOURCES, []) == "U29: test_results must be an object"


def test_essences_must_be_a_non_empty_list_of_objects_with_unique_ids():
    assert refusal(audit_unit, unit(essences=[]), SOURCES, RESULTS) == "U29: essences must be a non-empty list"
    assert refusal(audit_unit, unit(essences=["x"]), SOURCES, RESULTS) == "U29: each essence must be an object"
    e = UNIT["essences"][0]
    assert refusal(audit_unit, unit(essences=[e, e]), SOURCES, RESULTS) == "U29: duplicate essence id 'e1'"


def test_unknown_check_kind_and_missing_check_fields_are_refused():
    bad = lambda r: unit(essences=[{"id": "m", "fragment": "pitch writer", "requires": [r]}])
    assert refusal(audit_unit, bad({"kind": "magic"}), SOURCES, RESULTS) == "U29: essence 'm' has unknown check kind 'magic'"
    assert refusal(audit_unit, bad({"kind": "file"}), SOURCES, RESULTS) == "U29: essence 'm' check 'file' requires 'path'"
    assert refusal(audit_unit, bad({"kind": "symbol", "path": "a"}), SOURCES, RESULTS) == "U29: essence 'm' check 'symbol' requires 'name'"
    assert refusal(audit_unit, bad({"kind": "text", "path": "a"}), SOURCES, RESULTS) == "U29: essence 'm' check 'text' requires 'contains'"


def test_no_network_no_filesystem_no_subprocess_imports():
    import ast, inspect
    import app.modules.m20_general_cognitive_worker.quote_audit_u29 as m
    names = set()
    for n in ast.walk(ast.parse(inspect.getsource(m))):
        if isinstance(n, ast.Import):
            names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            names.add((n.module or "").split(".")[0])
    assert names <= {"__future__", "ast", "hashlib", "json", "re", "typing"}


# --- external-review hooks: a packet and a proposal; nothing is sent -----------------------------------------
def test_providers_are_exactly_the_four_named_by_the_owner():
    assert PROVIDERS == ("chatgpt", "deepseek", "claude", "perplexity")


def make_packet(**kw):
    rep = audit_unit(UNIT, SOURCES, RESULTS)
    args = dict(unit=UNIT, report=rep, excerpts={"pkg/pitch.py": SOURCES["pkg/pitch.py"]}, providers=["claude"], sources=SOURCES)
    args.update(kw)
    return build_external_packet(**args)


def test_packet_carries_only_the_quote_the_report_and_the_chosen_excerpts_with_a_hash():
    p = make_packet()
    assert set(p) == {"payload", "packet_sha256", "proposal"}
    assert set(p["payload"]) == {"unit_id", "quote", "report", "excerpts", "code_summary", "tests", "limits", "question"}
    assert p["payload"]["excerpts"] == {"pkg/pitch.py": SOURCES["pkg/pitch.py"]}
    assert p["payload"]["quote"] == QUOTE
    assert p["packet_sha256"] == hashlib.sha256(__import__("json").dumps(p["payload"], sort_keys=True).encode()).hexdigest()


def test_proposal_is_pending_owner_approval_and_marks_nothing_executed():
    p = make_packet(providers=["claude", "deepseek"])
    assert p["proposal"] == {
        "action": "external_validation_send", "status": "pending_owner_approval", "executed": False,
        "providers": ["claude", "deepseek"], "packet_sha256": p["packet_sha256"], "unit_id": "T01",
        "approval_path": "m00_approval_center", "sends_nothing_itself": True,
    }


def test_unknown_or_empty_or_duplicate_providers_are_refused():
    assert refusal(make_packet, providers=["gpt5"]) == "U29: provider 'gpt5' is not one of ('chatgpt', 'deepseek', 'claude', 'perplexity')"
    assert refusal(make_packet, providers=[]) == "U29: providers must be a non-empty list"
    assert refusal(make_packet, providers=["claude", "claude"]) == "U29: provider 'claude' listed more than once"


def test_excerpt_for_a_file_not_supplied_is_refused():
    assert refusal(make_packet, excerpts={"other.py": "x"}) == "U29: excerpt path 'other.py' is not in the supplied sources"


def test_excerpt_text_must_be_the_exact_supplied_text_not_an_edited_one():
    assert refusal(make_packet, excerpts={"pkg/pitch.py": "class Changed: pass"}) == \
        "U29: excerpt for 'pkg/pitch.py' is not part of the supplied source text"


@pytest.mark.parametrize("secret", ["AKIA" + "ABCDEFGHIJKLMNOP", "sk-" + "a" * 24, "-----BEGIN " + "PRIVATE KEY-----",
                                    "ghp_" + "a" * 36, "api_key = 'abcdefgh'", "password = 'hunter2'", "Bearer " + "a" * 20])
def test_credential_like_text_in_an_excerpt_is_refused(secret):
    src = dict(SOURCES); src["pkg/pitch.py"] = SOURCES["pkg/pitch.py"] + f"\n# {secret}\n"
    rep = audit_unit(UNIT, src, RESULTS)
    assert refusal(build_external_packet, UNIT, rep, {"pkg/pitch.py": src["pkg/pitch.py"]}, ["claude"], sources=src) == \
        "U29: excerpt for 'pkg/pitch.py' looks like it contains a credential; not packaged"


def approval(p, **over):
    a = {"decision": "approved", "approved_by": "owner", "packet_sha256": p["packet_sha256"], "providers": ["claude"]}
    a.update(over)
    return a


def test_release_requires_an_approval_that_matches_the_packet_hash_and_providers():
    p = make_packet()
    out = release_packet(p, approval(p))
    assert out == {"payload": p["payload"], "providers": ["claude"], "released": True, "sent": False,
                   "dispatch": "only through the approval center; this module has no send function"}


@pytest.mark.parametrize("over,msg", [
    ({"decision": "denied"}, "U29: approval decision is not 'approved'"),
    ({"decision": "pending"}, "U29: approval decision is not 'approved'"),
    ({"approved_by": "peer"}, "U29: approval must be recorded as approved_by 'owner'"),
    ({"packet_sha256": "0" * 64}, "U29: approval does not match this packet (sha256 differs)"),
    ({"providers": ["deepseek"]}, "U29: approval does not cover provider 'claude'"),
    ({"providers": []}, "U29: approval does not cover provider 'claude'"),
])
def test_release_refuses_a_non_matching_approval(over, msg):
    p = make_packet()
    assert refusal(release_packet, p, approval(p, **over)) == msg


def test_release_refuses_a_missing_or_malformed_approval():
    p = make_packet()
    assert refusal(release_packet, p, None) == "U29: an approval record is required"
    assert refusal(release_packet, p, "yes") == "U29: an approval record is required"


def test_release_refuses_a_packet_whose_payload_was_edited_after_hashing():
    p = make_packet()
    a = approval(p)
    p2 = copy.deepcopy(p); p2["payload"]["quote"] = "changed"
    assert refusal(release_packet, p2, a) == "U29: packet payload does not match its sha256"


def test_approval_may_cover_more_providers_than_the_packet_asks_for():
    p = make_packet(providers=["claude"])
    assert release_packet(p, approval(p, providers=["claude", "deepseek"]))["providers"] == ["claude"]


def test_missing_outranks_test_failed_in_one_essence():
    quote = "make it work"
    unit = {"unit_id": "X", "quote": quote, "quote_sha256": quote_sha256(quote),
            "essences": [{"id": "e1", "fragment": "make it work", "requires": [
                {"kind": "file", "path": "absent.py"},
                {"kind": "test", "path": "t.py", "name": "test_a"}]}]}
    rep = audit_unit(unit, {"t.py": "def test_a():\n    pass\n"}, {"t.py::test_a": "failed"})
    assert rep["essences"][0]["status"] == "missing"
    assert rep["counts"]["missing"] == 1 and rep["counts"]["test_failed"] == 0
