"""Actual child verifier executions; no simulated outcomes."""
from pathlib import Path
import json,pytest
from app.core.corpus_run_receipt import run_receipted
@pytest.mark.parametrize('corrupt',[False,True])
def test_actual_child_receipt(tmp_path,corrupt):
 db=Path('/tmp/verify-review/corrupted.sqlite') if corrupt else Path('/tmp/corpus-review/corpus.sqlite')
 export=Path('/tmp/corpus-review/train.jsonl')
 if not db.exists():pytest.skip('actual collected/corrupted receipt needed')
 p=tmp_path/'receipt.json';r=run_receipted(db,export,p)
 assert r['status']==('failed' if corrupt else 'verified') and r['exit_status']==(1 if corrupt else 0)
 assert json.loads(p.read_text())==r and '/tmp/' not in p.read_text() and '/home/' not in p.read_text()
 assert len(r['source_head'])==40
 with pytest.raises(FileExistsError):run_receipted(db,export,p)
def test_receipt_cannot_replace_corpus(tmp_path):
 with pytest.raises(ValueError):run_receipted(tmp_path/'db',tmp_path/'out',tmp_path/'db')
@pytest.mark.parametrize('rows',[0,-1,100001,True])
def test_invalid_collect_bounds_refused_before_execution(tmp_path,rows):
 with pytest.raises(ValueError):run_receipted(tmp_path/'db',tmp_path/'out',tmp_path/'receipt',mode='collect',max_rows=rows)
 assert list(tmp_path.iterdir())==[]
def test_startup_exception_is_failed_receipt(tmp_path,monkeypatch):
 import subprocess
 import app.core.corpus_run_receipt as module
 real=subprocess.run
 def runner(command,*args,**kwargs):
  if command[0]=='git':return real(command,*args,**kwargs)
  raise OSError('private launch path must not be retained')
 monkeypatch.setattr(module.subprocess,'run',runner)
 p=tmp_path/'receipt';r=run_receipted(tmp_path/'db',tmp_path/'out',p)
 assert r['status']=='failed' and r['exit_status'] is None and r['launch_error_type']=='OSError'
 assert 'private launch' not in p.read_text()
def test_real_child_killed_on_wall_clock_timeout(tmp_path,monkeypatch):
 import subprocess,time,os
 import app.core.corpus_run_receipt as module
 db=Path('/tmp/corpus-review/corpus.sqlite');export=Path('/tmp/corpus-review/train.jsonl')
 if not db.exists():pytest.skip('actual public receipt needed')
 real=subprocess.run;pidfile=tmp_path/'pid';finished=tmp_path/'finished'
 code='import os,time,pathlib;pathlib.Path('+repr(str(pidfile))+').write_text(str(os.getpid()));time.sleep(0.6);pathlib.Path('+repr(str(finished))+').write_text("completed");from app.core.corpus_cli import main;raise SystemExit(main(["verify","--db",'+repr(str(db))+',"--export",'+repr(str(export))+']))'
 def runner(command,*args,**kwargs):
  if command[0]=='git':return real(command,*args,**kwargs)
  return real([command[0],'-c',code],*args,**kwargs)
 monkeypatch.setattr(module,'DEFAULT_TIMEOUT_SECONDS',0.2,raising=False)
 monkeypatch.setattr(module.subprocess,'run',runner)
 started=time.monotonic();r=run_receipted(db,export,tmp_path/'receipt')
 assert r['status']=='failed' and r.get('timed_out') is True
 assert r['exit_status'] is None and time.monotonic()-started<0.6
 assert pidfile.exists() and not finished.exists()
 with pytest.raises(ProcessLookupError):os.kill(int(pidfile.read_text()),0)
