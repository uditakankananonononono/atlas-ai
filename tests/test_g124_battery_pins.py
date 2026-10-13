"""G124 mutation-battery pins (auditor protocol): every survivor of the
delete/invert battery over dataset_register_p254 + dataset_count_reader_p254
gets a pinning test here. Red against the mutant, green on baseline."""
import io

import pytest

from app.modules.instinct_doc.dataset_count_reader_p254 import (
    MAX_BYTES, check_declared, count_records)
from app.modules.instinct_doc.dataset_register_p254 import (
    MAX_ENTRIES, RECORDS_LIMIT, add_entry, bind_artifacts, create_register,
    render, summary)


def entry(**kw):
    e = {"id": "a", "project_id": "p", "dataset": "d", "records": 1,
         "source": "observed", "source_ref": "ref"}
    e.update(kw)
    return e


def refuse(fn, prefix):
    with pytest.raises(ValueError) as ei:
        fn()
    assert str(ei.value).startswith(prefix), str(ei.value)


# --- _text guards (del_text_type / del_text_empty / del_text_len / del_banned_chars)

def test_pin_text_type():
    refuse(lambda: add_entry(create_register(), entry(id=123)), "P254:bad_type:id")
    refuse(lambda: add_entry(create_register(), entry(id=True)), "P254:bad_type:id")


def test_pin_text_empty():
    refuse(lambda: add_entry(create_register(), entry(id="   ")), "P254:empty_field:id")


def test_pin_text_len():
    refuse(lambda: add_entry(create_register(), entry(id="x" * 65)), "P254:text_too_long:id")
    refuse(lambda: add_entry(create_register(), entry(source="x" * 257)), "P254:text_too_long:source")


def test_pin_banned_chars():
    refuse(lambda: add_entry(create_register(), entry(id="a\nb")), "P254:unsafe_chars:id")
    refuse(lambda: add_entry(create_register(), entry(id="a b")), "P254:unsafe_chars:id")
    refuse(lambda: add_entry(create_register(), entry(id="a b")), "P254:unsafe_chars:id")


# --- _validate guards (del_entry_type / del_unknown_fields / del_records_type / del_records_range)

def test_pin_entry_type():
    refuse(lambda: add_entry(create_register(), ["not", "a", "dict"]), "P254:bad_type:entry")


def test_pin_unknown_fields():
    refuse(lambda: add_entry(create_register(), entry(zot="x")), "P254:unknown_fields:entry")


def test_pin_records_type():
    refuse(lambda: add_entry(create_register(), entry(records="5")), "P254:bad_type:records")
    refuse(lambda: add_entry(create_register(), entry(records=True)), "P254:bad_type:records")
    refuse(lambda: add_entry(create_register(), entry(records=5.0)), "P254:bad_type:records")


def test_pin_records_range():
    refuse(lambda: add_entry(create_register(), entry(records=-1)), "P254:count_out_of_range:records")
    refuse(lambda: add_entry(create_register(), entry(records=RECORDS_LIMIT + 1)), "P254:count_out_of_range:records")
    r = add_entry(create_register(), entry(records=RECORDS_LIMIT))
    assert r.entries[0][3] == RECORDS_LIMIT


# --- add_entry guards (del_register_type_add / del_duplicate_id / del_max_entries)

def test_pin_register_type():
    refuse(lambda: add_entry("not-a-register", entry()), "P254:bad_type:register")
    refuse(lambda: summary("not-a-register"), "P254:bad_type:register")
    refuse(lambda: render(["x"]), "P254:bad_type:register")


def test_pin_duplicate_id():
    r = add_entry(create_register(), entry())
    refuse(lambda: add_entry(r, entry()), "P254:duplicate_id:a")


def test_pin_max_entries():
    r = create_register()
    for i in range(MAX_ENTRIES):
        r = add_entry(r, entry(id="e%d" % i))
    refuse(lambda: add_entry(r, entry(id="one-more")), "P254:limit_exceeded:entries")


# --- summary honesty flags (invert_counts_verified)

def test_pin_summary_honesty_flags():
    r = add_entry(create_register(), entry())
    s = summary(r)
    assert s["counts_verified"] is False
    assert s["sources_resolved"] is False
    assert s["completeness_verified"] is False
    assert s["status"] == "declared_register_only"
    assert s["entry_count"] == 1 and s["total_records"] == 1


# --- render project gate (del_unknown_project)

def test_pin_unknown_project():
    r = add_entry(create_register(), entry())
    refuse(lambda: render(r, "nope"), "P254:unknown_project:nope")
    refuse(lambda: render(r, 42), "P254:bad_type:project_id")
    assert "project p" in render(r)


# --- bind_artifacts guards

def bound_register():
    return add_entry(create_register(), entry())


def test_pin_bindings_type(tmp_path):
    r = bound_register()
    refuse(lambda: bind_artifacts(r, tmp_path, "x"), "P254:bad_type:bindings")
    refuse(lambda: bind_artifacts(r, tmp_path, [{}] * (MAX_ENTRIES + 1)), "P254:bad_type:bindings")


def test_pin_source_reader_callable(tmp_path):
    r = bound_register()
    refuse(lambda: bind_artifacts(r, tmp_path, [], source_reader="x"),
           "P254:bad_type:source_reader")


def test_pin_entry_id_known(tmp_path):
    r = bound_register()
    b = {"entry_id": "ghost", "artifact_path": "data", "row_ids": [], "project_ids": []}
    refuse(lambda: bind_artifacts(r, tmp_path, [b]), "P254:unknown_or_duplicate:entry_id")
    b2 = {"entry_id": "a", "artifact_path": "data", "row_ids": [], "project_ids": []}
    refuse(lambda: bind_artifacts(r, tmp_path, [b2, dict(b2)]), "P254:unknown_or_duplicate:entry_id")
    b3 = {"entry_id": 42, "artifact_path": "data", "row_ids": [], "project_ids": []}
    refuse(lambda: bind_artifacts(r, tmp_path, [b3]), "P254:unknown_or_duplicate:entry_id")


def test_pin_rowids_validation(tmp_path):
    r = bound_register()

    def b(**kw):
        x = {"entry_id": "a", "artifact_path": "data", "row_ids": [], "project_ids": []}
        x.update(kw)
        return x

    refuse(lambda: bind_artifacts(r, tmp_path, [b(row_ids="r1")]), "P254:bad_type:row_ids")
    refuse(lambda: bind_artifacts(r, tmp_path, [b(row_ids=["r1", "r1"])]), "P254:bad_type:row_ids")
    refuse(lambda: bind_artifacts(r, tmp_path, [b(row_ids=[42])]), "P254:bad_type:row_ids")
    refuse(lambda: bind_artifacts(r, tmp_path, [b(row_ids=["x" * 129])]), "P254:bad_type:row_ids")
    refuse(lambda: bind_artifacts(r, tmp_path, [b(row_ids=["a\nb"])]), "P254:bad_type:row_ids")
    refuse(lambda: bind_artifacts(r, tmp_path, [b(row_ids=["  "])]), "P254:bad_type:row_ids")
    refuse(lambda: bind_artifacts(r, tmp_path, [b(row_ids=["r%d" % i for i in range(1001)])]),
           "P254:bad_type:row_ids")
    refuse(lambda: bind_artifacts(r, tmp_path, [b(project_ids="p")]), "P254:bad_type:project_ids")


def test_pin_source_reader_bounded_bytes(tmp_path):
    # del_fetched_type_cap: an injected reader returning non-bytes or
    # over-budget bytes must fail the binding, never VERIFIED.
    (tmp_path / "data").write_bytes(b'{"x": 1}\n')
    r = bound_register()
    b = [{"entry_id": "a", "artifact_path": "data", "row_ids": [], "project_ids": []}]
    out = bind_artifacts(r, tmp_path, b, source_reader=lambda s, ref: "not-bytes")
    row = out["entries"][0]
    assert row["provenance"] == "UNVERIFIED"
    assert "read failed" in row["reason"]
    out = bind_artifacts(r, tmp_path, b, source_reader=lambda s, ref: b"x" * (8_000_001))
    row = out["entries"][0]
    assert row["provenance"] == "UNVERIFIED"
    assert "read failed" in row["reason"]


def test_pin_empty_content_match_excluded(tmp_path):
    # del_empty_match_exclusion: empty artifact + empty fetched bytes is
    # NOT a byte match; it is flagged empty_content_match and stays
    # UNVERIFIED.
    (tmp_path / "data").write_bytes(b"")
    r = bound_register()
    b = [{"entry_id": "a", "artifact_path": "data", "row_ids": [], "project_ids": []}]
    out = bind_artifacts(r, tmp_path, b, source_reader=lambda s, ref: b"")
    row = out["entries"][0]
    assert row["source_bytes_match"] is False
    assert row["empty_content_match"] is True
    assert row["provenance"] == "UNVERIFIED"


# --- reader: empty content refusal (del_empty_content)

def test_pin_reader_empty_content():
    out = count_records(io.BytesIO(b""), "jsonl")
    assert out["status"] == "UNVERIFIED"
    assert out["reason"] == "empty content"
    out = count_records(io.BytesIO(b"  \n\t "), "csv")
    assert out["status"] == "UNVERIFIED"
    assert out["reason"] == "empty content"
    out = check_declared(io.BytesIO(b""), "jsonl", 0)
    assert out["status"] == "UNVERIFIED"
