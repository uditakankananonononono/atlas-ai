"""Structured knowledge store: people and their work, with provenance."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, SessionLocal, engine

from .models import SocialPersonRow, SocialReadRunRow, SocialWorkRow


class KnowledgeStore:
    def __init__(self, sessions: sessionmaker | None = None):
        if sessions is None:
            Base.metadata.create_all(engine)
            sessions = SessionLocal
        self.sessions = sessions

    # -- people ---------------------------------------------------------------

    def upsert_person(self, tenant_id: str, *, platform: str, handle: str,
                      display_name: str = "", bio: str = "", external_url: str = "",
                      relation: str = "follower") -> SocialPersonRow:
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as db:
            row = db.scalar(select(SocialPersonRow).where(
                SocialPersonRow.tenant_id == tenant_id,
                SocialPersonRow.platform == platform,
                SocialPersonRow.handle == handle))
            if row is None:
                row = SocialPersonRow(tenant_id=tenant_id, platform=platform, handle=handle,
                                      first_seen_at=now, last_seen_at=now)
                db.add(row)
            if display_name:
                row.display_name = display_name
            if bio:
                row.bio = bio
            if external_url:
                row.external_url = external_url
            row.relation = relation
            row.last_seen_at = now
            db.flush()
            db.expunge(row)
            return row

    def list_people(self, tenant_id: str, platform: str | None = None, limit: int = 200) -> list[dict]:
        limit = max(1, min(limit, 1000))
        with self.sessions() as db:
            query = select(SocialPersonRow).where(SocialPersonRow.tenant_id == tenant_id)
            if platform:
                query = query.where(SocialPersonRow.platform == platform)
            rows = db.scalars(query.order_by(SocialPersonRow.last_seen_at.desc()).limit(limit)).all()
            return [self._person_view(r) for r in rows]

    def get_person(self, tenant_id: str, platform: str, handle: str) -> dict | None:
        with self.sessions() as db:
            row = db.scalar(select(SocialPersonRow).where(
                SocialPersonRow.tenant_id == tenant_id,
                SocialPersonRow.platform == platform,
                SocialPersonRow.handle == handle))
            if row is None:
                return None
            view = self._person_view(row)
            works = db.scalars(select(SocialWorkRow).where(
                SocialWorkRow.tenant_id == tenant_id,
                SocialWorkRow.platform == platform,
                SocialWorkRow.handle == handle).order_by(SocialWorkRow.observed_at.desc()).limit(100)).all()
            view["works"] = [self._work_view(w) for w in works]
            return view

    # -- observed work ----------------------------------------------------------

    def record_work(self, tenant_id: str, *, platform: str, handle: str, external_id: str,
                    kind: str = "post", text: str = "", source_url: str = "",
                    observed_at: datetime | None = None, detail: dict | None = None,
                    signal_score: float = 0.0) -> tuple[SocialWorkRow, bool]:
        """Insert one observation; the unique key makes re-reads idempotent."""
        with self.sessions.begin() as db:
            existing = db.scalar(select(SocialWorkRow).where(
                SocialWorkRow.tenant_id == tenant_id,
                SocialWorkRow.platform == platform,
                SocialWorkRow.external_id == external_id))
            if existing is not None:
                db.expunge(existing)
                return existing, False
            row = SocialWorkRow(tenant_id=tenant_id, platform=platform, handle=handle,
                                external_id=external_id, kind=kind, text=text,
                                source_url=source_url,
                                observed_at=observed_at or datetime.now(timezone.utc),
                                detail=detail or {}, signal_score=signal_score)
            db.add(row)
            db.flush()
            db.expunge(row)
            return row, True

    def list_signals(self, tenant_id: str, *, since: datetime | None = None,
                     unharvested: bool = False, limit: int = 200) -> list[dict]:
        limit = max(1, min(limit, 1000))
        with self.sessions() as db:
            query = select(SocialWorkRow).where(SocialWorkRow.tenant_id == tenant_id)
            if since is not None:
                query = query.where(SocialWorkRow.observed_at >= since)
            if unharvested:
                query = query.where(SocialWorkRow.idea_id.is_(None))
            rows = db.scalars(query.order_by(SocialWorkRow.signal_score.desc(),
                                             SocialWorkRow.observed_at.desc()).limit(limit)).all()
            return [self._work_view(r) for r in rows]

    def mark_harvested(self, tenant_id: str, work_ids: list[int], idea_id: str) -> int:
        with self.sessions.begin() as db:
            count = 0
            for work_id in work_ids:
                row = db.get(SocialWorkRow, work_id)
                if row is not None and row.tenant_id == tenant_id and row.idea_id is None:
                    row.idea_id = idea_id
                    count += 1
            return count

    # -- read runs ----------------------------------------------------------------

    def start_run(self, tenant_id: str, platform: str, operation: str, session_id: str = "") -> int:
        with self.sessions.begin() as db:
            row = SocialReadRunRow(tenant_id=tenant_id, platform=platform,
                                   operation=operation, session_id=session_id)
            db.add(row)
            db.flush()
            return row.id

    def finish_run(self, run_id: int, state: str, detail: dict | None = None) -> None:
        with self.sessions.begin() as db:
            row = db.get(SocialReadRunRow, run_id)
            if row is not None:
                row.state = state
                row.finished_at = datetime.now(timezone.utc)
                if detail:
                    row.detail = {**row.detail, **detail}

    def list_runs(self, tenant_id: str, limit: int = 50) -> list[dict]:
        with self.sessions() as db:
            rows = db.scalars(select(SocialReadRunRow).where(
                SocialReadRunRow.tenant_id == tenant_id
            ).order_by(SocialReadRunRow.id.desc()).limit(max(1, min(limit, 200)))).all()
            return [{"id": r.id, "platform": r.platform, "operation": r.operation,
                     "state": r.state, "started_at": r.started_at.isoformat() if r.started_at else None,
                     "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                     "detail": dict(r.detail)} for r in rows]

    # -- views --------------------------------------------------------------------

    @staticmethod
    def _person_view(row: SocialPersonRow) -> dict:
        return {"platform": row.platform, "handle": row.handle,
                "display_name": row.display_name, "bio": row.bio,
                "external_url": row.external_url, "relation": row.relation,
                "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
                "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None}

    @staticmethod
    def _work_view(row: SocialWorkRow) -> dict:
        return {"id": row.id, "platform": row.platform, "handle": row.handle,
                "external_id": row.external_id, "kind": row.kind, "text": row.text,
                "source_url": row.source_url,
                "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                "captured_at": row.captured_at.isoformat() if row.captured_at else None,
                "detail": dict(row.detail), "idea_id": row.idea_id,
                "signal_score": row.signal_score}
