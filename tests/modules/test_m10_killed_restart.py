"""Actual killed child/restart against persistent SQLite. No network/providers."""
import os,subprocess,sys
import pytest

@pytest.mark.parametrize('phase',['ready','model_inflight','model_done','approval_inflight','approval_done'])
def test_killed_pipeline_restart_only_safe_persisted_phases(tmp_path,phase):
 script="""
import asyncio,os,runpy
from pathlib import Path
ns=runpy.run_path('tests/modules/test_m10_email_assistant.py')
svc,repo,approvals,client=ns['make_service'](Path(os.environ['FIXTURE_DIR']))
repo.save_account(account_id='a',email_address='fixture-a@example.invalid',encrypted_refresh_token=svc.cipher.encrypt('rt'),history_id='100',watch_expiration=None)
phase=os.environ['KILL_PHASE']
mode=os.environ['MODE']
original=repo.transition_draft_work
if mode=='kill':
 async def stop(*args,**kwargs):os._exit(77)
 if phase=='ready':svc._draft_reply=stop
 elif phase=='model_inflight':
  async def generate(prompt,provider,model):
   if prompt.startswith('Extract action items'):return 'fixture','[]'
   os._exit(77)
  svc.llm_generate=generate
 else:
  def transition(mid,aid,expected,target,data):
   won=original(mid,aid,expected,target,data)
   if target==phase and won:os._exit(77)
   return won
  repo.transition_draft_work=transition
 asyncio.run(svc._ingest_message('a',ns['raw_message']('g','Please reply',snippet='please reply')))
 raise AssertionError('kill phase missed')
else:
 row=repo.list_messages()[0]
 assert repo.draft_work(row.id,'a')['phase']==phase
 calls=[]
 async def generate(*args):calls.append('model');return 'fixture','Subject: Re: fixture\\nFixture'
 svc.llm_generate=generate
 count=asyncio.run(svc.recover_draft_pipeline('a'))
 safe=phase in ['ready','model_done','approval_done']
 assert count==int(safe)
 assert len(repo.list_drafts())==int(safe)
 assert calls==(['model'] if phase=='ready' else [])
 assert len(approvals.items)==int(phase in ['ready','model_done'])
 assert repo.draft_work(row.id,'a')['phase']==('complete' if safe else phase)
"""
 env={**os.environ,'PYTHONPATH':'backend','FIXTURE_DIR':str(tmp_path),'KILL_PHASE':phase,'MODE':'kill'}
 killed=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=20)
 assert killed.returncode==77,killed.stderr
 resumed=subprocess.run([sys.executable,'-c',script],env={**env,'MODE':'restart'},capture_output=True,text=True,timeout=20)
 assert resumed.returncode==0,resumed.stderr
