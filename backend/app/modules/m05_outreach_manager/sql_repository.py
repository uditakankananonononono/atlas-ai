"""Tenant-scoped SQL contact repository with append-only changes."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from app.core.database import Base, SessionLocal, engine
from .campaigns import Campaign, MessageEvent, OutreachMessage
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


def _aware(moment):
    """Treat naive datetimes coming back from SQLite as UTC."""
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=timezone.utc)

def _contact(row: ContactRow) -> Contact:
    return Contact(id=row.id,project_id=row.project_id,name=row.name,email=row.email,institution=row.institution,research_topics=row.research_topics,profile_url=row.profile_url,metadata=row.metadata_json,created_at=_aware(row.created_at),updated_at=_aware(row.updated_at),version=row.version)

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
            return [ContactChange(contact_id=r.contact_id,version=r.version,changed_at=_aware(r.changed_at),changes=r.changes) for r in rows]

class CampaignRow(Base):
    __tablename__="m05_campaigns"
    __table_args__=(UniqueConstraint("tenant_id","id"),)
    pk: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    tenant_id: Mapped[str]=mapped_column(String(120),index=True)
    id: Mapped[str]=mapped_column(String(36),index=True)
    project_id: Mapped[str]=mapped_column(String(120),index=True)
    name: Mapped[str]=mapped_column(String(200))
    goal: Mapped[str]=mapped_column(Text)
    audience: Mapped[str]=mapped_column(String(40))
    status: Mapped[str]=mapped_column(String(20),index=True)
    max_follow_ups: Mapped[int]=mapped_column(Integer)
    follow_up_window_days: Mapped[int]=mapped_column(Integer)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))

class MessageRow(Base):
    __tablename__="m05_messages"
    __table_args__=(UniqueConstraint("tenant_id","id"),)
    pk: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    tenant_id: Mapped[str]=mapped_column(String(120),index=True)
    id: Mapped[str]=mapped_column(String(36),index=True)
    campaign_id: Mapped[str]=mapped_column(String(36),index=True)
    contact_id: Mapped[str]=mapped_column(String(36),index=True)
    sequence: Mapped[int]=mapped_column(Integer)
    kind: Mapped[str]=mapped_column(String(20))
    subject: Mapped[str]=mapped_column(String(500))
    body: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(20),index=True)
    approval_id: Mapped[str|None]=mapped_column(String(36),nullable=True)
    provider: Mapped[str|None]=mapped_column(String(40),nullable=True)
    model: Mapped[str|None]=mapped_column(String(120),nullable=True)
    thread_id: Mapped[str|None]=mapped_column(String(200),nullable=True)
    sent_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    version: Mapped[int]=mapped_column(Integer)

class MessageEventRow(Base):
    __tablename__="m05_message_events"
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    tenant_id: Mapped[str]=mapped_column(String(120),index=True)
    message_id: Mapped[str]=mapped_column(String(36),index=True)
    event: Mapped[str]=mapped_column(String(60))
    actor: Mapped[str|None]=mapped_column(String(120),nullable=True)
    at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str,Any]]=mapped_column(JSON)

def _campaign(row: CampaignRow) -> Campaign:
    return Campaign(id=row.id,project_id=row.project_id,name=row.name,goal=row.goal,audience=row.audience,status=row.status,max_follow_ups=row.max_follow_ups,follow_up_window_days=row.follow_up_window_days,created_at=_aware(row.created_at),updated_at=_aware(row.updated_at))

def _message(row: MessageRow) -> OutreachMessage:
    return OutreachMessage(id=row.id,campaign_id=row.campaign_id,contact_id=row.contact_id,sequence=row.sequence,kind=row.kind,subject=row.subject,body=row.body,status=row.status,approval_id=row.approval_id,provider=row.provider,model=row.model,thread_id=row.thread_id,sent_at=_aware(row.sent_at),created_at=_aware(row.created_at),updated_at=_aware(row.updated_at),version=row.version)

class SqlCampaignRepository:
    """Tenant-scoped SQL store for campaigns, messages, and audit events."""

    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal)->None:
        self.tenant_id=tenant_id; self.sessions=session_factory
        Base.metadata.create_all(engine)
    def save_campaign(self,campaign:Campaign)->Campaign:
        with self.sessions.begin() as db:
            row=db.scalar(select(CampaignRow).where(CampaignRow.tenant_id==self.tenant_id,CampaignRow.id==campaign.id))
            if row is None:
                row=CampaignRow(tenant_id=self.tenant_id,id=campaign.id,project_id=campaign.project_id,name=campaign.name,goal=campaign.goal,audience=campaign.audience,status=campaign.status,max_follow_ups=campaign.max_follow_ups,follow_up_window_days=campaign.follow_up_window_days,created_at=campaign.created_at,updated_at=campaign.updated_at); db.add(row)
            else:
                row.project_id=campaign.project_id; row.name=campaign.name; row.goal=campaign.goal; row.audience=campaign.audience; row.status=campaign.status; row.max_follow_ups=campaign.max_follow_ups; row.follow_up_window_days=campaign.follow_up_window_days; row.updated_at=campaign.updated_at
            db.flush(); return _campaign(row)
    def get_campaign(self,campaign_id:str)->Campaign|None:
        with self.sessions() as db:
            row=db.scalar(select(CampaignRow).where(CampaignRow.tenant_id==self.tenant_id,CampaignRow.id==campaign_id)); return _campaign(row) if row else None
    def list_campaigns(self,project_id:str|None=None)->list[Campaign]:
        with self.sessions() as db:
            stmt=select(CampaignRow).where(CampaignRow.tenant_id==self.tenant_id).order_by(CampaignRow.created_at)
            if project_id is not None: stmt=stmt.where(CampaignRow.project_id==project_id)
            return [_campaign(r) for r in db.scalars(stmt)]
    def save_message(self,message:OutreachMessage,event:MessageEvent)->OutreachMessage:
        with self.sessions.begin() as db:
            row=db.scalar(select(MessageRow).where(MessageRow.tenant_id==self.tenant_id,MessageRow.id==message.id))
            if row is None:
                row=MessageRow(tenant_id=self.tenant_id,id=message.id,campaign_id=message.campaign_id,contact_id=message.contact_id,sequence=message.sequence,kind=message.kind,subject=message.subject,body=message.body,status=message.status,approval_id=message.approval_id,provider=message.provider,model=message.model,thread_id=message.thread_id,sent_at=message.sent_at,created_at=message.created_at,updated_at=message.updated_at,version=message.version); db.add(row)
            else:
                row.sequence=message.sequence; row.kind=message.kind; row.subject=message.subject; row.body=message.body; row.status=message.status; row.approval_id=message.approval_id; row.provider=message.provider; row.model=message.model; row.thread_id=message.thread_id; row.sent_at=message.sent_at; row.updated_at=message.updated_at; row.version=message.version
            db.add(MessageEventRow(tenant_id=self.tenant_id,message_id=message.id,event=event.event,actor=event.actor,at=event.at,details=event.details)); db.flush(); return _message(row)
    def get_message(self,message_id:str)->OutreachMessage|None:
        with self.sessions() as db:
            row=db.scalar(select(MessageRow).where(MessageRow.tenant_id==self.tenant_id,MessageRow.id==message_id)); return _message(row) if row else None
    def list_messages(self,campaign_id:str|None=None,contact_id:str|None=None,status:str|None=None)->list[OutreachMessage]:
        with self.sessions() as db:
            stmt=select(MessageRow).where(MessageRow.tenant_id==self.tenant_id).order_by(MessageRow.created_at)
            if campaign_id is not None: stmt=stmt.where(MessageRow.campaign_id==campaign_id)
            if contact_id is not None: stmt=stmt.where(MessageRow.contact_id==contact_id)
            if status is not None: stmt=stmt.where(MessageRow.status==status)
            return [_message(r) for r in db.scalars(stmt)]
    def events(self,message_id:str)->list[MessageEvent]:
        with self.sessions() as db:
            rows=list(db.scalars(select(MessageEventRow).where(MessageEventRow.tenant_id==self.tenant_id,MessageEventRow.message_id==message_id).order_by(MessageEventRow.id)))
            return [MessageEvent(message_id=r.message_id,event=r.event,actor=r.actor,at=_aware(r.at),details=r.details) for r in rows]
