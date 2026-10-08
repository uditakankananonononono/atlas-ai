"""Read-only verification of an actual collected public corpus and export."""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .public_corpus import CARD,DATASET,CONFIGS

def verify(db_path,export_path):
 export=Path(export_path);manifest=json.loads(export.with_suffix(export.suffix+'.manifest.json').read_text())
 key=manifest['selection'];config,split=key.split('/')
 if config not in CONFIGS or split not in {'train','validation','test'}:raise ValueError('unsupported dataset selection')
 if manifest['dataset']!=DATASET or manifest['card']!=CARD or manifest['training_performed'] is not False:raise ValueError('manifest provenance mismatch')
 if hashlib.sha256(export.read_bytes()).hexdigest()!=manifest['export_sha256']:raise ValueError('export checksum mismatch')
 # URI mode=ro prevents creation/writes to the source database.
 with sqlite3.connect(Path(db_path).resolve().as_uri()+'?mode=ro',uri=True) as db:
  stored=db.execute('SELECT ordinal,text,sha256,source,fetched_at FROM rows WHERE selection=? ORDER BY ordinal',(key,)).fetchall()
  cursor=db.execute('SELECT next_offset FROM cursors WHERE selection=?',(key,)).fetchone()
 if not cursor or cursor[0]!=len(stored) or [r[0] for r in stored]!=list(range(len(stored))):raise ValueError('noncontiguous rows or cursor mismatch')
 expected={}
 for ordinal,text,digest,source,stamp in stored:
  if hashlib.sha256(text.encode()).hexdigest()!=digest:raise ValueError('stored text checksum mismatch')
  url=urlsplit(source);query=parse_qs(url.query)
  if url.scheme!='https' or url.netloc!='datasets-server.huggingface.co' or url.path!='/rows' or url.username or query.get('dataset')!=[DATASET] or query.get('config')!=[config] or query.get('split')!=[split]:raise ValueError('stored source mismatch')
  offset=int(query['offset'][0]);length=int(query['length'][0])
  if not offset<=ordinal<offset+length:raise ValueError('row outside source page')
  if text.strip():expected[ordinal]=(text,digest,source,stamp)
 seen=set()
 for line in export.read_text(encoding='utf-8').splitlines():
  row=json.loads(line);ordinal=row['row_index']
  if ordinal in seen or ordinal not in expected:raise ValueError('duplicate or unexpected export ordinal')
  seen.add(ordinal)
  if (row['text'],row['sha256'],row['source'],row['fetched_at'])!=expected[ordinal] or row['dataset_card']!=CARD or row['selection']!=key or not row['license'].startswith('CC-BY-SA'):raise ValueError('export correspondence mismatch')
 if seen!=set(expected):raise ValueError('export missing rows')
 if manifest['rows_total_in_db']!=len(stored) or manifest['next_offset']!=cursor[0] or manifest['nonempty_rows_exported']!=len(seen):raise ValueError('manifest count mismatch')
 return {'status':'verified','selection':key,'stored_rows_verified':len(stored),'nonempty_export_rows_verified':len(seen),'next_offset':cursor[0],'export_sha256':manifest['export_sha256'],'training_verified':False}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--export',required=True);args=parser.parse_args()
 print(json.dumps(verify(args.db,args.export),indent=2))
