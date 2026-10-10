import pytest
from app.core.approvals import ApprovalStore
from app.modules.m20_general_cognitive_worker.service import Service as Cognitive
from app.modules.m21_claire.service import Service
class Model:
 async def __call__(self,purpose,payload):return {"steps":[{"id":"p","title":"prepare safely","risk":"read"}]}

def _persisted_m00_rows(db_file):
 """Read M00 request and created-event rows straight from the fixture's SQLite file."""
 from sqlalchemy import create_engine,select
 from app.modules.m00_approval_center import service as m00
 engine=create_engine(f"sqlite:///{db_file}")
 try:
  with engine.connect() as conn:
   requests=list(conn.execute(select(m00.ApprovalRequestRow)).scalars())
   events=list(conn.execute(select(m00.ApprovalEventRow)).scalars())
 finally:engine.dispose()
 return requests,events

@pytest.mark.asyncio
async def test_claire_is_sandboxed_bounded_and_transparent(isolated_m00_approvals,tmp_path):
 approvals=ApprovalStore();s=Service(Cognitive(approvals,Model()),approvals,max_retries=999)
 g=s.intake("build a prototype",["tests pass"],{})
 assert g.limits["environment"]=="atlas" and g.limits["max_retries"]==5
 done=await s.realize(g.id);assert done.status=="succeeded" and done.evidence[0]["policy_basis"]
 req=s.request_environment_change(g.id,"install_package",{"package":"x"});assert req.status.value=="pending"
 requests,events=_persisted_m00_rows(tmp_path/"m00-approvals.sqlite3")
 assert len(requests)==1 and len(events)==1
 assert requests[0].id==req.id and requests[0].module_id==21 and requests[0].action_type=="claire:install_package" and requests[0].status=="pending"
 assert events[0].approval_id==req.id and events[0].event=="created" and events[0].at is not None

def test_claire_rejects_standing_nos():
 s=Service(Cognitive(ApprovalStore(),Model()),ApprovalStore())
 with pytest.raises(ValueError):s.intake("use a discord self-bot",[],{})

def test_claire_is_in_atlas_and_optional_local_endpoint():
 s=Service(Cognitive(ApprovalStore(),Model()),ApprovalStore())
 g=s.intake("manage my research workflow",[],{})
 assert g.limits["environment"]=="atlas" and "paired_local_pc" in g.limits["optional_capabilities"]

@pytest.mark.parametrize("goal",["piracy download","fabricate application activities","use bot evasion","login-driven scraping","do something illegal"])
def test_claire_enforces_full_cant_do_list(goal):
 s=Service(Cognitive(ApprovalStore(),Model()),ApprovalStore())
 with pytest.raises(ValueError):s.intake(goal,[],{})

def test_claire_sends_and_spend_are_per_action_approval(isolated_m00_approvals,tmp_path):
 approvals=ApprovalStore();s=Service(Cognitive(approvals,Model()),approvals);g=s.intake("manage outreach",[],{})
 assert s.request_environment_change(g.id,"send_message",{"recipient":"review first"}).status.value=="pending"
 assert s.request_environment_change(g.id,"spend_money",{"total":"review first"}).status.value=="pending"
 requests,events=_persisted_m00_rows(tmp_path/"m00-approvals.sqlite3")
 assert len(requests)==2 and len(events)==2
 assert {r.action_type for r in requests}=={"claire:send_message","claire:spend_money"}
 assert all(r.module_id==21 and r.status=="pending" for r in requests)
 assert {e.event for e in events}=={"created"}
 assert {e.approval_id for e in events}=={r.id for r in requests}

def test_claire_optional_pc_endpoint_has_full_owner_machine_capability_parity(isolated_m00_approvals,tmp_path):
 approvals=ApprovalStore();s=Service(Cognitive(approvals,Model()),approvals);g=s.intake("organize my machine",[],{})
 ops=("type_text","click","scroll","browser_navigate","install_package","run_command","run_workflow","read_file","write_file","move_file","copy_file")
 ids=[]
 for operation in ops:
  req=s.request_environment_change(g.id,operation,{"operation":operation})
  assert req.status.value=="pending"
  ids.append(req.id)
 requests,events=_persisted_m00_rows(tmp_path/"m00-approvals.sqlite3")
 assert len(requests)==len(ops) and len(events)==len(ops)
 assert {r.id for r in requests}==set(ids)
 assert {r.action_type for r in requests}=={f"claire:{op}" for op in ops}
 assert all(r.module_id==21 and r.status=="pending" for r in requests)
 assert {e.event for e in events}=={"created"}
 assert {e.approval_id for e in events}==set(ids)

def test_claire_refuses_deception_as_user():
 s=Service(Cognitive(ApprovalStore(),Model()),ApprovalStore())
 for goal in ("lie on my behalf to the organizer","deceive this contact","send a false statement as me"):
  with pytest.raises(ValueError):s.intake(goal,[],{})
