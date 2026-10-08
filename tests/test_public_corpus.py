"""Local corpus output validation plus refusal checks. No network fixtures."""
import hashlib,json,sqlite3
import pytest
from app.core.public_corpus import collect
@pytest.mark.parametrize('kwargs',[{'config':'private/unknown'},{'split':'private'},{'pace':0},{'max_rows':0},{'max_rows':100001}])
def test_policy_refuses_before_io(tmp_path,kwargs):
 with pytest.raises(ValueError):collect(tmp_path/'absent.sqlite',tmp_path/'absent.jsonl',**kwargs)
 assert list(tmp_path.iterdir())==[]
def test_live_corpus_receipt_integrity():
 from pathlib import Path
 p=Path('/tmp/corpus-review/train.jsonl')
 if not p.exists():pytest.skip('run the real public corpus collector first')
 rows=[json.loads(x) for x in p.read_text().splitlines()];assert len(rows)==399
 assert len({r['row_index'] for r in rows})==len(rows)
 for row in rows:
  assert hashlib.sha256(row['text'].encode()).hexdigest()==row['sha256']
  assert row['source'].startswith('https://datasets-server.huggingface.co/rows?')
 with sqlite3.connect('/tmp/corpus-review/corpus.sqlite') as db:
  assert db.execute('SELECT count(*) FROM rows').fetchone()[0]==600
  assert db.execute('SELECT next_offset FROM cursors').fetchone()[0]==600
 manifest=json.loads(p.with_suffix('.jsonl.manifest.json').read_text())
 assert manifest['export_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
