"""E1 rankers over the shipped PersistentJournal store (M21 Claire).

B0  = the shipped journal.retrieve (hashed bag of words, ties -> older id first).
B1  = BM25 over decision rows (classical lexical baseline).
H1a = B0 scoring + correction supersession (a decision with a later correction is replaced by the
      corrected text; the original is never returned).
H1b = B0 scoring + recency weight, no supersession.
H1  = both. Constants frozen before scoring: weight = 0.7 + 0.3 * 0.5 ** (age_days / 90).
Nothing here edits the journal or its schema; rankers only read rows.
"""
import math
import re
import sys
import importlib.util as _u
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_P = Path(__file__).resolve().parents[2] / "backend/app/modules/m21_claire/persistent_journal.py"
_spec = _u.spec_from_file_location("e1_persistent_journal", _P)
pj = _u.module_from_spec(_spec)
sys.modules["e1_persistent_journal"] = pj
_spec.loader.exec_module(pj)

FLOOR, GAIN, HALF_LIFE_DAYS = 0.7, 0.3, 90.0


def _rows(journal):
    from sqlalchemy import select
    with journal.sessions() as db:
        rows = list(db.scalars(select(pj.JournalEntry).where(
            pj.JournalEntry.tenant_id == journal.tenant_id, pj.JournalEntry.actor_id == journal.actor_id)))
        return [dict(id=r.id, kind=r.kind, decision=r.decision, reason=r.reason, context=r.context,
                     vector=r.vector, created_at=r.created_at) for r in rows]


def _age_days(row, now):
    t = row["created_at"]
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max(0.0, (now - t).total_seconds() / 86400)


def _cos(q, v):
    return sum(a * b for a, b in zip(q, v))


def b0(journal, query, k, now):
    return [r["decision"] for r in journal.retrieve(query, k=k)]


def b1(journal, query, k, now):
    docs = [r for r in _rows(journal) if r["kind"] == "decision"]
    toks = [re.findall(r"\w+", (r["decision"] + " " + r["reason"] + " " + r["context"]).casefold()) for r in docs]
    avg = sum(map(len, toks)) / max(1, len(toks))
    df = Counter(t for ts in toks for t in set(ts))
    n = len(docs)
    q = re.findall(r"\w+", query.casefold())
    scored = []
    for r, ts in zip(docs, toks):
        tf = Counter(ts)
        s = 0.0
        for t in q:
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(ts) / avg))
        scored.append((s, r["id"], r["decision"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [d for s, _, d in scored[:k] if s > 0]


def _hybrid(journal, query, k, now, supersede, recency):
    rows = _rows(journal)
    q = pj.lexical_vector(query)
    corr = {}
    for r in sorted((r for r in rows if r["kind"] == "correction"), key=lambda r: r["id"]):
        corr[r["decision"]] = r["reason"]  # latest correction per original text wins
    scored = []
    for r in rows:
        if r["kind"] != "decision":
            continue
        s = _cos(q, r["vector"])
        if s <= 0:
            continue
        if recency:
            s *= FLOOR + GAIN * 0.5 ** (_age_days(r, now) / HALF_LIFE_DAYS)
        text = corr.get(r["decision"], r["decision"]) if supersede else r["decision"]
        scored.append((-s, r["id"], text))
    scored.sort()
    return [t for _, _, t in scored[:k]]


def h1a(j, q, k, now): return _hybrid(j, q, k, now, True, False)
def h1b(j, q, k, now): return _hybrid(j, q, k, now, False, True)
def h1(j, q, k, now): return _hybrid(j, q, k, now, True, True)


RANKERS = {"B0": b0, "B1": b1, "H1a": h1a, "H1b": h1b, "H1": h1}
