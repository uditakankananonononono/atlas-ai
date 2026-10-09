from pathlib import Path
import os,subprocess,sys
os.chdir(Path(__file__).resolve().parents[3]);p=Path('backend/app/modules/m24_billing/generation.py');original=p.read_bytes()
cases=[
('balance-cas',"BudgetRow.available_micro_usd>=cost,",'','each_insufficient_balance and available_micro_usd'),
('input-cas',"BudgetRow.available_input>=inp,",'','each_insufficient_balance and available_input'),
('output-cas',"BudgetRow.available_output>=out,",'','each_insufficient_balance and available_output'),
('attempt-cas',"BudgetRow.available_attempts>=1",'True','each_insufficient_balance and available_attempts'),
('atomic-reserve',"hook('after-balance-update')","db.commit();hook('after-balance-update')",'after_balance_update_failure'),
('charged-pending',"attempt.state='charged-pending'","attempt.state='reserved'",'uncertain_charge_never'),
('model-response-account',"raw['account']!=p['account'] or ",'','unverified_or_changed_usage and account'),
('usage-verification'," or raw['usage_verified'] is not True",'','unverified_or_changed_usage and usage_verified'),
('exact-cost'," or cost!=inp*p['price_schedule']['input_micro_usd_per_token']+out*p['price_schedule']['output_micro_usd_per_token']",'','unverified_or_changed_usage and micro_usd'),
('readback',"if committed['fence']!=fence or committed['state']!='dispatching':",'if False:','adapter_binding_and_readback'),
('settlement-atomic',"db.flush();hook('before-output-commit')","db.flush();db.commit();hook('before-output-commit')",'output_commit_failure'),
('immutable-reserve',"if attempt is None or (attempt.reserved_input,attempt.reserved_output,attempt.reserved_micro_usd)!=(inp,out,cost):",'if False:','reserved_binding_tamper'),
('sql-barrier',"GenerationRow.fence.is_(None),barrier)","GenerationRow.fence.is_(None))",'sql_cutover_barrier_alone'),
('durable-only',"if row.state!='succeeded' or not row.output or ","if not row.output or ",'foreign_output_version_digest_or_late'),
]
try:
 for name,old,new,selection in cases:
  s=original.decode();assert s.count(old)==1,(name,s.count(old))
  try:
   p.write_text(s.replace(old,new,1))
   r=subprocess.run([sys.executable,'-m','pytest','-q','tests/modules/test_m24_generation_budget.py','-k',selection],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=30)
   Path('audits/rebuild-20261009/m24-slice6/RED-mutation-'+name+'.log').write_text(r.stdout+r.stderr)
   print(name,r.returncode,r.stdout.strip().splitlines()[-1],flush=True);assert r.returncode==1,(name,r.stdout,r.stderr)
  finally:p.write_bytes(original)
finally:p.write_bytes(original)
