from pathlib import Path
import subprocess,os
p=Path('backend/app/modules/m24_billing/checkout_dispatcher.py');original=p.read_text()
mutations=[
 ('bypass-readiness','        wa.require_dispatch_ready()\n        snapshot=', '        snapshot=', 'test_real_readiness_still_refuses_forged_row_zero_calls[sqlite]'),
 ('reclaim-unknown',"wa.OperationRow.state=='prepared',wa.OperationRow.fence.is_(None),", "wa.OperationRow.state.in_(['prepared','outcome_unknown']),", 'test_attempt_committed_before_entry_is_never_reclaimed[sqlite]'),
 ('approval-key',"        op.provider_key=op.id+':checkout'", "        op.provider_key=op.approval_id", 'test_exact_snapshot_and_step_key_before_provider[sqlite]'),
 ('unknown-safe',"state='outcome_unknown' if entered else 'failed_before_dispatch'", "state='failed_before_dispatch'", 'test_post_entry_failures_stay_unknown_no_replay_even_pruned[sqlite-timeout]'),
 ('lose-late',"op.state='succeeded_late' if op.state=='outcome_unknown' or _aware(op.lease_until)<=now else 'succeeded'", "op.state='succeeded'", 'test_late_result_recorded_no_stale_fence_or_replay[sqlite]'),
]
try:
 for name,old,new,node in mutations:
  assert old in original,name
  p.write_text(original.replace(old,new,1))
  result=subprocess.run(['/tmp/atlas-memo3-venv/bin/python','-m','pytest','-q','tests/modules/test_m24_checkout_dispatcher.py::'+node],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=15)
  Path('audits/rebuild-20261009/m24-slice2/RED-mutation-'+name+'.log').write_text(result.stdout+result.stderr)
  print(name,result.returncode)
  if result.returncode==0:raise RuntimeError('mutation survived '+name)
finally:p.write_text(original)
