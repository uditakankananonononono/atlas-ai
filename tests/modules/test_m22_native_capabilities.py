import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m22_tools_hub.native_capabilities import *
from app.modules.m22_tools_hub.native_capability_routes import router

def spec(): return {'name':'Field Notes','entities':[{'name':'Note','fields':[{'name':'title','type':'string'},{'name':'score','type':'integer'}]}]}
def source(text='Atlas supports bounded work.'):
 return {'id':'official','title':'Official docs','url':'https://example.org/docs','text':text,'observed_at':'2026-09-21T12:00:00Z','official':True}

def test_spec_to_app_generates_runnable_schema_ui_api_preview_tests_and_revision():
 b=SpecAppBuilder(); out=b.build(spec())
 assert out['preview']['stdout'].strip()=="{'status': 'ok'}"
 assert out['tests']['passed'] and {'NoteList','NoteForm','NoteDetail'}<=set(out['ui_components'])
 assert out['api_routes']==['GET /api/note','POST /api/note','GET /api/note/{id}','DELETE /api/note/{id}']
 revised=b.revise(out,[{'path':'app.py','old':"'status':'ok'","new":"'status': 'ok'"}])
 assert revised['revision']==1 and revised['tests']['passed']

def test_failed_revision_rolls_back_exact_files():
 b=SpecAppBuilder(); out=b.build(spec()); before=dict(out['files'])
 with pytest.raises(CapabilityError,match='rolled back'):
  b.revise(out,[{'path':'app.py','old':"'status':'ok'","new":"'status':'broken'"}])
 assert out['workspace'].files==before

def test_workspace_multifile_run_logs_manifest_snapshots_and_rollback():
 ws=CodeWorkspace('student-lab'); ws.write('main.py',"print('version one')\n"); ws.set_manifest({'python':'>=3.12'})
 stable=ws.snapshot('stable'); ws.write('main.py',"print('version two')\n")
 assert ws.run('main.py')['stdout']=='version two\n'
 result=ws.rollback(stable.id)
 assert result['safety_snapshot'] and ws.run('main.py')['stdout']=='version one\n' and len(ws.logs)==2

def test_workspace_rejects_escape_import_io_and_timeout():
 ws=CodeWorkspace()
 with pytest.raises(CapabilityError): ws.write('../secret','x')
 ws.write('bad.py','import os\n')
 with pytest.raises(SandboxError,match='imports'): ws.run('bad.py')
 ws.write('spin.py','while True: pass\n')
 out=ws.run('spin.py',.05); assert out['timed_out'] and out['exit_code']==124

def test_research_agent_returns_current_citations_reasoning_confidence_and_tools():
 o=ResearchAgent().answer('What is available?',[source()],[{'tool':'web_fetch','status':'ok'}])
 assert o['answer'].endswith('[official]') and o['citations'][0]['observed_at']
 assert 0<o['confidence']<=.95 and o['tool_calls'][0]['tool']=='web_fetch' and not o['provider_parity_claim']

def test_research_agent_refuses_uncited_or_stale_input():
 with pytest.raises(CapabilityError,match='current, cited'):
  ResearchAgent().answer('q',[{'url':'https://x','text':'claim'}])

def test_multimodal_normalization_grounding_and_action_approval_boundaries():
 a=LiveAssistant(); event=a.normalize({'kind':'image','mime_type':'image/png','content':'Receipt total reads INR 900','source_id':'upload-1'})
 safe=a.propose_action(event,'extract_fields',{'fields':['total']}); risky=a.propose_action(event,'send_payment',{'amount':900},'high')
 assert event['observation']['grounded_in']=='upload-1' and safe['status']=='ready' and not safe['executed']
 assert risky['approval_required'] and risky['status']=='awaiting_human_approval'
 with pytest.raises(CapabilityError): a.normalize({'kind':'audio','mime_type':'image/png','content':'hello'})

def test_discovery_pipeline_manifest_threat_license_adapter_sandbox_review_install_rollback():
 p=DiscoveryPipeline(); m=p.manifest('Calendar adapter',[source()],['list_events'],'MIT',['network'])
 a=p.generate_adapter(m); t=p.sandbox_test(a,'list_events'); waiting=p.install_plan(m,a,t)
 assert 'sensitive_permission:network' in m['threat_findings'] and t['output']['native_atlas_adapter']
 assert waiting['state']=='awaiting_human_approval' and waiting['rollback']['restore_previous_snapshot']
 installed=p.install_plan(m,a,t,approved=True); assert installed['state']=='installed'
 blocked=p.manifest('Unknown',[source()],['x'],'unknown',[])
 assert p.install_plan(blocked,p.generate_adapter(blocked),{'passed':True},approved=True)['state']=='blocked'

def test_native_routes_are_mounted_and_return_runnable_output_and_failures():
 app=FastAPI(); app.include_router(router,prefix='/tools-hub'); c=TestClient(app)
 assert len(c.get('/tools-hub/native-capabilities').json())==5
 built=c.post('/tools-hub/native-capabilities/apps/build',json={'data':spec()}); assert built.status_code==200 and built.json()['tests']['passed']
 run=c.post('/tools-hub/native-capabilities/workspaces/run',json={'files':{'x.py':"print('live')\n"},'manifest':{},'entrypoint':'x.py'}); assert run.json()['run']['stdout']=='live\n'
 bad=c.post('/tools-hub/native-capabilities/research',json={'question':'q','sources':[]}); assert bad.status_code==422
