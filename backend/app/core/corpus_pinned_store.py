"""Pinned public prompt snapshot composed into SQLite, caller owns lease."""
import hashlib,json,os,sqlite3,tempfile
from pathlib import Path
from .corpus_pinned_prompts import download,verify_snapshot,REVISION

def collect_pinned(db_path,export_path,max_rows=100):
 db_path=Path(db_path);export=Path(export_path);manifest=export.with_suffix(export.suffix+'.manifest.json')
 if any(p.exists() for p in (db_path,export,manifest)):raise FileExistsError('new pinned store artifacts required; explicit resume not supported')
 export.parent.mkdir(parents=True,exist_ok=True);db_path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.pinned-store-',dir=export.parent) as directory:
  snapshot=Path(directory)/'snapshot.jsonl';receipt=download(snapshot,max_rows);count=verify_snapshot(snapshot)
  staged_db=Path(directory)/'store.sqlite'
  with sqlite3.connect(staged_db) as db:
   db.execute('CREATE TABLE pinned_rows(revision TEXT,ordinal INTEGER,text TEXT,sha256 TEXT,source TEXT,PRIMARY KEY(revision,ordinal))')
   db.execute('CREATE TABLE pinned_manifest(revision TEXT PRIMARY KEY,manifest_json TEXT)')
   for line in snapshot.read_text().splitlines():
    row=json.loads(line);db.execute('INSERT INTO pinned_rows VALUES (?,?,?,?,?)',(REVISION,row['row_index'],row['text'],row['sha256'],row['source']))
   db.execute('INSERT INTO pinned_manifest VALUES (?,?)',(REVISION,json.dumps(receipt,sort_keys=True)))
  with sqlite3.connect(staged_db.as_uri()+'?mode=ro',uri=True) as db:
   stored=db.execute('SELECT ordinal,text,sha256 FROM pinned_rows ORDER BY ordinal').fetchall()
   if len(stored)!=count or any(i!=ordinal or hashlib.sha256(text.encode()).hexdigest()!=sha for i,(ordinal,text,sha) in enumerate(stored)):raise ValueError('pinned SQLite readback mismatch')
  # No overwrites. Files may be partially published on OS crash; never auto-resume.
  published=[]
  try:
   for source,target in ((staged_db,db_path),(snapshot,export),(snapshot.with_suffix('.jsonl.manifest.json'),manifest)):
    os.link(source,target);published.append(target)
  except Exception:
   for target in reversed(published):target.unlink()
   raise
 return {'status':'verified','selection':'cc0-pinned/train','publisher_revision':REVISION,'stored_rows_verified':count,'nonempty_export_rows_verified':count,'next_offset':count,'export_sha256':receipt['export_sha256'],'training_verified':False,'local_lock':True,'resumable':False}
