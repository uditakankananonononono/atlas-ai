"""Row 1299 E-Discovery: hermetic stdlib tests, exact-value pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import json
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/e_discovery1299.py"
_spec = importlib.util.spec_from_file_location("e_discovery1299", _SRC)
mod = importlib.util.module_from_spec(_spec)
sys.modules["e_discovery1299"] = mod
_spec.loader.exec_module(mod)

VOCAB = ("hold_scope", "custodians", "sources", "collection_provenance", "processing", "production_gates")
PACKAGE_VOCAB = ("provider_criteria", "applicant_assertions", "documents", "conflicts", "referral_status", "language", "disability", "cost", "geography", "procedure", "service_resource_evidence", "use_case", "data_flow", "vendor_evidence", "access", "retention", "human_review", "hold_scope", "custodians", "sources", "collection_provenance", "processing", "production_gates", "dataset_provenance", "target", "metric", "bias_limits", "nonpredictive_use", "protocol", "seed_decisions", "sampling_metrics", "drift", "pending_human_review", "document_hash", "custodian", "issue_labels", "responsiveness", "privilege_candidates", "matter_owner", "phase", "milestones", "budget_inputs", "controls", "approvals", "staffing", "capacity", "supervision", "approval_controlled_changes", "scope", "fee_formula", "assumptions", "triggers", "exclusions", "approval", "deliverables", "owners", "dependencies", "risks", "decision_gates", "artifact_provenance", "jurisdiction", "currency", "supersession", "audience", "learning_objective", "source_authority", "exercise", "assessment_limits",)
AS_OF = "2026-10-12"
BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel must verify "
            "jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.")


def entry(element, status="supplied", ref="REF-1", entry_date=None):
    e = {"element": element, "status": status}
    if ref is not None:
        e["source_ref"] = ref
    if entry_date is not None:
        e["entry_date"] = entry_date
    return e


def go(entries, row=1299, as_of=AS_OF):
    return mod.run({"row": row, "as_of": as_of, "entries": entries})


def run_with(**extra):
    request = {"row": 1299, "as_of": AS_OF, "entries": [entry(VOCAB[0])]}
    request.update(extra)
    return mod.run(request)


def refused(fn, code):
    with pytest.raises(mod.EDiscoveryError) as e:
        fn()
    assert str(e.value) == "EDISCO1299: " + code


def test_happy_mixed_statuses():
    v = VOCAB
    result = go([
        entry(v[0], "supplied", "REF-ALPHA", "2026-10-01"),
        entry(v[0], "missing", None),
        entry(v[1], "supplied", "REF-BETA", "2026-09-30"),
        entry(v[2], "disputed", "REF-GAMMA"),
        entry(v[3], "missing", None),
    ])
    by_name = {e["element"]: e for e in result["elements"]}
    assert [e["element"] for e in result["elements"]] == list(v)
    first = by_name[v[0]]
    assert first["status"] == "referenced"
    assert first["also_declared_missing"] is True
    assert first["latest_entry_date"] == "2026-10-01"
    assert first["days_since_latest"] == 11
    second = by_name[v[1]]
    assert (second["status"], second["also_declared_missing"]) == ("referenced", False)
    assert second["latest_entry_date"] == "2026-09-30"
    assert second["days_since_latest"] == 12
    third = by_name[v[2]]
    assert third["status"] == "disputed"
    assert third["latest_entry_date"] is None and third["days_since_latest"] is None
    assert by_name[v[3]]["status"] == "declared_missing"
    for name in v[4:]:
        assert by_name[name]["status"] == "unaddressed"
        assert by_name[name]["also_declared_missing"] is False
    assert result["coverage"] == {"elements_total": len(v), "referenced": 2, "disputed": 1,
                                  "declared_missing": 1, "unaddressed": len(v) - 4}
    assert result["row"] == 1299


def test_full_vocabulary_accepted():
    result = go([entry(name, "supplied", "REF-" + name, "2026-10-02") for name in VOCAB])
    assert all(e["status"] == "referenced" for e in result["elements"])
    assert result["coverage"]["referenced"] == len(VOCAB)
    assert all(e["days_since_latest"] == 10 for e in result["elements"])


def test_package_vocabulary_refused_cross_row():
    own = set(VOCAB)
    foreign = [name for name in PACKAGE_VOCAB if name not in own]
    assert foreign  # guard: the package must share vocabulary across rows for this to mean anything
    for name in foreign:
        refused(lambda: go([entry(name)]), "UNKNOWN:element")


def test_unknown_status():
    refused(lambda: go([entry(VOCAB[0], "unclear")]), "UNKNOWN:status")


def test_unknown_row_and_bool_row():
    refused(lambda: go([entry(VOCAB[0])], row=1299 + 1), "UNKNOWN:row")
    refused(lambda: go([entry(VOCAB[0])], row=True), "UNKNOWN:row")
    refused(lambda: go([entry(VOCAB[0])], row="1299"), "UNKNOWN:row")


def test_empty_and_oversize_entries():
    refused(lambda: go([]), "EMPTY:entries")
    refused(lambda: go([entry(VOCAB[0])] * 201), "OVERSIZE:entries")


def test_source_ref_rules():
    refused(lambda: go([entry(VOCAB[0], "supplied", None)]), "BAD_TYPE:source_ref")
    refused(lambda: go([entry(VOCAB[0], "disputed", None)]), "BAD_TYPE:source_ref")
    refused(lambda: go([entry(VOCAB[0], "missing", "REF-X")]), "BAD_TYPE:source_ref")
    refused(lambda: go([entry(VOCAB[0], "supplied", "")]), "BAD_TYPE:source_ref")
    refused(lambda: go([entry(VOCAB[0], "supplied", "x" * 201)]), "BAD_TYPE:source_ref")
    result = go([entry(VOCAB[0], "supplied", "x" * 200)])
    assert result["coverage"]["referenced"] == 1


def test_unicode_refusals():
    for bad in ["\x00", "\u0007", "\u200b", "\u2028", "\u2029"]:
        refused(lambda: go([entry(VOCAB[0], "supplied", "REF-" + bad + "1")]), "BAD_TYPE:source_ref")
    ok = go([entry(VOCAB[0], "supplied", "REF-\u00a0OK")])
    assert ok["coverage"]["referenced"] == 1


def test_date_gates():
    refused(lambda: go([entry(VOCAB[0], "supplied", "R1", "2026-02-30")]), "BAD_TYPE:entry_date")
    refused(lambda: go([entry(VOCAB[0], "supplied", "R1", "2026-10-13")]), "BAD_TYPE:entry_date")
    refused(lambda: go([entry(VOCAB[0], "supplied", "R1", 20261001)]), "BAD_TYPE:entry_date")
    refused(lambda: go([entry(VOCAB[0])], as_of="2026-13-01"), "BAD_TYPE:as_of")
    refused(lambda: go([entry(VOCAB[0])], as_of="\uff12\uff11\uff10\uff16-10-12"), "BAD_TYPE:as_of")
    refused(lambda: go([entry(VOCAB[0])], as_of="10/12/2026"), "BAD_TYPE:as_of")


def test_duplicate_refused():
    dup = entry(VOCAB[0], "supplied", "REF-DUP", "2026-10-01")
    refused(lambda: go([dup, dict(dup)]), "BAD_TYPE:entries")
    distinct = go([entry(VOCAB[0], "supplied", "REF-DUP"), entry(VOCAB[0], "missing", None)])
    assert distinct["coverage"]["referenced"] == 1  # distinct status is not a duplicate


def test_forbidden_keys():
    refused(lambda: run_with(approval="x"), "SEND:approval")
    refused(lambda: run_with(pay=1), "SPEND:pay")
    refused(lambda: run_with(password="hunter2"), "NOCREDS:password")
    refused(lambda: run_with(file=True), "EFFECT:file")
    refused(lambda: run_with(nested={"contact": "x"}), "EFFECT:contact")
    refused(lambda: run_with(deep=[{"serve": "x"}]), "EFFECT:serve")


def test_no_source_text_echo():
    secret = "ZEBRA-CONFIDENTIAL-9f4q"
    result = go([entry(VOCAB[0], "supplied", secret, "2026-10-01"),
                 entry(VOCAB[1], "disputed", secret + "-B")])
    assert secret not in json.dumps(result)
    try:
        go([entry(VOCAB[0], "missing", secret)])
    except mod.EDiscoveryError as e:
        assert secret not in str(e)
    else:
        raise AssertionError("expected refusal")


def test_days_arithmetic():
    result = go([
        entry(VOCAB[0], "supplied", "R-old", "2026-09-30"),
        entry(VOCAB[0], "supplied", "R-new", "2026-10-05"),
        entry(VOCAB[1], "disputed", "R-dis", "2026-10-11"),
        entry(VOCAB[2], "supplied", "R-same", "2026-10-12"),
    ])
    by_name = {e["element"]: e for e in result["elements"]}
    assert by_name[VOCAB[0]]["latest_entry_date"] == "2026-10-05"
    assert by_name[VOCAB[0]]["days_since_latest"] == 7
    assert by_name[VOCAB[1]]["latest_entry_date"] is None  # disputed dates never feed latest
    assert by_name[VOCAB[2]]["days_since_latest"] == 0


def test_honesty_flags_and_boundary():
    result = go([entry(VOCAB[0])])
    assert result["counsel_review_required"] is True
    assert result["legal_conclusion"] is False
    assert result["references_verified"] is False
    assert result["boundary"] == BOUNDARY
    assert "never" in result["scope"]
    assert result["row"] == 1299


def test_disputed_dominates():
    result = go([entry(VOCAB[0], "supplied", "R1"), entry(VOCAB[0], "disputed", "R2")])
    el = result["elements"][0]
    assert el["status"] == "disputed"
    assert el["also_declared_missing"] is False
    assert result["coverage"]["referenced"] == 0


def test_declared_missing_and_unaddressed():
    result = go([entry(VOCAB[0], "missing", None)])
    el = result["elements"][0]
    assert el["status"] == "declared_missing"
    assert el["latest_entry_date"] is None and el["days_since_latest"] is None
    assert result["coverage"]["unaddressed"] == len(VOCAB) - 1


def test_exact_key_sets():
    refused(lambda: run_with(extra=1), "BAD_TYPE:request")
    refused(lambda: mod.run({"row": 1299, "as_of": AS_OF}), "BAD_TYPE:request")
    bad = entry(VOCAB[0])
    bad["note"] = "x"
    refused(lambda: go([bad]), "BAD_TYPE:entry")
    refused(lambda: go([{"element": VOCAB[0], "source_ref": "R1"}]), "BAD_TYPE:entry")


def test_strict_types():
    refused(lambda: go((entry(VOCAB[0]),)), "BAD_TYPE:entries")
    refused(lambda: go([["not-a-dict"]]), "BAD_TYPE:entry")
    refused(lambda: go([{"element": 7, "status": "supplied", "source_ref": "R1"}]), "UNKNOWN:element")
    refused(lambda: mod.run(None), "BAD_TYPE:request")


def test_missing_with_entry_date_allowed():
    result = go([entry(VOCAB[0], "missing", None, "2026-10-01")])
    assert result["elements"][0]["status"] == "declared_missing"
    assert result["elements"][0]["latest_entry_date"] is None


def test_two_hundred_entries_accepted():
    entries = [entry(VOCAB[i % len(VOCAB)], "supplied", "REF-%d" % i) for i in range(200)]
    assert go(entries)["coverage"]["referenced"] == len(VOCAB)

@pytest.mark.parametrize('value',["20261012","2026-W41-1"])
@pytest.mark.parametrize('field',["as_of","entry_date"])
def test_closing_date_syntax(field,value):
    if field=="as_of":refused(lambda:go([entry(VOCAB[0])],as_of=value),"BAD_TYPE:as_of")
    else:refused(lambda:go([entry(VOCAB[0],entry_date=value)]),"BAD_TYPE:entry_date")


def test_closing_list_entry_refused():
    refused(lambda:go([["element","status"]]),"BAD_TYPE:entry")


def test_closing_right_count_wrong_request_keys():
    refused(lambda:mod.run({"row":1299,"as_of":AS_OF,"bogus":[]}),"BAD_TYPE:request")

@pytest.mark.parametrize('size',[1,200])
def test_closing_source_ref_accept_edges(size):
    assert go([entry(VOCAB[0],ref="x"*size)])["coverage"]["referenced"]==1

@pytest.mark.parametrize('size',[0,201])
def test_closing_source_ref_refuse_edges(size):
    refused(lambda:go([entry(VOCAB[0],ref="x"*size)]),"BAD_TYPE:source_ref")
