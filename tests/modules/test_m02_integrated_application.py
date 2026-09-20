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
 a=ApprovalStore();f=IntegratedApplicationFlow(Corpus(),GroundedApplicationDrafter(generate),NaturalVoiceService(generate),a)
 out=asyncio.run(f.prepare('comp1','https://official.example/app',[{'field':'impact','question':'What did you build?','requirements':'100 words'}]))
 assert out['stages']==['ai_curated_draft','natural_voice_pass','owner_review','browser_stage','separate_final_submit_approval']
 assert out['source_provenance']['impact'][0]=={'source_type':'google_doc','source_id':'doc1','locator':'docs/doc1'}
 assert out['official_url']=='https://official.example/app' and not out['submission_enabled'] and out['final_submit_requires_separate_approval']
 assert a.list()[-1].payload['exact_answers']==out['exact_answers']
def test_integrated_flow_refuses_to_generate_from_nothing():
 f=IntegratedApplicationFlow(Empty(),GroundedApplicationDrafter(generate),NaturalVoiceService(generate),ApprovalStore())
 try:asyncio.run(f.prepare('c','https://official',[{'field':'essay','question':'Why?'}]))
 except ValueError as e:assert 'no owner corpus evidence' in str(e)
 else:raise AssertionError
