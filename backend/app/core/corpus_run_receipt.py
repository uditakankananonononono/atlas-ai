"""Run a real collector/verifier subprocess and retain an atomic local receipt."""
import argparse,hashlib,json,os,subprocess,sys,time,tempfile
from datetime import datetime,timezone
from pathlib import Path
DEFAULT_TIMEOUT_SECONDS=900

def run_receipted(db_path,export_path,receipt_path,*,mode='verify',max_rows=100,config='wikitext-2-raw-v1',split='train'):
 from .public_corpus import source_spec
 if config!='cc0-pinned':source_spec(config)
 elif mode!='collect':raise ValueError('pinned receipt supports fresh collect only')
 if split not in {'train','validation','test'} or (config in {'cc0-prompts','cc0-pinned'} and split!='train'):raise ValueError('unsupported source split')
 if mode not in {'verify','collect'}:raise ValueError('mode must be verify or collect')
 if mode=='collect' and (isinstance(max_rows,bool) or not isinstance(max_rows,int) or not 1<=max_rows<=100000):raise ValueError('collect rows must be integer 1..100000')
 db=Path(db_path).resolve();export=Path(export_path).resolve();receipt=Path(receipt_path).resolve()
 if receipt in {db,export,export.with_suffix(export.suffix+'.manifest.json'),Path(str(db)+'.collection-lock'),Path(str(export)+'.collection-lock')}:raise ValueError('receipt cannot replace corpus artifacts')
 if receipt.exists():raise FileExistsError('receipt destination already exists')
 root=Path(__file__).resolve().parents[3]
 revision=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
 dirty=subprocess.run(['git','-C',str(root),'status','--porcelain'],capture_output=True,text=True,check=True).stdout
 command=[sys.executable,'-m','app.core.corpus_cli','verify','--db',str(db),'--export',str(export)] if mode=='verify' else [sys.executable,'-m','app.core.corpus_locked_cli','--db',str(db),'--export',str(export),'--max-rows',str(max_rows),'--config',config,'--split',split]
 env={**os.environ,'PYTHONPATH':str(root/'backend')}
 started=datetime.now(timezone.utc).isoformat();start=time.monotonic()
 launch_error=None;timed_out=False
 try:result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=DEFAULT_TIMEOUT_SECONDS)
 except subprocess.TimeoutExpired:
  timed_out=True;result=subprocess.CompletedProcess(command,None,stdout='',stderr='')
 except OSError as exc:
  launch_error=type(exc).__name__;result=subprocess.CompletedProcess(command,None,stdout='',stderr='')
 elapsed=time.monotonic()-start
 output=None
 if result.returncode==0:
  try:output=json.loads(result.stdout)
  except ValueError:pass
 success=result.returncode==0 and isinstance(output,dict) and output.get('status')=='verified'
 # Do not persist absolute paths, raw stderr, environment or credentials.
 report={'mode':mode,'selection':config+'/'+split,'source_head':revision,'source_tree_dirty':bool(dirty),'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':elapsed,'exit_status':result.returncode,'status':'verified' if success else 'failed','stdout_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(result.stderr.encode()).hexdigest(),'command_template':'python -m app.core.corpus_cli verify --db <corpus> --export <export>' if mode=='verify' else 'python -m app.core.corpus_locked_cli --db <corpus> --export <export> --max-rows N --config <fixed-selection> --split <split>','max_rows':max_rows if mode=='collect' else None,'training_performed':False}
 report['wall_clock_timeout_seconds']=DEFAULT_TIMEOUT_SECONDS
 if timed_out:report['timed_out']=True
 if launch_error:report['launch_error_type']=launch_error
 if success and output.get('selection')!=config+'/'+split:
  success=False;report['status']='failed';report['selection_mismatch']=True
 if success and output.get('publisher_revision'):report['publisher_revision']=output['publisher_revision']
 if success:report['result']={k:output[k] for k in ('stored_rows_verified','nonempty_export_rows_verified','next_offset','export_sha256')}
 receipt.parent.mkdir(parents=True,exist_ok=True)
 # Fully write/fsync temp, then atomically hard-link into absent receipt.
 # A failed run still publishes a failed receipt, never a success label.
 fd,temp=tempfile.mkstemp(prefix='.corpus-receipt-',dir=receipt.parent)
 try:
  with os.fdopen(fd,'w') as stream:json.dump(report,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
  os.link(temp,receipt) # no overwrite if another process won
 finally:
  Path(temp).unlink(missing_ok=True)
 return report
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--export',required=True);parser.add_argument('--receipt',required=True);parser.add_argument('--mode',choices=['verify','collect'],default='verify');parser.add_argument('--max-rows',type=int,default=100);parser.add_argument('--config',default='wikitext-2-raw-v1');parser.add_argument('--split',default='train');args=parser.parse_args()
 report=run_receipted(args.db,args.export,args.receipt,mode=args.mode,max_rows=args.max_rows,config=args.config,split=args.split);print(json.dumps(report,indent=2));raise SystemExit(0 if report['status']=='verified' else 1)
