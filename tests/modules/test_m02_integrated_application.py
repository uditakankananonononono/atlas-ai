import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m00_approval_center.service import Service as ApprovalService


@pytest.fixture(autouse=True)
def isolated_approval_database(tmp_path, monkeypatch):
 # This integration uses the real facade and real SQL service, but owns its
 # schema fixture. Never rely on the process-global atlas.db or auto-create.
 engine = create_engine(f"sqlite:///{tmp_path / 'approvals.db'}")
 Base.metadata.create_all(engine)
 service = ApprovalService(sessionmaker(bind=engine, expire_on_commit=False))
 monkeypatch.setattr("app.core.approvals.default_service", lambda: service)
 yield service
 engine.dispose()


import asyncio
from app.core.approvals import ApprovalStore
from app.modules.m02_competition_manager.grounded_drafting import GroundedApplicationDrafter
from app.modules.m02_competition_manager.humanize import NaturalVoiceService
from app.modules.m02_competition_manager.integrated_application import IntegratedApplicationFlow
class Corpus:
 async def retrieve(self,q,limit):return [{'id':1,'title':'My activities','source_type':'google_doc','source_id':'doc1','locator':'docs/doc1','text':'In 2025, I built Atlas and improved accuracy by 20%.','provenance':{'revision_id':'r1'}}]
class Empty:
 async def retrieve(self,q,limit):return []
async def generate(prompt,provider,model):
 if 'Draft an answer' in prompt:return 'draft-model','In 2025, I built Atlas and improved accuracy by 20%. [1]'
 return 'voice-model','In 2025, I built Atlas and improved accuracy by 20%. [1]'
def test_one_flow_carries_owner_provenance_through_voice_review_and_browser_handoff():
 a=ApprovalStore();f=IntegratedApplicationFlow(Corpus(),GroundedApplicationDrafter(generate),NaturalVoiceService(generate),a,'tenant-a')
 out=asyncio.run(f.prepare('comp1','https://official.example/app',[{'field':'impact','question':'What did you build?','requirements':'100 words'}]))
 assert out['stages']==['ai_curated_draft','natural_voice_pass','owner_review','browser_stage','separate_final_submit_approval']
 assert out['source_provenance']['impact'][0]=={'source_type':'google_doc','source_id':'doc1','locator':'docs/doc1'}
 assert out['official_url']=='https://official.example/app' and not out['submission_enabled'] and out['final_submit_requires_separate_approval']
 req=next(x for x in a.list(user_id='tenant-a') if x.id==out['approval_id'])
 assert a.list(user_id='tenant-b')==[]
 assert req.payload['exact_answers']==out['exact_answers']
def test_integrated_flow_refuses_to_generate_from_nothing():
 f=IntegratedApplicationFlow(Empty(),GroundedApplicationDrafter(generate),NaturalVoiceService(generate),ApprovalStore())
 try:asyncio.run(f.prepare('c','https://official',[{'field':'essay','question':'Why?'}]))
 except ValueError as e:assert 'no owner corpus evidence' in str(e)
 else:raise AssertionError
def test_integrated_flow_attaches_evidence_completeness():
 f=IntegratedApplicationFlow(Corpus(),GroundedApplicationDrafter(generate),NaturalVoiceService(generate),ApprovalStore(),'tenant-a')
 out=asyncio.run(f.prepare('comp1','https://official.example/app',[{'field':'impact','question':'What did you build?'}]))
 ev=out['evidence_completeness']
 assert ev['complete'] and ev['overall_score']==1.0
 assert ev['fields']['impact']['claims'][0]['sources'][0]['source_id']=='doc1'
