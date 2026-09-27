"""Consent-first, durable owner interview for Claire's decision calibration.

Answers are owner-supplied evidence, not a mandate to act as the owner. Questions
are selected from unanswered domains; uncertainty is reduced only by explicit
answers. No model guesses a missing answer and no external effects occur here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class InterviewBase(DeclarativeBase):
    pass


class InterviewConsent(InterviewBase):
    __tablename__ = "claire_interview_consent"
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InterviewAnswer(InterviewBase):
    __tablename__ = "claire_interview_answers"
    __table_args__ = (Index("claire_interview_active_answer", "tenant_id", "actor_id", "question_id", unique=True, sqlite_where=text("revoked_at IS NULL"), postgresql_where=text("revoked_at IS NULL")),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    question_id: Mapped[str] = mapped_column(String(80), nullable=False)
    choice: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# A fixed bank avoids letting external retrieved text write its own questions.
QUESTIONS = (
    {"id": "evidence", "domain": "evidence", "prompt": "When two sources disagree, what should Claire do first?", "choices": ("check_primary_source", "show_both_and_ask", "stop")},
    {"id": "reach_out", "domain": "outreach", "prompt": "For a new contact, which preparation should Claire prioritize?", "choices": ("research_and_draft", "find_introduction", "ask_before_research")},
    {"id": "opportunity", "domain": "competitions", "prompt": "Which competition fit should Claire prioritize?", "choices": ("research_alignment", "deadline_feasibility", "cost_and_access")},
    {"id": "uncertainty", "domain": "uncertainty", "prompt": "When evidence is weak, how should Claire present an idea?", "choices": ("label_hypothesis", "ask_for_evidence", "hold_the_idea")},
    {"id": "workflow", "domain": "workflow", "prompt": "For a new project, what should Claire prepare first?", "choices": ("small_test", "source_review", "decision_map")},
)
BY_ID = {q["id"]: q for q in QUESTIONS}


class InterviewStore:
    def __init__(self, tenant_id: str, actor_id: str, sessions: sessionmaker):
        if not tenant_id.strip() or not actor_id.strip():
            raise ValueError("authenticated tenant and actor are required")
        self.tenant_id, self.actor_id, self.sessions = tenant_id, actor_id, sessions
        InterviewBase.metadata.create_all(sessions.kw["bind"])

    def consent(self, enabled: bool) -> dict:
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as db:
            row = db.get(InterviewConsent, (self.tenant_id, self.actor_id))
            if row is None:
                db.add(InterviewConsent(tenant_id=self.tenant_id, actor_id=self.actor_id, enabled=enabled, updated_at=now))
            else:
                row.enabled, row.updated_at = enabled, now
        return {"enabled": enabled, "note": "Disabling pauses collection; delete answers separately."}

    def _enabled(self, db) -> bool:
        row = db.get(InterviewConsent, (self.tenant_id, self.actor_id))
        return bool(row and row.enabled)

    def _answers(self, db):
        return list(db.scalars(select(InterviewAnswer).where(
            InterviewAnswer.tenant_id == self.tenant_id,
            InterviewAnswer.actor_id == self.actor_id,
            InterviewAnswer.revoked_at.is_(None),
        ).order_by(InterviewAnswer.created_at, InterviewAnswer.id)))

    def next_question(self) -> dict:
        with self.sessions() as db:
            if not self._enabled(db):
                return {"status": "consent_required", "question": None}
            answered = {row.question_id for row in self._answers(db)}
        next_one = next((q for q in QUESTIONS if q["id"] not in answered), None)
        return {"status": "question" if next_one else "complete", "question": dict(next_one) if next_one else None,
                "answered": len(answered), "total": len(QUESTIONS)}

    def answer(self, question_id: str, choice: str, reason: str, source_reference: str) -> dict:
        question = BY_ID.get(question_id)
        if question is None or choice not in question["choices"]:
            raise ValueError("unknown question or invalid choice")
        if not reason.strip() or len(reason) > 2000 or not source_reference.strip() or len(source_reference) > 240:
            raise ValueError("owner reason and source reference are required within limits")
        with self.sessions.begin() as db:
            if not self._enabled(db):
                raise PermissionError("owner interview consent is not enabled")
            prior = next((row for row in self._answers(db) if row.question_id == question_id), None)
            if prior:
                raise ValueError("question already answered; revoke it before correcting")
            row = InterviewAnswer(tenant_id=self.tenant_id, actor_id=self.actor_id,
                                  question_id=question_id, choice=choice, reason=reason.strip(),
                                  source_reference=source_reference.strip(), created_at=datetime.now(timezone.utc))
            db.add(row)
            db.flush()
            return {"id": row.id, "question_id": question_id, "choice": choice, "reason": row.reason,
                    "source_reference": row.source_reference, "claim": "owner_reported_preference_not_action_permission"}

    def revoke(self, answer_id: int) -> bool:
        with self.sessions.begin() as db:
            row = db.get(InterviewAnswer, answer_id)
            if row is None or row.tenant_id != self.tenant_id or row.actor_id != self.actor_id or row.revoked_at:
                return False
            row.revoked_at = datetime.now(timezone.utc)
            return True

    def context(self) -> dict:
        with self.sessions() as db:
            if not self._enabled(db):
                return {"status": "consent_required", "preferences": []}
            rows = self._answers(db)
            return {"status": "owner_reported_preferences", "preferences": [
                {"question_id": r.question_id, "domain": BY_ID[r.question_id]["domain"],
                 "choice": r.choice, "reason": r.reason, "source_reference": r.source_reference,
                 "evidence_id": r.id} for r in rows],
                "external_action_permission": False}

    def delete_all(self) -> int:
        with self.sessions.begin() as db:
            rows = list(db.scalars(select(InterviewAnswer).where(
                InterviewAnswer.tenant_id == self.tenant_id, InterviewAnswer.actor_id == self.actor_id)))
            for row in rows:
                db.delete(row)
            return len(rows)
