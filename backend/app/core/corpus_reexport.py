"""Explicit read-only re-export into NEW artifacts, never automatic resume."""
import argparse,hashlib,json,os,sqlite3,tempfile
from pathlib import Path
from .public_corpus import source_spec
from .corpus_stream_verify import verify
from .corpus_locked_cli import corpus_lock

def reexport(db_path,export_path,selection):
 db_path=Path(db_path).resolve();export=Path(export_path).resolve();manifest=export.with_suffix(export.suffix+'.manifest.json')
 config,split=selection.split('/')
 if split not in {'train','validation','test'} or (config=='cc0-prompts' and split!='train'):raise ValueError('unsupported selection')
 dataset,card,remote_config,text_field,license_note=source_spec(config)
 if export==db_path or manifest==db_path:raise ValueError('output must not replace database')
 with corpus_lock(db_path,export):
  if export.exists() or manifest.exists():raise FileExistsError('new output paths required')
  with tempfile.TemporaryDirectory(prefix='.corpus-reexport-',dir=export.parent) as directory:
   stage=Path(directory)/'export.jsonl';h=hashlib.sha256();written=stored=0
   with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db,stage.open('wb') as stream:
    cursor=db.execute('SELECT next_offset FROM cursors WHERE selection=?',(selection,)).fetchone()
    if not cursor:raise ValueError('no stored selection cursor')
    for ordinal,text,digest,source,stamp in db.execute('SELECT ordinal,text,sha256,source,fetched_at FROM rows WHERE selection=? ORDER BY ordinal',(selection,)):
     stored+=1
     if not text.strip():continue
     row={'text':text,'sha256':digest,'source':source,'dataset_card':card,'license':license_note,'selection':selection,'row_index':ordinal,'fetched_at':stamp}
     line=(json.dumps(row,ensure_ascii=False)+'\n').encode();stream.write(line);h.update(line);written+=1
    stream.flush();os.fsync(stream.fileno())
   receipt={'dataset':dataset,'card':card,'license_note':license_note,'license_url':'https://creativecommons.org/publicdomain/zero/1.0/' if config=='cc0-prompts' else None,'selection':selection,'rows_total_in_db':stored,'nonempty_rows_exported':written,'next_offset':cursor[0],'export_sha256':h.hexdigest(),'training_performed':False,'offline_reexport':True,'requests_this_run':0}
   stage_manifest=stage.with_suffix('.jsonl.manifest.json');stage_manifest.write_text(json.dumps(receipt,indent=2)+'\n')
   checked=verify(db_path,stage) # verifies DB/hash/provenance/cursor BEFORE publication
   os.link(stage,export)
   try:os.link(stage_manifest,manifest)
   except Exception:
    export.unlink();raise
   return checked
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--export',required=True);parser.add_argument('--selection',required=True);args=parser.parse_args()
 print(json.dumps(reexport(args.db,args.export,args.selection),indent=2))
