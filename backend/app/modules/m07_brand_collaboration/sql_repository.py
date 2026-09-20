"""Tenant-isolated persistence for Module 7."""
from datetime import datetime
from sqlalchemy import JSON, DateTime, Float, LargeBinary, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from app.core.database import Base, SessionLocal, engine

class BrandRow(Base):
    __tablename__="m07_brands"
    pk: Mapped[int]=mapped_column(primary_key=True); tenant_id: Mapped[str]=mapped_column(String(120),index=True)
    id: Mapped[str]=mapped_column(String(36),index=True); name: Mapped[str]=mapped_column(String(200)); mission: Mapped[str]=mapped_column(Text)
    public_url: Mapped[str]=mapped_column(Text); contact_api: Mapped[str]=mapped_column(String(40)); audience_tags: Mapped[list]=mapped_column(JSON)
    alignment_score: Mapped[float]=mapped_column(Float); alignment_reasons: Mapped[list]=mapped_column(JSON); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
class ArtifactRow(Base):
    __tablename__="m07_artifacts"
    pk: Mapped[int]=mapped_column(primary_key=True); tenant_id: Mapped[str]=mapped_column(String(120),index=True); id: Mapped[str]=mapped_column(String(36),index=True)
    brand_id: Mapped[str]=mapped_column(String(36),index=True); kind: Mapped[str]=mapped_column(String(40)); content_type: Mapped[str]=mapped_column(String(120)); content: Mapped[bytes]=mapped_column(LargeBinary)
    sha256: Mapped[str]=mapped_column(String(64)); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); metadata_json: Mapped[dict]=mapped_column(JSON)
class EventRow(Base):
    __tablename__="m07_partnership_events"
    pk: Mapped[int]=mapped_column(primary_key=True); tenant_id: Mapped[str]=mapped_column(String(120),index=True); id: Mapped[str]=mapped_column(String(36),index=True)
    brand_id: Mapped[str]=mapped_column(String(36),index=True); kind: Mapped[str]=mapped_column(String(40)); occurred_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); data: Mapped[dict]=mapped_column(JSON); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
class Repository:
    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal): self.tenant_id=tenant_id; self.sessions=session_factory; Base.metadata.create_all(engine)
    def add_brand(self, **data):
        with self.sessions.begin() as db: db.add(BrandRow(tenant_id=self.tenant_id,**data))
    def brand(self,brand_id:str):
        with self.sessions() as db: return db.scalar(select(BrandRow).where(BrandRow.tenant_id==self.tenant_id,BrandRow.id==brand_id))
    def add_artifact(self,**data):
        with self.sessions.begin() as db: db.add(ArtifactRow(tenant_id=self.tenant_id,**data))
    def artifact(self,artifact_id:str):
        with self.sessions() as db: return db.scalar(select(ArtifactRow).where(ArtifactRow.tenant_id==self.tenant_id,ArtifactRow.id==artifact_id))
    def add_event(self,**data):
        with self.sessions.begin() as db: db.add(EventRow(tenant_id=self.tenant_id,**data))
    def events(self,brand_id:str):
        with self.sessions() as db: return list(db.scalars(select(EventRow).where(EventRow.tenant_id==self.tenant_id,EventRow.brand_id==brand_id).order_by(EventRow.occurred_at)))
