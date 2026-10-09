from pathlib import Path
import os,subprocess,sys
os.chdir(Path(__file__).resolve().parents[3]);p=Path('backend/app/modules/m24_billing/generation.py');original=p.read_bytes()
cases=[
('max-caps',"inp>p['max_input_tokens'] or out>p['max_output_tokens'] or cost>p['max_micro_usd'] or ",'','consistent_cost_over'),
('settle-fence',"row.fence!=fence or row.state not in {'dispatching','outcome_unknown'}","row.state not in {'dispatching','outcome_unknown'}",'wrong_fence and settle'),
('entry-fence'," or row.fence!=fence or _aware(row.lease_until)"," or _aware(row.lease_until)",'wrong_fence and before_entry'),
('unknown-fence',"if row.fence!=fence or row.state!='dispatching':","if row.state!='dispatching':",'wrong_fence and unknown'),
('regen-state'," or old.state not in {'dispatching','outcome_unknown','succeeded_late'}",'','ineligible_target_state'),
('regen-budget'," or old.budget_id!=budget.id",'','cross_owner_or_budget and budget'),
('regen-tenant'," or old.tenant_id!=tenant_id",'','cross_owner_or_budget and tenant'),
('response-price-id'," or raw['price_schedule_id']!=p['price_schedule']['id']",'','response_price_schedule_id_alone'),
('request-price'," or price!=budget.price_schedule",'','matches_budget and price'),
('request-account'," or payload['account']!=budget.account",'','matches_budget and account'),
('binding-hash',"if row.binding_hash!=digest({'id':row.id,'approval':row.approval_id,'request_hash':row.request_hash,'request':row.request}):",'if False:','exact_permit_alone and binding_hash'),
('permit-id'," or permit.effect_id!='m24-generation:'+row.id",'','exact_permit_alone and permit'),
('entry-pending',"if attempt is None or attempt.state!='charged-pending':raise wa.DispatchRefused('generation pending charge missing')",'if False:raise wa.DispatchRefused(\'generation pending charge missing\')','before_entry_pending_charge_alone'),
('stored-digest'," or row.output['digest']!=output_digest",'','digest_checks_independent and stored-digest'),
('usage-digest'," or digest(row.output['usage'])!=output_digest",'','digest_checks_independent and usage-digest'),
('budget-owner-cas',"BudgetRow.tenant_id==tenant_id,BudgetRow.account==p['account'],",'','owner_cas_isolated'),
]
try:
 for name,old,new,selection in cases:
  s=original.decode();assert s.count(old)==1,(name,s.count(old))
  try:
   p.write_text(s.replace(old,new,1))
   r=subprocess.run([sys.executable,'-m','pytest','-q','tests/modules/test_m24_generation_budget.py','-k',selection],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=30)
   Path('audits/rebuild-20261009/m24-slice6/RED-gate-'+name+'.log').write_text(r.stdout+r.stderr)
   print(name,r.returncode,r.stdout.strip().splitlines()[-1],flush=True);assert r.returncode==1 and 'DID NOT RAISE' in r.stdout,(name,r.stdout,r.stderr)
  finally:p.write_bytes(original)
finally:p.write_bytes(original)
