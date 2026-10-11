"""Named mutations for the repair delta; no authority or live execution."""
from pathlib import Path
import json,subprocess,sys
R=Path(__file__).resolve().parents[2];P=R/'backend/app/modules/c35/waiver_drafts.py'
cmd=[sys.executable,'-m','pytest','tests/modules/test_c35_waiver_drafts_s43.py','tests/modules/test_c35_waiver_drafts_s43_delta.py','-q']
s=P.read_text();results=[]
assert subprocess.run(cmd,cwd=R,capture_output=True).returncode==0
mutants=[
('year_zero','year < 1 or ','') ,
('ascii_control_regression','unicodedata.category(c) in policy.FORBIDDEN_CATEGORIES','ord(c) < 32 or ord(c) == 127'),
('controls_disabled','not any(unicodedata.category(c) in policy.FORBIDDEN_CATEGORIES for c in value)','True'),
('recipient_invalid_flag','return None, True, True','return None, True, False'),
('strict_recipient', 'if row["needs"]:', 'if False:'),
('year_minimum_offbyone','year < 1 or ','year < 2 or '),
]
for name,old,new in mutants:
 assert old in s,name
 try:
  P.write_text(s.replace(old,new,1))
  for p in P.parent.glob('__pycache__/waiver_drafts*.pyc'):p.unlink()
  done=subprocess.run(cmd,cwd=R,capture_output=True,text=True,timeout=15)
  output=done.stdout+done.stderr
  (R/'audits/s43-delta'/('mutant-'+name+'.log')).write_text('\n'.join(x.rstrip()for x in output.splitlines())+'\n')
  results.append({'name':name,'outcome':'SURVIVED' if done.returncode==0 else 'assertion/error','exit_code':done.returncode})
 finally:
  P.write_text(s)
  for p in P.parent.glob('__pycache__/waiver_drafts*.pyc'):p.unlink()
print(json.dumps({'mutants':len(results),'killed':sum(x['exit_code']!=0 for x in results),'results':results},indent=2))
