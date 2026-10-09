from pathlib import Path
import subprocess,os
p=Path('backend/app/modules/m24_billing/invoice_dispatcher.py');s=p.read_text()
items=[('item-no-dependency',"if draft is None or draft.state!='succeeded' or not draft.result:raise wa.DispatchRefused('invoice draft outcome not committed')",'if False:pass','test_uncommitted_or_unknown_draft_never_prepares_item[sqlite]'),('item-no-attachment',"'invoice':invoice_id", "'invoice':'in_wrong'",'test_item_snapshot_binds_committed_draft_id_not_pending_customer_item[sqlite]'),('final-no-total'," or raw['total']!=p['amount_cents']",'','test_final_total_or_incomplete_binding_holds_without_compensation[sqlite-total]'),('final-incomplete-lines'," or lines.get('has_more') is not False",'','test_final_total_or_incomplete_binding_holds_without_compensation[sqlite-lines]'),('postentry-safe',"state='outcome_unknown' if entered else 'failed_before_dispatch'", "state='failed_before_dispatch'",'test_step_accepted_timeout_stays_unknown_no_repeat[sqlite-draft-invoice]'),('readback-no-fence',"if committed['step']['fence']!=fence or committed['step']['state']!='dispatching':",'if False:','test_invoice_claim_readback_mismatch_no_adapter[sqlite]')]
try:
 for name,old,new,node in items:
  assert old in s;p.write_text(s.replace(old,new,1))
  r=subprocess.run(['/tmp/atlas-memo3-venv/bin/python','-m','pytest','-q','tests/modules/test_m24_invoice_dispatcher.py::'+node],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=15)
  Path('audits/rebuild-20261009/m24-slice3/RED-mutation-'+name+'.log').write_text(r.stdout+r.stderr)
  print(name,r.returncode)
finally:p.write_text(s)
