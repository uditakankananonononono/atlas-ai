"""Google Docs/Sheets export ingestion into the knowledge workspace (M09).

Offline and fixture-driven: the caller already holds export BYTES (a Google
Doc exported as text or HTML, a Google Sheet exported as CSV). This module
extracts bounded plain text and imports the document as a tenant-scoped FILE
node through the real Service API - no network, no OAuth, no account access.

Tenant scoping is enforced by the repository the Service was built with; the
import is bound to (source_module, external_id) which the schema constrains
as unique per tenant. The raw-bytes SHA-256 is recorded in node metadata, so
the import is hash-bound to the exact export. Re-ingesting the same document
with changed bytes is a revision: the node is updated through the Service's
optimistic-version path (expected_version), and the superseded content hash
is retained as previous_sha256. Identical bytes are a reported no-op, never
a fabricated revision.

The node factories default to the real .schemas models; they are injectable
so the mechanism can be exercised without the web stack (tests inject the
same call shape the Service uses). HTTP route wiring is intentionally not
included here - that is an integrator decision; the integration seam is the
Service.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from html.parser import HTMLParser

SOURCE_MODULE_GOOGLE_DOCS = "google_docs"
SOURCE_MODULE_GOOGLE_SHEETS = "google_sheets"

MAX_BYTES = 5_000_000        # raw export cap
MAX_BODY_CHARS = 200_000     # stored body cap after extraction
MAX_ROWS = 50_000            # sheet row cap
DOCUMENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
EXPORT_FORMATS = ("text", "html", "csv")


class IngestError(ValueError):
    """Coded ingestion refusal: M09INGEST:<code>."""


def _fail(code):
    raise IngestError(f"M09INGEST:{code}")


def _decode_utf8(data, what):
    try:
        return data.decode("utf-8-sig")
    except (UnicodeDecodeError, ValueError):
        _fail(f"bad_encoding:{what}")


class _TextExtractor(HTMLParser):
    """Visible-text extraction for a Docs HTML export: script/style dropped,
    block tags become newlines, entities handled by the parser."""

    _BLOCK = {"p", "div", "br", "li", "tr", "table", "h1", "h2", "h3", "h4",
              "h5", "h6", "ul", "ol", "blockquote", "section", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _normalize_text(text):
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def extract_google_doc_text(data, export_format):
    """Docs export bytes (text or html) -> bounded visible plain text."""
    if export_format == "text":
        return _normalize_text(_decode_utf8(data, "text"))
    if export_format == "html":
        parser = _TextExtractor()
        try:
            parser.feed(_decode_utf8(data, "html"))
            parser.close()
        except Exception:
            _fail("bad_html:html")
        return _normalize_text("".join(parser.parts))
    _fail(f"bad_format:{export_format}")


def extract_google_sheet_text(data):
    """Sheets CSV export bytes -> (bounded plain text, row_count, col_max).

    The text rendering is one line per row, cells joined with " | " (tabs
    are normalized away by the body normalizer, and commas collide with cell
    content) - stable and greppable; the structured counts ride in node
    metadata."""
    text = _decode_utf8(data, "csv")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) > MAX_ROWS:
        _fail("too_many_rows:csv")
    rendered = [" | ".join(cell.strip() for cell in row) for row in rows]
    col_max = max((len(row) for row in rows), default=0)
    return _normalize_text("\n".join(rendered)), len(rows), col_max


def _title_from(text, fallback):
    for line in text.split("\n"):
        if line.strip():
            return line.strip()[:500]
    return fallback


def ingest_export(service, *, document_id, export_bytes, export_format,
                  source_uri=None, title=None, source_module=None,
                  node_create=None, node_update=None):
    """Import one Google export through the real Service API.

    service: the module Service (tenant-bound via its repository).
    Returns a dict: {status, node_id, version, source_sha256, detail}; status
    is "created", "updated" (a real revision) or "noop" (identical bytes).
    Refusals raise IngestError with a coded message; the Service's
    ConflictError on a stale version propagates unchanged.
    """
    if node_create is None or node_update is None:
        from .schemas import NodeCreate, NodeUpdate  # real models in production
        node_create = node_create or NodeCreate
        node_update = node_update or NodeUpdate
    if source_module is None:
        source_module = (SOURCE_MODULE_GOOGLE_SHEETS if export_format == "csv"
                         else SOURCE_MODULE_GOOGLE_DOCS)
    if type(document_id) is not str or not DOCUMENT_ID_RE.fullmatch(document_id):
        _fail("bad_document_id")
    if export_format not in EXPORT_FORMATS:
        _fail(f"bad_format:{export_format}")
    if type(export_bytes) is not bytes or not export_bytes:
        _fail("empty_export")
    if len(export_bytes) > MAX_BYTES:
        _fail("export_too_large")
    if source_module not in (SOURCE_MODULE_GOOGLE_DOCS, SOURCE_MODULE_GOOGLE_SHEETS):
        _fail("bad_source_module")

    digest = hashlib.sha256(export_bytes).hexdigest()
    sheet_meta = {}
    if export_format == "csv":
        body, rows, cols = extract_google_sheet_text(export_bytes)
        sheet_meta = {"sheet_rows": rows, "sheet_cols_max": cols}
    else:
        body = extract_google_doc_text(export_bytes, export_format)
    if not body:
        _fail("empty_extraction")
    body = body[:MAX_BODY_CHARS]

    # exact repository lookup: no scan cap, so the match cannot spill past
    # a list_nodes limit and turn a no-op/revision into a UNIQUE violation
    existing = service.repository.get_by_source(source_module, document_id)

    if existing is not None and existing.metadata.get("source_sha256") == digest:
        return {"status": "noop", "node_id": existing.id, "version": existing.version,
                "source_sha256": digest, "detail": "identical bytes; no revision created"}

    resolved_title = (title or "").strip() or _title_from(body, f"document {document_id}")
    if existing is None:
        created = service.create_node(node_create(
            node_type="file", title=resolved_title, body=body,
            source_uri=source_uri, source_module=source_module,
            external_id=document_id,
            metadata={"source_sha256": digest, "revision": 1,
                      "export_format": export_format, **sheet_meta}))
        return {"status": "created", "node_id": created.id, "version": created.version,
                "source_sha256": digest, "detail": "imported as a new tenant-scoped node"}

    metadata = dict(existing.metadata)
    metadata.update({"source_sha256": digest,
                     "previous_sha256": existing.metadata.get("source_sha256"),
                     "revision": int(existing.metadata.get("revision", 1)) + 1,
                     "export_format": export_format, **sheet_meta})
    updated = service.update_node(existing.id, node_update(
        title=resolved_title, body=body, metadata=metadata,
        expected_version=existing.version))
    return {"status": "updated", "node_id": updated.id, "version": updated.version,
            "source_sha256": digest,
            "detail": f"revision {metadata['revision']} via optimistic-version update"}


__all__ = ["IngestError", "SOURCE_MODULE_GOOGLE_DOCS", "SOURCE_MODULE_GOOGLE_SHEETS",
           "MAX_BYTES", "MAX_BODY_CHARS", "MAX_ROWS", "EXPORT_FORMATS",
           "extract_google_doc_text", "extract_google_sheet_text", "ingest_export"]
