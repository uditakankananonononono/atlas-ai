"""Explicit collection or read-only integrity commands. Failures stay failures."""
import argparse,json,sys
from .corpus_verify import verify

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 commands=parser.add_subparsers(dest='command',required=True)
 for name in ('collect','verify'):
  command=commands.add_parser(name);command.add_argument('--db',required=True);command.add_argument('--export',required=True)
  if name=='collect':
   command.add_argument('--max-rows',type=int,default=500);command.add_argument('--config',default='wikitext-2-raw-v1');command.add_argument('--split',default='train')
 args=parser.parse_args(argv)
 try:
  collection=None
  if args.command=='collect':
   from .public_corpus import collect
   collection=collect(args.db,args.export,config=args.config,split=args.split,max_rows=args.max_rows)
  result=verify(args.db,args.export)
  if collection is not None:result['collection']=collection
  print(json.dumps(result,indent=2));return 0
 except Exception as exc:
  # Paths/remote error bodies may be private. Error class and named command
  # identify the failure without copying exception contents to public logs.
  print(json.dumps({'status':'failed','command':args.command,'error_type':type(exc).__name__,'verified':False}),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
