"""S7.2 pins added as a test-only child. Paper simulation only; no core change."""
import importlib.util
import math
import os
import statistics
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
source = Path(os.environ.get('S72_SOURCE', ROOT / 'backend/app/modules/m20_general_cognitive_worker/s72_paper.py'))
spec = importlib.util.spec_from_file_location('s72_private_pins', source)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def packet():
    return {'bars': [{'date': '2026-10-01', 'open': 100, 'high': 110, 'low': 90, 'close': 100},
                     {'date': '2026-10-02', 'open': 100, 'high': 120, 'low': 95, 'close': 110},
                     {'date': '2026-10-03', 'open': 110, 'high': 125, 'low': 100, 'close': 121}],
            'initial_cash': 1000, 'fee_bps': 0, 'slippage_bps': 0, 'periods_per_year': 252, 'as_of': '2026-10-11'}


class Pins(unittest.TestCase):
    def refusal(self, p, code, strategy=None, detail=None):
        with self.assertRaises(m.PaperRefusal) as exc:
            m.run(p, strategy=strategy)
        self.assertEqual(exc.exception.code, code)
        if detail is not None:
            self.assertIn(detail, str(exc.exception))
        return exc.exception

    # --- exact BUY / SELL with a nonzero fee ---
    def test_buy_partial_weight_exact_with_fee(self):
        p = packet(); p['fee_bps'] = 100
        r = m.run(p, strategy=lambda h: .5)
        q = 500 / (100 * 1.005)
        t = r['trades'][0]
        self.assertEqual(t['side'], 'buy')
        self.assertAlmostEqual(t['shares'], q, places=9)
        self.assertAlmostEqual(t['fee'], q * 100 * .01, places=9)
        self.assertAlmostEqual(t['fill_price'], 100)
        self.assertEqual(t['target_weight'], .5)
        self.assertAlmostEqual(r['equity_curve'][1]['cash'], 1000 - q * 100 - q * 100 * .01, places=9)
        self.assertAlmostEqual(r['equity_curve'][1]['shares'], q, places=9)
        self.assertAlmostEqual(r['fees_paid'], sum(x['fee'] for x in r['trades']), places=9)
        self.assertGreaterEqual(r['fees_paid'], q * 100 * .01)

    def test_sell_partial_weight_exact_with_fee(self):
        p = packet(); p['fee_bps'] = 100
        r = m.run(p, strategy=lambda h: 1 if len(h) == 1 else .5)
        s1 = 1000 / 101
        self.assertEqual([t['side'] for t in r['trades']], ['buy', 'sell'])
        q = .5 * s1 / .995
        sell = r['trades'][1]
        self.assertAlmostEqual(sell['shares'], q, places=9)
        self.assertAlmostEqual(sell['fee'], q * 110 * .01, places=9)
        self.assertAlmostEqual(sell['fill_price'], 110)
        self.assertEqual(sell['signal_date'], '2026-10-02')
        cash = q * 110 - q * 110 * .01
        self.assertAlmostEqual(r['equity_curve'][2]['cash'], cash, places=9)
        self.assertAlmostEqual(r['equity_curve'][2]['shares'], s1 - q, places=9)
        self.assertAlmostEqual(r['fees_paid'], s1 * 100 * .01 + q * 110 * .01, places=9)

    def test_buy_and_sell_slippage_direction_nonzero_fee(self):
        p = packet(); p['fee_bps'] = 50; p['slippage_bps'] = 200
        r = m.run(p, strategy=lambda h: 1 if len(h) == 1 else 0)
        self.assertAlmostEqual(r['trades'][0]['fill_price'], 102)
        self.assertAlmostEqual(r['trades'][1]['fill_price'], 110 * .98)
        self.assertGreater(r['trades'][0]['fee'], 0)
        self.assertGreater(r['trades'][1]['fee'], 0)

    def test_fee_charge_equals_fill_times_quantity_times_fee(self):
        p = packet(); p['fee_bps'] = 250; p['slippage_bps'] = 100
        r = m.run(p, strategy=lambda h: 1)
        t = r['trades'][0]
        self.assertGreater(t['fee'], 0)
        self.assertAlmostEqual(t['fee'], t['shares'] * t['fill_price'] * .025, places=9)
        self.assertAlmostEqual(r['equity_curve'][1]['cash'], 0, places=6)

    # --- fee / slippage upper bound 9999 pass, 10000 refuse ---
    def test_fee_and_slippage_bounds(self):
        for key in ('fee_bps', 'slippage_bps'):
            for strategy in (None, lambda h: 1, lambda h: 1 if len(h) == 1 else 0):
                p = packet(); p[key] = 9999
                r = m.run(p, strategy=strategy)
                self.assertEqual(len(r['equity_curve']), 3)
            p = packet(); p[key] = 0; self.assertEqual(len(m.run(p)['equity_curve']), 3)
            for bad in (10000, -.0001, float('nan'), float('inf'), '1', None, True):
                p = packet(); p[key] = bad
                self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail=key)

    # --- cash bounds and positive equity ---
    def test_initial_cash_bounds(self):
        for good in (1e-9, 1e12, 1, 1234.5):
            p = packet(); p['initial_cash'] = good
            self.assertEqual(m.run(p)['equity_curve'][0]['equity'], float(good))
        for bad in (0, 5e-10, -1, 1000000000001, float('nan'), True, '1000', None):
            p = packet(); p['initial_cash'] = bad
            self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='initial_cash')

    def test_tiny_positive_equity_is_accepted_and_returns_finite(self):
        p = packet(); p['initial_cash'] = 1e-9
        r = m.run(p, strategy=lambda h: 1)
        self.assertTrue(all(x['equity'] > 0 for x in r['equity_curve']))
        self.assertEqual(r['equity_curve'][0]['equity'], 1e-9)
        self.assertTrue(math.isfinite(r['total_return']))

    def test_price_bounds(self):
        for key in ('open', 'high', 'low', 'close'):
            for bad in (0, -1, 1000000000001 * 1.0, float('nan'), '1', None):
                p = packet(); p['bars'][0][key] = bad
                self.refusal(p, 'MONEY_REFUSED_SCHEMA')
        p = {'bars': [{'date': '2026-10-01', 'open': 1e-9, 'high': 1e-9, 'low': 1e-9, 'close': 1e-9},
                      {'date': '2026-10-02', 'open': 1e12, 'high': 1e12, 'low': 1e12, 'close': 1e12}],
             'as_of': 'x'}
        self.assertEqual(len(m.run(p)['equity_curve']), 2)

    def test_ohlc_envelope_each_edge(self):
        for change in ({'low': 100.1}, {'high': 99.9}, {'open': 111}, {'close': 89}, {'open': 89}, {'close': 111}):
            p = packet(); p['bars'][0].update(change)
            self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='envelope')
        p = packet(); p['bars'][0].update(open=90, close=110, low=90, high=110)
        self.assertEqual(len(m.run(p)['equity_curve']), 3)

    # --- periods_per_year 1..10000 ---
    def test_periods_bounds_and_sharpe_scaling(self):
        for good in (1, 10000, 252):
            p = packet(); p['periods_per_year'] = good
            self.assertEqual(len(m.run(p)['equity_curve']), 3)
        for bad in (0, 10001, -1, 252.0, True, '252', None):
            p = packet(); p['periods_per_year'] = bad
            self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='periods_per_year')
        returns = [.1, .1, 90 / 121 - 1]
        base = statistics.mean(returns) / statistics.stdev(returns)
        for annual in (1, 10000):
            p = packet(); p['periods_per_year'] = annual
            p['bars'].append({'date': '2026-10-04', 'open': 121, 'high': 121, 'low': 80, 'close': 90})
            self.assertAlmostEqual(m.run(p, strategy=lambda h: 1)['sharpe'], base * math.sqrt(annual), places=9)

    # --- bars 2..10000 ---
    def test_bars_count_bounds(self):
        self.assertEqual(m.MAX_BARS, 10000)
        p = packet(); p['bars'] = p['bars'][:2]
        self.assertEqual(len(m.run(p)['equity_curve']), 2)
        p = packet(); p['bars'] = p['bars'][:1]
        self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='list of')
        start = date(2000, 1, 1)

        def bars(n, bad_first=False):
            out = [{'date': (start + timedelta(days=i)).isoformat(), 'open': 1, 'high': 1, 'low': 1, 'close': 1} for i in range(n)]
            if bad_first: out[0]['extra'] = 1
            return out
        # 10000 passes the length gate (refused later, on row content); 10001 refused at the gate
        p = packet(); p['bars'] = bars(10000, True)
        self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='exact OHLC fields required')
        p = packet(); p['bars'] = bars(10001, True)
        e = self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='list of')
        self.assertNotIn('exact OHLC', str(e))
        p = packet(); p['bars'] = tuple(packet()['bars'])
        self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='list of')

    # --- as_of 64 pass, 65 refuse, MONEY prefix, SCHEMA wrapper ---
    def test_as_of_text_bounds_and_prefix(self):
        for n in (1, 63, 64):
            p = packet(); p['as_of'] = 'a' * n
            self.assertEqual(m.run(p)['scope']['as_of'], 'a' * n)
        p = packet(); p['as_of'] = 'a' * 65
        e = self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='MONEY_REFUSED_TEXT_TOO_LONG:as_of')
        self.assertEqual(str(e), 'MONEY_REFUSED_SCHEMA: MONEY_REFUSED_TEXT_TOO_LONG:as_of')
        for bad, tag in ((None, 'BAD_TYPE'), (5, 'BAD_TYPE'), (True, 'BAD_TYPE'), ('', 'EMPTY'), ('   ', 'EMPTY'), ('a\x00b', 'CONTROL_CHARS'), ('a\nb', 'CONTROL_CHARS')):
            p = packet(); p['as_of'] = bad
            e = self.refusal(p, 'MONEY_REFUSED_SCHEMA')
            self.assertEqual(str(e), 'MONEY_REFUSED_SCHEMA: MONEY_REFUSED_%s:as_of' % tag)
        p = packet(); del p['as_of']
        self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='MONEY_REFUSED_BAD_TYPE:as_of')

    # --- Sharpe null for fewer than 2 returns ---
    def test_sharpe_null_below_two_returns_and_present_at_two(self):
        p = packet(); p['bars'] = p['bars'][:2]
        r = m.run(p, strategy=lambda h: 1)
        self.assertEqual(len(r['returns']), 1)
        self.assertIsNone(r['sharpe'])
        r = m.run(packet(), strategy=lambda h: 0 if len(h) == 1 else 1)
        self.assertEqual(len(r['returns']), 2)
        rets = r['returns']
        self.assertAlmostEqual(rets[0], 0); self.assertAlmostEqual(rets[1], .1)
        self.assertAlmostEqual(r['sharpe'], statistics.mean(rets) / statistics.stdev(rets) * math.sqrt(252), places=9)
        self.assertIsNotNone(r['sharpe'])

    # --- drawdown starts from initial peak ---
    def test_drawdown_peak_starts_at_initial_cash(self):
        p = packet()
        p['bars'] = [{'date': '2026-10-01', 'open': 100, 'high': 100, 'low': 100, 'close': 100},
                     {'date': '2026-10-02', 'open': 100, 'high': 100, 'low': 80, 'close': 80},
                     {'date': '2026-10-03', 'open': 80, 'high': 80, 'low': 60, 'close': 60}]
        r = m.run(p, strategy=lambda h: 1)
        self.assertAlmostEqual(r['max_drawdown'], .4, places=9)
        self.assertEqual(m.run(packet())['max_drawdown'], 0)
        p['bars'][1]['close'] = 100; p['bars'][1]['low'] = 100; p['bars'][2].update(open=100, high=100, low=70, close=70)
        self.assertAlmostEqual(m.run(p, strategy=lambda h: 1)['max_drawdown'], .3, places=9)

    # --- starting cash curve row ---
    def test_first_curve_row_is_starting_cash(self):
        p = packet(); p['initial_cash'] = 1234.5
        for strategy in (None, lambda h: 1):
            r = m.run(p, strategy=strategy)
            self.assertEqual(r['equity_curve'][0], {'date': '2026-10-01', 'equity': 1234.5, 'cash': 1234.5, 'shares': 0.0})
            self.assertEqual(len(r['equity_curve']), 3)
            self.assertEqual([c['date'] for c in r['equity_curve']], ['2026-10-01', '2026-10-02', '2026-10-03'])
            self.assertAlmostEqual(r['total_return'], r['equity_curve'][-1]['equity'] / 1234.5 - 1)
        self.assertAlmostEqual(m.run(p, strategy=lambda h: 1)['turnover'], 1234.5 / 1234.5)

    # --- PaperRefusal message / code ---
    def test_refusal_error_message_and_code(self):
        self.assertEqual(str(m.PaperRefusal('X_CODE')), 'X_CODE')
        e = m.PaperRefusal('X_CODE', 'why')
        self.assertEqual(str(e), 'X_CODE: why'); self.assertEqual(e.code, 'X_CODE')
        self.assertIsInstance(e, ValueError)
        e = self.refusal({'action': 'spend'}, 'MONEY_REFUSED_SPEND')
        self.assertEqual(str(e), 'MONEY_REFUSED_SPEND: paper unit cannot spend real money')
        e = self.refusal([], 'MONEY_REFUSED_SCHEMA')
        self.assertEqual(str(e), 'MONEY_REFUSED_SCHEMA: request must be dict')
        e = self.refusal({'action': 'outreach'}, 'MONEY_REFUSED_OUTREACH')
        self.assertTrue(str(e).startswith('MONEY_REFUSED_OUTREACH: MONEY_REFUSED_OUTREACH'))
        e = self.refusal({'action': 'nonsense'}, 'MONEY_REFUSED_UNKNOWN')
        self.assertIn('nonsense', str(e))
        for bars in (None, []):
            self.refusal({'bars': bars}, 'MONEY_REFUSED_NODATA')

    def test_guarantee_profit_exactly_false_and_policy_unknown_code(self):
        p = packet(); p['guarantee_profit'] = False
        self.assertEqual(len(m.run(p)['equity_curve']), 3)
        for bad in (0, None, 'false', 1):
            p = packet(); p['guarantee_profit'] = bad
            self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='exactly false')
        with patch.object(m.policy, 'classify', return_value={'decision': 'refuse'}):
            self.refusal(packet(), 'POLICY_REFUSED_UNKNOWN')
        with patch.object(m.policy, 'classify', return_value={'decision': 'needs_approval', 'code': 'X_Y'}):
            self.refusal(packet(), 'X_Y')

    def test_bar_row_shape_and_date(self):
        p = packet(); p['bars'][0]['extra'] = 1
        self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='exact OHLC fields required')
        p = packet(); del p['bars'][0]['open']
        self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='exact OHLC fields required')
        p = packet(); p['bars'][0] = [1, 2]
        self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='exact OHLC fields required')
        for bad in ('2026-1-01', '20261001', 20261001, '2026-10-011', '2026-13-01'):
            p = packet(); p['bars'][0]['date'] = bad
            self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='YYYY-MM-DD')

    def test_strategy_result_bounds_and_callable(self):
        for good in (0, 1, 0.0, 1.0, .5):
            self.assertEqual(len(m.run(packet(), strategy=lambda h, g=good: g)['equity_curve']), 3)
        for bad in (-1e-9, 1.0000001, None, [1], float('inf')):
            self.refusal(packet(), 'MONEY_REFUSED_STRATEGY', lambda h, b=bad: b, detail='long-only target')
        self.refusal(packet(), 'MONEY_REFUSED_STRATEGY', 5, detail='trusted callable')

        def boom(h): raise RuntimeError('x')
        self.refusal(packet(), 'MONEY_REFUSED_STRATEGY', boom, detail='RuntimeError')

    def test_history_index_and_slice_boundaries(self):
        h = m.PrefixHistory(packet()['bars'][:2])
        self.assertEqual(h[1]['close'], 110); self.assertEqual(h[-2]['close'], 100)
        self.assertFalse(h.peeked)
        self.assertEqual(len(h[0:2]), 2); self.assertEqual(len(h[:]), 2); self.assertEqual(len(h[1:]), 1)
        self.assertFalse(h.peeked)
        for key in (2, -3):
            h2 = m.PrefixHistory(packet()['bars'][:2])
            with self.assertRaises(IndexError): h2[key]
            self.assertTrue(h2.peeked)
        h3 = m.PrefixHistory(packet()['bars'][:2])
        with self.assertRaises(IndexError): h3[2:]
        self.assertTrue(h3.peeked)
        h4 = m.PrefixHistory(packet()['bars'][:2])
        with self.assertRaises(IndexError): h4[:3]
        self.assertTrue(h4.peeked)
        with self.assertRaises(TypeError): m.PrefixHistory(packet()['bars'][:2])['a']
        with self.assertRaises(TypeError): m.PrefixHistory(packet()['bars'][:2])[1.0]

    # --- forecast check on both collections ---
    def test_forecast_requires_both_collections_either_direction(self):
        for only in ('forecast_predictions', 'forecast_resolutions'):
            p = packet(); p[only] = []
            self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='both forecast collections required')
        calls = []

        def scorer(a, b, **kw): calls.append((a, b, kw)); return {'ok': 1}
        p = packet(); p['forecast_predictions'] = [1]; p['forecast_resolutions'] = [2]; p['forecast_bins'] = 4; p['forecast_calibrated'] = False
        with patch.object(m, '_load_j1', return_value=scorer):
            r = m.run(p)
        self.assertEqual(calls, [([1], [2], {'bins': 4, 'calibrated': False})])
        self.assertEqual(r['forecast_scoring'], {'ok': 1})
        self.assertIsNone(m.run(packet())['forecast_scoring'])

    def test_unknown_field_and_report_shape(self):
        r = m.run(packet())
        self.assertEqual(r['unit'], 'S7.2'); self.assertIn('not financial advice', r['disclaimer'])
        self.assertEqual(r['scope']['data_source'], 'supplied OHLC fixture and trusted deterministic strategy callable')
        self.assertEqual(r['scope']['as_of'], '2026-10-11')
        self.assertIn('real money', r['scope']['not_implemented'])
        self.assertIn('Not a security sandbox', r['strategy_limit'])

    # --- characterization pins for clamp / zero-quantity paths (values from the unchanged core) ---
    def _fx(self, opens, ws, fee, slip):
        p = {'bars': [{'date': '2026-10-%02d' % (i + 1), 'open': o, 'high': o * 2, 'low': o / 2, 'close': o} for i, o in enumerate(opens)],
             'as_of': 'x', 'fee_bps': fee, 'slippage_bps': slip}
        return m.run(p, strategy=lambda h: ws[len(h) - 1])

    def test_clamped_quantity_paths_golden(self):
        r = self._fx([200, 50, 200], [.75, 1, 0], 5000, 2000)
        self.assertEqual([t['side'] for t in r['trades']], ['buy', 'buy'])
        self.assertAlmostEqual(r['trades'][1]['shares'], 0.5050505050505049, places=9)
        self.assertAlmostEqual(r['equity_curve'][2]['cash'], 0.0, places=6)
        r = self._fx([50, 200, 150, 100], [1, .75, .75, .5], 5000, 2000)
        self.assertEqual([t['side'] for t in r['trades']], ['buy', 'sell'])
        self.assertAlmostEqual(r['trades'][1]['shares'], 1.111111111111111, places=9)
        self.assertAlmostEqual(r['equity_curve'][3]['cash'], 66.66666666666666, places=6)
        r = self._fx([100, 200, 50, 100], [0, .75, .25, 0], 100, 9000)
        self.assertEqual([t['side'] for t in r['trades']], ['buy'])
        self.assertAlmostEqual(r['trades'][0]['shares'], 7.835967088938226, places=9)
        self.assertEqual(len(r['trades']), 1)

    def test_no_trade_at_exact_delta_threshold(self):
        p = packet(); p['initial_cash'] = 1e-9
        self.assertEqual(m.run(p, strategy=lambda h: 1)['trades'], [])

    # --- defaults ---
    def test_defaults_initial_cash_fee_slippage_periods(self):
        p = packet()
        for k in ('initial_cash', 'fee_bps', 'slippage_bps', 'periods_per_year'): del p[k]
        p['bars'].append({'date': '2026-10-04', 'open': 121, 'high': 121, 'low': 80, 'close': 90})
        r = m.run(p, strategy=lambda h: 1)
        self.assertEqual([c['equity'] for c in r['equity_curve']][:3], [1000, 1100, 1210])
        self.assertEqual(r['trades'][0]['fee'], 0)
        self.assertEqual(r['trades'][0]['fill_price'], 100)
        rets = [.1, .1, 90 / 121 - 1]
        self.assertAlmostEqual(r['sharpe'], statistics.mean(rets) / statistics.stdev(rets) * math.sqrt(252), places=9)

    def test_all_request_fields_accepted_together(self):
        p = packet(); p.update(action='simulate', guarantee_profit=False, forecast_predictions=[], forecast_resolutions=[], forecast_bins=3, forecast_calibrated=False)
        seen = []
        def scorer(a, b, **kw): seen.append(kw); return {}
        with patch.object(m, '_load_j1', return_value=scorer): m.run(p)
        self.assertEqual(seen, [{'bins': 3, 'calibrated': False}])
        self.assertEqual(set(m.FIELDS) - set(p), set())

    def test_policy_descriptor_exact(self):
        got = []
        def spy(d): got.append(d); return {'decision': 'allow'}
        with patch.object(m.policy, 'classify', side_effect=spy): m.run(packet())
        self.assertEqual(got, [{'class': 'offline', 'module_id': 20, 'tenant_id': 's72-supplied-fixture', 'action_type': 'analyze', 'payload': {}}])

    def test_unhashable_bar_row_refused_not_crashed(self):
        p = packet(); p['bars'][0] = [[]]
        self.refusal(p, 'MONEY_REFUSED_SCHEMA', detail='exact OHLC fields required')


if __name__ == '__main__':
    unittest.main()
