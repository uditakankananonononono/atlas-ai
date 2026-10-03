"""Resumable Brandi-style identity interviews grounded only in student answers."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine
from .story import StoryRepository
from .adaptive_interviewer import ADAPTIVE, FALLBACK, AdaptiveInterviewer

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


class IdentityInsightRow(Base):
    """Per-turn adaptive-interviewer output with its truth labels (model-backed or fallback)."""
    __tablename__ = "m23_identity_interview_insights"
    __table_args__ = (UniqueConstraint("session_id", "ordinal", name="uq_m23_insight_session_ordinal"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    step: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConcurrentAnswerError(ValueError):
    """Another answer for the same question was committed first (maps to HTTP 409)."""


class IdentityInterviewRepository:
    def __init__(self, tenant_id: str, session_factory: sessionmaker = SessionLocal,
                 interviewer: AdaptiveInterviewer | None = None):
        self.tenant_id, self.sessions, self.interviewer = tenant_id, session_factory, interviewer
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
            expected = row.question_index
            question = self._question_for(db, session_id, expected)
            now = datetime.now(timezone.utc)
            won = db.execute(update(IdentityInterviewRow).where(
                IdentityInterviewRow.id == session_id, IdentityInterviewRow.tenant_id == self.tenant_id,
                IdentityInterviewRow.question_index == expected, IdentityInterviewRow.status == "active").values(
                question_index=expected + 1, status="complete" if expected + 1 == len(QUESTIONS) else "active",
                updated_at=now)).rowcount
            if won != 1:
                raise ConcurrentAnswerError("another answer to this question was already recorded; reload the interview")
            ordinal = expected + 1
            db.add(IdentityTurnRow(session_id=session_id, ordinal=ordinal, modality=modality, question=question,
                                   student_response=response, evidence_tags=evidence_tags or [], created_at=now))
        self._run_interviewer(session_id, ordinal)
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
            insights = {i.ordinal: i.step for i in db.scalars(select(IdentityInsightRow).where(
                IdentityInsightRow.session_id == session_id).order_by(IdentityInsightRow.ordinal))}
            next_question = self._question_for(db, session_id, row.question_index) if row.status == "active" else None
            source = ("fixed_script_opening" if row.question_index == 0 else
                      (insights.get(row.question_index) or {}).get("question_source", FALLBACK))
            return {
                "id": row.id, "track": row.track, "status": row.status,
                "question_index": row.question_index,
                "next_question": next_question, "next_question_source": source if next_question else None,
                "interviewer": {
                    "adaptive_enabled": self.interviewer is not None,
                    "model_backed_turns": sorted(o for o, st in insights.items() if st.get("model_backed")),
                    "turns": [{"ordinal": o, "question_source": st.get("question_source"),
                               "extraction_mode": st.get("extraction_mode"), "provider": st.get("provider"),
                               "model": st.get("model"), "proposed_items": len(st.get("extraction", [])),
                               "rejected_items": len(st.get("rejected", [])), "detail": st.get("detail", "")}
                              for o, st in sorted(insights.items())],
                    "label": ("adaptive local-model interviewer; fixed-script entries are fallbacks"
                              if self.interviewer is not None else
                              "fixed script only: no model configured, not adaptive")},
                "turns": [{"ordinal": t.ordinal, "modality": t.modality,
                           "question": t.question, "student_response": t.student_response,
                           "evidence_tags": t.evidence_tags} for t in turns],
                "student_owned": True, "final_essay_prose": None,
            }

    def _question_for(self, db, session_id: str, index: int) -> str:
        """Adaptive question stored after the previous answer, else the fixed script question."""
        if index > 0:
            row = db.scalar(select(IdentityInsightRow).where(
                IdentityInsightRow.session_id == session_id, IdentityInsightRow.ordinal == index))
            if row is not None and row.step.get("question"):
                return row.step["question"]
        return QUESTIONS[index]

    def _run_interviewer(self, session_id: str, ordinal: int) -> None:
        """Model work happens after the answer is committed and can never fail the request."""
        if self.interviewer is None:
            return
        try:
            interview = self.get(session_id)
            turns = [t for t in interview["turns"] if t["ordinal"] <= ordinal]
            want_question = ordinal < len(QUESTIONS)
            fixed = QUESTIONS[ordinal] if want_question else None
            step = self.interviewer.step(track=interview["track"], turns=turns, fixed_next=fixed,
                                         want_question=want_question).as_dict()
        except Exception as exc:  # noqa: BLE001
            step = {"question": QUESTIONS[ordinal] if ordinal < len(QUESTIONS) else None, "question_source": FALLBACK,
                    "extraction": [], "rejected": [], "extraction_mode": "none_no_model", "provider": None,
                    "model": None, "detail": f"interviewer error ({type(exc).__name__})", "model_backed": False}
        try:
            with self.sessions.begin() as db:
                db.add(IdentityInsightRow(session_id=session_id, ordinal=ordinal, step=step,
                                          created_at=datetime.now(timezone.utc)))
        except IntegrityError:
            pass  # a concurrent writer already stored this ordinal's step

    def confirm_insight(self, session_id: str, ordinal: int, index: int, confirmed: bool = True,
                        actor_id: str | None = None) -> dict:
        """The student accepts or rejects one proposed item; only confirmed items feed BrandID labels."""
        with self.sessions.begin() as db:
            if db.scalar(select(IdentityInterviewRow.id).where(IdentityInterviewRow.id == session_id,
                         IdentityInterviewRow.tenant_id == self.tenant_id)) is None:
                raise LookupError(session_id)
            row = db.scalar(select(IdentityInsightRow).where(IdentityInsightRow.session_id == session_id,
                                                              IdentityInsightRow.ordinal == ordinal))
            items = list((row.step if row else {}).get("extraction", []))
            if row is None or not 0 <= index < len(items):
                raise LookupError("no such proposed item")
            items[index] = {**items[index], "student_confirmed": bool(confirmed),
                            "status": "student_confirmed" if confirmed else "student_rejected",
                            "decided_by_actor": actor_id}  # no student-only role exists in auth; actor is recorded, not enforced
            row.step = {**row.step, "extraction": items}
        self._refresh_brand(session_id)
        return self.get(session_id)

    def _grounded_items(self, session_id: str) -> list[dict]:
        with self.sessions() as db:
            rows = list(db.scalars(select(IdentityInsightRow).where(
                IdentityInsightRow.session_id == session_id).order_by(IdentityInsightRow.ordinal)))
        return [{"session_id": session_id, "turn": r.ordinal, **item, "model": r.step.get("model"),
                 "provenance": "model-PROPOSED label; quote is an exact copy from the student's answer; label not "
                               "semantically verified; " + ("confirmed by the student" if item.get("student_confirmed")
                                                           else "NOT yet confirmed by the student")}
                for r in rows if r.step.get("extraction_mode") == ADAPTIVE for item in r.step.get("extraction", [])]

    def _refresh_brand(self, session_id: str) -> None:
        interview = self.get(session_id)
        turns = interview["turns"]
        evidence = [{"session_id": session_id, "turn": t["ordinal"],
                     "modality": t["modality"], "student_response": t["student_response"]}
                    for t in turns]
        values = sorted({tag for t in turns for tag in t["evidence_tags"]})
        patterns = [t["student_response"] for t in turns[:3]]
        strengths = [tag.removeprefix("strength:") for tag in values if tag.startswith("strength:")]
        grounded = self._grounded_items(session_id)
        ok = [g for g in grounded if g.get("student_confirmed")]  # unconfirmed proposals stay evidence only
        values = sorted(set(values) | {g["label"] for g in ok if g["kind"] == "value"})
        strengths = sorted(set(strengths) | {g["label"] for g in ok if g["kind"] == "strength"})
        patterns = patterns + [g["label"] for g in ok if g["kind"] == "pattern"]
        StoryRepository(self.tenant_id, self.sessions).evolve_brand(values, patterns, strengths, evidence + grounded)
