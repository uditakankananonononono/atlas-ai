"""Actual separate-process lease contention, no simulated HTTP collection."""
import os,subprocess,sys,json
from pathlib import Path
import pytest
from app.core.corpus_locked_cli import corpus_lock,CorpusBusy
ENV={**os.environ,'PYTHONPATH':'backend'}
def test_two_process_contention_refuses_before_network(tmp_path):
 db=tmp_path/'db';export=tmp_path/'export'
 code='from app.core.corpus_locked_cli import corpus_lock; import sys;\nwith corpus_lock(sys.argv[1],sys.argv[2]):\n print("held",flush=True);sys.stdin.readline()'
 child=subprocess.Popen([sys.executable,'-c',code,str(db),str(export)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=ENV)
 try:
  assert child.stdout.readline().strip()=='held'
  result=subprocess.run([sys.executable,'-m','app.core.corpus_locked_cli','--db',str(db),'--export',str(export)],env=ENV,capture_output=True,text=True,timeout=10)
  assert result.returncode==2 and json.loads(result.stderr)['error_type']=='CorpusBusy'
  assert not db.exists() and not export.exists()
 finally:
  child.communicate('\n',timeout=10)
 assert child.returncode==0
 assert not list(tmp_path.glob('*.collection-lock'))
def test_exception_releases_owned_lease(tmp_path):
 with pytest.raises(ValueError):
  with corpus_lock(tmp_path/'db',tmp_path/'out'):raise ValueError('test')
 assert not list(tmp_path.glob('*.collection-lock'))
def test_shared_export_protected_across_different_databases(tmp_path):
 with corpus_lock(tmp_path/'a',tmp_path/'out'):
  with pytest.raises(CorpusBusy):
   with corpus_lock(tmp_path/'b',tmp_path/'out'):pass
  assert not Path(str(tmp_path/'b')+'.collection-lock').exists()
def test_stale_lease_not_stolen(tmp_path):
 lock=Path(str(tmp_path/'db')+'.collection-lock');lock.write_text('operator review required')
 with pytest.raises(CorpusBusy):
  with corpus_lock(tmp_path/'db',tmp_path/'out'):pass
 assert lock.read_text()=='operator review required'
def test_corrupted_resume_refused_before_network_and_unchanged(tmp_path,monkeypatch,capsys):
 import shutil,hashlib,sqlite3,httpx
 from app.core.corpus_locked_cli import main
 live=Path('/tmp/corpus-review')
 if not (live/'corpus.sqlite').exists():pytest.skip('actual public receipt needed')
 db=tmp_path/'corpus.sqlite';export=tmp_path/'train.jsonl'
 for name in ('corpus.sqlite','train.jsonl','train.jsonl.manifest.json'):shutil.copyfile(live/name,tmp_path/name)
 with sqlite3.connect(db) as conn:conn.execute("UPDATE rows SET text='corrupted' WHERE ordinal=1")
 before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}
 def refuse(*args,**kwargs):raise AssertionError('network must not run on corrupt resume')
 monkeypatch.setattr(httpx.Client,'get',refuse)
 assert main(['--db',str(db),'--export',str(export),'--max-rows','1'])==1
 assert json.loads(capsys.readouterr().err)['error_type']=='ValueError'
 assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}==before
def test_different_selection_cannot_replace_existing_export(tmp_path,monkeypatch,capsys):
 import shutil,hashlib,httpx
 from app.core.corpus_locked_cli import main
 live=Path('/tmp/corpus-review')
 if not (live/'corpus.sqlite').exists():pytest.skip('actual public corpus needed')
 for name in ('corpus.sqlite','train.jsonl','train.jsonl.manifest.json'):shutil.copyfile(live/name,tmp_path/name)
 before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}
 def refuse(*args,**kwargs):raise AssertionError('request must refuse mismatch before network')
 monkeypatch.setattr(httpx.Client,'get',refuse)
 assert main(['--db',str(tmp_path/'corpus.sqlite'),'--export',str(tmp_path/'train.jsonl'),'--config','cc0-prompts','--max-rows','1'])==1
 assert json.loads(capsys.readouterr().err)['error_type']=='ValueError'
 assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}==before
