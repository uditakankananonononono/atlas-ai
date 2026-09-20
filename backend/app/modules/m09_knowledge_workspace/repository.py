"""Tenant-scoped adjacency-list persistence with append-only audit history."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import JSON,DateTime,Float,Integer,String,Text,UniqueConstraint,or_,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .schemas import Edge,LinkSuggestion,Node,NodeType,Relationship,SuggestionStatus
class NodeRow(Base):
    __tablename__="m09_nodes";__table_args__=(UniqueConstraint("tenant_id","source_module","external_id",name="uq_m09_external"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),index=True)
    node_type:Mapped[str]=mapped_column(String(40),index=True);title:Mapped[str]=mapped_column(String(500),index=True);body:Mapped[str|None]=mapped_column(Text,nullable=True);source_uri:Mapped[str|None]=mapped_column(Text,nullable=True);source_module:Mapped[str|None]=mapped_column(String(80),nullable=True);external_id:Mapped[str|None]=mapped_column(String(500),nullable=True)
    metadata_json:Mapped[dict]=mapped_column(JSON,default=dict);embedding:Mapped[list|None]=mapped_column(JSON,nullable=True);version:Mapped[int]=mapped_column(Integer);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class EdgeRow(Base):
    __tablename__="m09_edges";__table_args__=(UniqueConstraint("tenant_id","source_id","target_id","relationship",name="uq_m09_edge"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),index=True);source_id:Mapped[str]=mapped_column(String(36),index=True);target_id:Mapped[str]=mapped_column(String(36),index=True);relationship:Mapped[str]=mapped_column(String(40));rationale:Mapped[str|None]=mapped_column(Text,nullable=True);evidence:Mapped[dict]=mapped_column(JSON,default=dict);confidence:Mapped[float]=mapped_column(Float);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class SuggestionRow(Base):
    __tablename__="m09_suggestions";__table_args__=(UniqueConstraint("tenant_id","source_id","target_id","relationship",name="uq_m09_suggestion"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),index=True);source_id:Mapped[str]=mapped_column(String(36));target_id:Mapped[str]=mapped_column(String(36));relationship:Mapped[str]=mapped_column(String(40));score:Mapped[float]=mapped_column(Float);reasons:Mapped[list]=mapped_column(JSON);status:Mapped[str]=mapped_column(String(20));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class AuditRow(Base):
    __tablename__="m09_audit";pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);actor_id:Mapped[str]=mapped_column(String(120));action:Mapped[str]=mapped_column(String(80));entity_id:Mapped[str]=mapped_column(String(36));detail:Mapped[dict]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
def _node(r):return Node(id=r.id,node_type=NodeType(r.node_type),title=r.title,body=r.body,source_uri=r.source_uri,source_module=r.source_module,external_id=r.external_id,metadata=r.metadata_json,embedding=r.embedding,version=r.version,created_at=r.created_at,updated_at=r.updated_at)
def _edge(r):return Edge(id=r.id,source_id=r.source_id,target_id=r.target_id,relationship=Relationship(r.relationship),rationale=r.rationale,evidence=r.evidence,confidence=r.confidence,created_at=r.created_at)
def _suggestion(r):return LinkSuggestion(id=r.id,source_id=r.source_id,target_id=r.target_id,relationship=Relationship(r.relationship),score=r.score,reasons=r.reasons,status=SuggestionStatus(r.status),created_at=r.created_at,reviewed_at=r.reviewed_at)
class SqlGraphRepository:
    def __init__(self,tenant_id:str,actor_id:str,session_factory:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.actor_id=actor_id;self.sessions=session_factory;Base.metadata.create_all(engine)
    def save_node(self,n:Node,action="node.created"):
        with self.sessions.begin() as db:
            r=db.scalar(select(NodeRow).where(NodeRow.tenant_id==self.tenant_id,NodeRow.id==n.id))
            if r is None:r=NodeRow(tenant_id=self.tenant_id,id=n.id);db.add(r)
            for k,v in {"node_type":n.node_type.value,"title":n.title,"body":n.body,"source_uri":n.source_uri,"source_module":n.source_module,"external_id":n.external_id,"metadata_json":n.metadata,"embedding":n.embedding,"version":n.version,"created_at":n.created_at,"updated_at":n.updated_at}.items():setattr(r,k,v)
            db.add(AuditRow(tenant_id=self.tenant_id,actor_id=self.actor_id,action=action,entity_id=n.id,detail={"version":n.version,"title":n.title},created_at=n.updated_at))
        return n
    def get_node(self,node_id):
        with self.sessions() as db:r=db.scalar(select(NodeRow).where(NodeRow.tenant_id==self.tenant_id,NodeRow.id==node_id));return _node(r) if r else None
    def list_nodes(self,limit=500):
        with self.sessions() as db:return [_node(r) for r in db.scalars(select(NodeRow).where(NodeRow.tenant_id==self.tenant_id).limit(limit))]
    def save_edge(self,e:Edge):
        with self.sessions.begin() as db:db.add(EdgeRow(tenant_id=self.tenant_id,id=e.id,source_id=e.source_id,target_id=e.target_id,relationship=e.relationship.value,rationale=e.rationale,evidence=e.evidence,confidence=e.confidence,created_at=e.created_at));db.add(AuditRow(tenant_id=self.tenant_id,actor_id=self.actor_id,action="edge.created",entity_id=e.id,detail={"relationship":e.relationship.value},created_at=e.created_at))
        return e
    def edges_for(self,node_ids:set[str],limit=1000):
        with self.sessions() as db:return [_edge(r) for r in db.scalars(select(EdgeRow).where(EdgeRow.tenant_id==self.tenant_id,or_(EdgeRow.source_id.in_(node_ids),EdgeRow.target_id.in_(node_ids))).limit(limit))]
    def save_suggestion(self,s:LinkSuggestion):
        with self.sessions.begin() as db:
            exists=db.scalar(select(SuggestionRow).where(SuggestionRow.tenant_id==self.tenant_id,SuggestionRow.source_id==s.source_id,SuggestionRow.target_id==s.target_id,SuggestionRow.relationship==s.relationship.value))
            if not exists:db.add(SuggestionRow(tenant_id=self.tenant_id,id=s.id,source_id=s.source_id,target_id=s.target_id,relationship=s.relationship.value,score=s.score,reasons=s.reasons,status=s.status.value,created_at=s.created_at,reviewed_at=s.reviewed_at))
        return s
    def get_suggestion(self,sid):
        with self.sessions() as db:r=db.scalar(select(SuggestionRow).where(SuggestionRow.tenant_id==self.tenant_id,SuggestionRow.id==sid));return _suggestion(r) if r else None
    def review_suggestion(self,sid,status,at):
        with self.sessions.begin() as db:r=db.scalar(select(SuggestionRow).where(SuggestionRow.tenant_id==self.tenant_id,SuggestionRow.id==sid));r.status=status.value;r.reviewed_at=at;db.flush();return _suggestion(r)
