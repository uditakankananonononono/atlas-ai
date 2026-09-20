"""Tenant-scoped SQL contact repository with append-only changes."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from app.core.database import Base, SessionLocal, engine
from .schemas import Contact, ContactChange

class ContactRow(Base):
    __tablename__="m05_contacts"
    __table_args__=(UniqueConstraint("tenant_id","id"),)
    pk: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    tenant_id: Mapped[str]=mapped_column(String(120),index=True)
    id: Mapped[str]=mapped_column(String(36),index=True)
    project_id: Mapped[str]=mapped_column(String(120),index=True)
    name: Mapped[str]=mapped_column(String(200))
    email: Mapped[str|None]=mapped_column(String(320),nullable=True,index=True)
    institution: Mapped[str|None]=mapped_column(String(300),nullable=True)
    research_topics: Mapped[list]=mapped_column(JSON,default=list)
    profile_url: Mapped[str|None]=mapped_column(Text,nullable=True)
    metadata_json: Mapped[dict]=mapped_column(JSON,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    version: Mapped[int]=mapped_column(Integer)

class ContactChangeRow(Base):
    __tablename__="m05_contact_changes"
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    tenant_id: Mapped[str]=mapped_column(String(120),index=True)
    contact_id: Mapped[str]=mapped_column(String(36),index=True)
    version: Mapped[int]=mapped_column(Integer)
    changed_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    changes: Mapped[dict[str,Any]]=mapped_column(JSON)

def _contact(row: ContactRow) -> Contact:
    return Contact(id=row.id,project_id=row.project_id,name=row.name,email=row.email,institution=row.institution,research_topics=row.research_topics,profile_url=row.profile_url,metadata=row.metadata_json,created_at=row.created_at,updated_at=row.updated_at,version=row.version)

class SqlContactRepository:
    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal)->None:
        self.tenant_id=tenant_id; self.sessions=session_factory
        Base.metadata.create_all(engine)
    def save(self,contact:Contact,changes:dict[str,Any])->Contact:
        with self.sessions.begin() as db:
            row=db.scalar(select(ContactRow).where(ContactRow.tenant_id==self.tenant_id,ContactRow.id==contact.id))
            data=contact.model_dump(mode="json"); data["profile_url"]=str(contact.profile_url) if contact.profile_url else None
            if row is None:
                row=ContactRow(tenant_id=self.tenant_id,id=contact.id,project_id=contact.project_id,name=contact.name,email=contact.email,institution=contact.institution,research_topics=contact.research_topics,profile_url=data["profile_url"],metadata_json=contact.metadata,created_at=contact.created_at,updated_at=contact.updated_at,version=contact.version); db.add(row)
            else:
                row.project_id=contact.project_id; row.name=contact.name; row.email=contact.email; row.institution=contact.institution; row.research_topics=contact.research_topics; row.profile_url=data["profile_url"]; row.metadata_json=contact.metadata; row.updated_at=contact.updated_at; row.version=contact.version
            db.add(ContactChangeRow(tenant_id=self.tenant_id,contact_id=contact.id,version=contact.version,changed_at=contact.updated_at,changes=changes)); db.flush(); return _contact(row)
    def get(self,contact_id:str)->Contact|None:
        with self.sessions() as db:
            row=db.scalar(select(ContactRow).where(ContactRow.tenant_id==self.tenant_id,ContactRow.id==contact_id)); return _contact(row) if row else None
    def changes(self,contact_id:str)->list[ContactChange]:
        with self.sessions() as db:
            rows=list(db.scalars(select(ContactChangeRow).where(ContactChangeRow.tenant_id==self.tenant_id,ContactChangeRow.contact_id==contact_id).order_by(ContactChangeRow.version)))
            return [ContactChange(contact_id=r.contact_id,version=r.version,changed_at=r.changed_at,changes=r.changes) for r in rows]
