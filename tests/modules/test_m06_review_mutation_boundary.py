import unittest
from datetime import datetime,timezone
from app.modules.m06_social_media_manager.scheduler import Scheduler,ScheduleEntry
from app.modules.m06_social_media_manager.models import Platform
class Repo:
 def __init__(self,e):self.e=e
 def get_schedule(self,key):return self.e
 def list_schedules(self):return [self.e]
 def save_schedule(self,e):return e
class MutationBoundary(unittest.TestCase):
 def setup_row(self):
  e=ScheduleEntry('s','p',Platform.LINKEDIN,'article_post','Synthetic',datetime(2026,10,15,tzinfo=timezone.utc),'approved-old',status='approved')
  s=Scheduler.__new__(Scheduler);s._repository=Repo(e);s._clock=lambda:datetime(2026,10,16,tzinfo=timezone.utc)
  return e,s
 def test_media_edit_cannot_keep_old_approval(self):
  e,s=self.setup_row();s.attach_media('s',['https://example.invalid/media'])
  self.assertEqual(e.approval_id,'');self.assertEqual(e.status,'awaiting_approval')
 def test_time_edit_cannot_keep_old_approval(self):
  e,s=self.setup_row();s.reschedule('s',datetime(2026,10,20,tzinfo=timezone.utc))
  self.assertEqual(e.approval_id,'');self.assertEqual(e.status,'awaiting_approval')
if __name__=='__main__':unittest.main()
