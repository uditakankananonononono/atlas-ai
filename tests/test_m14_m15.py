import asyncio,json
from app.core.models import ApprovalStatus
from app.modules.m14_project_builder.schemas import *
from app.modules.m14_project_builder.service import Service as Projects
from app.modules.m15_document_generator.schemas import CreateVersionRequest
from app.modules.m15_document_generator.service import Service as Documents
class Approvals:
 def put(self,item):item.status=ApprovalStatus.PENDING;return item
async def fake_generate(prompt,provider,model):
 return "model",json.dumps({"tasks":[{"id":"research","title":"Research","objective":"Find evidence","agent_kind":"literature","acceptance_criteria":["3 sources"]},{"id":"write","title":"Write","objective":"Create output","agent_kind":"writer","dependencies":["research"],"acceptance_criteria":["complete"]}],"risks":["source quality"]})
def test_project_plan_and_approval():
 s=Projects(Approvals(),fake_generate);p=s.create("tenant-a",CreateProjectRequest(goal="Build a grounded report"));asyncio.run(s.plan(p));assert [t.id for t in s.ready_tasks(p.plan)]==["research"];assert s.propose_execution(p).status=="pending"
def test_project_tenant_isolation():
 s=Projects(Approvals(),fake_generate);p=s.create("a",CreateProjectRequest(goal="Build a report"))
 try:s.get("b",p.id);assert False
 except KeyError:pass
def test_document_versions_diff_and_gate():
 s=Documents(Approvals());a=s.create_version("t","d",CreateVersionRequest(title="A",format="latex",template_id="report",content={"title":"A","sections":[]}));b=s.create_version("t","d",CreateVersionRequest(title="B",format="latex",template_id="report",parent_version_id=a.id,content={"title":"B","sections":[{"title":"One"}]}));assert b.version_number==2;assert {x.operation for x in s.diff(a,b).changes}=={"replace","add"};assert s.propose_export(b).status=="pending"
def test_document_tenant_isolation():
 s=Documents(Approvals());v=s.create_version("a","d",CreateVersionRequest(title="A",format="docx",template_id="report",content={"title":"A"}))
 try:s.get("b",v.id);assert False
 except KeyError:pass
