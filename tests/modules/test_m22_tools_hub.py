import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.modules.m00_approval_center.service import ApprovalRequestRow, ApprovalEventRow
from app.core.approvals import ApprovalStore
from app.modules.m22_tools_hub.service import Service
class Collector:
 name="official-registry"
 async def collect(self,q):
  for x in [{"name":"SafeTool","url":"https://example.org/tool","security":.9,"fit":.8,"maintenance":.9,"novelty":.7,"evidence":[{"url":"https://example.org"}]},{"name":"Bad","url":"https://bad.test","summary":"rotating proxy stealth scraping","security":1,"fit":1}]:yield x
@pytest.mark.asyncio
async def test_discovery_filters_and_install_is_approval_gated(isolated_m22_approvals, tmp_path):
 s=Service(ApprovalStore(),[Collector()]);items=await s.discover("new research tools")
 assert [x.name for x in items]==["SafeTool"]
 p=s.propose_install(items[0].id,"api",{"token_secret":"hidden","region":"us"},["read"])
 assert p.approval_id and not s.installed
 req=s.approvals.list()[0];assert "token_secret" not in req.payload["config_preview"]
 # Builder not run; peer rejected prior tree's score, audited a diagnostic fix.
 # Repaired head awaits peer recheck; reopen actual disk DB, not service facade.
 db_path=tmp_path / "m00-approvals.sqlite3"
 assert db_path.is_file()
 reader=create_engine(f"sqlite:///{db_path}")
 try:
  with Session(reader) as db:
   persisted=db.execute(select(ApprovalRequestRow).where(ApprovalRequestRow.id==p.approval_id)).scalars().one()
   assert persisted.id==p.approval_id==req.id
   assert persisted.action_type=="integrate_tool"
   assert persisted.module_id==22
   assert persisted.user_id=="default"
   assert persisted.status=="pending"
   assert persisted.decided_at is None
   assert persisted.approved_by is None
   assert persisted.expires_at is None
   assert persisted.created_at is not None
   expected_payload={
    "candidate_id":items[0].id,
    "name":"SafeTool",
    "url":"https://example.org/tool",
    "adapter_type":"api",
    "config_preview":{"region":"us"},
    "requested_scopes":["read"],
    "rollback_plan":{
     "strategy":"snapshot_then_restore",
     "remove_credentials":True,
     "disable_adapter":True,
     "candidate":"SafeTool",
    },
    "score":0.7833,
   }
   assert persisted.payload==expected_payload
   assert req.payload==expected_payload
   events=db.execute(select(ApprovalEventRow).where(ApprovalEventRow.approval_id==persisted.id)).scalars().all()
   assert len(events)==1
   event=events[0]
   assert event.id is not None
   assert event.approval_id==persisted.id==p.approval_id
   assert event.event=="created"
   assert event.actor is None
   assert event.at==persisted.created_at
 finally:
  reader.dispose()
 assert s.proposals[p.id]==p
 assert s.installed=={}
 assert s.portfolio()==[]
