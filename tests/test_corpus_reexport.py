"""Actual CC0 stored corpus recovery, no network or invented source rows."""
from pathlib import Path
import hashlib,shutil,sqlite3,pytest
from app.core.corpus_reexport import reexport
@pytest.fixture
def db(tmp_path):
 source=Path('/tmp/cc0-review/live.sqlite')
 if not source.exists():pytest.skip('actual CC0 corpus required')
 p=tmp_path/'source.sqlite';shutil.copyfile(source,p);return p
def test_actual_reexport_preserves_database_and_text(db,tmp_path):
 before=hashlib.sha256(db.read_bytes()).hexdigest();out=tmp_path/'restored.jsonl'
 report=reexport(db,out,'cc0-prompts/train')
 assert report['stored_rows_verified']==200 and report['nonempty_export_rows_verified']==200
 assert hashlib.sha256(db.read_bytes()).hexdigest()==before
 assert out.read_bytes()==Path('/tmp/cc0-review/live.jsonl').read_bytes()
 with pytest.raises(FileExistsError):reexport(db,out,'cc0-prompts/train')
def test_corrupt_source_publishes_nothing(db,tmp_path):
 with sqlite3.connect(db) as conn:conn.execute("UPDATE rows SET text='corrupt' WHERE ordinal=0")
 out=tmp_path/'restored.jsonl'
 with pytest.raises(ValueError):reexport(db,out,'cc0-prompts/train')
 assert not out.exists() and not out.with_suffix('.jsonl.manifest.json').exists()
 assert not list(tmp_path.glob('*.collection-lock'))
def test_interrupted_export_recovered_into_new_artifacts(db,tmp_path):
 import json
 original=Path('/tmp/cc0-review/live.jsonl').read_bytes()
 interrupted=tmp_path/'interrupted.jsonl';interrupted.write_bytes(original[:len(original)//2])
 # Simulate interruption after DB commit while export is half-written and
 # manifest absent. Keep broken artifact for inspection; never overwrite it.
 before=interrupted.read_bytes();out=tmp_path/'recovered.jsonl'
 report=reexport(db,out,'cc0-prompts/train')
 assert report['stored_rows_verified']==200 and out.read_bytes()==original
 assert interrupted.read_bytes()==before
 assert json.loads(out.with_suffix('.jsonl.manifest.json').read_text())['offline_reexport'] is True
