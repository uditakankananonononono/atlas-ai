"""Exclusive local corpus/export leases. Stale leases require operator review.

All writers must use this runner; legacy unlocked CLI is not fenced. Not a
network filesystem/distributed lock or crash recovery guarantee.
"""
import argparse,json,os,secrets,sys
from contextlib import contextmanager
from pathlib import Path

class CorpusBusy(RuntimeError):pass
@contextmanager
def corpus_lock(db_path,export_path):
 resources=sorted({Path(db_path).resolve(),Path(export_path).resolve()},key=str)
 owned=[];token=secrets.token_hex(16)
 try:
  for resource in resources:
   resource.parent.mkdir(parents=True,exist_ok=True)
   lock=Path(str(resource)+'.collection-lock')
   try:fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   except FileExistsError:raise CorpusBusy('local corpus resource locked; operator review needed if stale') from None
   owned.append(lock)
   with os.fdopen(fd,'w') as stream:json.dump({'pid':os.getpid(),'token':token,'resource':str(resource)},stream);stream.flush();os.fsync(stream.fileno())
  yield
 finally:
  for lock in reversed(owned):
   # Do not delete a replaced lease belonging to another writer.
   try:
    if json.loads(lock.read_text()).get('token')==token:lock.unlink()
   except (FileNotFoundError,ValueError):pass

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--db',required=True);parser.add_argument('--export',required=True);parser.add_argument('--max-rows',type=int,default=100);parser.add_argument('--config',default='wikitext-2-raw-v1');parser.add_argument('--split',default='train');args=parser.parse_args(argv)
 try:
  with corpus_lock(args.db,args.export):
   from .public_corpus import collect
   from .corpus_stream_verify import verify
   report=collect(args.db,args.export,config=args.config,split=args.split,max_rows=args.max_rows)
   verified=verify(args.db,args.export);verified['collection']=report;verified['local_lock']=True
   print(json.dumps(verified,indent=2))
  return 0
 except Exception as exc:
  print(json.dumps({'status':'blocked' if isinstance(exc,CorpusBusy) else 'failed','error_type':type(exc).__name__,'verified':False}),file=sys.stderr);return 2 if isinstance(exc,CorpusBusy) else 1
if __name__=='__main__':raise SystemExit(main())
