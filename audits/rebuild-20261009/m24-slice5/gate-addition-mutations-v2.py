"""Disposable-only runner: exactly two DID NOT RAISE failures per mutation."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,sys,tempfile
root=Path(__file__).resolve().parents[3]
os.chdir(root)
p=Path('backend/app/modules/m24_billing/inbox.py');original=p.read_bytes()
cases=[
('future-created',"<=int(datetime.now(timezone.utc).timestamp())+300",'<253402300800','future_created_bound_alone'),
('local-customer'," or local.customer_id!=binding.customer_id",'','mapping_drift_alone and customer_id'),
('local-subscription',"if not row.event_type.startswith('invoice.') and local.subscription_id!=resource:",'if False:','mapping_drift_alone and subscription_id'),
('checkout-state'," or op.state!='succeeded'",'','receipt_id_alone and state'),
('checkout-result-id'," or op.result.get('id')!=obj.get('id')",'','receipt_id_alone and result'),
('invoice-paid-status',"obj['status']!='paid' or ",'','confirmed_paid_single and status'),
('invoice-paid-amount'," or obj['amount_paid']<obj['amount_due']",'','confirmed_paid_single and amount_paid'),
('invoice-owner',"if current is not None and current.tenant_id!=binding.tenant_id:",'if False:','current_invoice_foreign_tenant_alone'),
('deleted-canceled',"if kind.endswith('deleted') and obj['status']!='canceled':",'if False:','deleted_subscription_active_status_alone'),
]
# Selected count, failed count, passing-control count, expected missing raises.
expectations={
 'future-created':(2,2,0,2),
 'local-customer':(2,2,0,2),
 'local-subscription':(2,2,0,2),
 'checkout-state':(4,2,2,2),
 'checkout-result-id':(2,2,0,2),
 'invoice-paid-status':(2,2,0,2),
 'invoice-paid-amount':(2,2,0,2),
 'invoice-owner':(2,2,0,2),
 'deleted-canceled':(2,2,0,2),
}

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case',action='append',choices=[case[0] for case in cases])
parser.add_argument('--output-dir',type=Path,help='Must be outside this repository; default new temporary directory.')
args=parser.parse_args()
output=(args.output_dir or Path(tempfile.mkdtemp(prefix='m24-inbox-mutations-v2-'))).resolve()
if output==root or root in output.parents:parser.error('--output-dir must be outside the repository')
output.mkdir(parents=True,exist_ok=True)
def git_status():return subprocess.run(['git','status','--porcelain=v1','--untracked-files=all'],capture_output=True,text=True,check=True).stdout
baseline=git_status()
print('receipts',str(output),flush=True)
def restore_receipt(name):
 actual=p.read_bytes();status=git_status();expected=hashlib.sha256(original).hexdigest()
 ok=actual==original and status==baseline
 receipt={'case':name,'file':str(p),'sha256':hashlib.sha256(actual).hexdigest(),'expected_sha256':expected,'restored':ok,'git_status':status,'baseline_git_status':baseline}
 (output/('RESTORED-'+name+'.json')).write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 print(json.dumps(receipt,sort_keys=True),flush=True)
 if not ok:raise RuntimeError('Restore hash/git-state mismatch; refusing next case: '+name)
try:
 for name,old,new,selection in cases:
  if args.case is not None and name not in args.case:continue
  s=original.decode();assert s.count(old)==1,(name,s.count(old))
  try:
   p.write_text(s.replace(old,new,1))
   r=subprocess.run([sys.executable,'-m','pytest','-q','tests/modules/test_m24_verified_inbox.py','-k',selection],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=30)
   (output/('RED-gate-'+name+'.log')).write_text(r.stdout+r.stderr)
   failed_nodes=re.findall(r'^FAILED (tests/[^\n ]+)',r.stdout,re.MULTILINE)
   failure_count=re.findall(r'(\d+) failed',r.stdout)
   missing_raise_count=len(re.findall(r'^E\s+Failed: DID NOT RAISE',r.stdout,re.MULTILINE))
   passed_counts=re.findall(r'(\d+) passed',r.stdout)
   passed=int(passed_counts[-1]) if passed_counts else 0
   failed=int(failure_count[-1]) if failure_count else -1
   shape=(failed+passed,failed,passed,missing_raise_count)
   count_ok=shape==expectations[name] and len(failed_nodes)==2 and len(set(failed_nodes))==2
   print(name,r.returncode,r.stdout.strip().splitlines()[-1],flush=True)
   print(json.dumps({'case':name,'failed_nodes':failed_nodes,'did_not_raise_count':missing_raise_count,'count_check':bool(count_ok),'observed_shape':shape,'expected_shape':expectations[name]},sort_keys=True),flush=True)
   if r.returncode!=1 or not count_ok:raise RuntimeError('Expected per-case selected/failure/control shape: '+name)
  finally:
   p.write_bytes(original);restore_receipt(name)
finally:p.write_bytes(original)
