"""Offline export-file adapter: caller-supplied CSV/JSON/JSONL path plus explicit column mapping."""
import ast
import asyncio
import hashlib
import inspect
import json
import socket

import pytest

import app.collectors.export_file_adapters as mod
from app.collectors.base import CollectionBatch
from app.collectors.export_file_adapters import ExportAdapterError, ExportFileCollector

run = lambda cfg: asyncio.run(ExportFileCollector().collect(cfg))


def csv_file(tmp_path, text, name="e.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def cfg(path, **kw):
    base = {"path": path, "format": "csv", "mapping": {"url": "link", "external_id": "id",
                                                          "fields": {"when": "date", "etype": "type"}}}
    base.update(kw)
    return base


CSV = "id,link,date,type\n1,https://example.org/a,2026-01-01,like\n2,https://example.org/b,2026-01-02,like\n"


def test_csv_basic_mapping(tmp_path):
    b = run(cfg(csv_file(tmp_path, CSV)))
    assert isinstance(b, CollectionBatch) and b.requests == 0 and b.cursor is None
    assert [i.external_id for i in b.items] == ["1", "2"]
    assert b.items[0].canonical_url == "https://example.org/a"
    assert b.items[0].payload["when"] == "2026-01-01" and b.items[0].payload["provider"] == "export_file"
    assert b.items[0].payload["record_index"] == 0
    assert b.detail["records_read"] == 2 and b.detail["records_emitted"] == 2 and b.detail["records_rejected"] == 0
    assert b.detail["layout_verified"] is False


def test_payload_and_detail_do_not_leak_directory(tmp_path):
    p = csv_file(tmp_path, CSV)
    b = run(cfg(p))
    blob = json.dumps([i.payload for i in b.items]) + json.dumps(b.detail)
    assert str(tmp_path) not in blob
    assert b.items[0].payload["source_file"] == "e.csv"
    assert b.detail["file_sha256"] == hashlib.sha256(open(p, "rb").read()).hexdigest()


def test_csv_bom_and_quoted_fields(tmp_path):
    p = tmp_path / "b.csv"
    p.write_bytes(b"\xef\xbb\xbfid,link,date,type\n1,https://example.org/a,\"a, b\",like\n")
    b = run(cfg(str(p)))
    assert b.items[0].payload["when"] == "a, b"


def test_missing_mapped_column_is_an_error_naming_it(tmp_path):
    with pytest.raises(ExportAdapterError, match="column 'link'"):
        run(cfg(csv_file(tmp_path, "id,date,type\n1,x,y\n")))


def test_json_array_nested_dotted_paths(tmp_path):
    rows = [{"id": "a", "t": {"href": "https://example.org/x", "when": [5, 6]}},
            {"id": "b", "t": {"href": "https://example.org/y", "when": [7]}}]
    p = tmp_path / "e.json"
    p.write_text(json.dumps(rows))
    b = run({"path": str(p), "format": "json",
             "mapping": {"url": "t.href", "external_id": "id", "fields": {"w": "t.when.0"}}})
    assert [i.payload["w"] for i in b.items] == [5, 7]


def test_json_record_path_and_jsonl(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"data": {"items": [{"u": "https://example.org/1"}]}}))
    b = run({"path": str(p), "format": "json", "record_path": "data.items", "mapping": {"url": "u"}})
    assert len(b.items) == 1
    q = tmp_path / "e.jsonl"
    q.write_text('{"u":"https://example.org/1"}\n\n{"u":"https://example.org/2"}\n')
    assert len(run({"path": str(q), "format": "jsonl", "mapping": {"url": "u"}}).items) == 2


def test_bad_json_shapes_are_errors(tmp_path):
    p = tmp_path / "e.json"
    p.write_text("not json")
    with pytest.raises(ExportAdapterError, match="valid JSON"):
        run({"path": str(p), "format": "json", "mapping": {"url": "u"}})
    p.write_text('{"a": 1}')
    with pytest.raises(ExportAdapterError, match="list"):
        run({"path": str(p), "format": "json", "mapping": {"url": "u"}})
    q = tmp_path / "e.jsonl"
    q.write_text('{"u":"https://example.org/1"}\nnope\n')
    with pytest.raises(ExportAdapterError, match="line 2"):
        run({"path": str(q), "format": "jsonl", "mapping": {"url": "u"}})


def test_rejected_rows_are_counted_with_reasons(tmp_path):
    text = ("id,link,date,type\n1,https://example.org/a,d,t\n2,javascript:alert(1),d,t\n"
            "3,,d,t\n1,https://example.org/dup,d,t\n4,ftp://example.org/x,d,t\n")
    b = run(cfg(csv_file(tmp_path, text)))
    assert [i.external_id for i in b.items] == ["1"]
    assert b.detail["records_read"] == 5 and b.detail["records_rejected"] == 4
    reasons = {r["index"]: r["reason"] for r in b.detail["rejected"]}
    assert set(reasons) == {1, 2, 3, 4}
    assert "http" in reasons[1] and "url" in reasons[2] and "duplicate" in reasons[3]


def test_json_non_object_record_rejected(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps([{"u": "https://example.org/1"}, 7, "x"]))
    b = run({"path": str(p), "format": "json", "mapping": {"url": "u"}})
    assert len(b.items) == 1 and b.detail["records_rejected"] == 2


def test_derived_external_id_is_deterministic_and_row_specific(tmp_path):
    q = tmp_path / "e.jsonl"
    q.write_text('{"u":"https://example.org/1","k":"a"}\n{"u":"https://example.org/1","k":"b"}\n')
    c = {"path": str(q), "format": "jsonl", "mapping": {"url": "u", "fields": {"k": "k"}}}
    ids1 = [i.external_id for i in run(c).items]
    ids2 = [i.external_id for i in run(c).items]
    assert ids1 == ids2 and len(set(ids1)) == 2 and all(len(x) == 16 for x in ids1)


def test_paging_cursor_covers_every_record_once(tmp_path):
    rows = "id,link,date,type\n" + "".join(f"{i},https://example.org/{i},d,t\n" for i in range(7))
    p = csv_file(tmp_path, rows)
    seen, cur, calls = [], None, 0
    while True:
        c = cfg(p, limit=3)
        if cur is not None:
            c["cursor"] = cur
        b = run(c)
        calls += 1
        seen += [i.external_id for i in b.items]
        cur = b.cursor
        if cur is None:
            break
    assert seen == [str(i) for i in range(7)] and calls == 3
    with pytest.raises(ExportAdapterError, match="cursor"):
        run(cfg(p, cursor="abc"))
    with pytest.raises(ExportAdapterError, match="cursor"):
        run(cfg(p, cursor="-1"))
    assert run(cfg(p, cursor="99")).items == []
    with pytest.raises(ExportAdapterError, match="limit"):
        run(cfg(p, limit=0))


@pytest.mark.parametrize("patch,match", [
    ({"format": "xml"}, "format"),
    ({"bogus": 1}, "unknown config key"),
    ({"profile": "linkedin"}, "unknown config key"),
    ({"mapping": {}}, "url"),
    ({"mapping": {"url": "link", "extra": "x"}}, "unknown mapping key"),
    ({"mapping": {"url": "link", "fields": {"provider": "date"}}}, "reserved"),
    ({"mapping": {"url": "link", "fields": "x"}}, "fields"),
    ({"max_bytes": 5}, "max_bytes"),
    ({"max_records": 1}, "max_records"),
])
def test_config_validation(tmp_path, patch, match):
    with pytest.raises(ExportAdapterError, match=match):
        run(cfg(csv_file(tmp_path, CSV), **patch))


def test_path_validation(tmp_path):
    with pytest.raises(ExportAdapterError, match="not found"):
        run(cfg(str(tmp_path / "nope.csv")))
    with pytest.raises(ExportAdapterError, match="regular file"):
        run(cfg(str(tmp_path)))
    with pytest.raises(ExportAdapterError, match="path"):
        run({"format": "csv", "mapping": {"url": "link"}})
    z = tmp_path / "x.zip"
    z.write_bytes(b"PK\x03\x04")
    with pytest.raises(ExportAdapterError, match="extract"):
        run(cfg(str(z)))


def test_empty_and_header_only_files(tmp_path):
    b = run(cfg(csv_file(tmp_path, "id,link,date,type\n")))
    assert b.items == [] and b.detail["records_read"] == 0
    with pytest.raises(ExportAdapterError, match="column"):
        run(cfg(csv_file(tmp_path, "", "empty.csv")))


def test_works_with_all_network_blocked_and_module_imports_no_network_library(tmp_path, monkeypatch):
    def deny(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)
    assert len(run(cfg(csv_file(tmp_path, CSV))).items) == 2
    tree = ast.parse(inspect.getsource(mod))
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0:
            names.add((n.module or "").split(".")[0])
    assert not names & {"httpx", "requests", "urllib", "socket", "http", "aiohttp", "subprocess", "webbrowser"}


def test_no_named_profiles_are_shipped():
    assert mod.PROFILES == {}


def test_read_is_non_mutating(tmp_path):
    p = csv_file(tmp_path, CSV)
    before = open(p, "rb").read()
    run(cfg(p))
    assert open(p, "rb").read() == before and sorted(x.name for x in tmp_path.iterdir()) == ["e.csv"]


def test_http_scheme_accepted_and_url_whitespace_stripped(tmp_path):
    p = csv_file(tmp_path, "id,link,date,type\n1,  http://example.org/a  ,d,t\n")
    b = run(cfg(p))
    assert b.items[0].canonical_url == "http://example.org/a"


def test_limit_and_cursor_reject_booleans(tmp_path):
    p = csv_file(tmp_path, CSV)
    with pytest.raises(ExportAdapterError, match="limit"):
        run(cfg(p, limit=True))
    with pytest.raises(ExportAdapterError, match="cursor"):
        run(cfg(p, cursor=True))


def test_size_guard_holds_even_if_stat_lies(tmp_path, monkeypatch):
    p = csv_file(tmp_path, CSV)
    monkeypatch.setattr(mod.os.path, "getsize", lambda _p: 0)
    with pytest.raises(ExportAdapterError, match="max_bytes"):
        run(cfg(p, max_bytes=10))


def test_archives_detected_by_content_and_by_suffix(tmp_path):
    magic = tmp_path / "looks_like_csv.csv"
    magic.write_bytes(b"PK\x03\x04rest")
    with pytest.raises(ExportAdapterError, match="extract"):
        run(cfg(str(magic)))
    suffix = tmp_path / "x.tar.gz"
    suffix.write_bytes(b"id,link\n")
    with pytest.raises(ExportAdapterError, match="extract"):
        run(cfg(str(suffix)))


def test_max_records_enforced_for_json_and_jsonl(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps([{"u": "https://example.org/1"}, {"u": "https://example.org/2"}]))
    with pytest.raises(ExportAdapterError, match="max_records"):
        run({"path": str(p), "format": "json", "mapping": {"url": "u"}, "max_records": 1})
    q = tmp_path / "e.jsonl"
    q.write_text('{"u":"https://example.org/1"}\n{"u":"https://example.org/2"}\n')
    with pytest.raises(ExportAdapterError, match="max_records"):
        run({"path": str(q), "format": "jsonl", "mapping": {"url": "u"}, "max_records": 1})


def test_record_path_not_found_message(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"a": []}))
    with pytest.raises(ExportAdapterError, match="record_path 'b.c' not found"):
        run({"path": str(p), "format": "json", "record_path": "b.c", "mapping": {"url": "u"}})


def test_exact_rejection_reasons(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps([7, {"x": 1}, {"u": "https://example.org/1", "id": None},
                             {"u": "https://example.org/2", "id": "  "}, {"u": "https://example.org/3", "id": {"a": 1}}]))
    b = run({"path": str(p), "format": "json", "mapping": {"url": "u", "external_id": "id"}})
    assert [r["reason"] for r in b.detail["rejected"]] == [
        "record is not an object", "missing url", "missing external_id", "missing external_id", "missing external_id"]


def test_rejected_list_is_capped_but_count_is_not(tmp_path):
    rows = "id,link,date,type\n" + "".join(f"{i},nope,d,t\n" for i in range(60))
    b = run(cfg(csv_file(tmp_path, rows)))
    assert b.detail["records_rejected"] == 60 and len(b.detail["rejected"]) == 50


def test_kind_and_platform_labels_are_carried_and_validated(tmp_path):
    p = csv_file(tmp_path, CSV)
    b = run(cfg(p, kind="like", platform="example"))
    assert b.items[0].payload["kind"] == "like" and b.items[0].payload["platform"] == "example"
    assert "kind" not in run(cfg(p)).items[0].payload
    with pytest.raises(ExportAdapterError, match="kind"):
        run(cfg(p, kind=""))
    with pytest.raises(ExportAdapterError, match="platform"):
        run(cfg(p, platform=3))


def test_unknown_config_key_names_the_key(tmp_path):
    with pytest.raises(ExportAdapterError, match=r"unknown config key\(s\) \['zzz'\]"):
        run(cfg(csv_file(tmp_path, CSV), zzz=1))


def test_oversized_file_is_refused_before_it_is_opened(tmp_path, monkeypatch):
    p = csv_file(tmp_path, CSV)
    monkeypatch.setattr(mod.os.path, "getsize", lambda _p: 10**12)

    def no_open(*a, **k):
        raise AssertionError("file was opened")

    monkeypatch.setattr("builtins.open", no_open)
    with pytest.raises(ExportAdapterError, match="max_bytes"):
        run(cfg(p))
