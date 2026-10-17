"""Genuine FastAPI/schema acceptance pins, supplied unrun by author."""
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m06_social_media_manager import routes
from app.modules.m06_social_media_manager.adapters import AdapterAuthError
from app.modules.m06_social_media_manager.schemas import ScheduleEntryOut

class AccountBindingHttp(unittest.TestCase):
 def test_identity_failure_is_fixed409_without_provider_diagnostics(self):
  class Refuser:
   def request_schedule(self,*args,**kwargs):raise AdapterAuthError('synthetic-private-diagnostic')
   def request_schedule_review(self,*args,**kwargs):raise AdapterAuthError('synthetic-private-diagnostic')
  app=FastAPI();app.include_router(routes.router)
  app.dependency_overrides[routes.get_service]=lambda:Refuser()
  with TestClient(app) as client:
   for path,body in [('/social-media-manager/plans/p/schedule',{}),('/social-media-manager/schedules/s/review',None)]:
    response=client.post(path,json=body)
    self.assertEqual(response.status_code,409)
    self.assertIn('publishing account could not be verified',response.text)
    self.assertNotIn('synthetic-private-diagnostic',response.text)

if __name__=='__main__':unittest.main()
