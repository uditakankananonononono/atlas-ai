"""Resumable Brandi-style identity interviews grounded only in student answers."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, Text, select
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
            db.add(IdentityInterviewRow(id=ident, tenant_id=self.tenant_id, track=track,
                                        status="active", question_index=0,
                                        created_at=now, updated_at=now))
        return self.get(ident)

    def answer(self, session_id: str, response: str, modality: str = "chat",
               evidence_tags: list[str] | None = None) -> dict:
        response = response.strip()
        if len(response) < 10:
            raise ValueError("student response must contain at least 10 characters")
        if modality not in {"chat", "voice"}:
            raise ValueError("modality must be chat or voice")
        with self.sessions.begin() as db:
            row = db.scalar(select(IdentityInterviewRow).where(
                IdentityInterviewRow.id == session_id,
                IdentityInterviewRow.tenant_id == self.tenant_id))
            if row is None:
                raise LookupError(session_id)
            if row.status != "active":
                raise ValueError("interview is already complete")
            question = QUESTIONS[row.question_index]
            db.add(IdentityTurnRow(session_id=session_id, ordinal=row.question_index + 1,
                                   modality=modality, question=question,
                                   student_response=response,
                                   evidence_tags=evidence_tags or [],
                                   created_at=datetime.now(timezone.utc)))
            row.question_index += 1
            row.status = "complete" if row.question_index == len(QUESTIONS) else "active"
            row.updated_at = datetime.now(timezone.utc)
        self._refresh_brand(session_id)
        return self.get(session_id)

    def get(self, session_id: str) -> dict:
        with self.sessions() as db:
            row = db.scalar(select(IdentityInterviewRow).where(
                IdentityInterviewRow.id == session_id,
                IdentityInterviewRow.tenant_id == self.tenant_id))
            if row is None:
                raise LookupError(session_id)
            turns = list(db.scalars(select(IdentityTurnRow).where(
                IdentityTurnRow.session_id == session_id).order_by(IdentityTurnRow.ordinal)))
            return {
                "id": row.id, "track": row.track, "status": row.status,
                "question_index": row.question_index,
                "next_question": QUESTIONS[row.question_index] if row.status == "active" else None,
                "turns": [{"ordinal": t.ordinal, "modality": t.modality,
                           "question": t.question, "student_response": t.student_response,
                           "evidence_tags": t.evidence_tags} for t in turns],
                "student_owned": True, "final_essay_prose": None,
            }

    def _refresh_brand(self, session_id: str) -> None:
        interview = self.get(session_id)
        turns = interview["turns"]
        evidence = [{"session_id": session_id, "turn": t["ordinal"],
                     "modality": t["modality"], "student_response": t["student_response"]}
                    for t in turns]
        values = sorted({tag for t in turns for tag in t["evidence_tags"]})
        patterns = [t["student_response"] for t in turns[:3]]
        strengths = [tag.removeprefix("strength:") for tag in values if tag.startswith("strength:")]
        StoryRepository(self.tenant_id, self.sessions).evolve_brand(values, patterns, strengths, evidence)
