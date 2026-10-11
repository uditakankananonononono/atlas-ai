"""J1 pin pack 2: tests-only pins for audit findings #19/#26, #69, #101, #103, #118/#140.

Loads the module like test_forecast.py (J1_SOURCE override runs a mutant).
No runtime change. Same limits as pack 1: hash chain is not adversarial auth.
"""
import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
SOURCE = Path(os.environ.get('J1_SOURCE', ROOT / 'backend/app/modules/m20_general_cognitive_worker/j1_forecast.py'))
spec = importlib.util.spec_from_file_location('j1_pins2', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

T0, T1, T2 = '2026-10-11T00:00:00Z', '2026-10-12T00:00:00Z', '2026-10-12T01:00:00Z'


def pred(**kw):
    row = dict(prediction_id='p1', claim='Event occurs', probability=0.8, horizon=T1,
               source='supplied fixture', made_at=T0)
    row.update(kw)
    return row


def res(**kw):
    row = dict(prediction_id='p1', outcome=True, resolved_at=T2)
    row.update(kw)
    return row


def code_of(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except m.ForecastRefusal as exc:
        return exc.code, str(exc)
    return None, ''


def rehash(event):
    event['sha256'] = m.digest({k: event[k] for k in ('seq', 'prev', 'kind', 'data')})
    return event


def write_events(path, events):
    Path(path).write_text(''.join(m.canonical(e) + '\n' for e in events))


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'ledger.jsonl'
        self.ledger = m.ForecastLedger(self.path, tenant_id='tenant-a')
        p = self.ledger.append_prediction(claim='c', probability=.8, horizon=T1, source='s', made_at=T0)
        self.ledger.resolve(p['prediction_id'], outcome=True, resolved_at=T2)
        self.good = [json.loads(line) for line in self.path.read_text().splitlines()]  # header, prediction, resolution

    def tearDown(self):
        self.tmp.cleanup()

    def report(self):
        return code_of(self.ledger.report, calibrated=False)


class Chain(LedgerCase):
    def test_spliced_prev_with_rehashed_event_is_integrity(self):  # #103
        for idx in (1, 2):
            for bad_prev in ('0' * 64, 'f' * 64, self.good[0]['sha256'] if idx == 2 else self.good[1]['sha256']):
                ev = copy.deepcopy(self.good)
                ev[idx]['prev'] = bad_prev
                rehash(ev[idx])  # the event's own hash is valid, only the link is wrong
                if idx == 1 and bad_prev == self.good[0]['sha256']:
                    continue  # that is the true link
                write_events(self.path, ev)
                self.assertEqual(self.report()[0], 'INTEL_REFUSED_INTEGRITY', (idx, bad_prev[:4]))
        # the spliced event alone is wrong: every later event rehashed in order is still refused
        ev = copy.deepcopy(self.good)
        ev[2]['prev'] = '0' * 64
        rehash(ev[2])
        write_events(self.path, ev)
        self.assertEqual(self.report()[0], 'INTEL_REFUSED_INTEGRITY')

    def test_genesis_prev_must_be_zero_hash(self):
        ev = copy.deepcopy(self.good)
        ev[0]['prev'] = '1' * 64
        rehash(ev[0])
        write_events(self.path, ev)
        self.assertEqual(self.report()[0], 'INTEL_REFUSED_INTEGRITY')

    def test_seq_true_float_or_wrong_int_with_rehash_is_integrity(self):  # #101
        for idx, bad in ((1, 8), (1, 2), (2, 1), (0, 1), (2, 3), (1, True), (1, 1.0), (0, False), (0, 0.0), (2, 2.0), (1, '1'), (1, None), (1, -1)):
            ev = copy.deepcopy(self.good)
            ev[idx]['seq'] = bad
            rehash(ev[idx])
            write_events(self.path, ev)
            self.assertEqual(self.report()[0], 'INTEL_REFUSED_INTEGRITY', (idx, bad))

    def test_valid_ledger_still_loads(self):
        write_events(self.path, self.good)
        self.assertEqual(self.ledger.report()['coverage'], {'predictions': 1, 'resolved': 1, 'unresolved': 0})


class NonFinite(LedgerCase):
    def test_nan_and_infinity_lines_are_integrity_not_finite_json(self):  # #118/#140
        header = m.canonical(self.good[0])
        for token in ('NaN', 'Infinity', '-Infinity'):
            raw = '{"seq":1,"prev":"%s","kind":"prediction","data":{"probability":%s},"sha256":"x"}' % (
                self.good[0]['sha256'], token)
            self.path.write_text(header + '\n' + raw + '\n')
            code, msg = self.report()
            self.assertEqual(code, 'INTEL_REFUSED_INTEGRITY', token)
            self.assertIn('event is not finite JSON', msg, token)
            before = self.path.read_bytes()
            self.assertEqual(code_of(self.ledger.append_prediction, claim='n', probability=.5, horizon=T1,
                                     source='s', made_at=T0)[0], 'INTEL_REFUSED_INTEGRITY')
            self.assertEqual(self.path.read_bytes(), before)  # refused, never repaired

    def test_non_finite_in_header_and_nested_values(self):
        for raw in ('{"seq":0,"prev":"%s","kind":"header","data":{"version":1,"tenant_id":NaN},"sha256":"x"}' % ('0' * 64),
                    '{"seq":NaN,"prev":"p","kind":"header","data":{},"sha256":"x"}',
                    '{"seq":0,"prev":"p","kind":"header","data":{"a":[1,[Infinity]]},"sha256":"x"}'):
            self.path.write_text(raw + '\n')
            code, msg = self.report()
            self.assertEqual(code, 'INTEL_REFUSED_INTEGRITY', raw[:40])
            self.assertIn('event is not finite JSON', msg)


class ScorerSchema(unittest.TestCase):
    def schema(self, predictions, resolutions, **kw):
        return code_of(m.score_predictions, predictions, resolutions, **kw)[0]

    def test_non_dict_resolution_rows_are_schema_not_typeerror(self):  # #19/#26
        for bad in (5, None, 'x', 'prediction_id', [], ['prediction_id'], 1.5, True, ('a',), {'prediction_id'}):
            self.assertEqual(self.schema([pred()], [bad]), 'INTEL_REFUSED_SCHEMA', repr(bad))
        self.assertEqual(self.schema([pred()], [res(), 5]), 'INTEL_REFUSED_SCHEMA')

    def test_non_list_resolution_and_prediction_collections_are_schema(self):
        for bad in (None, 'x', 5, {'a': 1}, (res(),), {res()['prediction_id']}, True):
            self.assertEqual(self.schema([pred()], bad), 'INTEL_REFUSED_SCHEMA', repr(bad))
            self.assertEqual(self.schema(bad, [res()]), 'INTEL_REFUSED_SCHEMA', repr(bad))
            self.assertEqual(self.schema(bad, bad, calibrated=False), 'INTEL_REFUSED_SCHEMA', repr(bad))

    def test_unhashable_or_wrong_typed_ids_are_schema(self):
        for bad in ([], {}, ['p1'], 5, None):
            self.assertEqual(self.schema([pred()], [res(prediction_id=bad)]), 'INTEL_REFUSED_SCHEMA', repr(bad))
            self.assertEqual(self.schema([pred(prediction_id=bad)], [], calibrated=False), 'INTEL_REFUSED_SCHEMA', repr(bad))


class PredictionCapInCheck(LedgerCase):
    def build(self, n):
        events, prev = [], '0' * 64
        entries = [('header', self.good[0]['data'])]
        for i in range(n):
            row = m.validate_prediction(pred(claim='claim %d' % i))
            row['prediction_id'] = m.digest({k: v for k, v in row.items() if k != 'prediction_id'})
            entries.append(('prediction', row))
        for i, (kind, data) in enumerate(entries):
            body = {'seq': i, 'prev': prev, 'kind': kind, 'data': data}
            ev = dict(body, sha256=m.digest(body))
            events.append(ev)
            prev = ev['sha256']
        write_events(self.path, events)

    def test_over_cap_ledger_refused_limit_inside_check_both_sides(self):  # #69
        self.assertLess(m.MAX_PREDICTIONS + 2, m.MAX_EVENTS)  # the event cap cannot be what trips this
        self.build(m.MAX_PREDICTIONS)
        self.assertEqual(self.ledger.report(calibrated=False)['coverage']['predictions'], m.MAX_PREDICTIONS)
        self.build(m.MAX_PREDICTIONS + 1)
        code, msg = self.report()
        self.assertEqual(code, 'INTEL_REFUSED_LIMIT')
        self.assertIn('prediction cap exceeded', msg)
        before = self.path.read_bytes()
        self.assertEqual(code_of(self.ledger.append_prediction, claim='x', probability=.5, horizon=T1,
                                 source='s', made_at=T0)[0], 'INTEL_REFUSED_LIMIT')
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
