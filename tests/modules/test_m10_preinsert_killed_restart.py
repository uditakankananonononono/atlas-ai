"""Actual process death across extraction/embed claims, persistent SQLite only."""
import os,subprocess,sys
import pytest

@pytest.mark.parametrize('phase',['extraction_inflight','extraction_done','embedding_inflight','effects_done'])
def test_preinsert_killed_restart_only_safe_results_resume(tmp_path,phase):
 script="""
import asyncio,os,runpy
from pathlib import Path
ns=runpy.run_path('tests/modules/test_m10_email_assistant.py')
svc,repo,sink,client=ns['make_service'](Path(os.environ['FIXTURE_DIR']))
phase=os.environ['PHASE'];mode=os.environ['MODE'];calls=[]
repo.save_account(account_id='a',email_address='fixture@example.invalid',encrypted_refresh_token=svc.cipher.encrypt('rt'),history_id='100',watch_expiration=None)
async def gen(prompt,provider,model):
 kind='extract' if prompt.startswith('Extract action items') else 'draft';calls.append(kind)
 if mode=='kill' and phase=='extraction_inflight' and kind=='extract':os._exit(77)
 return await ns['fake_generate'](prompt,provider,model)
class Embed:
 async def embed(self,*args):
  calls.append('embed')
  if mode=='kill' and phase=='embedding_inflight':os._exit(77)
  return [[]]
svc.llm_generate=gen;svc.embedder=Embed()
raw=ns['raw_message']('g','Please reply',snippet='please reply')
if mode=='kill':
 original=repo.transition_ingest_work
 def transition(aid,gid,expected,target,data):
  won=original(aid,gid,expected,target,data)
  if won and target==phase:os._exit(77)
  return won
 repo.transition_ingest_work=transition
 asyncio.run(svc._ingest_message('a',raw));raise AssertionError('missed kill')
else:
 assert repo.ingest_work('a','g')['phase']==phase
 result=asyncio.run(svc._ingest_message('a',raw))
 safe=phase in ['extraction_done','effects_done']
 assert result is (True if safe else None)
 assert len(repo.list_messages())==int(safe) and len(repo.list_drafts())==int(safe)
 assert calls==(['embed','draft'] if phase=='extraction_done' else ['draft'] if phase=='effects_done' else [])
 assert repo.ingest_work('a','g')['phase']==('complete' if safe else phase)
"""
 env={**os.environ,'PYTHONPATH':'backend','FIXTURE_DIR':str(tmp_path),'PHASE':phase,'MODE':'kill'}
 first=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=25)
 assert first.returncode==77,first.stderr
 resumed=subprocess.run([sys.executable,'-c',script],env={**env,'MODE':'restart'},capture_output=True,text=True,timeout=25)
 assert resumed.returncode==0,resumed.stderr
