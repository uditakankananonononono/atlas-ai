"""Actual offline CLI process evidence. No simulated collection success."""
import json,os,subprocess,sys
from pathlib import Path
import pytest
ROOT=Path('/tmp/corpus-review')
def run(db):
 env={**os.environ,'PYTHONPATH':'backend'}
 return subprocess.run([sys.executable,'-m','app.core.corpus_cli','verify','--db',str(db),'--export',str(ROOT/'train.jsonl')],env=env,capture_output=True,text=True)
def test_verify_actual_corpus():
 if not (ROOT/'corpus.sqlite').exists():pytest.skip('actual corpus receipt needed')
 result=run(ROOT/'corpus.sqlite');assert result.returncode==0
 assert json.loads(result.stdout)['stored_rows_verified']==600
 assert result.stderr==''
def test_verify_actual_corrupted_copy():
 db=Path('/tmp/verify-review/corrupted.sqlite')
 if not db.exists():pytest.skip('actual corrupted copy needed')
 result=run(db);assert result.returncode==1 and result.stdout==''
 report=json.loads(result.stderr);assert report=={'status':'failed','command':'verify','error_type':'ValueError','verified':False}
def test_missing_corpus_fails_not_created(tmp_path):
 db=tmp_path/'absent.sqlite';result=run(db)
 assert result.returncode==1 and not db.exists() and json.loads(result.stderr)['status']=='failed'
