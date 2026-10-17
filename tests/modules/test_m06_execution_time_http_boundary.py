"""Requires real repository FastAPI/Pydantic deps, not run by author locally."""
import unittest
from fastapi import HTTPException
from app.modules.m06_social_media_manager.routes import execute_due
from app.modules.m06_social_media_manager.scheduler import NaivePublishTimeError

class ExecutionTimeHTTPBoundary(unittest.TestCase):
 def test_ambiguous_persisted_time_is_actionable_conflict(self):
  class Scheduler:
   def execute_due(self):raise NaivePublishTimeError('synthetic')
  with self.assertRaises(HTTPException) as caught:execute_due(Scheduler())
  self.assertEqual(caught.exception.status_code,409)
  self.assertEqual(caught.exception.detail,'approved schedule has no explicit timezone; reschedule before execution')
 def test_unexpected_fault_is_not_misreported_as_time_conflict(self):
  class Scheduler:
   def execute_due(self):raise RuntimeError('synthetic')
  with self.assertRaises(RuntimeError):execute_due(Scheduler())
 def test_success_receipts_unchanged(self):
  receipts=[{'synthetic':'receipt'}]
  class Scheduler:
   def execute_due(self):return receipts
  self.assertIs(execute_due(Scheduler()),receipts)
if __name__=='__main__':unittest.main()
