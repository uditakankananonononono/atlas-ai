from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalBroadcaster, Service as ApprovalService
from app.modules.m17_advice_essay.schemas import AdviceSource, IdentityMaterial, SourceKind
from app.modules.m20_general_cognitive_worker.schemas import Risk
from app.runtime.cross_module_proofs import CognitiveEvidenceWorkflow,CognitiveWorkflowRequest,EssayReviewWorkflow,EssayWorkflowRequest,LocalToolDefinition,VersionStore

@pytest.fixture
def approvals(tmp_path):
 engine=create_engine(f"sqlite:///{tmp_path}/cross.db",connect_args={"check_same_thread":False});Base.metadata.create_all(engine)
 return ApprovalService(sessionmaker(bind=engine,expire_on_commit=False),ApprovalBroadcaster())

def essay_request(tenant="student-a"):
 owner=uuid4()
 return EssayWorkflowRequest(tenant_id=tenant,owner_id=owner,advice_sources=[AdviceSource(owner_id=owner,source_kind=SourceKind.PUBLIC_WEB,platform="admissions-office",canonical_url="https://example.edu/admissions/essay-advice",content="Specific scenes reveal character. Verify every factual claim.",permission_basis="public university page")],identity_materials=[IdentityMaterial(owner_id=owner,label="Grandmother's loom",description="I learned Tai-Ahom words while watching my grandmother weave faa-sin.",user_confirmed=True)],prompt="Describe an experience that shaped your identity.",word_limit=650,student_draft="At my grandmother's loom, I recorded each Tai-Ahom word in my own notebook.",student_authored=True)

def test_identity_advice_to_student_version_stops_at_review_gate(approvals):
 w=EssayReviewWorkflow(approvals);req=essay_request();result=w.start(req)
 assert result.document_version.content==req.student_draft and result.document_version.student_authored
 assert result.document_version.version==1 and result.concept_ids and result.advice_confidence>0
 assert result.external_side_effects is False
 assert w.review_state(tenant_id="student-a",approval_id=result.approval_id)=="pending"
 approvals.decide(result.approval_id,ApprovalStatus.APPROVED,decided_by="student-a")
 assert w.review_state(tenant_id="student-a",approval_id=result.approval_id)=="approved"

def test_essay_flow_fails_closed_for_authorship_and_tenant_boundaries(approvals):
 raw=essay_request().model_dump();raw["student_authored"]=False
 with pytest.raises(ValueError,match="student-authored"): EssayWorkflowRequest(**raw)
 w=EssayReviewWorkflow(approvals);result=w.start(essay_request())
 with pytest.raises(KeyError): w.review_state(tenant_id="student-b",approval_id=result.approval_id)
 with pytest.raises(KeyError): w.versions.get("student-b",result.document_version.document_id,1)

def test_document_versions_are_append_only_and_hash_exact_student_text():
 store=VersionStore();first=store.append(tenant_id="student-a",content="draft one",student_authored=True);second=store.append(tenant_id="student-a",content="draft two",student_authored=True,document_id=first.document_id)
 assert second.version==2 and second.parent_version_id==first.id and store.get("student-a",first.document_id,1).content=="draft one"
 with pytest.raises(PermissionError): store.append(tenant_id="student-b",content="intrusion",student_authored=True,document_id=first.document_id)

class Planner:
 def decompose(self,goal,*,context=""):
  return [{"id":"extract","title":"extract facts","tool":"extract","risk":"read","arguments":{"text":context}},{"id":"score","title":"score facts","tool":"score","risk":"reversible","depends_on":["extract"],"arguments":{"weights":[2,3]}}]

@pytest.mark.asyncio
async def test_goal_to_bounded_tools_evidence_artifact_and_approval(approvals):
 w=CognitiveEvidenceWorkflow(approvals,Planner());calls=[]
 async def extract(args): calls.append(("extract",args));return {"facts":["A","B"],"source":"provided context"}
 async def score(args): calls.append(("score",args));return {"score":sum(args["weights"]),"method":"deterministic sum"}
 w.register_local_tool(LocalToolDefinition(name="extract",description="Extract local facts"),extract);w.register_local_tool(LocalToolDefinition(name="score",description="Score local facts",risk=Risk.REVERSIBLE),score)
 result=await w.run(CognitiveWorkflowRequest(tenant_id="tenant-a",goal="Produce a local evidence brief",context="A and B are supplied facts.",project_id="proof-project",max_tool_calls=2,allowed_tools={"extract","score"}))
 assert [n for n,_ in calls]==["extract","score"] and result.tool_calls==result.plan_steps==2
 assert all(x.succeeded and len(x.result_sha256)==64 for x in result.evidence)
 assert result.artifact["kind"]=="workflow_evidence" and result.artifact_quality==1.0 and result.external_side_effects is False
 assert w.review_state(tenant_id="tenant-a",approval_id=result.approval_id,artifact_id=result.artifact["id"])=="pending"
 approvals.decide(result.approval_id,ApprovalStatus.DENIED,decided_by="tenant-a")
 assert w.review_state(tenant_id="tenant-a",approval_id=result.approval_id,artifact_id=result.artifact["id"])=="denied"

@pytest.mark.asyncio
async def test_cognitive_flow_fails_closed_on_budget_disallowed_tools_and_cross_tenant(approvals):
 w=CognitiveEvidenceWorkflow(approvals,Planner())
 async def local(args): return {"ok":True}
 w.register_local_tool(LocalToolDefinition(name="extract",description="Local extraction"),local);w.register_local_tool(LocalToolDefinition(name="score",description="Local scoring",risk=Risk.REVERSIBLE),local)
 with pytest.raises(ValueError,match="budget"): await w.run(CognitiveWorkflowRequest(tenant_id="tenant-a",goal="brief",context="x",project_id="p",max_tool_calls=1,allowed_tools={"extract","score"}))
 with pytest.raises(ValueError,match="not registered"): await w.run(CognitiveWorkflowRequest(tenant_id="tenant-a",goal="brief",context="x",project_id="p",max_tool_calls=2,allowed_tools={"extract","missing"}))
 result=await w.run(CognitiveWorkflowRequest(tenant_id="tenant-a",goal="brief",context="x",project_id="p",max_tool_calls=2,allowed_tools={"extract","score"}))
 with pytest.raises(KeyError): w.review_state(tenant_id="tenant-b",approval_id=result.approval_id,artifact_id=result.artifact["id"])
 with pytest.raises(KeyError): w.review_state(tenant_id="tenant-a",approval_id=result.approval_id,artifact_id="swapped")

def test_external_tool_registration_is_rejected_before_any_call(approvals):
 w=CognitiveEvidenceWorkflow(approvals,Planner())
 async def never(args): raise AssertionError("external handler ran")
 with pytest.raises(ValueError,match="only local"): w.register_local_tool(LocalToolDefinition(name="publish",description="publish",risk=Risk.EXTERNAL),never)
