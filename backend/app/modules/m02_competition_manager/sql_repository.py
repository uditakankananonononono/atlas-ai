"""Tenant-scoped durable competition state."""
from sqlalchemy import JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from app.core.database import Base, SessionLocal, engine
from .schemas import Competition

class CompetitionRow(Base):
    __tablename__="m02_competitions"
    __table_args__=(UniqueConstraint("tenant_id","competition_id"),)
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    tenant_id: Mapped[str]=mapped_column(String(120),index=True)
    competition_id: Mapped[str]=mapped_column(String(36),index=True)
    data: Mapped[dict]=mapped_column(JSON)

class SqlCompetitionRepository:
    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal)->None:
        self.tenant_id=tenant_id; self.sessions=session_factory; Base.metadata.create_all(engine)
    def save(self,competition:Competition)->Competition:
        with self.sessions.begin() as db:
            row=db.scalar(select(CompetitionRow).where(CompetitionRow.tenant_id==self.tenant_id,CompetitionRow.competition_id==competition.id))
            data=competition.model_dump(mode="json")
            if row is None: db.add(CompetitionRow(tenant_id=self.tenant_id,competition_id=competition.id,data=data))
            else: row.data=data
        return competition
    def get(self,competition_id:str)->Competition|None:
        with self.sessions() as db:
            row=db.scalar(select(CompetitionRow).where(CompetitionRow.tenant_id==self.tenant_id,CompetitionRow.competition_id==competition_id))
            return Competition.model_validate(row.data) if row else None
