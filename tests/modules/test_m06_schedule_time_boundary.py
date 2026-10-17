"""Real Scheduler due-scan methods, no external effects or dependency shims."""
import unittest
from datetime import datetime, timezone, timedelta, tzinfo
from app.modules.m06_social_media_manager.scheduler import Scheduler,ScheduleEntry,NaivePublishTimeError
from app.modules.m06_social_media_manager.models import Platform

class Rows:
 def __init__(self,rows):self.rows=rows
 def list_schedules(self):return self.rows

class TimeBoundary(unittest.TestCase):
 def make(self,entries,clock=None):
  # Only due-scan dependencies initialized. No fake enforcer/guardrail modules.
  s=Scheduler.__new__(Scheduler);s._repository=Rows(entries)
  s._clock=lambda:clock or datetime(2026,10,15,12,tzinfo=timezone.utc)
  return s
 def row(self,moment,status='approved'):
  return ScheduleEntry('entry','plan',Platform.LINKEDIN,'article_post','Synthetic post',moment,'approval',status=status)
 def test_legacy_naive_approved_row_refuses_instead_of_utc_guess(self):
  s=self.make([self.row(datetime(2026,10,14,12))])
  with self.assertRaises(NaivePublishTimeError):s.due_entries()
 def test_naive_scan_time_refuses_even_empty_queue(self):
  with self.assertRaises(NaivePublishTimeError):self.make([]).due_entries(datetime(2026,10,15,12))
 def test_naive_clock_refuses_even_empty_queue(self):
  with self.assertRaises(NaivePublishTimeError):self.make([],datetime(2026,10,15,12)).due_entries()
 def test_whole_approved_batch_validated_before_due_result(self):
  rows=[self.row(datetime(2026,10,14,tzinfo=timezone.utc)),self.row(datetime(2026,10,20))]
  with self.assertRaises(NaivePublishTimeError):self.make(rows).due_entries()
 def test_offset_instant_preserved_and_future_excluded(self):
  offset=timezone(timedelta(hours=5,minutes=30))
  due=self.row(datetime(2026,10,15,17,30,tzinfo=offset))
  future=self.row(datetime(2026,10,15,17,31,tzinfo=offset))
  self.assertEqual(self.make([due,future]).due_entries(),[due])
 def test_pending_legacy_row_is_not_a_publish_candidate(self):
  self.assertEqual(self.make([self.row(datetime(2026,10,14),status='awaiting_approval')]).due_entries(),[])
 def test_timezone_with_no_offset_is_not_aware(self):
  class NoOffset(tzinfo):
   def utcoffset(self,dt):return None
  with self.assertRaises(NaivePublishTimeError):self.make([self.row(datetime(2026,10,14,tzinfo=NoOffset()))]).due_entries()
 def test_execute_refuses_before_approval_or_adapter_work(self):
  # No decisions/adapters/enforcer attached. Any access before refusal fails test.
  with self.assertRaises(NaivePublishTimeError):self.make([self.row(datetime(2026,10,14))]).execute_due()
if __name__=='__main__':unittest.main()
