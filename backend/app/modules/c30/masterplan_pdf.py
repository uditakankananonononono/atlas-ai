"""G118 / c30.masterplan_pdf - rendered pagination and a PDF artifact.

The pinned masterplan.run assembles supplied sections and estimates pages by
character count; 'rendered pagination' is in its not_implemented list. This
module closes that gap: it lays the assembled markdown out on fixed
page geometry (Courier base-14, fixed metrics, so layout is deterministic),
emits a valid PDF (xref table, byte offsets, page tree), and checks its own
output with a strict structural parser that counts page objects. It never
authors research: all text is caller-supplied via the pinned assembler, and
target_met is computed from the counted pages, never asserted. stdlib only,
offline, deterministic.
"""
from __future__ import annotations

import re

from app.modules.c30 import masterplan, policy

PREFIX = "PLANPDF"

# layout geometry: US Letter, 1in margins, Courier 11pt (600/1000 em width
# for every glyph, so line capacity is fixed), 14pt leading.
PAGE_W, PAGE_H = 612.0, 792.0
MARGIN = 72.0
FONT_SIZE = 11.0
LEADING = 14.0
COURIER_EM = 0.6  # every Courier glyph is 600/1000 em
CHARS_PER_LINE = int((PAGE_W - 2 * MARGIN) // (COURIER_EM * FONT_SIZE))  # 70
LINES_PER_PAGE = int((PAGE_H - 2 * MARGIN) // LEADING)  # 46
_BASE14 = "Courier"
_PDF_RE = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _wrap_paragraph(text, width):
    """Greedy word wrap; words longer than the line are hard-split. Real layout."""
    out, cur = [], ""
    for word in text.split(" "):
        while len(word) > width:
            if cur:
                out.append(cur)
                cur = ""
            out.append(word[:width])
            word = word[width:]
        cand = word if not cur else cur + " " + word
        if len(cand) <= width:
            cur = cand
        else:
            out.append(cur)
            cur = word
    if cur or not out:
        out.append(cur)
    return out


def paginate(markdown, title=None):
    """Lay markdown text out on pages. Returns a list of pages of lines."""
    if type(markdown) is not str:
        _refuse("BAD_TYPE", "markdown")
    text = policy.clean_text(markdown, PREFIX, "markdown", 20_000_000, allow_ws=True)
    lines = []
    if title is not None:
        t = policy.clean_text(title, PREFIX, "title", 200)
        lines.extend(_wrap_paragraph(t, CHARS_PER_LINE))
        lines.append("")
    for raw in text.split("\n"):
        para = raw.rstrip()
        if para.startswith("#"):
            para = para.lstrip("#").strip().upper()
        lines.extend(_wrap_paragraph(para, CHARS_PER_LINE) if para else [""])
    pages, i = [], 0
    while i < len(lines) or not pages:
        pages.append(lines[i:i + LINES_PER_PAGE])
        i += LINES_PER_PAGE
        if i >= len(lines):
            break
    return pages


def _escape_pdf_text(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _latin1(s):
    return s.encode("latin-1", "replace").decode("latin-1")


def render_pdf(pages, title="Masterplan"):
    """Serialize pages to a valid PDF with an xref table. Deterministic."""
    if type(pages) is not list or not pages or any(
            type(p) is not list or any(type(l) is not str for l in p) for p in pages):
        _refuse("BAD_TYPE", "pages")
    n = len(pages)
    font_obj = 3
    first_page_obj = 4
    objects = {}

    def obj(num, body):
        objects[num] = body if type(body) is bytes else body.encode("latin-1")

    kids = " ".join("%d 0 R" % (first_page_obj + 2 * i) for i in range(n))
    obj(1, "<< /Type /Catalog /Pages 2 0 R >>")
    obj(2, "<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n))
    obj(font_obj, "<< /Type /Font /Subtype /Type1 /BaseFont /%s >>" % _BASE14)
    for i, page in enumerate(pages):
        pnum, cnum = first_page_obj + 2 * i, first_page_obj + 2 * i + 1
        obj(pnum, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %g %g] "
                  "/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                  % (PAGE_W, PAGE_H, font_obj, cnum))
        stream = ["BT /F1 %g Tf %g %g Td %g TL" % (FONT_SIZE, MARGIN, PAGE_H - MARGIN, LEADING)]
        for line in page:
            stream.append("(%s) Tj T*" % _escape_pdf_text(_latin1(line)))
        stream.append("ET")
        data = "\n".join(stream).encode("latin-1")
        obj(cnum, b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += b"%d 0 obj\n" % num + objects[num] + b"\nendobj\n"
    xref_at = len(out)
    size = max(objects) + 1
    out += b"xref\n0 %d\n" % size
    out += b"0000000000 65535 f \n"
    for num in range(1, size):
        out += b"%010d 00000 n \n" % offsets[num]
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (size, xref_at))
    return bytes(out)


def count_pdf_pages(pdf_bytes):
    """Strict structural self-check: header, xref, trailer, page objects."""
    if type(pdf_bytes) is not bytes or not pdf_bytes.startswith(b"%PDF-1."):
        _refuse("BAD_TYPE", "pdf_bytes")
    if b"startxref" not in pdf_bytes or not pdf_bytes.rstrip().endswith(b"%%EOF"):
        _refuse("MALFORMED", "pdf_bytes")
    m = re.search(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", pdf_bytes, re.S)
    if not m:
        _refuse("MALFORMED", "pages_tree")
    declared = int(m.group(1))
    found = len(_PDF_RE.findall(pdf_bytes))
    if found != declared:
        _refuse("MALFORMED", "page_count_mismatch")
    return found


def assemble_pdf(request, title="Masterplan"):
    """Compose the pinned assembler with rendered pagination and a PDF artifact."""
    return assemble_pdf_many([request], title=title)


def assemble_pdf_many(requests, title="Masterplan"):
    """Assemble several pinned-assembler batches into one PDF document.

    The pinned input cap (15M body chars per call) bounds one batch, not the
    document: a 5,000+ page masterplan is assembled from multiple supplied
    batches into a single page tree, exactly like binding volumes.
    """
    if type(requests) is not list or not requests:
        _refuse("EMPTY_FIELD", "requests")
    plans = [masterplan.run(r) for r in requests]  # pinned validation per batch
    all_pages = []
    for plan, request in zip(plans, requests):
        for volume in plan["volumes"]:
            all_pages.extend(paginate(volume["markdown"], title=volume["title"]))
    pdf = render_pdf(all_pages, title=title)
    verified = count_pdf_pages(pdf)
    target = sum(p["target_estimated_text_pages"] for p in plans) if len(plans) > 1 \
        else plans[0]["target_estimated_text_pages"]
    receipts = [r for p in plans for r in p["section_receipts"]]
    toc = [c for p in plans for c in p["table_of_contents"]]
    unfilled = sum(p["unfilled_count"] for p in plans)
    excluded = sum(p["excluded_count"] for p in plans)
    return {
        "as_of": requests[0]["as_of"],
        "batch_count": len(plans),
        "pdf_bytes": pdf,
        "pdf_bytes_len": len(pdf),
        "real_page_count": verified,
        "target_pages": target,
        "target_met": verified >= target,
        "chars_per_line": CHARS_PER_LINE,
        "lines_per_page": LINES_PER_PAGE,
        "section_receipts": receipts,
        "table_of_contents": toc,
        "unfilled_count": unfilled,
        "excluded_count": excluded,
        "scope": policy.scope(
            ["rendered pagination of the pinned assembler's output on fixed "
             "Courier geometry (70 chars x 46 lines per Letter page)",
             "a valid PDF artifact (page tree, xref offsets, trailer) checked "
             "by a strict structural page-count parser",
             "target_met computed from the counted page objects, never asserted"],
            ["research authorship - every byte of text is caller-supplied through the "
             "pinned assembler; this module adds layout only",
             "typographic fonts beyond base-14 Courier; latin-1 text only",
             "persistence and delivery - bytes are returned to the caller"],
            "pinned masterplan.run output (caller-supplied sections, %d batch(es))"
            % len(plans), requests[0]["as_of"]),
    }
