"""Tenant-scoped durable social plans and analytics reports."""
from datetime import datetime
from sqlalchemy import JSON,String,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .service import AnalysisReport,AssetPrompt,ContentPlan,Platform,PlatformDraft

class SocialPlanRow(Base):
    __tablename__="m06_social_plans"; __table_args__=(UniqueConstraint("tenant_id","item_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); item_id:Mapped[str]=mapped_column(String(36),index=True); data:Mapped[dict]=mapped_column(JSON)
class SocialReportRow(Base):
    __tablename__="m06_social_reports"; __table_args__=(UniqueConstraint("tenant_id","item_id"),)
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); item_id:Mapped[str]=mapped_column(String(36),index=True); data:Mapped[dict]=mapped_column(JSON)

def plan_data(x:ContentPlan)->dict:
    return {"id":x.id,"brief":x.brief,"status":x.status,"created_at":x.created_at.isoformat(),"drafts":[{"platform":d.platform.value,"format":d.format,"post_copy":d.post_copy,"asset_prompts":[a.__dict__ for a in d.asset_prompts]} for d in x.drafts]}
def to_plan(d:dict)->ContentPlan:
    return ContentPlan(id=d["id"],brief=d["brief"],status=d["status"],created_at=datetime.fromisoformat(d["created_at"]),drafts=[PlatformDraft(platform=Platform(x["platform"]),format=x["format"],post_copy=x["post_copy"],asset_prompts=[AssetPrompt(**a) for a in x["asset_prompts"]]) for x in d["drafts"]])
def report_data(x:AnalysisReport)->dict: return {"id":x.id,"platform":x.platform.value,"since_days":x.since_days,"suggestions":x.suggestions,"model":x.model,"created_at":x.created_at.isoformat()}
def to_report(d:dict)->AnalysisReport: return AnalysisReport(id=d["id"],platform=Platform(d["platform"]),since_days=d["since_days"],suggestions=d["suggestions"],model=d["model"],created_at=datetime.fromisoformat(d["created_at"]))

class SqlSocialRepository:
    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal)->None: self.tenant_id=tenant_id; self.sessions=session_factory; Base.metadata.create_all(engine)
    def _save(self,model,item_id,data):
        with self.sessions.begin() as db:
            row=db.scalar(select(model).where(model.tenant_id==self.tenant_id,model.item_id==item_id))
            if row is None: db.add(model(tenant_id=self.tenant_id,item_id=item_id,data=data))
            else: row.data=data
    def save_plan(self,x): self._save(SocialPlanRow,x.id,plan_data(x)); return x
    def get_plan(self,item_id):
        with self.sessions() as db: row=db.scalar(select(SocialPlanRow).where(SocialPlanRow.tenant_id==self.tenant_id,SocialPlanRow.item_id==item_id)); return to_plan(row.data) if row else None
    def save_report(self,x): self._save(SocialReportRow,x.id,report_data(x)); return x
    def get_report(self,item_id):
        with self.sessions() as db: row=db.scalar(select(SocialReportRow).where(SocialReportRow.tenant_id==self.tenant_id,SocialReportRow.item_id==item_id)); return to_report(row.data) if row else None
