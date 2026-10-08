"""Verifier kill pins on COPIES of the actual public HTTP-collected corpus.
No fabricated data or network requests. Optional receipt absent means skipped.
"""
import hashlib,json,shutil,sqlite3
from pathlib import Path
import pytest
from app.core.corpus_verify import verify
LIVE=Path('/tmp/corpus-review')
@pytest.fixture
def corpus(tmp_path):
 if not (LIVE/'corpus.sqlite').exists():pytest.skip('requires actual collector receipt')
 for name in ('corpus.sqlite','train.jsonl','train.jsonl.manifest.json'):shutil.copyfile(LIVE/name,tmp_path/name)
 return tmp_path/'corpus.sqlite',tmp_path/'train.jsonl'
def rehash(export):
 p=export.with_suffix('.jsonl.manifest.json');m=json.loads(p.read_text());m['export_sha256']=hashlib.sha256(export.read_bytes()).hexdigest();p.write_text(json.dumps(m))
def test_actual_corpus(corpus):
 db,export=corpus;before=hashlib.sha256(db.read_bytes()).hexdigest()
 report=verify(db,export);assert report['stored_rows_verified']==600 and report['nonempty_export_rows_verified']==399
 assert hashlib.sha256(db.read_bytes()).hexdigest()==before
@pytest.mark.parametrize('fault',['db_text','cursor','export_bytes','manifest_count','missing_row','duplicate_row','provenance'])
def test_actual_corruption_refused(corpus,fault):
 db,export=corpus
 if fault in {'db_text','cursor','provenance'}:
  with sqlite3.connect(db) as conn:
   if fault=='db_text':conn.execute("UPDATE rows SET text='tampered' WHERE ordinal=1")
   elif fault=='cursor':conn.execute('UPDATE cursors SET next_offset=999')
   else:conn.execute("UPDATE rows SET source='https://example.invalid/rows' WHERE ordinal=1")
 elif fault=='export_bytes':export.write_text(export.read_text()+'garbage')
 elif fault=='manifest_count':
  p=export.with_suffix('.jsonl.manifest.json');m=json.loads(p.read_text());m['nonempty_rows_exported']=999;p.write_text(json.dumps(m))
 else:
  lines=export.read_text().splitlines()
  lines=lines[1:] if fault=='missing_row' else lines+[lines[0]]
  export.write_text('\n'.join(lines)+'\n');rehash(export)
 with pytest.raises(ValueError):verify(db,export)
