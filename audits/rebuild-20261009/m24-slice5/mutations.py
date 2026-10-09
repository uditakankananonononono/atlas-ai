from pathlib import Path
import os,subprocess,sys
os.chdir(Path(__file__).resolve().parents[3])
p=Path('backend/app/modules/m24_billing/inbox.py');original=p.read_bytes()
cases=[
('unsigned-admission',"self.quarantine(event.id,hashlib.sha256(raw).hexdigest(),'unsigned-diagnostic')","self.admit(VerifiedEvent('acct_fixture',event.model_dump(),hashlib.sha256(raw).hexdigest()))",'unsigned_same_id'),
('digest-conflict',"elif row.digest!=event.raw_digest:",'elif False:','changed_digest'),
('payment-status'," or obj.get('payment_status')!='paid'",'','single_binding_violation and unpaid'),
('deadline',"if op.dispatch_not_after and row.created>int(_aware(op.dispatch_not_after).timestamp()):",'if False:','single_binding_violation and deadline'),
('amount'," or obj['amount_total']!=int(op.result['amount_total'])",'','single_binding_violation and amount'),
('tenant',"if field in md and md[field]!=binding.tenant_id:",'if False:','object_binding_refuses and metadata'),
('customer'," or binding.customer_id!=obj.get('customer')",'','object_binding_refuses and customer'),
('stale',"if row.created<binding.version:",'if False:','older_and_equal'),
('equal-time',"elif row.created==binding.version and binding.event_digest!=row.digest:",'elif False:','older_and_equal'),
('test-event',"data.get('livemode') is not False or ",'','envelope_binding and livemode'),
('version'," or data.get('api_version')!=API_VERSION",'','envelope_binding and api_version'),
('account',"if data.get('account')!=self.connected_account:",'if False:','envelope_binding and account'),
('applied-marker',"row.state='applied';row.failure=None","row.state='pending';row.failure=None",'admit_pending_then_atomic'),
('payload-digest',"if row.payload_digest!=hashlib.sha256(json.dumps(row.payload,sort_keys=True,separators=(',',':')).encode()).hexdigest():",'if False:','stored_payload_only'),
('rollback-atomic',"self._apply(db,row,obj,binding,local);db.flush();hook('inside-apply')","self._apply(db,row,obj,binding,local);db.commit();hook('inside-apply')",'apply_transaction_failure'),
]
try:
 for name,old,new,selection in cases:
  text=original.decode();assert old in text,name
  p.write_text(text.replace(old,new,1))
  try:
   r=subprocess.run([sys.executable,'-m','pytest','-q','tests/modules/test_m24_verified_inbox.py','-k',selection],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=30)
   Path('audits/rebuild-20261009/m24-slice5/RED-mutation-'+name+'.log').write_text(r.stdout+r.stderr)
   print(name,r.returncode,r.stdout.strip().splitlines()[-1],flush=True)
   assert r.returncode==1,(name,r.stdout,r.stderr)
  finally:p.write_bytes(original)
finally:p.write_bytes(original)
