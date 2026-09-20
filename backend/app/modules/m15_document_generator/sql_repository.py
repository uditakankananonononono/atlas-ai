"""Immutable, tenant-scoped document version repository."""
from sqlalchemy import JSON,Integer,String,Text,UniqueConstraint,func,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .schemas import Citation,DocumentVersion,FigureSpec
class VersionRow(Base):
 __tablename__="m15_document_versions";__table_args__=(UniqueConstraint("tenant_id","id"),UniqueConstraint("tenant_id","document_id","version_number"))
 pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),index=True);document_id:Mapped[str]=mapped_column(String(120),index=True);version_number:Mapped[int]=mapped_column(Integer)
 format:Mapped[str]=mapped_column(String(20));template_id:Mapped[str]=mapped_column(String(200));content:Mapped[dict]=mapped_column(JSON);parent_version_id:Mapped[str|None]=mapped_column(String(36),nullable=True);content_hash:Mapped[str]=mapped_column(String(64),index=True);status:Mapped[str]=mapped_column(String(40),index=True);output_uri:Mapped[str|None]=mapped_column(Text,nullable=True);citations:Mapped[list]=mapped_column(JSON);figures:Mapped[list]=mapped_column(JSON)
def _view(r):return DocumentVersion(id=r.id,tenant_id=r.tenant_id,document_id=r.document_id,version_number=r.version_number,format=r.format,template_id=r.template_id,content=r.content,parent_version_id=r.parent_version_id,content_hash=r.content_hash,status=r.status,output_uri=r.output_uri,citations=[Citation.model_validate(x) for x in r.citations],figures=[FigureSpec.model_validate(x) for x in r.figures])
class SqlVersionRepository:
 def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=session_factory;Base.metadata.create_all(engine)
 def next_number(self,document_id:str)->int:
  with self.sessions() as db:return int(db.scalar(select(func.max(VersionRow.version_number)).where(VersionRow.tenant_id==self.tenant_id,VersionRow.document_id==document_id)) or 0)+1
 def get(self,version_id:str):
  with self.sessions() as db:
   row=db.scalar(select(VersionRow).where(VersionRow.tenant_id==self.tenant_id,VersionRow.id==version_id));return _view(row) if row else None
 def save(self,item:DocumentVersion):
  with self.sessions.begin() as db:
   exists=db.scalar(select(VersionRow).where(VersionRow.tenant_id==self.tenant_id,VersionRow.id==item.id))
   if exists:raise RuntimeError("document versions are immutable; create a new version")
   row=VersionRow(tenant_id=self.tenant_id,id=item.id,document_id=item.document_id,version_number=item.version_number,format=item.format,template_id=item.template_id,content=item.content,parent_version_id=item.parent_version_id,content_hash=item.content_hash,status=item.status,output_uri=item.output_uri,citations=[x.model_dump(mode="json") for x in item.citations],figures=[x.model_dump(mode="json") for x in item.figures]);db.add(row);db.flush();return _view(row)
