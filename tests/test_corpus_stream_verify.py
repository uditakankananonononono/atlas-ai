"""Real receipt and corrupted-copy checks, explicitly optional without receipts."""
import hashlib,json,shutil,sqlite3
from pathlib import Path
import pytest
from app.core.corpus_stream_verify import verify
LIVE=Path('/tmp/corpus-review')
@pytest.fixture
def corpus(tmp_path):
 if not (LIVE/'corpus.sqlite').exists():pytest.skip('actual public corpus receipt needed')
 for name in ('corpus.sqlite','train.jsonl','train.jsonl.manifest.json'):shutil.copyfile(LIVE/name,tmp_path/name)
 return tmp_path/'corpus.sqlite',tmp_path/'train.jsonl'
def test_actual_stream(corpus):
 db,export=corpus;r=verify(db,export);assert r['stored_rows_verified']==600 and r['nonempty_export_rows_verified']==399
@pytest.mark.parametrize('fault',['stored_hash','source','cursor','reordered_export','extra_row','missing_row'])
def test_actual_stream_corruption(corpus,fault):
 db,export=corpus
 if fault in {'stored_hash','source','cursor'}:
  with sqlite3.connect(db) as conn:
   if fault=='stored_hash':conn.execute("UPDATE rows SET text='tampered' WHERE ordinal=1")
   elif fault=='source':conn.execute("UPDATE rows SET source='https://example.invalid' WHERE ordinal=1")
   else:conn.execute('UPDATE cursors SET next_offset=999')
 else:
  lines=export.read_text().splitlines()
  if fault=='reordered_export':lines[0],lines[1]=lines[1],lines[0]
  elif fault=='extra_row':lines.append(lines[0])
  else:lines.pop()
  export.write_text('\n'.join(lines)+'\n')
  p=export.with_suffix('.jsonl.manifest.json');m=json.loads(p.read_text());m['export_sha256']=hashlib.sha256(export.read_bytes()).hexdigest();p.write_text(json.dumps(m))
 with pytest.raises(ValueError):verify(db,export)
