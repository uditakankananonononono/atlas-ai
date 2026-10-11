"""Export file adapter: boundary and exact-string pins (tests only, module unchanged).

Pins exact limits, messages, payload keys and refusal paths of the module as it is. These are
synthetic-file checks; no real platform export was used and nothing here proves a whole export
was read correctly.
"""
import asyncio
import json
import os

import pytest

import app.collectors.export_file_adapters as mod
from app.collectors.export_file_adapters import ExportAdapterError, ExportFileCollector

run = lambda cfg: asyncio.run(ExportFileCollector().collect(cfg))


def write(tmp_path, data, name="e.csv"):
    p = tmp_path / name
    p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return str(p)


def cfg(path, fmt="csv", **kw):
    base = {"path": path, "format": fmt,
            "mapping": {"url": "link", "external_id": "id", "fields": {"when": "date"}}}
    base.update(kw)
    return base


def csv_rows(n):
    return "id,link,date\n" + "".join(f"{i},https://example.org/{i},d\n" for i in range(n))


def jsonl_rows(n):
    return "".join(json.dumps({"id": i, "link": f"https://example.org/{i}", "date": "d"}) + "\n" for i in range(n))


def json_rows(n):
    return json.dumps([{"id": i, "link": f"https://example.org/{i}", "date": "d"} for i in range(n)])


def msg(path, **kw):
    with pytest.raises(ExportAdapterError) as ei:
        run(cfg(path, **kw))
    return str(ei.value)


# --- defaults (module lines 24-25) ------------------------------------------------------------
def test_default_limits_are_exact():
    assert mod.DEFAULT_MAX_BYTES == 268435456 == 256 * 1024 * 1024
    assert mod.DEFAULT_MAX_RECORDS == 500000


def test_defaults_are_applied_when_the_keys_are_absent(tmp_path):
    c = mod._validate(cfg(write(tmp_path, csv_rows(1))))
    assert c["max_bytes"] == 268435456 and c["max_records"] == 500000
    assert c["limit"] is None and c["cursor"] == 0


def test_no_limit_emits_every_accepted_record_and_no_cursor(tmp_path):
    b = run(cfg(write(tmp_path, csv_rows(7))))
    assert len(b.items) == 7 and b.cursor is None


# --- max_bytes: pre-check and post-read are both exact (lines 111, 114, 115) -------------------
@pytest.mark.parametrize("fmt,name,body", [("csv", "e.csv", csv_rows(1)), ("jsonl", "e.jsonl", jsonl_rows(1)),
                                           ("json", "e.json", json_rows(1))])
def test_max_bytes_exact_size_is_accepted_and_one_more_is_refused(tmp_path, fmt, name, body):
    data = body.encode()
    n = len(data)
    ok = run(cfg(write(tmp_path, data, name), fmt, max_bytes=n))
    assert ok.detail["file_bytes"] == n
    assert msg(write(tmp_path, data + b" ", name), fmt=fmt, max_bytes=n) == f"file larger than max_bytes={n}"


def test_max_bytes_pre_check_refuses_before_reading(tmp_path, monkeypatch):
    p = write(tmp_path, b"x" * 11)
    opened = []
    real = open
    monkeypatch.setattr("builtins.open", lambda *a, **k: (opened.append(a), real(*a, **k))[1])
    with pytest.raises(ExportAdapterError) as ei:
        mod._read_bytes(p, 10)
    assert str(ei.value) == "file larger than max_bytes=10" and opened == []


def test_max_bytes_post_read_refuses_when_the_file_grows_after_the_size_check(tmp_path, monkeypatch):
    """getsize lies (file grew after the check): the bounded read still refuses at max_bytes + 1."""
    p = write(tmp_path, b"x" * 11)
    monkeypatch.setattr(os.path, "getsize", lambda _p: 10)
    with pytest.raises(ExportAdapterError) as ei:
        mod._read_bytes(p, 10)
    assert str(ei.value) == "file larger than max_bytes=10"


def test_max_bytes_post_read_accepts_exactly_max_bytes_when_getsize_understates(tmp_path, monkeypatch):
    p = write(tmp_path, b"a,b\n")
    monkeypatch.setattr(os.path, "getsize", lambda _p: 0)
    assert mod._read_bytes(p, 4) == b"a,b\n"


def test_read_is_bounded_to_max_bytes_plus_one(tmp_path, monkeypatch):
    p = write(tmp_path, b"x" * 50)
    monkeypatch.setattr(os.path, "getsize", lambda _p: 0)
    with pytest.raises(ExportAdapterError):
        mod._read_bytes(p, 10)


# --- max_records: exact accept, +1 refuse (lines 139, 153, 166) --------------------------------
@pytest.mark.parametrize("fmt,name,rows", [("csv", "e.csv", csv_rows), ("jsonl", "e.jsonl", jsonl_rows),
                                           ("json", "e.json", json_rows)])
def test_max_records_exact_is_accepted_and_one_more_is_refused(tmp_path, fmt, name, rows):
    assert len(run(cfg(write(tmp_path, rows(3), name), fmt, max_records=3)).items) == 3
    assert msg(write(tmp_path, rows(4), name), fmt=fmt, max_records=3) == "more than max_records=3 records"


def test_jsonl_blank_lines_do_not_count_toward_max_records(tmp_path):
    body = jsonl_rows(3).replace("\n", "\n\n")
    assert len(run(cfg(write(tmp_path, body, "e.jsonl"), "jsonl", max_records=3)).items) == 3


# --- text and syntax errors (lines 126, 143) ------------------------------------------------------
def test_invalid_utf8_is_refused_with_the_exact_message(tmp_path):
    assert msg(write(tmp_path, b"id,link,date\n\xff\xfe,x,y\n")) == "file is not valid UTF-8"


def test_malformed_csv_message_has_the_invalid_csv_prefix(tmp_path):
    text = "id,link,date\n1," + "x" * 200000 + ",d\n"
    m = msg(write(tmp_path, text))
    assert m == "invalid CSV: field larger than field limit (131072)"


def test_csv_missing_column_message_is_not_the_invalid_csv_prefix(tmp_path):
    assert msg(write(tmp_path, "id,link\n1,https://example.org/a\n")) == "column 'date' not found in the CSV header"


# --- continue: a rejected record never becomes an item (line 210) ---------------------------------
def test_record_without_external_id_is_rejected_and_skipped_not_emitted(tmp_path):
    body = "id,link,date\n,https://example.org/a,d\n2,https://example.org/b,d\n"
    b = run(cfg(write(tmp_path, body)))
    assert [i.external_id for i in b.items] == ["2"]
    assert b.detail["records_rejected"] == 1
    assert b.detail["rejected"] == [{"index": 0, "reason": "missing external_id"}]


def test_whitespace_only_external_id_is_rejected_and_the_loop_continues(tmp_path):
    body = "id,link,date\n   ,https://example.org/a,d\n5,https://example.org/b,d\n"
    b = run(cfg(write(tmp_path, body)))
    assert [i.external_id for i in b.items] == ["5"]
    assert b.detail["rejected"] == [{"index": 0, "reason": "missing external_id"}]


# --- nested JSON path: index must be < len (line 49) ------------------------------------------------
def test_dig_index_equal_to_list_length_is_missing():
    assert mod._dig({"a": [10, 20]}, "a.1") == 20
    assert mod._dig({"a": [10, 20]}, "a.2") is mod._MISSING
    assert mod._dig({"a": []}, "a.0") is mod._MISSING


def test_record_path_index_equal_to_length_is_refused(tmp_path):
    p = write(tmp_path, json.dumps({"x": [json_rows(1)]}), "e.json")
    assert msg(p, fmt="json", record_path="x.1") == "record_path 'x.1' not found"


def test_record_path_last_valid_index_is_read(tmp_path):
    p = write(tmp_path, json.dumps({"x": [[], json.loads(json_rows(2))]}), "e.json")
    assert len(run(cfg(p, "json", record_path="x.1")).items) == 2


# --- _pos_int default minimum (line 39) ---------------------------------------------------------------
def test_pos_int_default_minimum_is_one():
    assert mod._pos_int("n", 1) == 1
    with pytest.raises(ExportAdapterError) as ei:
        mod._pos_int("n", 0)
    assert str(ei.value) == "n must be an integer >= 1"
    assert mod._pos_int("n", 0, 0) == 0


@pytest.mark.parametrize("key", ["max_bytes", "max_records", "limit"])
def test_zero_is_refused_for_the_size_and_page_keys(tmp_path, key):
    with pytest.raises(ExportAdapterError) as ei:
        mod._validate(cfg(write(tmp_path, csv_rows(1)), **{key: 0}))
    assert str(ei.value) == f"{key} must be an integer >= 1"


def test_cursor_zero_is_allowed_and_negative_is_refused(tmp_path):
    p = write(tmp_path, csv_rows(1))
    assert mod._validate(cfg(p, cursor=0))["cursor"] == 0
    with pytest.raises(ExportAdapterError) as ei:
        mod._validate(cfg(p, cursor=-1))
    assert str(ei.value) == "cursor must be a non-negative integer (or its string form)"


# --- exact payload keys (line 218-222) ----------------------------------------------------------------------
def test_provenance_keys_are_exactly_these(tmp_path):
    b = run(cfg(write(tmp_path, csv_rows(1)), kind="like", platform="x"))
    assert list(b.items[0].payload) == ["provider", "source_file", "record_index", "kind", "platform", "when"]
    assert b.items[0].payload["provider"] == "export_file"
    assert b.items[0].payload["kind"] == "like" and b.items[0].payload["platform"] == "x"


def test_payload_without_labels_has_no_kind_or_platform(tmp_path):
    b = run(cfg(write(tmp_path, csv_rows(1))))
    assert list(b.items[0].payload) == ["provider", "source_file", "record_index", "when"]


def test_reserved_names_are_exactly_these():
    assert mod.RESERVED == frozenset({"provider", "source_file", "record_index", "kind", "platform"})


@pytest.mark.parametrize("name", ["provider", "source_file", "record_index", "kind", "platform"])
def test_each_reserved_output_name_is_refused(tmp_path, name):
    c = cfg(write(tmp_path, csv_rows(1)))
    c["mapping"]["fields"] = {name: "date"}
    with pytest.raises(ExportAdapterError) as ei:
        mod._validate(c)
    assert str(ei.value) == f"mapping.fields uses reserved output name(s) ['{name}']"


# --- archives: each extension refused, and the magic bytes (line 117-118) --------------------------------
ARCHIVE_MSG = "archives are not read; extract the export and pass the file inside"


def test_archive_suffix_list_is_exactly_these():
    assert mod._ARCHIVE_SUFFIXES == (".zip", ".gz", ".tgz", ".tar", ".7z", ".rar")


@pytest.mark.parametrize("ext", [".zip", ".gz", ".tgz", ".tar", ".7z", ".rar"])
def test_each_archive_extension_is_refused_even_with_valid_csv_content(tmp_path, ext):
    assert msg(write(tmp_path, csv_rows(1), "export" + ext)) == ARCHIVE_MSG


@pytest.mark.parametrize("ext", [".ZIP", ".Tar.GZ", ".TGZ"])
def test_archive_suffix_check_is_case_insensitive(tmp_path, ext):
    assert msg(write(tmp_path, csv_rows(1), "export" + ext)) == ARCHIVE_MSG


def test_pk_magic_bytes_are_refused_without_an_archive_suffix(tmp_path):
    assert msg(write(tmp_path, b"PK\x03\x04" + csv_rows(1).encode())) == ARCHIVE_MSG


def test_non_archive_suffix_is_not_refused(tmp_path):
    assert len(run(cfg(write(tmp_path, csv_rows(1), "export.csv.txt"))).items) == 1


# --- page slice (line 239) is documented equivalent: no pin beyond behaviour --------------------------
def test_page_beyond_the_end_is_empty_with_no_cursor(tmp_path):
    b = run(cfg(write(tmp_path, csv_rows(3)), cursor=3, limit=2))
    assert b.items == [] and b.cursor is None


def test_read_asks_for_exactly_max_bytes_plus_one_byte(tmp_path, monkeypatch):
    """The bound on the read itself: max_bytes + 1, so an oversize file is seen without reading it all."""
    p = write(tmp_path, b"x" * 50)
    sizes = []
    real = open

    class Spy:
        def __init__(self, fh):
            self._fh = fh

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self._fh.close()

        def read(self, n=-1):
            sizes.append(n)
            return self._fh.read(n)

    monkeypatch.setattr("builtins.open", lambda *a, **k: Spy(real(*a, **k)))
    monkeypatch.setattr(os.path, "getsize", lambda _p: 0)
    with pytest.raises(ExportAdapterError):
        mod._read_bytes(p, 10)
    assert sizes == [11]


# --- rejection reasons and detail keys (exact strings) ----------------------------------------------
def test_rejection_reasons_are_exact_strings(tmp_path):
    body = ("id,link,date\n"
            "1,ftp://example.org/a,d\n"
            "2,https://example.org/b,d\n"
            "2,https://example.org/c,d\n"
            "3,,d\n")
    b = run(cfg(write(tmp_path, body)))
    assert b.detail["rejected"] == [
        {"index": 0, "reason": "url must start with http:// or https://"},
        {"index": 2, "reason": "duplicate external_id"},
        {"index": 3, "reason": "missing url"},
    ]


def test_detail_keys_are_exactly_these(tmp_path):
    b = run(cfg(write(tmp_path, csv_rows(2))))
    assert list(b.detail) == ["format", "file_bytes", "file_sha256", "records_read", "records_accepted_in_file",
                              "records_emitted", "records_rejected", "rejected", "layout_verified"]
    assert b.detail["format"] == "csv" and b.detail["records_accepted_in_file"] == 2


def test_known_config_keys_are_exactly_these():
    assert mod._CONFIG_KEYS == {"path", "format", "mapping", "record_path", "limit", "cursor", "max_bytes",
                                "max_records", "kind", "platform"}


def test_cursor_string_form_is_accepted(tmp_path):
    b = run(cfg(write(tmp_path, csv_rows(3)), cursor="1", limit=1))
    assert [i.external_id for i in b.items] == ["1"] and b.cursor == "2"
