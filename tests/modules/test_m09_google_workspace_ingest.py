"""M09 Google Docs/Sheets export ingestion tests. Hermetic, no network.

The Service double records calls and enforces optimistic versions exactly
like the production Service boundary; the ingest module under test is the
real production module. pydantic-free: factories are injected, matching the
call shape the real Service uses.
"""
import hashlib
from types import SimpleNamespace

import pytest

from app.modules.m09_knowledge_workspace import google_workspace_ingest as ing

DOC = b"My Research Notes\n\nSecond line of the doc.\n"
DOC_V2 = b"My Research Notes\n\nSecond line, revised.\n"


class ConflictError(RuntimeError):
    pass


class FakeNode:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class ServiceDouble:
    def __init__(self):
        self.nodes = []
        self.calls = []
        self._next = 0
        self.after_read = None

    class _Repo:
        def get_by_source(self, source_module, external_id):
            n = next((n for n in self.outer.nodes
                      if getattr(n, "source_module", None) == source_module
                      and getattr(n, "external_id", None) == external_id), None)
            snap = FakeNode(**dict(n.__dict__)) if n is not None else None
            if self.outer.after_read is not None:
                self.outer.after_read()
            return snap

        def __init__(self, outer):
            self.outer = outer

        def list_nodes(self):
            snap = [FakeNode(**dict(n.__dict__)) for n in self.outer.nodes]
            if self.outer.after_read is not None:
                self.outer.after_read()
            return snap

    @property
    def repository(self):
        return self._Repo(self)

    def create_node(self, data):
        self.calls.append(("create", data))
        self._next += 1
        node = FakeNode(id=f"n{self._next}", version=1, **data)
        self.nodes.append(node)
        return node

    def update_node(self, node_id, data):
        self.calls.append(("update", node_id, data))
        node = next(n for n in self.nodes if n.id == node_id)
        if node.version != data["expected_version"]:
            raise ConflictError("node changed; refresh before editing")
        for key, value in data.items():
            if key != "expected_version" and value is not None:
                setattr(node, key, value)
        node.version += 1
        return node


def ingest(svc, **kw):
    return ing.ingest_export(svc, node_create=lambda **k: dict(k),
                             node_update=lambda **k: dict(k), **kw)


def test_create_text_doc_hash_bound():
    svc = ServiceDouble()
    out = ingest(svc, document_id="doc-1", export_bytes=DOC, export_format="text")
    assert out["status"] == "created"
    assert out["source_sha256"] == hashlib.sha256(DOC).hexdigest()
    node = svc.nodes[0]
    assert (node.node_type, node.source_module, node.external_id) == ("file", "google_docs", "doc-1")
    assert node.metadata["revision"] == 1
    assert node.body == "My Research Notes\nSecond line of the doc."


def test_changed_bytes_create_revision_via_optimistic_version():
    svc = ServiceDouble()
    ingest(svc, document_id="doc-1", export_bytes=DOC, export_format="text")
    out = ingest(svc, document_id="doc-1", export_bytes=DOC_V2, export_format="text")
    assert out["status"] == "updated" and out["version"] == 2
    node = svc.nodes[0]
    assert node.metadata["revision"] == 2
    assert node.metadata["previous_sha256"] == hashlib.sha256(DOC).hexdigest()
    assert node.metadata["source_sha256"] == hashlib.sha256(DOC_V2).hexdigest()
    assert [c[0] for c in svc.calls] == ["create", "update"]


def test_identical_bytes_are_reported_noop_without_writes():
    svc = ServiceDouble()
    ingest(svc, document_id="doc-1", export_bytes=DOC, export_format="text")
    out = ingest(svc, document_id="doc-1", export_bytes=DOC, export_format="text")
    assert out["status"] == "noop"
    assert len(svc.calls) == 1


def test_sheet_csv_rows_cols_and_rendering():
    svc = ServiceDouble()
    ingest(svc, document_id="sheet-9", export_bytes=b"name,score\nalpha, 3\nbeta, 4\n",
           export_format="csv")
    node = svc.nodes[0]
    assert node.source_module == "google_sheets"
    assert (node.metadata["sheet_rows"], node.metadata["sheet_cols_max"]) == (3, 2)
    assert "alpha | 3" in node.body


def test_html_export_strips_markup_and_drops_script_style():
    svc = ServiceDouble()
    html = (b"<html><head><style>.x{}</style><script>bad()</script></head>"
            b"<body><h1>Title</h1><p>one <b>two</b></p></body></html>")
    ingest(svc, document_id="doc-h", export_bytes=html, export_format="html")
    body = svc.nodes[0].body
    assert "Title" in body and "one two" in body
    assert "bad()" not in body and ".x{}" not in body and "<p>" not in body


@pytest.mark.parametrize("kw,code", [
    (dict(document_id="bad id!", export_bytes=b"x", export_format="text"), "bad_document_id"),
    (dict(document_id="d", export_bytes=b"", export_format="text"), "empty_export"),
    (dict(document_id="d", export_bytes=b"x" * (ing.MAX_BYTES + 1), export_format="text"), "export_too_large"),
    (dict(document_id="d", export_bytes=b"\xff\xfe\x00", export_format="text"), "bad_encoding:text"),
    (dict(document_id="d", export_bytes=b"   ", export_format="text"), "empty_extraction"),
    (dict(document_id="d", export_bytes=b"x", export_format="pdf"), "bad_format:pdf"),
])
def test_coded_refusals_write_nothing(kw, code):
    svc = ServiceDouble()
    with pytest.raises(ing.IngestError, match=f"M09INGEST:{code}"):
        ingest(svc, **kw)
    assert svc.calls == []


def test_stale_version_conflict_propagates():
    svc = ServiceDouble()
    ingest(svc, document_id="doc-1", export_bytes=DOC, export_format="text")

    def concurrent_edit():
        svc.nodes[0].version = 7  # lands between the ingest read and its update

    svc.after_read = concurrent_edit
    with pytest.raises(ConflictError):
        ingest(svc, document_id="doc-1", export_bytes=DOC_V2, export_format="text")


def test_existing_beyond_first500_is_noop_not_unique_violation():
    svc = ServiceDouble()
    seed = ingest(svc, document_id="doc-target", export_bytes=b"same bytes",
                  export_format="text")
    assert seed["status"] == "created"
    # 600 unrelated nodes push the match beyond any list_nodes(limit=500) scan
    for i in range(600):
        svc.nodes.append(SimpleNamespace(
            id=f"other-{i}", source_module="google_docs", external_id=f"doc{i}",
            metadata={}, version=1))
    again = ingest(svc, document_id="doc-target", export_bytes=b"same bytes",
                   export_format="text")
    assert again["status"] == "noop" and again["node_id"] == seed["node_id"]
    changed = ingest(svc, document_id="doc-target", export_bytes=b"changed bytes",
                     export_format="text")
    assert changed["status"] == "updated" and changed["node_id"] == seed["node_id"]
