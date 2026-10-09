from pathlib import Path
import os,subprocess,sys
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
try:
 for name,p,old,new,file,selection in cases:
  s=base[p].decode();assert s.count(old)>=1,(name,s.count(old));p.write_text(s.replace(old,new,1))
  try:
   result=subprocess.run([sys.executable,'-m','pytest','-q','tests/modules/'+file,'-k',selection],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=30)
   Path('audits/rebuild-20261009/m24-slice4/RED-gate-'+name+'.log').write_text(result.stdout+result.stderr)
   print(name,result.returncode,result.stdout.strip().splitlines()[-1],flush=True)
   assert result.returncode==1 and 'DID NOT RAISE' in result.stdout,(name,result.stdout,result.stderr)
  finally:p.write_bytes(base[p])
finally:
 for p,s in base.items():p.write_bytes(s)
