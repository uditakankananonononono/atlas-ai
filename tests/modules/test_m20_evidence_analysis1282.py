"""Row 1282 Evidence Analysis (custody completeness and gaps, weight tags passed through).

Hermetic: stdlib only, no files, no network. Loads the module by path.
"""
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/evidence_analysis1282.py"


def _load():
    spec = importlib.util.spec_from_file_location("evidence_analysis1282", _SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["evidence_analysis1282"] = mod
    spec.loader.exec_module(mod)
    return mod


ev = _load()


def item(eid="E1", **kw):
    d = {"evidence_id": eid, "type": "document", "source": "alice", "timestamp": "2026-01-01T10:00:00+00:00",
         "custody": [
             {"from": "alice", "to": "bob", "at": "2026-01-01T11:00:00+00:00"},
             {"from": "bob", "to": "carol", "at": "2026-01-02T09:00:00+00:00"}]}
    d.update(kw)
    return d


def run(*items):
    return ev.analyze_evidence(list(items))


def gap_codes(r, i=0):
    return [g["code"] for g in r["items"][i]["gaps"]]


def refuse(items, text=None):
    with pytest.raises(ev.EvidenceError) as e:
        ev.analyze_evidence(items)
    assert str(e.value).startswith("EVID1282: ")
    if text:
        assert text in str(e.value)
    return str(e.value)


# ---- shape of a good result -------------------------------------------------
def test_complete_chain_passes_fields_through_and_reports_complete():
    r = run(item(weight_tag="caller-high"))
    it = r["items"][0]
    assert it["evidence_id"] == "E1" and it["type"] == "document" and it["source"] == "alice"
    assert it["timestamp"] == "2026-01-01T10:00:00+00:00"
    assert it["weight_tag"] == "caller-high"
    assert it["custody_status"] == "CUSTODY_COMPLETE" and it["gaps"] == [] and it["custody_events"] == 2
    assert r["summary"] == {"total": 1, "complete": 1, "with_gaps": 0, "no_custody": 0}


def test_result_states_what_it_does_not_do():
    r = run(item())
    assert r["admissibility_judged"] is False and r["weights_invented"] is False
    assert r["scope"] == "EVID1282 custody completeness only"
    assert "does not establish authenticity" in r["boundary"]
    assert "legal_support_1260_1309" in r["boundary"]


def test_weight_tag_absent_is_none_never_invented():
    r = run(item())
    assert r["items"][0]["weight_tag"] is None
    assert "weight" not in "".join(k for k in r if k not in ("weights_invented",))


def test_weight_tag_passed_through_byte_for_byte():
    for tag in ["x", "A B", "  spaced  ", "ünï", "0.7", "high/medium"]:
        assert run(item(weight_tag=tag))["items"][0]["weight_tag"] == tag


def test_items_keep_caller_order_and_are_not_ranked_or_merged():
    r = run(item("B", weight_tag="z"), item("A", weight_tag="a"), item("C"))
    assert [x["evidence_id"] for x in r["items"]] == ["B", "A", "C"]


def test_input_is_not_mutated():
    a = item()
    before = repr(a)
    run(a)
    assert repr(a) == before


# ---- custody statuses and gaps ---------------------------------------------
@pytest.mark.parametrize("custody", [[], None])
def test_empty_or_missing_custody_is_no_custody(custody):
    d = item()
    if custody is None:
        del d["custody"]
    else:
        d["custody"] = custody
    r = run(d)
    it = r["items"][0]
    assert it["custody_status"] == "NO_CUSTODY" and it["custody_events"] == 0
    assert [g["code"] for g in it["gaps"]] == ["CUSTODY_EMPTY"]
    assert r["summary"] == {"total": 1, "complete": 0, "with_gaps": 0, "no_custody": 1}


def test_first_transfer_not_from_source_is_a_gap():
    d = item(custody=[{"from": "mallory", "to": "bob", "at": "2026-01-01T11:00:00+00:00"}])
    r = run(d)
    assert gap_codes(r) == ["FIRST_FROM_NOT_SOURCE"]
    assert r["items"][0]["gaps"][0]["index"] == 0
    assert r["items"][0]["custody_status"] == "CUSTODY_GAPS"
    assert r["summary"]["with_gaps"] == 1


def test_holder_discontinuity_is_a_gap_at_the_second_event():
    d = item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-01T11:00:00+00:00"},
                      {"from": "dave", "to": "carol", "at": "2026-01-02T09:00:00+00:00"}])
    r = run(d)
    assert gap_codes(r) == ["HOLDER_DISCONTINUITY"]
    assert r["items"][0]["gaps"][0]["index"] == 1


def test_time_reversed_event_is_a_gap():
    d = item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-03T11:00:00+00:00"},
                      {"from": "bob", "to": "carol", "at": "2026-01-02T09:00:00+00:00"}])
    r = run(d)
    assert gap_codes(r) == ["TIME_REVERSED"]
    assert r["items"][0]["gaps"][0]["index"] == 1


def test_equal_event_times_are_not_reversed():
    d = item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-03T11:00:00+00:00"},
                      {"from": "bob", "to": "carol", "at": "2026-01-03T11:00:00+00:00"}])
    assert gap_codes(run(d)) == []


def test_event_before_item_timestamp_is_a_gap():
    d = item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-01T09:59:59+00:00"}])
    r = run(d)
    assert gap_codes(r) == ["BEFORE_ITEM_TIMESTAMP"]


def test_event_at_exactly_item_timestamp_is_not_a_gap():
    d = item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-01T10:00:00+00:00"}])
    assert gap_codes(run(d)) == []


def test_timestamps_compared_in_utc_not_as_text():
    d = item(timestamp="2026-01-01T10:00:00+00:00",
             custody=[{"from": "alice", "to": "bob", "at": "2026-01-01T12:00:00+05:00"}])  # 07:00 UTC, earlier
    assert gap_codes(run(d)) == ["BEFORE_ITEM_TIMESTAMP"]
    d = item(timestamp="2026-01-01T10:00:00-05:00",   # 15:00 UTC
             custody=[{"from": "alice", "to": "bob", "at": "2026-01-01T16:00:00+00:00"}])
    assert gap_codes(run(d)) == []


def test_z_suffix_timestamps_are_accepted():
    d = item(timestamp="2026-01-01T10:00:00Z", custody=[{"from": "alice", "to": "bob", "at": "2026-01-01T11:00:00Z"}])
    assert gap_codes(run(d)) == [] and run(d)["items"][0]["timestamp"] == "2026-01-01T10:00:00Z"


def test_multiple_gaps_are_all_reported_in_order():
    d = item(custody=[{"from": "x", "to": "bob", "at": "2026-01-01T09:00:00+00:00"},
                      {"from": "zed", "to": "carol", "at": "2026-01-01T08:00:00+00:00"}])
    r = run(d)
    assert [(g["code"], g["index"]) for g in r["items"][0]["gaps"]] == [
        ("FIRST_FROM_NOT_SOURCE", 0), ("BEFORE_ITEM_TIMESTAMP", 0),
        ("HOLDER_DISCONTINUITY", 1), ("TIME_REVERSED", 1), ("BEFORE_ITEM_TIMESTAMP", 1)]


def test_gap_detail_text_names_the_values():
    d = item(custody=[{"from": "mallory", "to": "bob", "at": "2026-01-01T11:00:00+00:00"}])
    g = run(d)["items"][0]["gaps"][0]
    assert g["detail"] == "first transfer is from 'mallory' but the declared source is 'alice'"


def test_summary_counts_across_items():
    ok = item("A")
    bad = item("B", custody=[{"from": "q", "to": "bob", "at": "2026-01-01T11:00:00+00:00"}])
    none = item("C", custody=[])
    r = run(ok, bad, none)
    assert [x["custody_status"] for x in r["items"]] == ["CUSTODY_COMPLETE", "CUSTODY_GAPS", "NO_CUSTODY"]
    assert r["summary"] == {"total": 3, "complete": 1, "with_gaps": 1, "no_custody": 1}


def test_custody_event_may_carry_a_note_which_is_not_interpreted():
    d = item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-01T11:00:00+00:00", "note": "sealed bag 7"}])
    assert gap_codes(run(d)) == []


# ---- refusals ---------------------------------------------------------------
@pytest.mark.parametrize("bad", [None, "x", {}, (item(),), 5])
def test_items_must_be_a_list(bad):
    refuse(bad, "items must be a list")


def test_items_must_not_be_empty():
    refuse([], "items must not be empty")


def test_items_over_limit_refused():
    many = [item(f"E{i}", custody=[]) for i in range(ev.MAX_ITEMS + 1)]
    refuse(many, "too many items")
    assert len(ev.analyze_evidence(many[:-1])["items"]) == ev.MAX_ITEMS


@pytest.mark.parametrize("bad", [None, "s", 1, [1], ("a",)])
def test_each_item_must_be_a_dict(bad):
    refuse([bad], "item 0 must be an object")


@pytest.mark.parametrize("key", ["evidence_id", "type", "source", "timestamp"])
def test_required_keys_missing(key):
    d = item()
    del d[key]
    refuse([d], f"item 0 missing '{key}'")


def test_unknown_item_key_refused():
    refuse([item(extra=1)], "item 0 has unknown key 'extra'")


@pytest.mark.parametrize("key", ["evidence_id", "type", "source"])
@pytest.mark.parametrize("bad", ["", "   ", 5, None, ["a"], "a\nb", "a\x00b", "x" * 501])
def test_string_fields_validated(key, bad):
    refuse([item(**{key: bad})], f"item 0 '{key}'")


def test_string_field_at_exact_limit_accepted():
    assert run(item(source="s" * 500, custody=[]))["items"][0]["source"] == "s" * 500


def test_duplicate_evidence_id_refused():
    refuse([item("A"), item("A")], "duplicate evidence_id 'A'")


@pytest.mark.parametrize("bad", ["2026-01-01T10:00:00", "2026-01-01", "yesterday", "", 5, None, "2026-13-01T10:00:00+00:00",
                                 "2026-01-01T10:00:00+0000x"])
def test_item_timestamp_requires_offset_and_iso(bad):
    refuse([item(timestamp=bad)], "item 0 'timestamp'")


@pytest.mark.parametrize("bad", ["", "  ", 5, ["x"], "a\nb", "x" * 65])
def test_weight_tag_must_be_a_plain_string_when_present(bad):
    refuse([item(weight_tag=bad)], "item 0 'weight_tag'")


def test_weight_tag_none_is_refused_not_treated_as_absent():
    refuse([item(weight_tag=None)], "item 0 'weight_tag'")


def test_weight_tag_at_exact_limit_accepted():
    assert run(item(weight_tag="w" * 64))["items"][0]["weight_tag"] == "w" * 64


@pytest.mark.parametrize("bad", ["x", {}, 5, ("a",)])
def test_custody_must_be_a_list(bad):
    refuse([item(custody=bad)], "item 0 'custody' must be a list")


def test_custody_events_over_limit_refused_and_exact_limit_accepted():
    ok = [{"from": "alice" if i == 0 else f"h{i-1}", "to": f"h{i}", "at": "2026-01-01T11:00:00+00:00"} for i in range(ev.MAX_EVENTS)]
    assert run(item(custody=ok))["items"][0]["custody_events"] == ev.MAX_EVENTS
    refuse([item(custody=ok + [{"from": "x", "to": "y", "at": "2026-01-01T11:00:00+00:00"}])], "too many custody events")


@pytest.mark.parametrize("bad", [None, "x", 1, [1]])
def test_custody_event_must_be_dict(bad):
    refuse([item(custody=[bad])], "item 0 custody event 0 must be an object")


@pytest.mark.parametrize("key", ["from", "to", "at"])
def test_custody_event_missing_key(key):
    e = {"from": "alice", "to": "bob", "at": "2026-01-01T11:00:00+00:00"}
    del e[key]
    refuse([item(custody=[e])], f"item 0 custody event 0 missing '{key}'")


@pytest.mark.parametrize("key", ["from", "to"])
@pytest.mark.parametrize("bad", ["", "  ", 5, None, "a\nb", "x" * 501])
def test_custody_event_holders_validated(key, bad):
    e = {"from": "alice", "to": "bob", "at": "2026-01-01T11:00:00+00:00"}
    e[key] = bad
    refuse([item(custody=[e])], f"item 0 custody event 0 '{key}'")


@pytest.mark.parametrize("bad", ["2026-01-01T11:00:00", "soon", "", 5, None])
def test_custody_event_time_requires_offset_and_iso(bad):
    e = {"from": "alice", "to": "bob", "at": bad}
    refuse([item(custody=[e])], "item 0 custody event 0 'at'")


def test_second_item_error_names_item_index():
    refuse([item("A"), item("B", type="")], "item 1 'type'")


def test_exception_is_a_value_error_subclass():
    assert issubclass(ev.EvidenceError, ValueError)


def test_bool_is_not_accepted_as_string_field():
    refuse([item(source=True)], "item 0 'source'")


def test_module_is_hermetic_no_io_imports():
    src = _SRC.read_text()
    for banned in ("import socket", "import subprocess", "import requests", "urllib", "open(", "os.environ"):
        assert banned not in src


def test_unknown_custody_event_key_refused():
    e = {"from": "alice", "to": "bob", "at": "2026-01-01T11:00:00+00:00", "weight": 9}
    refuse([item(custody=[e])], "item 0 custody event 0 has unknown key 'weight'")


@pytest.mark.parametrize("bad", ["", 5, None, "a\nb", "n" * 501])
def test_custody_note_must_be_a_plain_string(bad):
    e = {"from": "alice", "to": "bob", "at": "2026-01-01T11:00:00+00:00", "note": bad}
    refuse([item(custody=[e])], "item 0 custody event 0 'note'")


def test_naive_and_offset_aware_timestamps_never_compared():
    refuse([item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-01T11:00:00"}])], "'at'")


def test_gap_dict_has_exact_keys():
    g = run(item(custody=[{"from": "q", "to": "bob", "at": "2026-01-01T11:00:00+00:00"}]))["items"][0]["gaps"][0]
    assert set(g) == {"code", "index", "detail"}


def test_no_custody_gap_has_no_index():
    g = run(item(custody=[]))["items"][0]["gaps"][0]
    assert g == {"code": "CUSTODY_EMPTY", "index": None, "detail": "no custody transfers were declared"}


def test_item_result_has_exact_keys():
    assert set(run(item())["items"][0]) == {"evidence_id", "type", "source", "timestamp", "weight_tag",
                                            "custody_status", "gaps", "custody_events"}
    assert set(run(item())) == {"scope", "boundary", "items", "summary", "admissibility_judged", "weights_invented"}


def test_discontinuity_and_reversal_detail_text():
    d = item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-03T11:00:00+00:00"},
                      {"from": "dave", "to": "carol", "at": "2026-01-02T09:00:00+00:00"}])
    g = run(d)["items"][0]["gaps"]
    assert g[0]["detail"] == "transfer 1 is from 'dave' but the previous transfer went to 'bob'"
    assert g[1]["detail"] == "transfer 1 is dated before transfer 0"


def test_documented_limits_are_the_literal_values():
    assert (ev.MAX_ITEMS, ev.MAX_EVENTS, ev.MAX_TEXT, ev.MAX_TAG) == (1000, 200, 500, 64)
    assert len(ev.analyze_evidence([item(f"E{i}", custody=[]) for i in range(1000)])["items"]) == 1000
    refuse([item(f"E{i}", custody=[]) for i in range(1001)], "too many items")
    ok = [{"from": "alice" if i == 0 else f"h{i-1}", "to": f"h{i}", "at": "2026-01-01T11:00:00+00:00"} for i in range(200)]
    assert run(item(custody=ok))["items"][0]["custody_events"] == 200
    refuse([item(custody=ok + [ok[-1]])], "too many custody events")


@pytest.mark.parametrize("ch", ["\x7f", "\x1f", "\t", "\r"])
def test_control_characters_refused_in_text(ch):
    refuse([item(source=f"a{ch}b")], "item 0 'source'")


def test_space_inside_text_is_allowed():
    assert run(item(source="a b", custody=[]))["items"][0]["source"] == "a b"


def test_reversal_is_judged_in_utc_not_wall_clock():
    # first transfer 2026-01-01T10:00Z (wall clock Jan 2 00:00 +14:00); second 12:00Z (wall clock Jan 1 12:00)
    d = item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-02T00:00:00+14:00"},
                      {"from": "bob", "to": "carol", "at": "2026-01-01T12:00:00+00:00"}])
    assert gap_codes(run(d)) == []
    d = item(custody=[{"from": "alice", "to": "bob", "at": "2026-01-01T12:00:00+00:00"},
                      {"from": "bob", "to": "carol", "at": "2026-01-02T00:00:00+14:00"}])
    assert gap_codes(run(d)) == ["TIME_REVERSED"]
