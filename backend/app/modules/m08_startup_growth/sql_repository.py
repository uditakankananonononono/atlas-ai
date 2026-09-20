from datetime import datetime
from sqlalchemy import JSON,DateTime,LargeBinary,String,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class BuildRow(Base):
    __tablename__="m08_builds"
    pk:Mapped[int]=mapped_column(primary_key=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); id:Mapped[str]=mapped_column(String(36),index=True)
    project_id:Mapped[str]=mapped_column(String(120),index=True); kind:Mapped[str]=mapped_column(String(40)); archive:Mapped[bytes]=mapped_column(LargeBinary); manifest:Mapped[dict]=mapped_column(JSON); sha256:Mapped[str]=mapped_column(String(64)); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class Repository:
    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=session_factory;Base.metadata.create_all(engine)
    def save(self,**data):
        with self.sessions.begin() as db:db.add(BuildRow(tenant_id=self.tenant_id,**data))
    def get(self,ident):
        with self.sessions() as db:return db.scalar(select(BuildRow).where(BuildRow.tenant_id==self.tenant_id,BuildRow.id==ident))
