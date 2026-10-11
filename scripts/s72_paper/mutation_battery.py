import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'backend/app/modules/m20_general_cognitive_worker/s72_paper.py'
MUTANTS={
'leak_postcheck_removed':("        if history.peeked:refuse('LOOKAHEAD','future history access attempted')",'        pass'),
'leak_flag_removed':("if key>=len(self) or key< -len(self):self.peeked=True",'if key>=len(self) or key< -len(self):self.peeked=False'),
'future_included':('bars[:index]','bars[:index+1]'),
'same_close_execution':("open_price=bar['open']","open_price=bar['close']"),
'fee_removed':("'fee_bps',0,9999)/10000","'fee_bps',0,9999)*0"),
'slippage_removed':("'slippage_bps',0,9999)/10000","'slippage_bps',0,9999)*0"),
'sale_charge_removed':('cash+=quantity*fill-charge','cash+=quantity*fill'),
'drawdown_wrong':('(peak-point[\'equity\'])/peak','(peak-point[\'equity\'])/initial'),
'sharpe_population':('statistics.stdev(returns)','statistics.pstdev(returns)'),
'turnover_wrong':('notional/initial','notional/(initial*2)'),
'guarantee_allowed':("if request.get('guarantee_profit') is True:refuse('GUARANTEE','no profit guarantees')",'if False:pass'),
'trade_code_wrong':("refuse('TRADE','no order-routing exists')","refuse('SCHEMA','no order-routing exists')"),
'spend_code_wrong':("refuse('SPEND','paper unit cannot spend real money')","refuse('SCHEMA','paper unit cannot spend real money')"),
'nodata_code_wrong':("refuse('NODATA','supplied OHLC bars required')","refuse('SCHEMA','supplied OHLC bars required')"),
'policy_removed':("if decision.get('decision')!='allow':",'if False:'),
'determinism_removed':("if outputs[0]!=outputs[1]:",'if False:'),
'weight_bool_allowed':('type(result) not in (int,float)','not isinstance(result,(int,float))'),
'ohlc_guard_removed':("if not bar['low']<=min(bar['open'],bar['close'])<=max(bar['open'],bar['close'])<=bar['high']:",'if False:'),
'dates_duplicates_allowed':('day<=previous','day<previous'),
'j1_params_wrong':("calibrated=request.get('forecast_calibrated',True)","calibrated=False"),
'disclaimer_removed':("'disclaimer':DISCLAIMER","'disclaimer':''"),
}
results=[];source=SOURCE.read_text()
with tempfile.TemporaryDirectory() as td:
 for name,(old,new) in MUTANTS.items():
  assert old in source,name
  p=Path(td)/(name+'.py');p.write_text(source.replace(old,new,1))
  r=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests/s72_paper','-p','test_paper.py'],cwd=ROOT,env=dict(os.environ,S72_SOURCE=str(p)),capture_output=True,text=True,timeout=30)
  killed=r.returncode!=0 and '_FailedTest' not in r.stderr and 'SyntaxError' not in r.stderr
  results.append({'mutant':name,'outcome':'killed' if killed else 'SURVIVED','tail':r.stderr[-800:]})
print(json.dumps({'total':len(results),'killed':sum(r['outcome']=='killed' for r in results),'results':results},indent=2))
raise SystemExit(0 if all(r['outcome']=='killed' for r in results) else 1)
