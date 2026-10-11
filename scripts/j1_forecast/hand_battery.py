"""Frozen cohort scoring plus real ledger exercise, no market feeds."""
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/j1_forecast'))
from test_forecast import m,pred,resolved

probs=[0,.1,.25,.5,.5,.75,.9,1]
outcomes=[False,False,True,False,True,True,True,True]
ps=[pred(prediction_id='p'+str(i),probability=p) for i,p in enumerate(probs)]
ys=[resolved(prediction_id='p'+str(i),outcome=y) for i,y in enumerate(outcomes)]
r=m.score_predictions(ps,ys,bins=4)
assert abs(r['brier_score']-.143125)<1e-12
assert abs(r['sharpness']-.118125)<1e-12
assert r['calibration_label']=='insufficient_sample'
with tempfile.TemporaryDirectory(prefix='j1-hand-') as td:
 ledger=m.ForecastLedger(Path(td)/'ledger.jsonl',tenant_id='hand-fixture')
 p=pred();del p['prediction_id'];row=ledger.append_prediction(**p)
 try:ledger.report();raise AssertionError('unresolved calibrated report allowed')
 except m.ForecastRefusal as exc:assert exc.code=='INTEL_REFUSED_UNSCORED'
 ledger.resolve(row['prediction_id'],outcome=True,resolved_at='2026-10-12T00:00:00Z')
 actual=m.ForecastLedger(Path(td)/'ledger.jsonl',tenant_id='hand-fixture').report()
 assert abs(actual['brier_score']-.04)<1e-12
print(json.dumps({'frozen_probabilities':probs,'frozen_outcomes':outcomes,'measured_report':r,
                  'ledger_reloaded_brier':actual['brier_score'],'unscored_refusal_verified':True},indent=2))
