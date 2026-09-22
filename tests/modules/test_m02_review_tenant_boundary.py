import asyncio
from app.core.approvals import ApprovalStore
from app.modules.m02_competition_manager.application_pipeline import ApplicationAnswerPipeline
from app.modules.m02_competition_manager.humanize import NaturalVoiceService

async def good(prompt,provider,model):
 return 'model','In 2025, I built Atlas for MIT and improved accuracy by 20%.'

def test_review_approval_carries_tenant():
 approvals=ApprovalStore()
 pipeline=ApplicationAnswerPipeline(NaturalVoiceService(good),approvals,'tenant-a')
 asyncio.run(pipeline.prepare_review('c1',{'impact':'In 2025, I built Atlas for MIT and improved accuracy by 20%.'}))
 assert approvals.list()[0].payload['tenant_id']=='tenant-a'

def test_empty_tenant_fails_closed():
 try:ApplicationAnswerPipeline(NaturalVoiceService(good),ApprovalStore(),' ')
 except ValueError as exc:assert 'tenant_id' in str(exc)
 else:raise AssertionError('empty tenant accepted')
