"""Run in genuine Atlas dependency environment, not executed by author locally."""
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.approvals import ApprovalStore
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service as ApprovalCenter
from app.modules.m06_social_media_manager.service import Service
from app.modules.m06_social_media_manager.models import ContentPlan,Platform,PlatformDraft
from app.modules.m06_social_media_manager.scheduler import Scheduler,ScheduleEntry
from app.modules.m06_social_media_manager.routes import _ApprovalCenterLookup
from app.modules.m06_social_media_manager.review_binding import publish_snapshot,review_matches

class Repo:
 def __init__(self,row):self.row=row
 def get_schedule(self,key):return self.row
 def save_schedule(self,row):self.row=row;return row
 def get_plan(self,key):return ContentPlan('plan','Synthetic',[],datetime.now(timezone.utc))
class RealReviewFlow(unittest.TestCase):
 def setUp(self):
  self.engine=create_engine('sqlite://')
  Base.metadata.create_all(self.engine)
  self.center=ApprovalCenter(session_factory=sessionmaker(self.engine,expire_on_commit=False))
  self.override=patch('app.core.approvals.default_service',return_value=self.center);self.override.start()
 def tearDown(self):self.override.stop();self.engine.dispose()
 def test_fresh_review_uses_stored_snapshot_and_own_tenant(self):
  row=ScheduleEntry('schedule','plan',Platform.LINKEDIN,'article_post','Synthetic',datetime(2026,10,20,tzinfo=timezone.utc),'',status='awaiting_approval')
  repo=Repo(row);scheduler=Scheduler.__new__(Scheduler);scheduler._repository=repo
  class AccountAdapter:
   async def account_identity(self):return {'platform':'linkedin','account_id':'123'}
  class AccountFactory:
   def for_platform(self,platform):return AccountAdapter()
  scheduler._adapters=AccountFactory()
  service=Service.__new__(Service);service.tenant_id='tenant-a';service._repository=repo;service._scheduler=scheduler;service._approvals=ApprovalStore()
  request=service.request_schedule_review('schedule')
  self.assertEqual(request.status,ApprovalStatus.PENDING)
  self.assertEqual(request.payload['publish_snapshot']['publish_target'],{'platform':'linkedin','account_id':'123'})
  self.assertTrue(review_matches(row,request.payload))
  self.center.decide(request.id,ApprovalStatus.APPROVED,decided_by='synthetic-owner')
  own=_ApprovalCenterLookup('tenant-a');foreign=_ApprovalCenterLookup('tenant-b')
  self.assertIsNone(foreign.reviewed_payload(request.id))
  stored=own.reviewed_payload(request.id)
  self.assertTrue(review_matches(row,stored))
  row.text='Changed after approval'
  self.assertFalse(review_matches(row,stored))
  self.assertEqual(self.center.get(request.id)['payload']['publish_snapshot']['text'],'Synthetic')
 def test_changed_target_files_new_pending_review_without_rewriting_old_approval(self):
  row=ScheduleEntry('schedule','plan',Platform.LINKEDIN,'article_post','Synthetic',datetime(2026,10,20,tzinfo=timezone.utc),'',status='awaiting_approval')
  repo=Repo(row);scheduler=Scheduler.__new__(Scheduler);scheduler._repository=repo
  current={'id':'123'}
  class Adapter:
   async def account_identity(self):return {'platform':'linkedin','account_id':current['id']}
  class Factory:
   def for_platform(self,platform):return Adapter()
  scheduler._adapters=Factory()
  service=Service.__new__(Service);service.tenant_id='tenant-a';service._repository=repo;service._scheduler=scheduler;service._approvals=ApprovalStore()
  first=service.request_schedule_review('schedule')
  self.center.decide(first.id,ApprovalStatus.APPROVED,decided_by='synthetic-owner')
  current['id']='456'
  second=service.request_schedule_review('schedule')
  self.assertNotEqual(first.id,second.id)
  self.assertEqual(second.status,ApprovalStatus.PENDING)
  self.assertEqual(row.status,'awaiting_approval')
  self.assertEqual(row.publish_target,{'platform':'linkedin','account_id':'456'})
  self.assertEqual(self.center.get(first.id)['payload']['publish_snapshot']['publish_target']['account_id'],'123')
  self.assertEqual(second.payload['publish_snapshot']['publish_target']['account_id'],'456')
 def test_duplicate_platform_drafts_keep_own_stored_approval(self):
  plan=ContentPlan('plan','Synthetic first Synthetic second',[
   PlatformDraft(Platform.LINKEDIN,'article_post','Synthetic first'),
   PlatformDraft(Platform.LINKEDIN,'article_post','Synthetic second')],datetime(2026,10,15,tzinfo=timezone.utc))
  class BatchRepo:
   def __init__(self):self.rows=[]
   def get_plan(self,key):return plan
   def save_plan(self,value):return value
   def save_schedule(self,row):self.rows.append(row);return row
  repo=BatchRepo();scheduler=Scheduler.__new__(Scheduler);scheduler._repository=repo
  class Adapter:
   async def account_identity(self):return {'platform':'linkedin','account_id':'123'}
  class Factory:
   def for_platform(self,platform):return Adapter()
  scheduler._adapters=Factory()
  service=Service.__new__(Service);service.tenant_id='tenant-a';service._repository=repo;service._scheduler=scheduler;service._approvals=ApprovalStore()
  requests=service.request_schedule('plan',datetime(2026,10,20,tzinfo=timezone.utc))
  self.assertEqual(len(requests),2)
  self.assertNotEqual(requests[0].id,requests[1].id)
  self.assertEqual([row.approval_id for row in repo.rows],[request.id for request in requests])
  for row,request in zip(repo.rows,requests):
   self.assertEqual(request.status,ApprovalStatus.PENDING)
   self.assertEqual(self.center.get(request.id)['payload']['publish_snapshot']['text'],row.text)
 def test_wrong_action_is_not_publish_authority(self):
  request=self.center.submit(module_id=6,action_type='ab_test',payload={},user_id='tenant-a')
  self.center.decide(request['id'],ApprovalStatus.APPROVED,decided_by='synthetic-owner')
  self.assertIsNone(_ApprovalCenterLookup('tenant-a').reviewed_payload(request['id']))
if __name__=='__main__':unittest.main()
