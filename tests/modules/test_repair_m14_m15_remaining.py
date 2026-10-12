import pytest
from app.modules.m14_project_builder.service import Service as Projects
from app.modules.m14_project_builder.schemas import CreateProjectRequest
from app.core.providers import ProviderError,ProviderOutcomeUnknown
from app.modules.m15_document_generator import delivery
from app.modules.m15_document_generator.schemas import DocumentVersion

def version(body):return DocumentVersion(id='v',tenant_id='t',document_id='d',version_number=1,format='pdf',template_id='report',content={'title':'Report','sections':[{'title':'Result','body':body}]},content_hash='x')
@pytest.mark.asyncio
async def test_planner_absent_runtime_typed_and_project_unchanged():
 from app.modules.m14_project_builder.service import PlannerUnavailable
 async def missing(*a):raise ProviderError('No configured route')
 s=Projects(None,generate_fn=missing);p=s.create('t',CreateProjectRequest(goal='Build a project'))
 with pytest.raises(PlannerUnavailable):await s.plan(p)
 assert p.status=='draft' and p.plan is None and p.revision==0

def test_nonlatin_pdf_rejected_before_process(monkeypatch):
 calls=[];monkeypatch.setattr(delivery.subprocess,'run',lambda *a,**kw:calls.append(a))
 with pytest.raises(delivery.RenderFailed,match='Unicode'):
  delivery.render_pdf(version('研究结果'))
 assert calls==[]

def test_grounded_version_route_is_mounted_and_persistent():
 from app.modules.m15_document_generator.routes import router
 assert any(r.path.endswith('/grounded-versions') for r in router.routes)

def test_creative_catalog_declares_planning_not_production():
 from app.modules.m15_document_generator.creative_production_306_332 import catalog
 assert all(x['execution_scope']=='planning_only' for x in catalog())
OUTLINE={'title':'Evidence report','sources':[{'id':'s','title':'Source','content':'Recorded value is ten units.','url':'https://example.org'}],'sections':[{'heading':'Finding','claims':[{'text':'Recorded value is ten units.','evidence':[{'source_id':'s','quote':'Recorded value is ten units.'}]}]}]}
def test_grounded_endpoint_validates_quotes_persists_and_checks_tenant(tmp_path):
 from sqlalchemy import create_engine
 from sqlalchemy.orm import sessionmaker
 from app.core.database import Base
 from app.modules.m15_document_generator.sql_repository import SqlVersionRepository
 from app.modules.m15_document_generator.service import Service
 from app.modules.m15_document_generator.routes import create_grounded_version,GroundedVersionInput
 engine=create_engine('sqlite:///'+str(tmp_path/'ground.db'));Base.metadata.create_all(engine)
 sf=sessionmaker(bind=engine,expire_on_commit=False)
 service=Service(None,SqlVersionRepository('t',sf))
 v=create_grounded_version('d',GroundedVersionInput(outline=OUTLINE,format='docx',template_id='report'),'t',service)
 assert service.get('t',v.id).content['_source_trace']==OUTLINE
 assert service.preflight(v)['grounding']['status']=='quote_presence_verified'
 assert SqlVersionRepository('other',sf).get(v.id) is None
 import copy
 bad=copy.deepcopy(OUTLINE);bad['sections'][0]['claims'][0]['evidence'][0]['quote']='Fabricated quote'
 from fastapi import HTTPException
 with pytest.raises(HTTPException) as exc:
  create_grounded_version('d',GroundedVersionInput(outline=bad,format='docx',template_id='report'),'t',service)
 assert exc.value.status_code==422

def test_grounded_content_swap_and_free_prose_refused():
 from app.modules.m15_document_generator.grounded_versions import grounded_request,validate_grounded_content
 import copy
 r=grounded_request(OUTLINE,'docx','report');r.content['sections'][0]['body']='Different claim'
 with pytest.raises(ValueError):validate_grounded_content(r.content)
 bad=copy.deepcopy(OUTLINE);bad['sections'][0]['prose']='Uncited claim'
 with pytest.raises(ValueError):grounded_request(bad,'docx','report')

@pytest.mark.asyncio
async def test_planner_unknown_outcome_no_retry():
 calls=[]
 async def unknown(*args):calls.append(args);raise ProviderOutcomeUnknown('unknown')
 s=Projects(None,generate_fn=unknown);p=s.create('t',CreateProjectRequest(goal='Build a project'))
 with pytest.raises(ProviderOutcomeUnknown):await s.plan(p)
 assert len(calls)==1 and p.plan is None

@pytest.mark.asyncio
async def test_configured_planner_executes_json_contract():
 import json
 async def gen(*args):return 'fixture',json.dumps({'tasks':[{'id':'a','title':'Inspect inputs','agent_kind':'analyst','objective':'Inspect supplied evidence','acceptance_criteria':['Report contains evidence']}],'assumptions':[],'risks':[],'quality_gates':[]})
 s=Projects(None,generate_fn=gen);p=s.create('t',CreateProjectRequest(goal='Build a project'))
 r=await s.plan(p)
 assert r.project.status=='planned' and r.project.plan.tasks[0].status=='ready'

@pytest.mark.asyncio
@pytest.mark.parametrize('error,code,state',[(ProviderError,503,'unavailable'),(ProviderOutcomeUnknown,409,'unknown')])
async def test_planner_route_typed_outcomes(error,code,state):
 from app.modules.m14_project_builder.routes import plan
 from fastapi import HTTPException
 async def gen(*args):raise error('fixture')
 s=Projects(None,generate_fn=gen);p=s.create('t',CreateProjectRequest(goal='Build a project'))
 with pytest.raises(HTTPException) as exc:await plan(p.id,'t',s)
 assert exc.value.status_code==code and exc.value.detail['state']==state
 assert not exc.value.detail['plan_created'] and p.revision==0

def test_pdf_proposal_refused_without_approval_write():
 from app.modules.m15_document_generator.service import Service
 from app.modules.m15_document_generator.routes import export
 from fastapi import HTTPException
 class Sink:
  def put(self,*a,**kw):pytest.fail('must not create approval')
 s=Service(Sink());v=version('研究');s._versions[('t',v.id)]=v
 with pytest.raises(HTTPException) as exc:export(v.id,'t',s)
 assert exc.value.status_code==422 and 'Unicode' in exc.value.detail

def test_grounded_citations_cannot_be_removed_or_substituted():
 from app.modules.m15_document_generator.grounded_versions import grounded_request,validate_grounded_content
 r=grounded_request(OUTLINE,'docx','report')
 assert '[1]' in r.content['sections'][0]['body']
 with pytest.raises(ValueError):validate_grounded_content(r.content,[])
 with pytest.raises(ValueError):grounded_request(OUTLINE,'pptx','report')

def test_legacy_versions_explicitly_ungrounded():
 from app.modules.m15_document_generator.service import Service
 result=Service(None).preflight(version('Supplied text'))
 assert result['grounding']['status']=='ungrounded' and result['warnings']

def test_design_scope_preserves_supplied_data_support():
 from app.modules.m15_document_generator.design_support_333_359 import _base
 r=_base(333,{'brief':'Inspect concept','decision_owner':'reviewer'})
 assert r['execution_scope']=='supplied_data_design_support' and not r['production_execution_performed']

def test_unicode_preflight_not_ready():
 from app.modules.m15_document_generator.service import Service
 r=Service(None).preflight(version('研究'))
 assert not r['ready'] and any('Unicode' in x for x in r['issues'])

def test_grounded_bridge_snapshots_input():
 import copy
 from app.modules.m15_document_generator.grounded_versions import grounded_request,validate_grounded_content
 source=copy.deepcopy(OUTLINE);r=grounded_request(source,'docx','report')
 source['sources'][0]['content']='Changed after creation'
 assert validate_grounded_content(r.content,r.citations)['status']=='quote_presence_verified'
