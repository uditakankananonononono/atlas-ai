import asyncio
from app.core.approvals import ApprovalStore
from app.modules.m02_competition_manager.humanize import NaturalVoiceService
from app.modules.m02_competition_manager.application_pipeline import ApplicationAnswerPipeline
async def good(prompt,provider,model):
 assert 'Do not optimize for AI-detector evasion' in prompt
 return 'voice-model','In 2025, I built Atlas for MIT and improved accuracy by 20%.'
async def bad(prompt,provider,model):return 'bad','I built something.'
def test_application_pipeline_order_and_exact_review_gate():
 a=ApprovalStore();out=asyncio.run(ApplicationAnswerPipeline(NaturalVoiceService(good),a).prepare_review('c1',{'impact':'In 2025, I built Atlas for MIT and improved accuracy by 20%.'}))
 assert out['stages']==['ai_curated_draft','natural_voice_pass','owner_review','browser_stage','separate_final_submit_approval']
 assert out['submission_enabled'] is False and out['exact_answers']['impact'].endswith('20%.')
 req=a.list()[0];assert req.action_type=='review_humanized_application_answers'
 assert req.payload['prohibitions']==['detector_evasion','authorship_misrepresentation','fabricated_content']
def test_changed_factual_anchors_fail_before_review_or_submission():
 a=ApprovalStore();before=len(a.list())
 try:asyncio.run(ApplicationAnswerPipeline(NaturalVoiceService(bad),a).prepare_review('c',{'x':'In 2025 I built Atlas at MIT.'}))
 except ValueError as e:assert 'factual anchors' in str(e)
 else:raise AssertionError
 assert len(a.list())==before
