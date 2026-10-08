"""Streaming internal consistency checks. No remote attestation or training."""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .public_corpus import CARD,DATASET,CONFIGS

def verify(db_path,export_path):
 export=Path(export_path);manifest=json.loads(export.with_suffix(export.suffix+'.manifest.json').read_text())
 key=manifest['selection'];config,split=key.split('/')
 if config not in CONFIGS or split not in {'train','validation','test'}:raise ValueError('unsupported selection')
 if manifest['dataset']!=DATASET or manifest['card']!=CARD or manifest['training_performed'] is not False:raise ValueError('manifest provenance mismatch')
 digest=hashlib.sha256()
 with export.open('rb') as stream:
  for block in iter(lambda:stream.read(65536),b''):digest.update(block)
 if digest.hexdigest()!=manifest['export_sha256']:raise ValueError('export checksum mismatch')
 stored=written=0
 with sqlite3.connect(Path(db_path).resolve().as_uri()+'?mode=ro',uri=True) as db,export.open(encoding='utf-8') as stream:
  cursor=db.execute('SELECT next_offset FROM cursors WHERE selection=?',(key,)).fetchone()
  for ordinal,text,sha,source,stamp in db.execute('SELECT ordinal,text,sha256,source,fetched_at FROM rows WHERE selection=? ORDER BY ordinal',(key,)):
   if ordinal!=stored:raise ValueError('noncontiguous stored ordinals')
   stored+=1
   if hashlib.sha256(text.encode()).hexdigest()!=sha:raise ValueError('stored text checksum mismatch')
   url=urlsplit(source);query=parse_qs(url.query)
   if url.scheme!='https' or url.netloc!='datasets-server.huggingface.co' or url.path!='/rows' or url.username or query.get('dataset')!=[DATASET] or query.get('config')!=[config] or query.get('split')!=[split]:raise ValueError('stored source mismatch')
   if not int(query['offset'][0])<=ordinal<int(query['offset'][0])+int(query['length'][0]):raise ValueError('row outside source page')
   if not text.strip():continue
   line=stream.readline()
   if not line:raise ValueError('export missing row')
   row=json.loads(line)
   if (row['row_index'],row['text'],row['sha256'],row['source'],row['fetched_at'])!=(ordinal,text,sha,source,stamp) or row['dataset_card']!=CARD or row['selection']!=key or not row['license'].startswith('CC-BY-SA'):raise ValueError('ordered export correspondence mismatch')
   written+=1
  if stream.readline():raise ValueError('unexpected extra export row')
  if not cursor or cursor[0]!=stored:raise ValueError('cursor mismatch')
 if manifest['rows_total_in_db']!=stored or manifest['next_offset']!=stored or manifest['nonempty_rows_exported']!=written:raise ValueError('manifest count mismatch')
 return {'status':'verified','selection':key,'stored_rows_verified':stored,'nonempty_export_rows_verified':written,'next_offset':stored,'export_sha256':digest.hexdigest(),'training_verified':False,'method':'ordered-stream','buffer_bytes':65536}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--export',required=True);args=parser.parse_args()
 print(json.dumps(verify(args.db,args.export),indent=2))
