"""Actor-scoped SQL decision journal with explicit lexical retrieval limits.

This is lexical hashing, not a semantic model or an owner's consent grant. Entries
are owner reports, so a provenance reference is required and never self-verifying.
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, JSON, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class JournalBase(DeclarativeBase):
    pass


class JournalEntry(JournalBase):
    __tablename__ = "claire_owner_journal"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    decision: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[str] = mapped_column(String(240))
    vector: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def lexical_vector(text: str, size: int = 256) -> list[float]:
    """Deterministic hashed bag of words; never label it a semantic embedding."""
    vector = [0.0] * size
    for token in re.findall(r"[\w]+", text.casefold()):
        bucket = int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], "big") % size
        vector[bucket] += 1
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


class PersistentJournal:
    def __init__(self, tenant_id: str, actor_id: str, sessions: sessionmaker):
        if not tenant_id.strip() or not actor_id.strip():
            raise ValueError("authenticated tenant and actor required")
        self.tenant_id, self.actor_id, self.sessions = tenant_id, actor_id, sessions
        JournalBase.metadata.create_all(sessions.kw["bind"])

    def capture(self, decision: str, reason: str, context: str, source_reference: str) -> dict:
        if not decision.strip() or not reason.strip() or not source_reference.strip():
            raise ValueError("decision, one-line reason and owner source reference required")
        if "\n" in reason or len(decision) > 2000 or len(reason) > 1000 or len(context) > 2000 or len(source_reference) > 240:
            raise ValueError("journal field exceeds length or reason is multiline")
        with self.sessions.begin() as db:
            row = JournalEntry(tenant_id=self.tenant_id, actor_id=self.actor_id, kind="decision",
                               decision=decision.strip(), reason=reason.strip(), context=context.strip(),
                               source_reference=source_reference.strip(), vector=lexical_vector(decision + " " + reason + " " + context))
            db.add(row)
            db.flush()
            return {"id": row.id, "decision": row.decision, "reason": row.reason,
                    "source_reference": row.source_reference, "retrieval": "lexical_not_semantic",
                    "persistent_record": True, "external_action_permission": False}

    def correction(self, original: str, corrected: str, context: str, source_reference: str) -> dict:
        if not original.strip() or not corrected.strip() or original.strip() == corrected.strip() or not source_reference.strip():
            raise ValueError("distinct original and correction and owner source reference required")
        if max(map(len, (original, corrected, context))) > 2000 or len(source_reference) > 240:
            raise ValueError("correction field exceeds length")
        with self.sessions.begin() as db:
            row = JournalEntry(tenant_id=self.tenant_id, actor_id=self.actor_id, kind="correction",
                               decision=original.strip(), reason=corrected.strip(), context=context.strip(),
                               source_reference=source_reference.strip(), vector=lexical_vector(original + " " + context))
            db.add(row)
            db.flush()
            return {"id": row.id, "original": row.decision, "correction": row.reason,
                    "source_reference": row.source_reference, "few_shot_example": True,
                    "external_action_permission": False}

    def retrieve(self, query: str, k: int = 5, kind: str = "decision") -> list[dict]:
        if not query.strip() or not 1 <= k <= 20:
            raise ValueError("nonempty query and limit 1-20 required")
        q = lexical_vector(query)
        with self.sessions() as db:
            rows = list(db.scalars(select(JournalEntry).where(
                JournalEntry.tenant_id == self.tenant_id, JournalEntry.actor_id == self.actor_id,
                JournalEntry.kind == kind)))
        scored = [(sum(a * b for a, b in zip(q, row.vector)), row) for row in rows]
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [{"id": row.id, "decision": row.decision, "reason": row.reason,
                 "source_reference": row.source_reference, "score": round(score, 4),
                 "retrieval": "lexical_not_semantic"} for score, row in scored[:k] if score > 0]

    def delete(self, entry_id: int) -> bool:
        with self.sessions.begin() as db:
            row = db.get(JournalEntry, entry_id)
            if not row or row.tenant_id != self.tenant_id or row.actor_id != self.actor_id:
                return False
            db.delete(row)
            return True

    def delete_all(self) -> int:
        with self.sessions.begin() as db:
            rows = list(db.scalars(select(JournalEntry).where(
                JournalEntry.tenant_id == self.tenant_id, JournalEntry.actor_id == self.actor_id)))
            for row in rows:
                db.delete(row)
            return len(rows)

    def retrieve_bounded(self, query: str, **bounds) -> dict:
        """Recent ID-window lexical retrieval; never global top-k or consent."""
        from .bounded_journal_retrieval import bounded_retrieve
        with self.sessions() as db:
            return bounded_retrieve(db, tenant_id=self.tenant_id, actor_id=self.actor_id,
                                    query=query, **bounds)
