import json
from app.modules.m18_side_hustle_scraper.wiring import build_collectors
from app.modules.m18_side_hustle_scraper.runner import HustleRunner,StepState
from app.modules.m00_approval_center.service import Service as ApprovalService
from app.modules.m00_approval_center.service import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_collector_wiring_free_defaults_and_optional_keys():
 free=build_collectors({})
 assert {'reddit','hacker_news','dev_to'} <= set(free)
 assert not {'youtube','pinterest','x','instagram'} & set(free)
 configured=build_collectors({'ATLAS_YOUTUBE_API_KEY':'y','ATLAS_PINTEREST_ACCESS_TOKEN':'p','ATLAS_X_BEARER_TOKEN':'x','ATLAS_INSTAGRAM_GRAPH_TOKEN':'i','ATLAS_M18_RSS_FEEDS':'https://example.com/feed','ATLAS_M18_PUBLIC_URLS':'https://example.com/page'})
 assert {'reddit','hacker_news','dev_to','youtube','pinterest','x','instagram','rss','public_web'} <= set(configured)

def approval_service():
 engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine);return ApprovalService(sessionmaker(bind=engine,expire_on_commit=False))

def test_runner_produces_artifacts_and_blocks_every_effect_for_approval():
 approvals=approval_service();runner=HustleRunner(approvals)
 run=runner.create(title='Tutoring',first_experiment='Interview five students',max_budget=10,source_urls=['https://example.com'])
 assert [s.kind for s in run.steps]==['landing_page','listing','outreach','budget','measurement']
 assert all(s.artifact for s in run.steps)
 external=[s for s in run.steps if s.external_action]
 for step in external:
  runner.request_action(run.id,step.id,'owner');assert step.state is StepState.BLOCKED and step.approval_id
  assert approvals.get(step.approval_id)['status']=='pending'
 assert runner.complete_preparation(run.id,run.steps[-1].id).state is StepState.COMPLETED

def test_approved_step_returns_one_shot_permit_but_does_not_fake_execution():
 approvals=approval_service();runner=HustleRunner(approvals);run=runner.create(title='Tutoring',first_experiment='Interview five students')
 step=run.steps[0];runner.request_action(run.id,step.id,'owner');approvals.decide(step.approval_id,__import__('app.core.models',fromlist=['ApprovalStatus']).ApprovalStatus.APPROVED,'owner')
 result=runner.authorize_action(run.id,step.id,'owner','worker')
 assert result['permit']['allowed'] and result['executed'] is False
