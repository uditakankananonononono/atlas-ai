"""Actual pinned SQLite store readback, and overwrite refusal without HTTP."""
from pathlib import Path
import json,sqlite3,hashlib,pytest
from app.core.corpus_pinned_store import collect_pinned
from app.core.corpus_pinned_prompts import REVISION,verify_snapshot

def test_actual_pinned_store():
 root=Path('/tmp/archive-store-review')
 if not (root/'live.sqlite').exists():pytest.skip('real pinned collection run required')
 assert verify_snapshot(root/'live.jsonl')==100
 with sqlite3.connect(root/'live.sqlite') as db:
  rows=db.execute('SELECT revision,ordinal,text,sha256 FROM pinned_rows ORDER BY ordinal').fetchall()
  assert len(rows)==100
  for i,(revision,ordinal,text,sha) in enumerate(rows):assert revision==REVISION and ordinal==i and hashlib.sha256(text.encode()).hexdigest()==sha
  assert json.loads(db.execute('SELECT manifest_json FROM pinned_manifest').fetchone()[0])['publisher_revision']==REVISION

def test_existing_store_refuses_no_overwrite(tmp_path):
 db=tmp_path/'db';db.write_bytes(b'preserve')
 with pytest.raises(FileExistsError):collect_pinned(db,tmp_path/'out')
 assert db.read_bytes()==b'preserve' and not (tmp_path/'out').exists()
