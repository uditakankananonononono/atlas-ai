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
