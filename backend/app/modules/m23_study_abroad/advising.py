"""Explainable identity-grounded college advising tools with tenant history."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine


class AdvisingResultRow(Base):
    __tablename__ = "m23_advising_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    inputs: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AdvisingService:
    def __init__(self, tenant_id: str, session_factory: sessionmaker = SessionLocal):
        self.tenant_id, self.sessions = tenant_id, session_factory
        Base.metadata.create_all(engine)

    @staticmethod
    def _tokens(values) -> set[str]:
        text = " ".join(str(v) for v in values).lower()
        return {w.strip(".,:;!?()[]") for w in text.split() if len(w) > 2}

    def major_mentor(self, profile: dict, majors: list[dict]) -> dict:
        identity = self._tokens(profile.get("values", []) + profile.get("strengths", []) +
                                profile.get("interests", []) + profile.get("goals", []))
        ranked = []
        for major in majors:
            tags = self._tokens(major.get("themes", []) + major.get("skills", []) + major.get("careers", []))
            overlap = sorted(identity & tags)
            score = round(len(overlap) / max(1, len(tags)), 3)
            ranked.append({"id": major["id"], "name": major["name"], "score": score,
                           "matched_evidence": overlap,
                           "questions": [f"Which experience best demonstrates your interest in {major['name']}?",
                                         f"Which course would help you test {major['name']} before committing?"]})
        return self._save("major_mentor", {"profile": profile, "majors": majors},
                          {"recommendations": sorted(ranked, key=lambda x: (-x["score"], x["name"])),
                           "basis": "student-supplied identity evidence"})

    def school_match(self, profile: dict, schools: list[dict]) -> dict:
        goals = self._tokens(profile.get("goals", []) + profile.get("interests", []))
        budget = profile.get("annual_budget_usd")
        ranked = []
        for school in schools:
            programs = self._tokens(school.get("programs", []))
            overlap = sorted(goals & programs)
            program_score = min(1.0, len(overlap) / max(1, len(goals)))
            cost = school.get("annual_cost_usd")
            affordability = None if budget is None or cost is None else budget >= cost
            score = round(.75 * program_score + .25 * (1 if affordability else 0), 3)
            ranked.append({"id": school["id"], "name": school["name"], "score": score,
                           "official_url": school["official_url"], "matched_evidence": overlap,
                           "affordable": affordability,
                           "explanation": {"program_match": program_score, "budget_fit": affordability}})
        return self._save("school_match", {"profile": profile, "schools": schools},
                          {"matches": sorted(ranked, key=lambda x: (-x["score"], x["name"])),
                           "not_an_admission_prediction": True})

    def activity_plan(self, profile: dict, activities: list[dict], weekly_hours: float) -> dict:
        if weekly_hours <= 0:
            raise ValueError("weekly_hours must be positive")
        identity = self._tokens(profile.get("values", []) + profile.get("interests", []) + profile.get("goals", []))
        candidates = []
        for activity in activities:
            hours = float(activity.get("hours_per_week", 1))
            overlap = sorted(identity & self._tokens(activity.get("themes", [])))
            candidates.append((len(overlap) / max(hours, .5), activity, overlap, hours))
        selected, used = [], 0.0
        for _, activity, overlap, hours in sorted(candidates, key=lambda x: -x[0]):
            if used + hours <= weekly_hours:
                used += hours
                selected.append({"id": activity["id"], "name": activity["name"],
                                 "hours_per_week": hours, "matched_evidence": overlap,
                                 "milestone": activity.get("milestone", "Define a concrete first milestone")})
        return self._save("activity_planner", {"profile": profile, "activities": activities,
                                               "weekly_hours": weekly_hours},
                          {"plan": selected, "scheduled_hours": used, "capacity_hours": weekly_hours,
                           "invented_activities": False})

    def passion_projects(self, profile: dict, constraints: dict, ideas: list[dict]) -> dict:
        identity = self._tokens(profile.get("values", []) + profile.get("strengths", []) + profile.get("interests", []))
        max_hours = float(constraints.get("max_hours_per_week", 168))
        max_budget = float(constraints.get("max_budget_usd", 1e20))
        ranked = []
        for idea in ideas:
            feasible = float(idea.get("hours_per_week", 0)) <= max_hours and float(idea.get("budget_usd", 0)) <= max_budget
            overlap = sorted(identity & self._tokens(idea.get("themes", [])))
            ranked.append({"id": idea["id"], "title": idea["title"], "feasible": feasible,
                           "score": round((len(overlap) + (1 if feasible else 0)) / (len(identity) + 1), 3),
                           "matched_evidence": overlap,
                           "first_experiment": idea.get("first_experiment", "Interview one intended beneficiary")})
        return self._save("passion_project_picker", {"profile": profile, "constraints": constraints, "ideas": ideas},
                          {"ideas": sorted(ranked, key=lambda x: (not x["feasible"], -x["score"], x["title"])),
                           "student_must_choose_and_author": True})

    def history(self, kind: str | None = None) -> list[dict]:
        with self.sessions() as db:
            q = select(AdvisingResultRow).where(AdvisingResultRow.tenant_id == self.tenant_id)
            if kind:
                q = q.where(AdvisingResultRow.kind == kind)
            rows = list(db.scalars(q.order_by(AdvisingResultRow.created_at.desc())))
            return [{"id": r.id, "kind": r.kind, "result": r.result,
                     "created_at": r.created_at.isoformat()} for r in rows]

    def _save(self, kind: str, inputs: dict, result: dict) -> dict:
        ident, now = str(uuid4()), datetime.now(timezone.utc)
        with self.sessions.begin() as db:
            db.add(AdvisingResultRow(id=ident, tenant_id=self.tenant_id, kind=kind,
                                     inputs=inputs, result=result, created_at=now))
        return {"id": ident, "kind": kind, **result}
