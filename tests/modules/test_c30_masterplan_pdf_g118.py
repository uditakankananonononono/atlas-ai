"""G118: rendered pagination and a 5,000+ page PDF masterplan."""
from __future__ import annotations

import re

import pytest

from app.modules.c30 import masterplan_pdf as mp


def _varied_body(n_sentences):
    # deterministic, non-repetitive text: the pinned repetition guard requires
    # unique 200-char windows, so every sentence carries its own index
    return " ".join(
        "Sentence %d records finding %d with measured detail and context."
        % (i, (i * 37) % 1009) for i in range(n_sentences))


def _request(n_sentences, target=5):
    return {"as_of": "2026-10-12", "target_pages": target,
            "volumes": [{"id": "v1", "title": "Research Volume", "sections": [
                {"id": "s1", "heading": "Findings", "body": _varied_body(n_sentences),
                 "source_ref": "notebook/2026-10-12"}]}]}


def test_layout_geometry_is_exact():
    assert mp.CHARS_PER_LINE == int(468 / (0.6 * 11)) == 70
    assert mp.LINES_PER_PAGE == int(648 / 14) == 46


def test_pagination_is_real_wrap_not_estimate():
    pages = mp.paginate("alpha beta gamma\n\n" + "word " * 400, title="T")
    total_lines = sum(len(p) for p in pages)
    wrapped = len(mp._wrap_paragraph("word " * 399 + "word", 70))
    assert total_lines == wrapped + 1 + 1 + 2  # title + blank + blank + body
    assert all(len(p) <= 46 for p in pages)
    assert all(len(line) <= 70 for p in pages for line in p)


def test_pdf_is_structurally_valid_and_self_verified():
    req = _request(600)
    out = mp.assemble_pdf(req, title="Masterplan")
    body = req["volumes"][0]["sections"][0]["body"]
    expected = len(mp.paginate("# Research Volume\n\n## Findings\n\n" + body + "\n",
                               title="Research Volume"))
    assert out["real_page_count"] == expected
    assert out["target_met"] is True
    pdf = out["pdf_bytes"]
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert mp.count_pdf_pages(pdf) == out["real_page_count"]
    m = re.search(rb"startxref\n(\d+)", pdf)
    assert pdf[int(m.group(1)):].startswith(b"xref\n0 ")
    first = pdf.find(b"/Type /Page\x20")
    assert b"/Contents" in pdf[first:first + 200]


def test_pypdf_cross_checks_real_pages_and_text():
    pytest.importorskip("pypdf")
    import io
    import pypdf
    out = mp.assemble_pdf(_request(600))
    reader = pypdf.PdfReader(io.BytesIO(out["pdf_bytes"]))
    assert len(reader.pages) == out["real_page_count"]
    text = reader.pages[0].extract_text()
    assert "RESEARCH VOLUME" in text.upper()
    assert "FINDINGS" in text.upper()


def test_five_thousand_plus_real_pages():
    # one pinned batch caps at 15M body chars (~4.6k dense pages), so the 5,000+
    # page document is bound from two batches - the stated volume model
    out = mp.assemble_pdf_many([_request(200_000), _request(200_000)])
    assert out["batch_count"] == 2
    assert out["real_page_count"] >= 5000
    assert out["target_met"] is True
    assert out["unfilled_count"] == 0
    assert mp.count_pdf_pages(out["pdf_bytes"]) == out["real_page_count"]
    assert out["target_pages"] == 10  # per-batch targets are not summed into a claim


def test_short_content_reports_target_not_met_honestly():
    out = mp.assemble_pdf(_request(50, target=5000))
    assert out["target_met"] is False
    assert out["real_page_count"] < 5000


def test_unsourced_and_unfilled_sections_propagate():
    req = _request(50)
    req["volumes"][0]["sections"].append(
        {"id": "s2", "heading": "Empty", "body": "", "source_ref": ""})
    out = mp.assemble_pdf(req)
    assert out["unfilled_count"] == 1
    statuses = {r["section_id"]: r["status"] for r in out["section_receipts"]}
    assert statuses["s2"] == "unfilled" and statuses["s1"] == "accepted"
