import copy
import unittest
from datetime import datetime,timezone,timedelta
from app.modules.m06_social_media_manager.scheduler import Scheduler,ScheduleEntry
from app.modules.m06_social_media_manager.models import Platform
from app.modules.m06_social_media_manager.review_binding import publish_snapshot,review_matches

class Repository:
 def __init__(self,entry):self.entry=entry
 def get_schedule(self,key):return self.entry
 def list_schedules(self):return [self.entry]
 def save_schedule(self,entry):self.entry=entry;return entry

class BindingTests(unittest.TestCase):
 def row(self):return ScheduleEntry('s','p',Platform.LINKEDIN,'article_post','Synthetic',datetime(2026,10,15,tzinfo=timezone.utc),'old',status='approved',publish_target={'platform':'linkedin','account_id':'123'})
 def scheduler(self,row,reviewed):
  s=Scheduler.__new__(Scheduler);s._repository=Repository(row);s._clock=lambda:datetime(2026,10,16,tzinfo=timezone.utc)
  class Decisions:
   def status_of(self,key):return 'approved'
   def reviewed_payload(self,key):return reviewed
  s._decisions=Decisions()
  return s
 def test_snapshot_detaches_media_lists(self):
  row=self.row();row.media_urls=['https://example.invalid/a'];snap=publish_snapshot(row)
  row.media_urls.append('https://example.invalid/b');self.assertEqual(len(snap['media_urls']),1)
 def test_whole_payload_fields_bound(self):
  for field,value in [('publish_target',{'platform':'linkedin','account_id':'456'}),('text','changed'),('format','different'),('link','https://example.invalid/x'),('media_urls',['https://example.invalid/m']),('alt_texts',['different']),('thread_chunks',['different']),('sponsored',True),('publish_at',datetime(2026,10,14,tzinfo=timezone.utc))]:
   row=self.row();payload={'publish_snapshot':publish_snapshot(row)};setattr(row,field,value)
   self.assertFalse(review_matches(row,payload),field)
 def test_missing_legacy_snapshot_refuses_before_enforcer(self):
  row=self.row();s=self.scheduler(row,{})
  self.assertEqual(s.execute_due(),[]);self.assertEqual(row.status,'awaiting_approval');self.assertEqual(row.approval_id,'')
 def test_changed_text_refuses_before_enforcer(self):
  row=self.row();payload={'publish_snapshot':publish_snapshot(row)};row.text='Changed'
  self.assertEqual(self.scheduler(row,payload).execute_due(),[])
  self.assertEqual(row.failure,'review_required')
 def test_lookup_exception_fails_closed(self):
  row=self.row();s=self.scheduler(row,{})
  s._decisions.reviewed_payload=lambda key: (_ for _ in ()).throw(RuntimeError('synthetic'))
  self.assertEqual(s.execute_due(),[])
 def test_attach_media_invalidates_old_decision(self):
  row=self.row();s=self.scheduler(row,{})
  s.attach_media('s',['https://example.invalid/media'],['alt'])
  self.assertEqual(row.approval_id,'');self.assertEqual(row.status,'awaiting_approval')
  s.sync_decisions() # Even a permissive injected status lookup cannot revive an empty ID.
  self.assertEqual(row.status,'awaiting_approval')
 def test_reschedule_invalidates_old_decision(self):
  row=self.row();s=self.scheduler(row,{})
  s.reschedule('s',datetime(2026,10,20,tzinfo=timezone.utc))
  self.assertEqual(row.approval_id,'');self.assertEqual(row.status,'awaiting_approval')
 def test_matching_snapshot_reaches_gate_not_automatic_effect(self):
  from app.modules.m06_social_media_manager.scheduler import _ApprovalAuthority
  row=self.row();payload={'publish_snapshot':publish_snapshot(row)};s=self.scheduler(row,payload)
  seen=[]
  class Gate:
   def dispatch_outbound(self,action,declarations,**kwargs):
    seen.append(action);raise RuntimeError('gate-reached')
  s._authority=_ApprovalAuthority(s._decisions);s._enforcer=Gate();s._declarations={}
  with self.assertRaisesRegex(RuntimeError,'gate-reached'):s.execute_due()
  self.assertEqual(seen[0]['text'],'Synthetic')
  self.assertEqual(seen[0]['approval_id'],'old')
 def test_lookup_side_mutation_cannot_change_dispatch_copy(self):
  from app.modules.m06_social_media_manager.scheduler import _ApprovalAuthority
  row=self.row();payload={'publish_snapshot':publish_snapshot(row)};s=self.scheduler(row,payload)
  def read(key):
   row.text='Unreviewed';row.platform=Platform.TIKTOK;row.approval_id='other'
   return payload
  s._decisions.reviewed_payload=read
  captured=[]
  class Gate:
   def dispatch_outbound(self,action,declarations,**kwargs):
    captured.append(action);raise RuntimeError('gate-reached')
  s._authority=_ApprovalAuthority(s._decisions);s._enforcer=Gate();s._declarations={}
  with self.assertRaisesRegex(RuntimeError,'gate-reached'):s.execute_due()
  self.assertEqual(captured[0]['text'],'Synthetic')
  self.assertEqual(captured[0]['platform'],'linkedin')
  self.assertEqual(captured[0]['approval_id'],'old')
 def test_equivalent_offset_is_same_instant(self):
  row=self.row();payload={'publish_snapshot':publish_snapshot(row)}
  row.publish_at=row.publish_at.astimezone(timezone(timedelta(hours=5,minutes=30)))
  self.assertTrue(review_matches(row,payload))
if __name__=='__main__':unittest.main()
