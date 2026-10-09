from pathlib import Path
import subprocess,os
p=Path('backend/app/modules/m24_billing/checkout_dispatcher.py');s=p.read_text()
items=[('readback',"if committed['fence']!=fence or committed['state']!='dispatching':",'if False:','test_claim_readback_difference_never_enters_adapter[sqlite-fence]'),('lease'," or _aware(op.lease_until)<=now",'','test_lease_expires_between_claim_and_entry_zero_network[sqlite]'),('deadline-claim',"if deadline.tzinfo is None or deadline<=now:",'if deadline.tzinfo is None:','test_commitment_deadline_elapsed_refused_at_both_boundaries[sqlite-claim]'),('deadline-entry',"if deadline.tzinfo is None or deadline<=now:",'if deadline.tzinfo is None:','test_commitment_deadline_elapsed_refused_at_both_boundaries[sqlite-entry]'),('unknown-safe',"if state=='failed_before_dispatch' and op.state!='dispatching':",'if False:','test_uncertain_cannot_become_failed_before_dispatch[sqlite]')]
try:
 for name,old,new,node in items:
  assert old in s;p.write_text(s.replace(old,new,1))
  r=subprocess.run(['/tmp/atlas-memo3-venv/bin/python','-m','pytest','-q','tests/modules/test_m24_checkout_dispatcher.py::'+node],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=15)
  Path('audits/rebuild-20261009/m24-slice2/RED-gate-gap-'+name+'.log').write_text(r.stdout+r.stderr)
  print(name,r.returncode);assert r.returncode==1
finally:p.write_text(s)
