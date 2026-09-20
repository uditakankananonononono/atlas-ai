"""Tenant-scoped durable storage for the Social Media Manager.

Every row carries tenant_id and every query filters on it, matching the
tenant pattern used across Atlas module repositories. Plans/reports keep the
original JSON-blob shape for backward compatibility; schedules, publish
receipts, metrics snapshots, and A/B tests follow the same blob pattern with
typed (de)serializers so domain dataclasses round-trip losslessly.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine

from .adapters import NormalizedMetrics
from .marketing import MarketingArtifact
from .analytics import ABTest, MetricsSnapshot
from .scheduler import PublishRecord, ScheduleEntry
from .service import AnalysisReport, AssetPrompt, ContentPlan, Platform, PlatformDraft


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SocialPlanRow(Base):
    __tablename__="m06_social_plans"; __table_args__=(UniqueConstraint("tenant_id","item_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); item_id:Mapped[str]=mapped_column(String(36),index=True); data:Mapped[dict]=mapped_column(JSON)
class SocialReportRow(Base):
    __tablename__="m06_social_reports"; __table_args__=(UniqueConstraint("tenant_id","item_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); item_id:Mapped[str]=mapped_column(String(36),index=True); data:Mapped[dict]=mapped_column(JSON)
class SocialScheduleRow(Base):
    __tablename__="m06_social_schedules"; __table_args__=(UniqueConstraint("tenant_id","item_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); item_id:Mapped[str]=mapped_column(String(36),index=True); status:Mapped[str]=mapped_column(String(30),index=True); data:Mapped[dict]=mapped_column(JSON)
class SocialPublishRow(Base):
    __tablename__="m06_social_publishes"; __table_args__=(UniqueConstraint("tenant_id","item_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); item_id:Mapped[str]=mapped_column(String(36),index=True); data:Mapped[dict]=mapped_column(JSON)
class SocialSnapshotRow(Base):
    __tablename__="m06_social_snapshots"; __table_args__=(UniqueConstraint("tenant_id","item_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); item_id:Mapped[str]=mapped_column(String(36),index=True); platform:Mapped[str]=mapped_column(String(30),index=True); data:Mapped[dict]=mapped_column(JSON)
class SocialABTestRow(Base):
    __tablename__="m06_social_ab_tests"; __table_args__=(UniqueConstraint("tenant_id","item_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); item_id:Mapped[str]=mapped_column(String(36),index=True); data:Mapped[dict]=mapped_column(JSON)
class SocialArtifactRow(Base):
    __tablename__="m06_social_artifacts"; __table_args__=(UniqueConstraint("tenant_id","item_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); item_id:Mapped[str]=mapped_column(String(36),index=True); kind:Mapped[str]=mapped_column(String(60),index=True); data:Mapped[dict]=mapped_column(JSON)

def plan_data(x:ContentPlan)->dict:
    return {"id":x.id,"brief":x.brief,"status":x.status,"created_at":x.created_at.isoformat(),"drafts":[{"platform":d.platform.value,"format":d.format,"post_copy":d.post_copy,"asset_prompts":[a.__dict__ for a in d.asset_prompts]} for d in x.drafts]}
def to_plan(d:dict)->ContentPlan:
    return ContentPlan(id=d["id"],brief=d["brief"],status=d["status"],created_at=datetime.fromisoformat(d["created_at"]),drafts=[PlatformDraft(platform=Platform(x["platform"]),format=x["format"],post_copy=x["post_copy"],asset_prompts=[AssetPrompt(**a) for a in x["asset_prompts"]]) for x in d["drafts"]])
def report_data(x:AnalysisReport)->dict: return {"id":x.id,"platform":x.platform.value,"since_days":x.since_days,"suggestions":x.suggestions,"model":x.model,"created_at":x.created_at.isoformat()}
def to_report(d:dict)->AnalysisReport: return AnalysisReport(id=d["id"],platform=Platform(d["platform"]),since_days=d["since_days"],suggestions=d["suggestions"],model=d["model"],created_at=datetime.fromisoformat(d["created_at"]))

def schedule_data(x: ScheduleEntry) -> dict:
    return {
        "id": x.id, "plan_id": x.plan_id, "platform": x.platform.value, "format": x.format,
        "text": x.text, "publish_at": x.publish_at.isoformat(), "approval_id": x.approval_id,
        "status": x.status, "media_urls": list(x.media_urls), "alt_texts": list(x.alt_texts),
        "thread_chunks": list(x.thread_chunks), "link": x.link, "sponsored": x.sponsored,
        "created_at": x.created_at.isoformat(), "decided_at": _iso(x.decided_at),
        "published_at": _iso(x.published_at), "external_id": x.external_id,
        "external_url": x.external_url, "draft_only": x.draft_only, "failure": x.failure,
    }

def to_schedule(d: dict) -> ScheduleEntry:
    return ScheduleEntry(
        id=d["id"], plan_id=d["plan_id"], platform=Platform(d["platform"]), format=d["format"],
        text=d["text"], publish_at=datetime.fromisoformat(d["publish_at"]), approval_id=d["approval_id"],
        status=d["status"], media_urls=list(d.get("media_urls") or []), alt_texts=list(d.get("alt_texts") or []),
        thread_chunks=list(d.get("thread_chunks") or []), link=d.get("link"), sponsored=bool(d.get("sponsored")),
        created_at=datetime.fromisoformat(d["created_at"]), decided_at=_dt(d.get("decided_at")),
        published_at=_dt(d.get("published_at")), external_id=d.get("external_id"),
        external_url=d.get("external_url"), draft_only=bool(d.get("draft_only")), failure=d.get("failure"),
    )

def publish_record_data(x: PublishRecord) -> dict:
    return {
        "schedule_id": x.schedule_id, "platform": x.platform, "external_id": x.external_id,
        "external_url": x.external_url, "draft_only": x.draft_only, "published_at": x.published_at.isoformat(),
    }

def to_publish_record(d: dict) -> PublishRecord:
    return PublishRecord(
        schedule_id=d["schedule_id"], platform=d["platform"], external_id=d["external_id"],
        external_url=d.get("external_url"), draft_only=bool(d.get("draft_only")),
        published_at=datetime.fromisoformat(d["published_at"]),
    )

def snapshot_data(x: MetricsSnapshot) -> dict:
    return {
        "id": x.id, "platform": x.platform.value, "since_days": x.since_days,
        "metrics": asdict(x.metrics), "captured_at": x.captured_at.isoformat(),
    }

def to_snapshot(d: dict) -> MetricsSnapshot:
    return MetricsSnapshot(
        id=d["id"], platform=Platform(d["platform"]), since_days=d["since_days"],
        metrics=NormalizedMetrics(**d["metrics"]), captured_at=datetime.fromisoformat(d["captured_at"]),
    )

def ab_test_data(x: ABTest) -> dict:
    return {
        "id": x.id, "plan_id": x.plan_id, "platform": x.platform.value, "variant_a": x.variant_a,
        "variant_b": x.variant_b, "approval_id": x.approval_id, "status": x.status,
        "external_id_a": x.external_id_a, "external_id_b": x.external_id_b,
        "metrics_a": dict(x.metrics_a), "metrics_b": dict(x.metrics_b), "verdict": x.verdict,
        "created_at": x.created_at.isoformat(),
    }

def to_ab_test(d: dict) -> ABTest:
    return ABTest(
        id=d["id"], plan_id=d["plan_id"], platform=Platform(d["platform"]), variant_a=d["variant_a"],
        variant_b=d["variant_b"], approval_id=d["approval_id"], status=d["status"],
        external_id_a=d.get("external_id_a"), external_id_b=d.get("external_id_b"),
        metrics_a=dict(d.get("metrics_a") or {}), metrics_b=dict(d.get("metrics_b") or {}),
        verdict=d.get("verdict"), created_at=datetime.fromisoformat(d["created_at"]),
    )


def artifact_data(x: MarketingArtifact) -> dict:
    return {"id": x.id, "row": x.row, "kind": x.kind, "title": x.title, "sections": x.sections,
            "inputs": x.inputs, "status": x.status, "provenance": x.provenance, "model": x.model,
            "created_at": x.created_at.isoformat()}

def to_artifact(d: dict) -> MarketingArtifact:
    return MarketingArtifact(id=d["id"], row=d["row"], kind=d["kind"], title=d["title"],
                             sections=d["sections"], inputs=d["inputs"], status=d.get("status", "draft"),
                             provenance=d.get("provenance", "llm-draft"), model=d.get("model"),
                             created_at=datetime.fromisoformat(d["created_at"]))


class SqlSocialRepository:
    """Durable tenant-scoped store for plans, reports, schedules, and analytics."""

    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal)->None:
        self.tenant_id=tenant_id; self.sessions=session_factory; Base.metadata.create_all(engine)

    def _save(self,model,item_id,data,extra=None):
        with self.sessions.begin() as db:
            row=db.scalar(select(model).where(model.tenant_id==self.tenant_id,model.item_id==item_id))
            if row is None:
                row=model(tenant_id=self.tenant_id,item_id=item_id,data=data,**(extra or {})); db.add(row)
            else:
                row.data=data
                for key,value in (extra or {}).items(): setattr(row,key,value)

    def _get(self,model,item_id,convert):
        with self.sessions() as db:
            row=db.scalar(select(model).where(model.tenant_id==self.tenant_id,model.item_id==item_id))
            return convert(row.data) if row else None

    def _list(self,model,convert,filters=()):
        with self.sessions() as db:
            rows=list(db.scalars(select(model).where(model.tenant_id==self.tenant_id,*filters)))
            return [convert(row.data) for row in rows]

    # plans + reports (original API; signatures unchanged)
    def save_plan(self,x): self._save(SocialPlanRow,x.id,plan_data(x)); return x
    def get_plan(self,item_id): return self._get(SocialPlanRow,item_id,to_plan)
    def save_report(self,x): self._save(SocialReportRow,x.id,report_data(x)); return x
    def get_report(self,item_id): return self._get(SocialReportRow,item_id,to_report)

    # schedules + publish receipts
    def save_schedule(self,x): self._save(SocialScheduleRow,x.id,schedule_data(x),{"status":x.status}); return x
    def get_schedule(self,item_id): return self._get(SocialScheduleRow,item_id,to_schedule)
    def list_schedules(self,plan_id:str|None=None):
        entries=self._list(SocialScheduleRow,to_schedule)
        return [e for e in entries if plan_id is None or e.plan_id==plan_id]
    def save_publish_record(self,x):
        import uuid as _uuid
        self._save(SocialPublishRow,f"{x.schedule_id}:{_uuid.uuid4().hex[:8]}",publish_record_data(x)); return x
    def list_publish_records(self,schedule_id:str|None=None):
        records=self._list(SocialPublishRow,to_publish_record)
        return [r for r in records if schedule_id is None or r.schedule_id==schedule_id]

    # metrics snapshots + A/B tests
    def save_snapshot(self,x): self._save(SocialSnapshotRow,x.id,snapshot_data(x),{"platform":x.platform.value}); return x
    def get_snapshot(self,item_id): return self._get(SocialSnapshotRow,item_id,to_snapshot)
    def list_snapshots(self,platform=None):
        filters=(SocialSnapshotRow.platform==platform.value,) if platform else ()
        return self._list(SocialSnapshotRow,to_snapshot,filters)
    def save_ab_test(self,x): self._save(SocialABTestRow,x.id,ab_test_data(x)); return x
    def get_ab_test(self,item_id): return self._get(SocialABTestRow,item_id,to_ab_test)
    def list_ab_tests(self,plan_id:str|None=None):
        tests=self._list(SocialABTestRow,to_ab_test)
        return [t for t in tests if plan_id is None or t.plan_id==plan_id]
    def save_artifact(self,x): self._save(SocialArtifactRow,x.id,artifact_data(x),{"kind":x.kind}); return x
    def get_artifact(self,item_id): return self._get(SocialArtifactRow,item_id,to_artifact)
    def list_artifacts(self,kind:str|None=None):
        return self._list(SocialArtifactRow,to_artifact,(() if kind is None else (SocialArtifactRow.kind==kind,)))
