from pathlib import Path
import os,subprocess,sys
os.chdir(Path(__file__).resolve().parents[3]);p=Path('backend/app/modules/m24_billing/inbox.py');original=p.read_bytes()
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
try:
 for name,old,new,selection in cases:
  s=original.decode();assert s.count(old)==1,(name,s.count(old))
  try:
   p.write_text(s.replace(old,new,1))
   r=subprocess.run([sys.executable,'-m','pytest','-q','tests/modules/test_m24_verified_inbox.py','-k',selection],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=30)
   Path('audits/rebuild-20261009/m24-slice5/RED-gate-'+name+'.log').write_text(r.stdout+r.stderr)
   print(name,r.returncode,r.stdout.strip().splitlines()[-1],flush=True)
   assert r.returncode==1 and 'DID NOT RAISE' in r.stdout,(name,r.stdout,r.stderr)
  finally:
   p.write_bytes(original);assert p.read_bytes()==original
finally:p.write_bytes(original)
