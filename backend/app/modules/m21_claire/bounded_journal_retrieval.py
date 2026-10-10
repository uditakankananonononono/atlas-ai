"""Bounded lexical retrieval over the persistent owner journal (prep-only helper).

Problem: ``PersistentJournal.retrieve`` loads every row for a tenant/actor/kind
into memory and scores them in Python, so read cost grows without bound as the
journal grows. This helper is the additive repair prep: caller bounds and
filters are validated BEFORE any read, the deterministic time/ID window is
pushed into the SQL WHERE clause, the scan is capped, and the result reports
exactly what was read, scored, omitted and truncated.

Contract (for the integrator - wiring is owned elsewhere and unchanged here):
  * Call ``validate_retrieval_bounds`` (or ``bounded_retrieve``, which calls it
    first) with caller-supplied parameters. All validation completes before any
    database read; invalid input raises ``ValueError`` and no query is issued.
  * Call ``bounded_retrieve`` with an open SQLAlchemy ``Session``. The helper
    performs read-only SELECTs (one bounded row scan with a window COUNT so omission
    counts are honest without reading the uncapped set). It never creates
    tables, never writes, and never commits; transaction lifetime is the
    caller's.
  * The scan window is deterministic: newest matching rows first
    (``ORDER BY id DESC``), capped at ``scan_cap``. ``truncated`` is True when
    more rows matched than were read; ``omitted_by_scan_cap`` says how many.
    Page older rows with ``before_id = <oldest id already seen>``.
  * Scoring is the same hashed bag-of-words lexical score as
    ``PersistentJournal.retrieve`` (``lexical_vector`` is imported, not
    duplicated). It is NOT a semantic embedding, NOT a trained model, and NOT
    an owner's consent grant; the "retrieval": "lexical_not_semantic" label is
    carried through every hit and the summary. No returned decision grants
    permission for external action.
  * Hit ordering matches ``PersistentJournal.retrieve``: score descending,
    then id ascending on ties, zero/negative scores dropped, then the caller's
    ``limit`` applied.

Open dependency decisions (stated, not invented):
  * Reuses ``JournalEntry`` and ``lexical_vector`` from ``persistent_journal``
    so scoring stays identical to the existing path; nothing in that module is
    modified.
  * The journal schema has no created-at index requirement declared here; the
    ID window (autoincrement primary key) is the deterministic ordering and
    paging mechanism. Time filters are additional predicates on ``created_at``.
  * Routes, service wiring, migrations and execution of these tests are owned
    by the integrating side; this branch adds files only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .persistent_journal import JournalEntry, lexical_vector

MAX_LIMIT = 20            # same ceiling as PersistentJournal.retrieve
DEFAULT_SCAN_CAP = 500    # rows read before scoring when the caller sets no cap
MAX_SCAN_CAP = 2000       # hard ceiling on rows read per call
MAX_QUERY_LENGTH = 4000
ALLOWED_KINDS = ("decision", "correction")


@dataclass(frozen=True)
class JournalRetrievalBounds:
    """Caller bounds and filters, validated before any database read."""

    query: str
    limit: int
    kind: str
    since: datetime | None
    until: datetime | None
    after_id: int | None
    before_id: int | None
    scan_cap: int


def _aware(value: datetime | None, name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value


def validate_retrieval_bounds(
    query: str,
    limit: int = 5,
    kind: str = "decision",
    since: datetime | None = None,
    until: datetime | None = None,
    after_id: int | None = None,
    before_id: int | None = None,
    scan_cap: int = DEFAULT_SCAN_CAP,
) -> JournalRetrievalBounds:
    """Validate caller bounds and filters. Runs BEFORE any database read."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("nonempty query required")
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"query exceeds {MAX_QUERY_LENGTH} characters")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer 1-{MAX_LIMIT}")
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"kind must be one of {ALLOWED_KINDS}")
    since = _aware(since, "since")
    until = _aware(until, "until")
    if since is not None and until is not None and since > until:
        raise ValueError("since must not be after until")
    for name, value in (("after_id", after_id), ("before_id", before_id)):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
            raise ValueError(f"{name} must be a positive integer entry id")
    if after_id is not None and before_id is not None and after_id >= before_id:
        raise ValueError("after_id must be less than before_id")
    if not isinstance(scan_cap, int) or isinstance(scan_cap, bool) or not 1 <= scan_cap <= MAX_SCAN_CAP:
        raise ValueError(f"scan_cap must be an integer 1-{MAX_SCAN_CAP}")
    if limit > scan_cap:
        raise ValueError("limit must not exceed scan_cap; hits cannot exceed rows read")
    return JournalRetrievalBounds(query.strip(), limit, kind, since, until, after_id, before_id, scan_cap)


def _predicates(tenant_id: str, actor_id: str, b: JournalRetrievalBounds) -> list:
    preds = [JournalEntry.tenant_id == tenant_id, JournalEntry.actor_id == actor_id,
             JournalEntry.kind == b.kind]
    if b.since is not None:
        preds.append(JournalEntry.created_at >= b.since)
    if b.until is not None:
        preds.append(JournalEntry.created_at <= b.until)
    if b.after_id is not None:
        preds.append(JournalEntry.id > b.after_id)
    if b.before_id is not None:
        preds.append(JournalEntry.id < b.before_id)
    return preds


def bounded_retrieve(
    session: Session,
    *,
    tenant_id: str,
    actor_id: str,
    query: str,
    limit: int = 5,
    kind: str = "decision",
    since: datetime | None = None,
    until: datetime | None = None,
    after_id: int | None = None,
    before_id: int | None = None,
    scan_cap: int = DEFAULT_SCAN_CAP,
) -> dict:
    """Score journal entries inside a validated, capped, deterministic window.

    Read-only against ``session``; raises ``ValueError`` on invalid bounds
    before issuing any query. Returns hits plus honest read/score/omission
    accounting; see the module docstring for the full contract.
    """
    if not isinstance(tenant_id,str) or not isinstance(actor_id,str) or not tenant_id.strip() or not actor_id.strip():
        raise ValueError("authenticated tenant and actor required")
    b = validate_retrieval_bounds(query, limit, kind, since, until, after_id, before_id, scan_cap)
    preds = _predicates(tenant_id, actor_id, b)

    # One SQL statement: count and bounded rows share the same statement view.
    pairs = list(session.execute(select(JournalEntry, func.count().over().label("matched_total"))
        .where(*preds).order_by(JournalEntry.id.desc()).limit(b.scan_cap)))
    rows = [pair[0] for pair in pairs]
    matched_total = int(pairs[0][1]) if pairs else 0

    q = lexical_vector(b.query)
    scored = [(sum(a * c for a, c in zip(q, row.vector)), row) for row in rows]
    scored.sort(key=lambda item: (-item[0], item[1].id))
    positive = [(score, row) for score, row in scored if score > 0]
    top = positive[: b.limit]

    hits = [{"id": row.id, "decision": row.decision, "reason": row.reason,
             "source_reference": row.source_reference, "score": round(score, 4),
             "created_at": row.created_at.isoformat() if row.created_at else None,
             "retrieval": "lexical_not_semantic"} for score, row in top]
    return {
        "hits": hits,
        "matched_total": matched_total,
        "rows_read": len(rows),
        "oldest_scanned_id": min((row.id for row in rows), default=None),
        "newest_scanned_id": max((row.id for row in rows), default=None),
        "count_consistency": "single_statement_window_count",
        "global_top_k_claimed": False,
        "scored": len(scored),
        "below_threshold": len(scored) - len(positive),
        "omitted_by_limit": len(positive) - len(hits),
        "omitted_by_scan_cap": matched_total - len(rows),
        "truncated": matched_total > len(rows),
        "window": {"kind": b.kind, "limit": b.limit, "scan_cap": b.scan_cap,
                   "since": b.since.isoformat() if b.since else None,
                   "until": b.until.isoformat() if b.until else None,
                   "after_id": b.after_id, "before_id": b.before_id,
                   "scan_order": "id_desc_newest_first"},
        "retrieval": "lexical_not_semantic",
        "external_action_permission": False,
    }
