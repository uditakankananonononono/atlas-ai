import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tests/s72_paper'))
from test_paper import m,packet
p=packet();r=m.run(p,strategy=lambda h:1)
assert [x['equity'] for x in r['equity_curve']]==[1000,1100,1210]
p['fee_bps']=100;p['slippage_bps']=100;cost=m.run(p,strategy=lambda h:1)
assert cost['total_return']<r['total_return']
def peek(h):
 try:h[len(h)]
 except IndexError:pass
 return 1
try:m.run(packet(),strategy=peek);raise AssertionError('peeking allowed')
except m.PaperRefusal as exc:assert exc.code=='MONEY_REFUSED_LOOKAHEAD'
print(json.dumps({'baseline':r,'cost_run':cost,'swallowed_peek_refused':True},indent=2))
