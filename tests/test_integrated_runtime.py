import asyncio
from app.runtime.integration import AtlasRuntime,RuntimeContext
from app.runtime.workflows import OpportunityToApplicationWorkflow,ResearchToDocumentWorkflow

def handler(name,calls):
 async def run(context,handoff):
  calls.append((name,context.tenant_id,handoff.source_module,handoff.target_module,handoff.requires_approval,len(handoff.evidence)))
  return {"step":name,"received":sorted(handoff.payload)}
 return run

def test_opportunity_application_is_one_cross_module_flow_with_shared_tenant_evidence_and_gate():
 calls=[];r=AtlasRuntime()
 for m,o,n in [(2,"analyze_opportunity","rules"),(2,"draft_application","draft"),(13,"stage_form","browser"),(0,"request_approval","approval")]:r.register(m,o,handler(n,calls))
 ctx=RuntimeContext("tenant-a","owner","corr-1")
 out=asyncio.run(OpportunityToApplicationWorkflow(r).prepare(ctx,{"id":"opp-1","url":"https://official.example"},[{"type":"google_doc","revision":"r1"}]))
 assert out["correlation_id"]=="corr-1"
 assert [x[0] for x in calls]==["rules","draft","browser","approval"]
 assert all(x[1]=="tenant-a" and x[5]==2 for x in calls)
 assert calls[-2][4] and calls[-1][4]
 assert [x["state"] for x in r.trace]==["started","completed"]*4

def test_research_document_is_cross_module_not_side_by_side():
 calls=[];r=AtlasRuntime()
 for m,o,n in [(4,"research","research"),(3,"draft_grounded","draft"),(15,"render_document","render"),(0,"request_approval","approval")]:r.register(m,o,handler(n,calls))
 out=asyncio.run(ResearchToDocumentWorkflow(r).prepare(RuntimeContext("t","u","c"),"Question?",[{"paper_id":"p1","url":"https://arxiv.org/x"}]))
 assert [x[0] for x in calls]==["research","draft","render","approval"] and out["approval"]["step"]=="approval"

def test_runtime_fails_closed_on_unregistered_handoff_or_missing_tenant():
 r=AtlasRuntime()
 async def run():
  from app.runtime.integration import Handoff
  try:await r.dispatch(RuntimeContext("","u","c"),Handoff(source_module=1,target_module=2,operation="x",payload={}))
  except PermissionError:pass
  else:raise AssertionError
  try:await r.dispatch(RuntimeContext("t","u","c"),Handoff(source_module=1,target_module=2,operation="x",payload={}))
  except LookupError:pass
  else:raise AssertionError
 asyncio.run(run())
