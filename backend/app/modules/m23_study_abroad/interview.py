"""Resumable Brandi-style identity interviews grounded only in student answers."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine
from .story import StoryRepository

QUESTIONS = (
    "What experience has shaped how you see yourself?",
    "Which values guided a difficult choice you made?",
    "What work or activity gives you energy, and why?",
    "What strength have other people seen you demonstrate?",
    "What do you want to explore next in college or your career?",
)


class IdentityInterviewRow(Base):
    __tablename__ = "m23_identity_interviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    track: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active")
    question_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdentityTurnRow(Base):
    __tablename__ = "m23_identity_interview_turns"
    # One turn per (session, ordinal): concurrent answers can no longer both
    # land on the same ordinal. NOTE: create_all does not ALTER pre-existing
    # tables - deployments with an existing turns table need a migration for
    # the constraint to exist.
    __table_args__ = (UniqueConstraint("session_id", "ordinal"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    modality: Mapped[str] = mapped_column(String(10))
    question: Mapped[str] = mapped_column(Text)
    student_response: Mapped[str] = mapped_column(Text)
    evidence_tags: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdentityInterviewRepository:
    def __init__(self, tenant_id: str, session_factory: sessionmaker = SessionLocal):
        self.tenant_id, self.sessions = tenant_id, session_factory
        Base.metadata.create_all(engine)

    def start(self, track: str) -> dict:
        if track not in {"college", "career"}:
            raise ValueError("track must be college or career")
        now = datetime.now(timezone.utc)
        ident = str(uuid4())
        with self.sessions.begin() as db:
            row = IdentityInterviewRow(id=ident, tenant_id=self.tenant_id, track=track,
                                       status="active", question_index=0,
                                       created_at=now, updated_at=now)
            db.add(row)
            db.flush()
            # The returned view comes from THIS transaction's own flushed
            # state, not a post-commit re-read that could observe another
            # writer's interleaved commit.
            view = self._view(row, [])
        return view

    def answer(self, session_id: str, response: str, modality: str = "chat",
               evidence_tags: list[str] | None = None) -> dict:
        response = response.strip()
        if len(response) < 10:
            raise ValueError("student response must contain at least 10 characters")
        if modality not in {"chat", "voice"}:
            raise ValueError("modality must be chat or voice")
        # Serialization contract: a (session_id, ordinal) unique collision
        # means a concurrent answer committed first. The retry re-reads the
        # row in a fresh transaction and proceeds ONLY while the interview is
        # still on the question this response was written for; if the
        # interview advanced, the stale answer is rejected, never shifted
        # under a question it was not written for. Bounded to three attempts,
        # then a domain error. A raw IntegrityError never escapes.
        # Deterministic handler-path contract only; no real-race closure is
        # claimed. Binding scope: expected_index is captured on THIS call's
        # first attempt, so stale rejection covers only advancement during
        # this call's own retry window (tested: a competitor committing
        # between attempts). A separate LATE call - e.g. an identical-text
        # resubmission after the first answer committed - captures the
        # already-advanced index and files its response under the current
        # question; cross-call late answers are NOT rejected or deduplicated
        # (client idempotency/expected-question semantics are not invented
        # here).
        from sqlalchemy.exc import IntegrityError as _IE
        expected_index: int | None = None
        last = None
        for _ in range(3):
            try:
                with self.sessions.begin() as db:
                    row = db.scalar(select(IdentityInterviewRow).where(
                        IdentityInterviewRow.id == session_id,
                        IdentityInterviewRow.tenant_id == self.tenant_id))
                    if row is None:
                        raise LookupError(session_id)
                    if row.status != "active":
                        raise ValueError("interview is already complete")
                    if expected_index is None:
                        expected_index = row.question_index
                    elif row.question_index != expected_index:
                        raise ValueError(
                            "the interview advanced while this answer was in flight; "
                            "resubmit the answer to the current question")
                    question = QUESTIONS[row.question_index]
                    db.add(IdentityTurnRow(session_id=session_id, ordinal=row.question_index + 1,
                                           modality=modality, question=question,
                                           student_response=response,
                                           evidence_tags=evidence_tags or [],
                                           created_at=datetime.now(timezone.utc)))
                    row.question_index += 1
                    row.status = "complete" if row.question_index == len(QUESTIONS) else "active"
                    row.updated_at = datetime.now(timezone.utc)
                    db.flush()
                    # Brand refresh runs INSIDE the turn transaction: a refresh
                    # failure rolls the turn back instead of leaving the answer
                    # persisted with an advanced index and a stale brand.
                    turns = list(db.scalars(select(IdentityTurnRow).where(
                        IdentityTurnRow.session_id == session_id).order_by(IdentityTurnRow.ordinal)))
                    evidence = [{"session_id": session_id, "turn": t.ordinal,
                                 "modality": t.modality, "student_response": t.student_response}
                                for t in turns]
                    values = sorted({tag for t in turns for tag in (t.evidence_tags or [])})
                    patterns = [t.student_response for t in turns[:3]]
                    strengths = [tag.removeprefix("strength:") for tag in values if tag.startswith("strength:")]
                    StoryRepository(self.tenant_id, self.sessions).evolve_brand(
                        values, patterns, strengths, evidence, _db=db)
                    # Returned view built inside the committing transaction:
                    # what the caller gets is exactly what this call
                    # committed, never a post-commit re-read that could
                    # observe interleaved writes.
                    view = self._view(row, turns)
                return view
            except _IE as exc:
                last = exc
        raise ValueError("interview answer collided repeatedly; resubmit the answer") from last

    @staticmethod
    def _view(row, turns) -> dict:
        return {
            "id": row.id, "track": row.track, "status": row.status,
            "question_index": row.question_index,
            "next_question": QUESTIONS[row.question_index] if row.status == "active" else None,
            "turns": [{"ordinal": t.ordinal, "modality": t.modality,
                       "question": t.question, "student_response": t.student_response,
                       "evidence_tags": t.evidence_tags} for t in turns],
            "student_owned": True, "final_essay_prose": None,
        }

    def get(self, session_id: str) -> dict:
        with self.sessions() as db:
            row = db.scalar(select(IdentityInterviewRow).where(
                IdentityInterviewRow.id == session_id,
                IdentityInterviewRow.tenant_id == self.tenant_id))
            if row is None:
                raise LookupError(session_id)
            turns = list(db.scalars(select(IdentityTurnRow).where(
                IdentityTurnRow.session_id == session_id).order_by(IdentityTurnRow.ordinal)))
            return self._view(row, turns)
