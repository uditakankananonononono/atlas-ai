"""Disposable-clone mutation runner; --case NAME selects one or more cases."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,tempfile
root=Path(__file__).resolve().parents[3]
os.chdir(root)
c=Path('backend/app/modules/m24_billing/cancellation.py');r=Path('backend/app/modules/m24_billing/reconciliation.py');i=Path('backend/app/modules/m24_billing/invoice_dispatcher.py')
base={p:p.read_bytes() for p in (c,r,i)}
cases=[
('reviewer-tenant',r,' or principal.tenant_id!=op.tenant_id','','test_m24_reconciliation.py','helper_foreign'),
('local-status',c,"local.status!=before['status'] or ",'','test_m24_cancellation.py','drift_alone and status'),
('local-period-end',c," or local.cancel_at_period_end!=before['cancel_at_period_end']",'','test_m24_cancellation.py','drift_alone and cancel_at_period_end'),
('provider-status',c," or raw.get('status')!=before['status']",'','test_m24_cancellation.py','field_drift_alone and status'),
('provider-period-end',c," or raw.get('cancel_at_period_end') is not before['cancel_at_period_end']",'','test_m24_cancellation.py','field_drift_alone and cancel_at_period_end'),
('provider-object',c," or raw.get('object')!='subscription'",'','test_m24_cancellation.py','field_drift_alone and object'),
('provider-id',c," or raw.get('id')!=snap['subscription_id']",'','test_m24_cancellation.py','field_drift_alone and id'),
('provider-customer',c," or raw.get('customer')!=snap['customer_id']",'','test_m24_cancellation.py','field_drift_alone and customer'),
('provider-livemode',c," or raw.get('livemode') is not False",'','test_m24_cancellation.py','field_drift_alone and livemode'),
('provider-tenant',c,"if raw.get('metadata',{}).get('atlas_tenant_id')!=snap['operation']['tenant_id']:",'if False:','test_m24_cancellation.py','field_drift_alone and metadata'),
('invoice-terminal',r,"op.state in {'closed_unknown','cancelled_before_dispatch'} or ",'','test_m24_reconciliation.py','parent_terminal_alone'),
('failed-cancel-fence',i,"wa.OperationRow.state!='cancelled_before_dispatch'","wa.OperationRow.state.notin_(['cancelled_before_dispatch','failed_before_dispatch'])",'test_m24_cancellation.py','fence_all_cancel and failed_before_dispatch'),
]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case',action='append',choices=[case[0] for case in cases],help='Repeat for multiple cases; omitted means all twelve.')
parser.add_argument('--output-dir',type=Path,help='Receipt directory; default is a new private temporary directory.')
args=parser.parse_args()
output=args.output_dir or Path(tempfile.mkdtemp(prefix='m24-survivors-v2-'))
output.mkdir(parents=True,exist_ok=True)
print('receipts',str(output.resolve()),flush=True)
selected=[case for case in cases if args.case is None or case[0] in args.case]
def git_status():
 return subprocess.run(['git','status','--porcelain=v1','--untracked-files=all'],capture_output=True,text=True,check=True).stdout
baseline_product_status=subprocess.run(['git','status','--porcelain=v1','--',*[str(p) for p in base]],capture_output=True,text=True,check=True).stdout
def restored_receipt(name,p):
 actual=p.read_bytes()
 expected=hashlib.sha256(base[p]).hexdigest()
 product_status=subprocess.run(['git','status','--porcelain=v1','--',*[str(p) for p in base]],capture_output=True,text=True,check=True).stdout
 ok=all(path.read_bytes()==saved for path,saved in base.items()) and product_status==baseline_product_status
 receipt={'case':name,'file':str(p),'sha256':hashlib.sha256(actual).hexdigest(),'expected_sha256':expected,
  'restored':ok,'git_status':git_status(),'product_git_status':product_status,'baseline_product_git_status':baseline_product_status}
 (output/('RESTORED-'+name+'.json')).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
 print(json.dumps(receipt,sort_keys=True),flush=True)
 if not ok:raise RuntimeError('Restore mismatch; refusing next case: '+name)
try:
 for name,p,old,new,file,selection in selected:
  s=base[p].decode();assert s.count(old)>=1,(name,s.count(old))
  try:
   p.write_text(s.replace(old,new,1))
   result=subprocess.run([sys.executable,'-m','pytest','-q','tests/modules/'+file,'-k',selection],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=30)
   (output/('RED-gate-'+name+'.log')).write_text(result.stdout+result.stderr)
   print(name,result.returncode,result.stdout.strip().splitlines()[-1],flush=True)
   assert result.returncode==1 and 'DID NOT RAISE' in result.stdout,(name,result.stdout,result.stderr)
  finally:
   p.write_bytes(base[p])
   restored_receipt(name,p)
finally:
 for p,s in base.items():p.write_bytes(s)
