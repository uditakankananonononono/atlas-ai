import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
source=Path(os.environ.get('S72_SOURCE',ROOT/'backend/app/modules/m20_general_cognitive_worker/s72_paper.py'))
spec=importlib.util.spec_from_file_location('s72_private',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def packet():
    return {'bars':[{'date':'2026-10-01','open':100,'high':110,'low':90,'close':100},
                    {'date':'2026-10-02','open':100,'high':120,'low':95,'close':110},
                    {'date':'2026-10-03','open':110,'high':125,'low':100,'close':121}],
            'initial_cash':1000,'fee_bps':0,'slippage_bps':0,'periods_per_year':252,'as_of':'2026-10-11'}

class PaperTests(unittest.TestCase):
    def refusal(self,p,code,strategy=None):
        with self.assertRaises(m.PaperRefusal) as exc:m.run(p,strategy=strategy)
        self.assertEqual(exc.exception.code,code)
    def test_buy_hold_known_fixture(self):
        r=m.run(packet(),strategy=lambda history:1)
        self.assertEqual([x['equity'] for x in r['equity_curve']],[1000,1100,1210])
        self.assertAlmostEqual(r['total_return'],.21)
        self.assertAlmostEqual(r['turnover'],1)
        self.assertEqual(r['max_drawdown'],0)
        self.assertIsNone(r['sharpe'])
        self.assertIn('not financial advice, simulated, past results',r['disclaimer'])
    def test_default_cash(self):
        r=m.run(packet());self.assertEqual(r['total_return'],0);self.assertEqual(r['trades'],[])
    def test_fee_slippage_exact(self):
        p=packet();p['fee_bps']=100;p['slippage_bps']=100
        r=m.run(p,strategy=lambda h:1)
        shares=1000/(100*1.01*1.01)
        self.assertAlmostEqual(r['trades'][0]['shares'],shares)
        self.assertAlmostEqual(r['trades'][0]['fee'],shares*101*.01)
        self.assertAlmostEqual(r['equity_curve'][-1]['equity'],shares*121)
    def test_next_open_no_same_close_execution(self):
        p=packet();p['bars'][1].update(open=105,low=95)
        r=m.run(p,strategy=lambda h:1)
        self.assertEqual(r['trades'][0]['date'],'2026-10-02')
        self.assertEqual(r['trades'][0]['fill_price'],105)
        self.assertEqual(r['trades'][0]['signal_date'],'2026-10-01')
    def test_future_peek_refused(self):
        def peek(h):return 1 if h[len(h)]['close']>100 else 0
        self.refusal(packet(),'MONEY_REFUSED_LOOKAHEAD',peek)
    def test_swallowed_peek_still_refused(self):
        def peek(h):
            try:h[len(h)]
            except IndexError:pass
            return 1
        self.refusal(packet(),'MONEY_REFUSED_LOOKAHEAD',peek)
    def test_immutable_history(self):
        def mutate(h):h[0]['close']=999;return 1
        self.refusal(packet(),'MONEY_REFUSED_STRATEGY',mutate)
    def test_nondeterministic_strategy_refused(self):
        state=[]
        def alternating(h):state.append(1);return len(state)%2
        self.refusal(packet(),'MONEY_REFUSED_STRATEGY',alternating)
    def test_effects_guarantee_nodata(self):
        for p,code in [({'action':'trade'},'MONEY_REFUSED_TRADE'),({'action':'order_route'},'MONEY_REFUSED_TRADE'),
                       ({'action':'spend'},'MONEY_REFUSED_SPEND'),({'guarantee_profit':True},'MONEY_REFUSED_GUARANTEE'),
                       ({'bars':[]},'MONEY_REFUSED_NODATA')]:self.refusal(p,code)
    def test_invalid_ohlc(self):
        for change in [{'low':120},{'open':0},{'close':True},{'high':float('inf')},{'date':'bad'}]:
            p=packet();p['bars'][0].update(change);self.refusal(p,'MONEY_REFUSED_SCHEMA')
    def test_duplicates_unsorted(self):
        p=packet();p['bars'][1]['date']=p['bars'][0]['date'];self.refusal(p,'MONEY_REFUSED_SCHEMA')
        p=packet();p['bars'].reverse();self.refusal(p,'MONEY_REFUSED_SCHEMA')
    def test_fraction_limit(self):
        for weight in [-.1,1.1,True,'1',float('nan')]:self.refusal(packet(),'MONEY_REFUSED_STRATEGY',lambda h:weight)
    def test_numeric_config_bounds(self):
        for key,value in [('initial_cash',0),('fee_bps',-1),('fee_bps',10001),('slippage_bps',10000),('periods_per_year',0),('periods_per_year',True)]:
            p=packet();p[key]=value;self.refusal(p,'MONEY_REFUSED_SCHEMA')
    def test_drawdown_sharpe(self):
        p=packet();p['bars'].append({'date':'2026-10-04','open':121,'high':121,'low':80,'close':90})
        r=m.run(p,strategy=lambda h:1)
        self.assertAlmostEqual(r['max_drawdown'],(1210-900)/1210)
        import math,statistics
        returns=[.1,.1,90/121-1]
        expected=statistics.mean(returns)/statistics.stdev(returns)*math.sqrt(252)
        self.assertAlmostEqual(r['sharpe'],expected)
    def test_sale_fees_turnover(self):
        p=packet();p['fee_bps']=100
        r=m.run(p,strategy=lambda h:1 if len(h)==1 else 0)
        shares=1000/101
        self.assertEqual([t['side'] for t in r['trades']],['buy','sell'])
        self.assertAlmostEqual(r['equity_curve'][-1]['equity'],shares*110*.99)
        self.assertAlmostEqual(r['turnover'],shares*(100+110)/1000)
    def test_prefix_and_input_unchanged(self):
        import copy
        p=packet();old=copy.deepcopy(p);seen=[]
        def strategy(h):seen.append(len(h));return .5
        first=m.run(p,strategy=strategy)
        self.assertEqual(seen,[1,1,2,2]);self.assertEqual(p,old)
        self.assertEqual(first,m.run(p,strategy=lambda h:.5))
    def test_policy_import_called(self):
        with patch.object(m.policy,'classify',return_value={'decision':'refuse','code':'POLICY_REFUSED_TEST'}):
            self.refusal(packet(),'POLICY_REFUSED_TEST')
    def test_dependency_fail_closed(self):
        p=packet();p['forecast_predictions']=[];p['forecast_resolutions']=[]
        with patch.object(m,'_load_j1',side_effect=ImportError('not landed')):
            self.refusal(p,'MONEY_REFUSED_DEPENDENCY')
    def test_delegates_single_scorer(self):
        p=packet();p['forecast_predictions']=[{'fixture':1}];p['forecast_resolutions']=[]
        calls=[]
        def scorer(predictions,resolutions,**kw):calls.append((predictions,resolutions,kw));return {'delegated':True}
        with patch.object(m,'_load_j1',return_value=scorer):r=m.run(p)
        self.assertEqual(r['forecast_scoring'],{'delegated':True})
        self.assertEqual(calls,[(p['forecast_predictions'],[],{'bins':10,'calibrated':True})])
    def test_unknown_schema_refused(self):
        p=packet();p['broker']='anything';self.refusal(p,'MONEY_REFUSED_SCHEMA')


    def test_slice_peek(self):
        def peek(h):
            try:h[:len(h)+1]
            except IndexError:pass
            return 0
        self.refusal(packet(),'MONEY_REFUSED_LOOKAHEAD',peek)
    def test_short_input_and_non_callable(self):
        p=packet();p['bars']=p['bars'][:1];self.refusal(p,'MONEY_REFUSED_SCHEMA')
        self.refusal(packet(),'MONEY_REFUSED_STRATEGY',False)
    def test_both_forecast_fields_required(self):
        p=packet();p['forecast_predictions']=[];self.refusal(p,'MONEY_REFUSED_SCHEMA')
    def test_cap_boundary(self):
        with patch.object(m,'MAX_BARS',3):self.assertEqual(len(m.run(packet())['equity_curve']),3)
        with patch.object(m,'MAX_BARS',2):self.refusal(packet(),'MONEY_REFUSED_SCHEMA')
    def test_unknown_effects_policy(self):
        for action in ['outreach','fakeacct','autopost','scrape','unknown']:
            p=packet();p['action']=action
            self.refusal(p,'MONEY_REFUSED_'+('UNKNOWN' if action=='unknown' else action.upper()))
    def test_cannot_mutate_prior_bar(self):
        history=m.PrefixHistory(packet()['bars'][:1])
        with self.assertRaises(TypeError):history[0]['close']=0
        self.assertEqual(history[-1]['close'],100)

if __name__=='__main__':unittest.main()
