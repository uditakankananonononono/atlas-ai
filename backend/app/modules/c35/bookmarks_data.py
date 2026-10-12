"""G116 / c35.bookmarks_data - corpus commitment and runtime loader.

The owner's bookmark corpus is private data and does not ship in the
repository. This module carries metadata only: the row count, the category
structure (counts per executable kind), and the SHA-256 provenance hash of
the canonical corpus serialization. The corpus itself is supplied at
runtime as a private payload through the owner's own channels; load_corpus
binds a supplied payload to this commitment (count, hash, category
structure) before any consumer may use it. A payload that does not match
the commitment is refused, so metadata and corpus can never drift apart
silently.

Canonical serialization: json.dumps of the list of [title, url] pairs in
original document order, ensure_ascii=False, separators=(",", ":"), utf-8.
"""
from __future__ import annotations

import hashlib
import json

PREFIX = "BOOKMARKS"

ROW_COUNT = 436
CORPUS_SHA256 = "b96dc86f8393640e8a9d05b58a3c838979c170e058ddd4eda5816f30c0b460d9"
CATEGORY_STRUCTURE = {
    "application_form": 12,
    "scholarship": 40,
    "competition": 46,
    "fellowship": 0,
    "incubator": 18,
    "admissions_info": 53,
    "template_doc": 23,
    "platform_account": 4,
    "community": 0,
    "reference": 240,
}
PROVENANCE = {"source": "owner private bookmarks export", "exported": "2026-10-12",
              "content_in_repo": False}
MAX_TITLE = 500
MAX_URL = 2048


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def canonical_bytes(rows):
    """Canonical corpus bytes; the provenance hash commits to this form."""
    if type(rows) is not list:
        _refuse("BAD_TYPE", "corpus")
    pairs = []
    for i, row in enumerate(rows):
        if type(row) not in (list, tuple) or len(row) != 2:
            _refuse("BAD_TYPE", "corpus[%d]" % i)
        title, url = row
        if type(title) is not str or type(url) is not str:
            _refuse("BAD_TYPE", "corpus[%d]" % i)
        pairs.append([title, url])
    return json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def corpus_sha256(rows):
    return hashlib.sha256(canonical_bytes(rows)).hexdigest()


def load_corpus(rows, classify=None):
    """Bind a runtime-supplied corpus to the commitment; return the rows.

    classify (optional) is the c35.bookmarks_exec classifier; when given, the
    payload's category structure is recomputed and must match the committed
    structure as well.
    """
    if len(rows) != ROW_COUNT:
        _refuse("CORPUS_COUNT", "corpus")
    if corpus_sha256(rows) != CORPUS_SHA256:
        _refuse("CORPUS_HASH", "corpus")
    if classify is not None:
        counts = {k: 0 for k in CATEGORY_STRUCTURE}
        for title, url in rows:
            kind = classify(title, url)
            if kind not in counts:
                _refuse("CORPUS_KIND", kind)
            counts[kind] += 1
        if counts != CATEGORY_STRUCTURE:
            _refuse("CORPUS_KIND_STRUCTURE", "corpus")
    return [list(r) for r in rows]


def metadata():
    """The public metadata record: count, category structure, provenance hash."""
    return {"row_count": ROW_COUNT, "corpus_sha256": CORPUS_SHA256,
            "category_structure": dict(CATEGORY_STRUCTURE),
            "provenance": dict(PROVENANCE)}
