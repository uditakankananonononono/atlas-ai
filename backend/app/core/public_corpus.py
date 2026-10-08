"""Bounded public WikiText ingestion, resumable SQLite and real JSONL export.

No arbitrary URLs, credentials, private pages, bypass or remote uploads.
Corpus is CC BY-SA as identified by the publisher's dataset card.
"""
import argparse,hashlib,json,sqlite3,time
from datetime import datetime,timezone
from pathlib import Path
import httpx
DATASET='Salesforce/wikitext'
CARD='https://huggingface.co/datasets/Salesforce/wikitext'
ENDPOINT='https://datasets-server.huggingface.co/rows'
CONFIGS={'wikitext-2-raw-v1','wikitext-103-raw-v1','cc0-prompts'}
def source_spec(config):
 if config=='cc0-prompts':return ('fka/prompts.chat','https://huggingface.co/datasets/fka/prompts.chat','default','prompt','CC0-1.0 https://creativecommons.org/publicdomain/zero/1.0/')
 if config in CONFIGS:return (DATASET,CARD,config,'text','CC-BY-SA (see dataset card for upstream attribution and terms)')
 raise ValueError('unsupported public dataset selection')
def collect(db_path,export_path,*,config='wikitext-2-raw-v1',split='train',max_rows=500,pace=3.0):
 if config not in CONFIGS or split not in {'train','validation','test'}:raise ValueError('unsupported public dataset selection')
 if not 1<=max_rows<=100000 or pace<3:raise ValueError('bounded rows and minimum 3 second pacing required')
 Path(db_path).parent.mkdir(parents=True,exist_ok=True)
 dataset,card,remote_config,text_field,license_note=source_spec(config)
 key=f'{config}/{split}'
 with sqlite3.connect(db_path) as db,httpx.Client(timeout=30,follow_redirects=False) as client:
  db.execute('CREATE TABLE IF NOT EXISTS rows (selection TEXT,ordinal INTEGER,text TEXT,sha256 TEXT,source TEXT,fetched_at TEXT,PRIMARY KEY(selection,ordinal))')
  db.execute('CREATE TABLE IF NOT EXISTS cursors (selection TEXT PRIMARY KEY,next_offset INTEGER)')
  saved=db.execute('SELECT next_offset FROM cursors WHERE selection=?',(key,)).fetchone();offset=saved[0] if saved else 0
  fetched=0;requests=0;total=None
  while fetched<max_rows:
   if requests:time.sleep(pace)
   length=min(100,max_rows-fetched)
   params={'dataset':dataset,'config':remote_config,'split':split,'offset':offset,'length':length}
   response=client.get(ENDPOINT,params=params);requests+=1
   response.raise_for_status() # 401/403/429/challenges stop, never bypassed/retried.
   payload=response.json();rows=payload['rows'];total=payload['num_rows_total']
   if not rows and offset==total:break
   if payload.get('partial') or not rows:raise RuntimeError('incomplete dataset response; cursor unchanged')
   expected=list(range(offset,offset+len(rows)))
   if [r['row_idx'] for r in rows]!=expected or len(rows)>length:raise RuntimeError('invalid row sequence; cursor unchanged')
   now=datetime.now(timezone.utc).isoformat()
   for row in rows:
    text=row['row'][text_field]
    if not isinstance(text,str) or row.get('truncated_cells'):raise RuntimeError('truncated or invalid text; cursor unchanged')
   with db:
    for row in rows:
     text=row['row'][text_field];digest=hashlib.sha256(text.encode()).hexdigest()
     existing=db.execute('SELECT text,sha256,source FROM rows WHERE selection=? AND ordinal=?',(key,row['row_idx'])).fetchone()
     if existing is not None and existing!=(text,digest,str(response.url)):raise ValueError('stored ordinal conflict; reconcile before resume')
     db.execute('INSERT OR IGNORE INTO rows VALUES (?,?,?,?,?,?)',(key,row['row_idx'],text,digest,str(response.url),now))
    offset+=len(rows);fetched+=len(rows)
    db.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)',(key,offset))
   if offset>=total:break
  export=Path(export_path);export.parent.mkdir(parents=True,exist_ok=True);temp=export.with_suffix(export.suffix+'.tmp');written=0
  with temp.open('w',encoding='utf-8') as out:
   for ordinal,text,digest,source,stamp in db.execute('SELECT ordinal,text,sha256,source,fetched_at FROM rows WHERE selection=? ORDER BY ordinal',(key,)):
    if not text.strip():continue
    out.write(json.dumps({'text':text,'sha256':digest,'source':source,'dataset_card':card,'license':license_note,'selection':key,'row_index':ordinal,'fetched_at':stamp},ensure_ascii=False)+'\n');written+=1
  temp.replace(export)
  report={'dataset':dataset,'card':card,'license_note':license_note,'license_url':'https://creativecommons.org/publicdomain/zero/1.0/' if config=='cc0-prompts' else None,'selection':key,'rows_fetched_this_run':fetched,'rows_total_in_db':db.execute('SELECT count(*) FROM rows WHERE selection=?',(key,)).fetchone()[0],'nonempty_rows_exported':written,'next_offset':offset,'publisher_total_rows':total,'requests_this_run':requests,'pace_seconds':pace,'export_sha256':hashlib.sha256(export.read_bytes()).hexdigest(),'training_performed':False}
  export.with_suffix(export.suffix+'.manifest.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--export',required=True);parser.add_argument('--max-rows',type=int,default=500);parser.add_argument('--config',default='wikitext-2-raw-v1');parser.add_argument('--split',default='train')
 args=parser.parse_args();print(json.dumps(collect(args.db,args.export,config=args.config,split=args.split,max_rows=args.max_rows),indent=2))
