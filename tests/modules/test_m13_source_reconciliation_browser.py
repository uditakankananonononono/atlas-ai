"""Actual isolated Chromium owning-session readback; no external navigation/click."""
import asyncio
from pathlib import Path
import pytest
from app.modules.m13_browser_agent.playwright_adapter import PlaywrightSessions
from app.modules.m13_browser_agent.service import Service as BrowserService
from app.modules.m13_browser_agent.application_flow import ApplicationFlow,ApplicationSession
from app.modules.m13_browser_agent.application_store import InMemoryApplicationSessionStore

@pytest.mark.asyncio
async def test_actual_browser_source_reconciliation_uses_same_session_and_no_second_click(tmp_path,monkeypatch):
 import socket
 monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))])
 class Audit:
  async def was_consumed(self,aid):return aid=='approval'
  async def append_audit(self,event):pass
 class Approvals:
  def get(self,aid):return {'id':'approval','payload':{'tenant_id':'a','actor_id':'u','session_id':'s','selector':'#submit','page_url':'https://example.com/apply'}}
 sessions=PlaywrightSessions(str(tmp_path/'browser'),allowed_hosts={'example.com'})
 try:
  page=await sessions.page('a','s')
  # Override requests only for this hermetic context, serving all bytes locally.
  await page.context.unroute('**/*')
  html=['<html><body><h1>Application pending</h1><form><button id="submit">Submit</button></form></body></html>']
  requests=[]
  async def serve(route):requests.append(route.request.url);await route.fulfill(status=200,content_type='text/html',body=html[0])
  await page.context.route('**/*',serve)
  await page.goto('https://example.com/apply')
  store=InMemoryApplicationSessionStore();store.create(ApplicationSession(tenant_id='a',actor_id='u',session_id='s',url='https://example.com/apply',status='outcome_unknown',approval_id='approval',submit_selector='#submit'))
  browser=BrowserService(sessions,Approvals(),Audit(),str(tmp_path/'shots'),{'example.com'})
  flow=ApplicationFlow(browser,store,Approvals())
  before=len(requests)
  assert not (await flow.reconcile_submit('a','u','s'))['reconciled']
  assert len(requests)==before # reading does not navigate or send
  html[0]='<html><body><h1>Your application was received.</h1><p>Reference: local fixture only</p></body></html>'
  await page.goto('https://example.com/apply/thanks') # simulated site outcome, not agent reconciliation
  before=len(requests)
  result=await flow.reconcile_submit('a','u','s')
  assert not result['submitted'] and not result['reconciled']
  assert result['observation']['final_url']=='https://example.com/apply/thanks' and not result['observation']['transaction_bound']
  assert len(requests)==before
  await page.screenshot(path='/downloads/m13-local-source-receipt.png',full_page=True)
 finally:await sessions.close()
