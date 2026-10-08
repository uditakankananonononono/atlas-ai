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
