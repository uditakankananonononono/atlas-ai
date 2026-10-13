"""J1 pin pack: tests-only pins for gaps the mutation audit reproduced.

Loads the module like test_forecast.py (J1_SOURCE override lets a mutant be
run against these pins). Does NOT pin audit-proven equivalents: tzinfo/utcoffset
redundancy, seek(0) vs seek(END), LOCK_UN/os.close, allow_nan.
Carried limits (see contract): hash chain is not adversarial auth, partial
append refuses with no auto-repair, POSIX only, caller outcomes unverified.
"""
import copy
import importlib.util
import json
import multiprocessing
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
SOURCE = Path(os.environ.get('J1_SOURCE', ROOT / 'backend/app/modules/m20_general_cognitive_worker/j1_forecast.py'))
spec = importlib.util.spec_from_file_location('j1_pins', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

T0 = '2026-10-11T00:00:00Z'
T1 = '2026-10-12T00:00:00Z'
T2 = '2026-10-12T01:00:00Z'


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
    """Run fn and return the ForecastRefusal code. Anything else fails the test."""
    try:
        fn(*a, **kw)
    except m.ForecastRefusal as exc:
        return exc.code
    return None


def rechain(events):
    """Recompute seq/prev/sha256 over (kind, data) pairs: a tamper that keeps the chain valid."""
    out, prev = [], '0' * 64
    for i, (kind, data) in enumerate(events):
        body = {'seq': i, 'prev': prev, 'kind': kind, 'data': data}
        ev = dict(body, sha256=m.digest(body))
        out.append(ev)
        prev = ev['sha256']
    return out


def write_events(path, events):
    Path(path).write_text(''.join(m.canonical(e) + '\n' for e in events))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'ledger.jsonl'
        self.ledger = m.ForecastLedger(self.path, tenant_id='tenant-a')

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, **kw):
        p = pred(**kw)
        del p['prediction_id']
        return self.ledger.append_prediction(**p)

    def events(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def pairs(self):
        return [(e['kind'], copy.deepcopy(e['data'])) for e in self.events()]


# 1 ------------------------------------------------------------------------
class TimeTypes(Base):
    def test_non_string_timestamps_are_refused_with_time_code(self):
        for bad in (5, 5.5, b'2026-10-12T00:00:00Z', ['x'], {'a': 1}, True):
            self.assertEqual(code_of(m.score_predictions, [pred(horizon=bad)], [], calibrated=False),
                             'INTEL_REFUSED_TIME', repr(bad))
            self.assertEqual(code_of(m.score_predictions, [pred(made_at=bad)], [], calibrated=False),
                             'INTEL_REFUSED_TIME', repr(bad))
            self.assertEqual(code_of(self.ledger.append_prediction, claim='c', probability=.5, horizon=bad,
                                     source='s', made_at=T0), 'INTEL_REFUSED_TIME', repr(bad))
        self.assertEqual(code_of(m.score_predictions, [pred()], [res(resolved_at=5)]), 'INTEL_REFUSED_TIME')

    def test_horizon_zero_is_time_not_nohorizon(self):
        self.assertEqual(code_of(m.score_predictions, [pred(horizon=0)], [], calibrated=False), 'INTEL_REFUSED_TIME')


# 2 + 3 --------------------------------------------------------------------
class TamperedLedger(Base):
    def setUp(self):
        super().setUp()
        self.p = self.add()
        self.ledger.resolve(self.p['prediction_id'], outcome=True, resolved_at=T2)

    def report_code(self):
        return code_of(self.ledger.report, calibrated=False)

    def test_event_missing_any_key_is_integrity_not_keyerror(self):
        base = self.events()
        for idx in (0, 1):
            for key in ('seq', 'prev', 'kind', 'data', 'sha256'):
                ev = copy.deepcopy(base)
                del ev[idx][key]
                write_events(self.path, ev)
                self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY', (idx, key))
            ev = copy.deepcopy(base)
            ev[idx]['extra'] = 1
            write_events(self.path, ev)
            self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY', (idx, 'extra'))

    def test_non_object_event_is_integrity(self):
        for bad in ([1], 'x', None, 7):
            self.path.write_text(json.dumps(bad) + '\n')
            self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY', repr(bad))

    def test_header_shape_each_clause_with_valid_chain(self):
        good = self.pairs()
        header = good[0][1]
        variants = [
            {k: v for k, v in header.items() if k != 'version'},
            {k: v for k, v in header.items() if k != 'tenant_id'},
            dict(header, extra=1),
            'not-a-dict', None, [1],
            dict(header, version='1'), dict(header, version=1.0), dict(header, version=True),
        ]
        for data in variants:
            write_events(self.path, rechain([('header', data)] + good[1:]))
            self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY', repr(data))
        write_events(self.path, rechain([('prediction', header)] + good[1:]))
        self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY')

    def test_duplicate_prediction_event_with_recomputed_chain_is_integrity(self):
        good = self.pairs()
        write_events(self.path, rechain(good[:2] + [good[1]] + good[2:]))
        self.assertEqual(code_of(self.ledger.report), 'INTEL_REFUSED_INTEGRITY')
        self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY')
        self.assertEqual(code_of(self.add), 'INTEL_REFUSED_INTEGRITY')

    def test_duplicate_prediction_event_at_tail_is_integrity(self):
        good = self.pairs()
        write_events(self.path, rechain(good + [good[1]]))
        self.assertEqual(code_of(self.ledger.report), 'INTEL_REFUSED_INTEGRITY')

    def test_unknown_event_kind_is_integrity(self):
        good = self.pairs()
        for kind in ('tamper', 'Prediction', 'header', '', 5):
            write_events(self.path, rechain(good + [(kind, good[1][1])]))
            self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY', repr(kind))

    def test_invalid_ledger_json_is_integrity(self):
        for raw in (b'{not json}\n', b'\xff\xfe\n', b'{"a":1}\n{\n', b'NaN\n'):
            self.path.write_bytes(raw)
            self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY', raw)
        self.path.write_bytes(b'')
        self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY')  # missing header

    def test_prediction_id_must_bind_content(self):
        good = self.pairs()
        data = dict(good[1][1], prediction_id='forged')
        write_events(self.path, rechain([good[0], ('prediction', data)]))
        self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY')

    def test_duplicate_resolution_with_recomputed_chain_is_integrity(self):
        good = self.pairs()
        write_events(self.path, rechain(good + [good[2]]))
        self.assertEqual(self.report_code(), 'INTEL_REFUSED_INTEGRITY')


# 4 + 5 --------------------------------------------------------------------
class PolicyGuard(Base):
    def run_guard(self, fn):
        with tempfile.TemporaryDirectory() as d:
            return code_of(m.ForecastLedger, Path(d) / 'l.jsonl', tenant_id='t', policy_guard=fn)

    def test_injected_guard_is_used_instead_of_policy_classify(self):
        calls = []

        def allow(desc):
            calls.append(desc)
            return {'decision': 'allow'}
        default_calls = []

        def default(desc):
            default_calls.append(desc)
            return {'decision': 'allow'}
        with patch.object(m.policy, 'classify', default):
            led = m.ForecastLedger(Path(self.tmp.name) / 'inj.jsonl', tenant_id='tenant-z', policy_guard=allow)
            led.append_prediction(claim='c', probability=.5, horizon=T1, source='s', made_at=T0)
            led.report(calibrated=False)
        self.assertEqual([c['action_type'] for c in calls], ['record', 'record', 'read'])
        # the ledger never falls back to the default classifier; only the shared scorer inside report() does
        self.assertEqual([(c['action_type'], c['tenant_id']) for c in default_calls], [('analyze', 'j1-offline-scorer')])
        for c in calls:
            self.assertEqual(c['class'], 'offline')
            self.assertEqual(c['module_id'], 20)
            self.assertEqual(c['tenant_id'], 'tenant-z')
            self.assertEqual(c['payload'], {})

    def test_denied_code_propagates_from_injected_guard(self):
        self.assertEqual(self.run_guard(lambda d: {'decision': 'refuse', 'code': 'POLICY_REFUSED_INJECTED'}),
                         'POLICY_REFUSED_INJECTED')
        led_path = Path(self.tmp.name) / 'g.jsonl'
        deny = {'on': False}

        def toggle(d):
            return {'decision': 'refuse', 'code': 'POLICY_REFUSED_LATER'} if deny['on'] else {'decision': 'allow'}
        led = m.ForecastLedger(led_path, tenant_id='t', policy_guard=toggle)
        deny['on'] = True
        before = led_path.read_bytes()
        self.assertEqual(code_of(led.append_prediction, claim='c', probability=.5, horizon=T1, source='s', made_at=T0),
                         'POLICY_REFUSED_LATER')
        self.assertEqual(code_of(led.resolve, 'x', outcome=True, resolved_at=T2), 'POLICY_REFUSED_LATER')
        self.assertEqual(code_of(led.report), 'POLICY_REFUSED_LATER')
        self.assertEqual(led_path.read_bytes(), before)

    def test_unknown_fallback_when_no_code_or_non_dict(self):
        for decision in ({'decision': 'refuse'}, {'decision': 'refuse', 'code': None}, {'decision': 'refuse', 'code': ''},
                         {'decision': 'needs_approval', 'code': None}, {'decision': 'ALLOW'}, {}, None, 'allow', True):
            self.assertEqual(self.run_guard(lambda d, x=decision: x), 'POLICY_REFUSED_UNKNOWN', repr(decision))
        self.assertEqual(self.run_guard(lambda d: {'decision': 'needs_approval', 'code': 'POLICY_REFUSED_X'}),
                         'POLICY_REFUSED_X')

    def test_classifier_valueerror_maps_to_first_colon_segment(self):
        def boom(d):
            raise ValueError('POLICY_REFUSED_A:middle:last')
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(m.ForecastRefusal) as cm:
                m.ForecastLedger(Path(d) / 'l.jsonl', tenant_id='t', policy_guard=boom)
        self.assertEqual(cm.exception.code, 'POLICY_REFUSED_A')
        self.assertIn('middle:last', str(cm.exception))
        self.assertIsInstance(cm.exception.__cause__, ValueError)

        def nocolon(d):
            raise ValueError('POLICY_REFUSED_B')
        self.assertEqual(self.run_guard(nocolon), 'POLICY_REFUSED_B')

    def test_scorer_uses_policy_classify_with_offline_analyze_descriptor(self):
        seen = []

        def fake(d):
            seen.append(d)
            return {'decision': 'allow'}
        with patch.object(m.policy, 'classify', fake):
            m.score_predictions([], [], calibrated=False)
        self.assertEqual(seen, [{'class': 'offline', 'module_id': 20, 'tenant_id': 'j1-offline-scorer',
                                 'action_type': 'analyze', 'payload': {}}])

    def test_real_policy_accepts_the_descriptor_for_every_action(self):
        for action in ('analyze', 'record', 'read'):
            m.guard(action, 'tenant-a')  # no raise


# 6 ------------------------------------------------------------------------
class GoldenDigest(Base):
    CLAIM = 'Événement «Ω» 日本語 \u2603'
    GOLDEN = '5e59b322d6c8404b2dd8981ab0feb44c70c88600bbbced237c1d37ca5ccad121'

    def test_prediction_id_golden_vector(self):
        p = self.add(claim=self.CLAIM, probability=0.25)
        body = {'claim': self.CLAIM, 'horizon': T1, 'made_at': T0, 'probability': 0.25, 'source': 'supplied fixture'}
        wire = ('{"claim":"%s","horizon":"%s","made_at":"%s","probability":0.25,"source":"supplied fixture"}'
                % (self.CLAIM, T1, T0))
        self.assertEqual(m.canonical(body), wire)  # sorted keys, tight separators, raw UTF-8
        import hashlib
        self.assertEqual(hashlib.sha256(wire.encode('utf-8')).hexdigest(), p['prediction_id'])
        self.assertEqual(p['prediction_id'], self.GOLDEN)

    def test_canonical_form_pins(self):
        self.assertEqual(m.canonical({'b': 1, 'a': 'é'}), '{"a":"é","b":1}')  # no \u escapes, sorted
        self.assertNotIn('\\u', m.canonical({'a': '日本'}))
        self.assertEqual(m.canonical({'z': [1, 2], 'a': None}), '{"a":null,"z":[1,2]}')
        self.assertEqual(m.digest({'a': 1}), '015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862')
        for bad in (float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                m.canonical({'a': bad})


# 7 ------------------------------------------------------------------------
class Bins(Base):
    def test_default_bins_is_ten_with_upper_bound(self):
        r = m.score_predictions([pred(probability=.55)], [res()])
        bins = r['reliability_bins']
        self.assertEqual(len(bins), 10)
        for i, b in enumerate(bins):
            self.assertEqual((b['index'], b['lower'], b['upper']), (i, i / 10, (i + 1) / 10))
        self.assertEqual(bins[5]['count'], 1)
        self.assertEqual(bins[9]['upper'], 1.0)

    def test_report_default_bins_and_explicit_bins(self):
        p = self.add(probability=.55)
        self.ledger.resolve(p['prediction_id'], outcome=True, resolved_at=T2)
        self.assertEqual(len(self.ledger.report()['reliability_bins']), 10)
        r = self.ledger.report(bins=4)
        self.assertEqual([b['upper'] for b in r['reliability_bins']], [.25, .5, .75, 1.0])
        self.assertEqual(r['reliability_bins'][2]['count'], 1)

    def test_bins_bounds_each_side(self):
        for ok in (1, 100):
            self.assertEqual(len(m.score_predictions([], [], bins=ok, calibrated=False)['reliability_bins']), ok)
        for bad in (0, 101, -1, 2.0, True, '10', None):
            self.assertEqual(code_of(m.score_predictions, [], [], bins=bad, calibrated=False), 'INTEL_REFUSED_SCHEMA',
                             repr(bad))
        for bad in (1, 0, 'true', None):
            self.assertEqual(code_of(m.score_predictions, [], [], calibrated=bad), 'INTEL_REFUSED_SCHEMA', repr(bad))


# 8 ------------------------------------------------------------------------
class Caps(Base):
    def test_constants(self):
        self.assertEqual((m.MAX_EVENTS, m.MAX_BYTES, m.MAX_PREDICTIONS, m.MAX_TEXT, m.MIN_CALIBRATION_SAMPLE),
                         (20001, 16000000, 10000, 4096, 20))
        self.assertEqual(m.MAX_EVENTS, m.MAX_PREDICTIONS * 2 + 1)  # header + prediction + resolution each

    def test_score_prediction_and_resolution_caps_both_sides(self):
        with patch.object(m, 'MAX_PREDICTIONS', 3):
            ps = [pred(prediction_id='p%d' % i) for i in range(3)]
            ys = [res(prediction_id='p%d' % i) for i in range(3)]
            self.assertEqual(m.score_predictions(ps, ys)['scored_n'], 3)
            self.assertEqual(code_of(m.score_predictions, ps + [pred(prediction_id='p3')], ys, calibrated=False),
                             'INTEL_REFUSED_LIMIT')
            self.assertEqual(code_of(m.score_predictions, ps, ys + [res(prediction_id='p0')], calibrated=False),
                             'INTEL_REFUSED_LIMIT')
            self.assertEqual(code_of(m.score_predictions, ps, 'x', calibrated=False), 'INTEL_REFUSED_SCHEMA')
            self.assertEqual(code_of(m.score_predictions, tuple(ps), [], calibrated=False), 'INTEL_REFUSED_SCHEMA')

    def test_event_cap_on_load_both_sides(self):
        self.add()
        raw = self.path.read_bytes()  # header + 1 prediction = 2 events
        with patch.object(m, 'MAX_EVENTS', 2):
            self.assertIsNotNone(self.ledger.report(calibrated=False))
        with patch.object(m, 'MAX_EVENTS', 1):
            self.assertEqual(code_of(self.ledger.report, calibrated=False), 'INTEL_REFUSED_LIMIT')
        self.assertEqual(self.path.read_bytes(), raw)

    def test_event_cap_on_append_both_sides(self):
        with patch.object(m, 'MAX_EVENTS', 2):
            self.add()  # 1 event present -> second allowed
            before = self.path.read_bytes()
            self.assertEqual(code_of(self.add, claim='other'), 'INTEL_REFUSED_LIMIT')  # 2 events -> refused
            self.assertEqual(self.path.read_bytes(), before)

    def test_byte_cap_on_load_both_sides(self):
        self.add()
        size = self.path.stat().st_size
        with patch.object(m, 'MAX_BYTES', size):
            self.assertIsNotNone(self.ledger.report(calibrated=False))  # exactly at cap loads
        with patch.object(m, 'MAX_BYTES', size - 1):
            self.assertEqual(code_of(self.ledger.report, calibrated=False), 'INTEL_REFUSED_LIMIT')

    def test_byte_cap_on_append_both_sides(self):
        self.add()
        before = self.path.read_bytes()
        probe = Path(self.tmp.name) / 'probe.jsonl'
        other = m.ForecastLedger(probe, tenant_id='tenant-a')
        other.append_prediction(claim='other', probability=.8, horizon=T1, source='supplied fixture', made_at=T0)
        need = probe.stat().st_size  # same header + one 'other' prediction
        base = len(before) - len(m.canonical(self.events()[1]).encode()) - 1  # header bytes
        line = need - base
        with patch.object(m, 'MAX_BYTES', len(before) + line - 1):
            self.assertEqual(code_of(self.add, claim='other'), 'INTEL_REFUSED_LIMIT')
            self.assertEqual(self.path.read_bytes(), before)
        with patch.object(m, 'MAX_BYTES', len(before) + line):
            self.add(claim='other')  # lands exactly on the cap
        self.assertEqual(self.path.stat().st_size, len(before) + line)

    def test_ledger_prediction_cap_both_sides(self):
        with patch.object(m, 'MAX_PREDICTIONS', 2):
            self.add(claim='a')
            self.add(claim='b')  # at cap is allowed
            self.assertEqual(code_of(self.add, claim='c'), 'INTEL_REFUSED_LIMIT')
            self.assertEqual(self.add(claim='a')['claim'], 'a')  # idempotent replay still fine
        with patch.object(m, 'MAX_PREDICTIONS', 1):  # existing 2 now exceed cap
            self.assertEqual(code_of(self.ledger.report, calibrated=False), 'INTEL_REFUSED_LIMIT')

    def test_timestamp_length_boundary_63_64_65(self):
        def stamp(n):
            return '2026-10-11T00:00:00.' + '0' * (n - 21) + 'Z'
        for n in (63, 64):
            s = stamp(n)
            self.assertEqual(len(s), n)
            try:
                m.timestamp(s, 'made_at')
            except m.ForecastRefusal as exc:  # parser may reject long fractions; the length guard must not
                self.assertEqual(exc.code, 'INTEL_REFUSED_TIME')
                self.assertNotIn('timezone-aware ISO text', str(exc))
        s = stamp(65)
        self.assertEqual(len(s), 65)
        with self.assertRaises(m.ForecastRefusal) as cm:
            m.timestamp(s, 'made_at')
        self.assertEqual(cm.exception.code, 'INTEL_REFUSED_TIME')
        self.assertIn('timezone-aware ISO text', str(cm.exception))
        self.assertEqual(m.timestamp('2026-10-11T00:00:00Z', 'x').isoformat(), '2026-10-11T00:00:00+00:00')

    def test_text_length_boundary(self):
        ok = 'x' * m.MAX_TEXT
        self.assertEqual(m.text(ok, 'claim'), ok)
        self.assertEqual(code_of(m.text, ok + 'x', 'claim'), 'INTEL_REFUSED_SCHEMA')


# 9 ------------------------------------------------------------------------
class RefusalCodes(Base):
    def test_exact_codes_per_path(self):
        cases = [
            ('INTEL_REFUSED_TIME', m.score_predictions, ([pred(horizon=T0)], []), {'calibrated': False}),
            ('INTEL_REFUSED_TIME', m.score_predictions, ([pred(horizon='2026-10-12T00:00:00')], []), {'calibrated': False}),
            ('INTEL_REFUSED_TIME', m.score_predictions, ([pred(horizon='nope')], []), {'calibrated': False}),
            ('INTEL_REFUSED_TIME', m.score_predictions, ([pred()], [res(resolved_at='2026-10-11T23:59:59Z')]), {}),
            ('INTEL_REFUSED_SCHEMA', m.score_predictions, ([pred(probability=2)], []), {'calibrated': False}),
            ('INTEL_REFUSED_SCHEMA', m.score_predictions, ([pred(extra=1)], []), {'calibrated': False}),
            ('INTEL_REFUSED_SCHEMA', m.score_predictions, (['x'], []), {'calibrated': False}),
            ('INTEL_REFUSED_SCHEMA', m.score_predictions, ([pred()], [res(outcome=1)]), {}),
            ('INTEL_REFUSED_SCHEMA', m.score_predictions, ([pred()], [{'prediction_id': 'p1'}]), {}),
            ('INTEL_REFUSED_NOHORIZON', m.score_predictions, ([pred(horizon='  ')], []), {'calibrated': False}),
            ('INTEL_REFUSED_REFERENCE', m.score_predictions, ([pred()], [res(prediction_id='zz')]), {}),
            ('INTEL_REFUSED_DUPLICATE', m.score_predictions, ([pred(), pred()], []), {'calibrated': False}),
            ('INTEL_REFUSED_DUPLICATE', m.score_predictions, ([pred()], [res(), res()]), {}),
            ('INTEL_REFUSED_UNSCORED', m.score_predictions, ([pred()], []), {}),
            ('INTEL_REFUSED_SCHEMA', m.text, ('x' * 5000, 'claim'), {}),
        ]
        for code, fn, args, kw in cases:
            self.assertEqual(code_of(fn, *args, **kw), code, (code, repr(args)[:80]))

    def test_ledger_path_tenant_conflict_reference_codes(self):
        p = self.add()
        self.ledger.resolve(p['prediction_id'], outcome=True, resolved_at=T2)
        self.assertEqual(code_of(m.ForecastLedger, self.path, tenant_id='tenant-b'), 'INTEL_REFUSED_TENANT')
        self.assertEqual(code_of(self.ledger.resolve, p['prediction_id'], outcome=False, resolved_at=T2),
                         'INTEL_REFUSED_CONFLICT')
        self.assertEqual(code_of(self.ledger.resolve, 'nope', outcome=True, resolved_at=T2), 'INTEL_REFUSED_REFERENCE')
        self.assertEqual(code_of(self.ledger.resolve, p['prediction_id'], outcome=True, resolved_at='2026-10-11T00:00:00Z'),
                         'INTEL_REFUSED_TIME')  # validation runs before the immutability check
        d = Path(self.tmp.name)
        self.assertEqual(code_of(m.ForecastLedger, d, tenant_id='t'), 'INTEL_REFUSED_PATH')  # a directory
        (d / 'real').write_text('')
        (d / 'link').symlink_to(d / 'real')
        self.assertEqual(code_of(m.ForecastLedger, d / 'link', tenant_id='t'), 'INTEL_REFUSED_PATH')
        self.assertEqual(code_of(m.ForecastLedger, d / 'x.jsonl', tenant_id=''), 'INTEL_REFUSED_SCHEMA')
        self.assertEqual(code_of(m.ForecastLedger, d / 'x.jsonl', tenant_id=5), 'INTEL_REFUSED_SCHEMA')

    def test_clean_text_uses_intel_domain_and_field_names(self):
        for fn, args, expect in [
            (m.text, ('', 'claim'), 'INTEL_REFUSED_EMPTY:claim'),
            (m.text, (5, 'source'), 'INTEL_REFUSED_BAD_TYPE:source'),
            (m.text, ('a\x00b', 'claim'), 'INTEL_REFUSED_CONTROL_CHARS:claim'),
            (m.text, ('x' * 4097, 'claim'), 'INTEL_REFUSED_TEXT_TOO_LONG:claim'),
        ]:
            with self.assertRaises(m.ForecastRefusal) as cm:
                fn(*args)
            self.assertEqual(cm.exception.code, 'INTEL_REFUSED_SCHEMA')
            self.assertIn(expect, str(cm.exception))
        self.assertEqual(code_of(self.add, claim='  '), 'INTEL_REFUSED_SCHEMA')

    def test_refusal_is_valueerror_with_code_prefix(self):
        with self.assertRaises(ValueError) as cm:
            m.refuse('TIME', 'detail')
        self.assertEqual((cm.exception.code, str(cm.exception)), ('INTEL_REFUSED_TIME', 'INTEL_REFUSED_TIME: detail'))
        with self.assertRaises(m.ForecastRefusal) as cm:
            m.refuse('LIMIT', '')
        self.assertEqual(str(cm.exception), 'INTEL_REFUSED_LIMIT')


# 10 -----------------------------------------------------------------------
def _worker(path, wid, n):
    led = m.ForecastLedger(path, tenant_id='tenant-mp')
    for i in range(n):
        led.append_prediction(claim='w%d-%d' % (wid, i), probability=.5, horizon=T1, source='mp', made_at=T0)


class MultiProcess(unittest.TestCase):
    def test_concurrent_processes_keep_chain_valid_and_lose_nothing(self):
        ctx = multiprocessing.get_context('fork')
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'mp.jsonl'
            m.ForecastLedger(path, tenant_id='tenant-mp')
            procs = [ctx.Process(target=_worker, args=(path, w, 25)) for w in range(6)]
            for p in procs:
                p.start()
            for p in procs:
                p.join(60)
            self.assertEqual([p.exitcode for p in procs], [0] * 6)
            led = m.ForecastLedger(path, tenant_id='tenant-mp')
            r = led.report(calibrated=False)  # raises INTEGRITY when the chain is torn
            self.assertEqual(r['coverage']['predictions'], 150)
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([e['seq'] for e in events], list(range(151)))


# 11 -----------------------------------------------------------------------
class Durability(Base):
    def test_flush_happens_before_fsync(self):
        sizes = []
        real = os.fsync
        before = self.path.stat().st_size

        def spy(fd):
            sizes.append(os.fstat(fd).st_size)  # bytes visible to the OS at fsync time
            return real(fd)
        with patch.object(m.os, 'fsync', spy):
            self.add()
        after = self.path.stat().st_size
        self.assertGreater(after, before)
        self.assertEqual(sizes, [after])  # new line was flushed before fsync, not after

    def test_one_fsync_per_append_and_none_on_idempotent_replay(self):
        with patch.object(m.os, 'fsync', wraps=os.fsync) as sync:
            p = self.add()
            self.assertEqual(sync.call_count, 1)
            self.add()
            self.assertEqual(sync.call_count, 1)
            self.ledger.resolve(p['prediction_id'], outcome=True, resolved_at=T2)
            self.assertEqual(sync.call_count, 2)

    def test_nested_parent_dirs_are_created(self):
        nested = Path(self.tmp.name) / 'a' / 'b' / 'c' / 'ledger.jsonl'
        led = m.ForecastLedger(nested, tenant_id='t')
        self.assertTrue(nested.is_file())
        led.append_prediction(claim='c', probability=.5, horizon=T1, source='s', made_at=T0)
        self.assertEqual(m.ForecastLedger(nested, tenant_id='t').report(calibrated=False)['coverage']['predictions'], 1)
        self.assertEqual(oct(nested.stat().st_mode & 0o777), '0o600')

    def test_stated_limitation_no_auto_repair_of_partial_append(self):
        self.add()
        with self.path.open('ab') as f:
            f.write(b'{"seq":2')  # torn write
        torn = self.path.read_bytes()
        self.assertEqual(code_of(self.add, claim='next'), 'INTEL_REFUSED_INTEGRITY')
        self.assertEqual(self.path.read_bytes(), torn)  # refused, never repaired


if __name__ == '__main__':
    unittest.main()
