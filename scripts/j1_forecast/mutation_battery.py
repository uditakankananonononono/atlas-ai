"""Finite targeted J1 guard/calculation mutants, behavioral kills only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'backend/app/modules/m20_general_cognitive_worker/j1_forecast.py'
MUTANTS={
'policy_removed':("    guard('analyze', 'j1-offline-scorer')",'    pass'),
'record_policy_removed':("        guard('record', self.tenant_id, policy_guard=self.policy_guard)",'        pass'),
'policy_refuse_allowed':("decision.get('decision') != 'allow'",'False'),
'horizon_guard_removed':("    if row.get('horizon') is None or (isinstance(row.get('horizon'), str) and not row['horizon'].strip()):",'    if False:'),
'horizon_equal_allowed':('if horizon <= made_at:', 'if horizon < made_at:'),
'resolution_early_allowed':("if resolved_at < timestamp(predictions[ident]['horizon'], 'horizon'):",'if False:'),
'resolution_at_deadline_denied':("if resolved_at < timestamp(predictions[ident]['horizon'], 'horizon'):","if resolved_at <= timestamp(predictions[ident]['horizon'], 'horizon'):"),
'probability_lower_removed':('not 0 <= probability <= 1','not probability <= 1'),
'probability_upper_removed':('not 0 <= probability <= 1','not 0 <= probability'),
'probability_bool_allowed':('type(probability) not in (int, float)', 'not isinstance(probability, (int, float))'),
'outcome_bool_guard_removed':("    if type(row['outcome']) is not bool:",'    if False:'),
'unscored_allowed':('    if calibrated and (not ps or len(ys) != len(ps)):','    if False:'),
'brier_wrong':('(p - y) ** 2','abs(p - y)'),
'sharpness_wrong':('(p - .5) ** 2','(p - .4) ** 2'),
'bin_last_wrong':('min(int(p * bins), bins - 1)','int(p * bins)'),
'bin_rate_wrong':('math.fsum(y for p, y in values)','math.fsum(p for p, y in values)'),
'small_sample_ge':('len(scored) < MIN_CALIBRATION_SAMPLE','len(scored) <= MIN_CALIBRATION_SAMPLE'),
'future_skill_claim':("scope['future_skill_proven'] = False","scope['future_skill_proven'] = True"),
'bins_bool_allowed':('type(bins) is not int','not isinstance(bins,int)'),
'bins_limit_wrong':('1 <= bins <= 100','1 <= bins <= 99'),
'capacity_ge':('len(predictions) > MAX_PREDICTIONS','len(predictions) >= MAX_PREDICTIONS'),
'duplicate_prediction_allowed':('        if ident in ps:', '        if False:'),
'duplicate_resolution_allowed':('        if ident in ys:', '        if False:'),
'reference_guard_removed':('    if ident not in predictions:','    if False:'),
'symlink_allowed':(' | os.O_NOFOLLOW',''),
'partial_line_allowed':("        if raw and not raw.endswith(b'\\n'):",'        if False:'),
'hash_guard_removed':("or event['sha256'] != actual",''),
'sequence_guard_removed':("event['seq'] != index",'False'),
'tenant_guard_removed':("                if event['data']['tenant_id'] != self.tenant_id:",'                if False:'),
'conflict_allowed':("                if row != ys[prediction_id]:",'                if False:'),
'id_wrong':("row['prediction_id'] = digest({k: v for k, v in row.items() if k != 'prediction_id'})","row['prediction_id'] = '0' * 64"),
}

def main():
 results=[];source=SOURCE.read_text()
 with tempfile.TemporaryDirectory(prefix='j1-mutants-') as td:
  for name,(old,new) in MUTANTS.items():
   assert old in source,name
   path=Path(td)/(name+'.py');path.write_text(source.replace(old,new,1))
   proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests/j1_forecast','-p','test_forecast.py'],cwd=ROOT,env=dict(os.environ,J1_SOURCE=str(path)),capture_output=True,text=True,timeout=30)
   killed=proc.returncode!=0 and '_FailedTest' not in proc.stderr and 'SyntaxError' not in proc.stderr and 'Ran ' in proc.stderr
   results.append({'mutant':name,'killed':killed,'tail':proc.stderr[-1200:]})
 out={'total':len(results),'killed':sum(r['killed'] for r in results),'results':results};print(json.dumps(out,indent=2))
 return 0 if all(r['killed'] for r in results) else 1

if __name__=='__main__':raise SystemExit(main())
