import copy
import importlib.util
import json
import math
import sys
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
import os
SOURCE = Path(os.environ.get('J1_SOURCE', ROOT / 'backend/app/modules/m20_general_cognitive_worker/j1_forecast.py'))
spec = importlib.util.spec_from_file_location('j1_private', SOURCE)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def pred(**kw):
    row = dict(prediction_id='p1', claim='Event occurs', probability=0.8, horizon='2026-10-12T00:00:00Z',
               source='supplied fixture', made_at='2026-10-11T00:00:00Z')
    row.update(kw); return row


def resolved(**kw):
    row = dict(prediction_id='p1', outcome=True, resolved_at='2026-10-12T01:00:00Z')
    row.update(kw); return row


class ScoreTests(unittest.TestCase):
    def refuse(self, predictions, resolutions, code, **kw):
        with self.assertRaises(m.ForecastRefusal) as exc:
            m.score_predictions(predictions, resolutions, **kw)
        self.assertEqual(exc.exception.code, code)

    def test_known_brier_sharpness(self):
        r = m.score_predictions([pred()], [resolved()])
        self.assertAlmostEqual(r['brier_score'], 0.04)
        self.assertAlmostEqual(r['sharpness'], 0.09)
        self.assertEqual(r['coverage'], {'predictions': 1, 'resolved': 1, 'unresolved': 0})
        self.assertFalse(r['scope']['future_skill_proven'])

    def test_frozen_suite(self):
        probabilities = [0, 0.1, 0.25, 0.5, 0.5, 0.75, 0.9, 1]
        outcomes = [False, False, True, False, True, True, True, True]
        p = [pred(prediction_id='p'+str(i), probability=v) for i,v in enumerate(probabilities)]
        y = [resolved(prediction_id='p'+str(i), outcome=v) for i,v in enumerate(outcomes)]
        r=m.score_predictions(p,y,bins=4)
        self.assertAlmostEqual(r['brier_score'], 1.145 / 8)
        self.assertAlmostEqual(r['sharpness'], 0.945 / 8)
        self.assertEqual([b['count'] for b in r['reliability_bins']], [2,1,2,3])
        self.assertAlmostEqual(r['reliability_bins'][0]['mean_probability'], .05)
        self.assertEqual(r['reliability_bins'][0]['observed_rate'], 0)
        self.assertAlmostEqual(r['reliability_bins'][3]['observed_rate'], 1)

    def test_empty_unresolved_refused(self):
        self.refuse([], [], 'INTEL_REFUSED_UNSCORED')
        self.refuse([pred()], [], 'INTEL_REFUSED_UNSCORED')

    def test_partial_not_calibrated(self):
        p=[pred(),pred(prediction_id='p2')];r=m.score_predictions(p,[resolved()],calibrated=False)
        self.assertEqual(r['status'],'descriptive_partial')
        self.assertEqual(r['coverage']['unresolved'],1)
        r=m.score_predictions([],[],calibrated=False)
        self.assertIsNone(r['brier_score']);self.assertIsNone(r['sharpness'])
        self.assertTrue(all(b['mean_probability'] is None for b in r['reliability_bins']))

    def test_no_horizon(self):
        for horizon in [None,'']:
            self.refuse([pred(horizon=horizon)],[], 'INTEL_REFUSED_NOHORIZON')
        p=pred();del p['horizon'];self.refuse([p],[], 'INTEL_REFUSED_NOHORIZON')

    def test_probabilities(self):
        for value in [-.01,1.01,float('nan'),float('inf'),True,'0.8',None]:
            self.refuse([pred(probability=value)],[],'INTEL_REFUSED_SCHEMA')
        for value in [0,1]:
            self.assertIsNotNone(m.score_predictions([pred(probability=value)],[resolved()])['brier_score'])

    def test_outcomes_exact_bool(self):
        for value in [0,1,'true',None]: self.refuse([pred()],[resolved(outcome=value)],'INTEL_REFUSED_SCHEMA')

    def test_aware_times_and_order(self):
        self.refuse([pred(made_at='2026-10-11')],[],'INTEL_REFUSED_TIME')
        self.refuse([pred(horizon='2026-10-11T00:00:00Z')],[],'INTEL_REFUSED_TIME')
        self.refuse([pred()],[resolved(resolved_at='2026-10-11T23:59:59Z')],'INTEL_REFUSED_TIME')
        r=m.score_predictions([pred(horizon='2026-10-12T05:30:00+05:30')],[resolved(resolved_at='2026-10-12T00:00:00Z')])
        self.assertEqual(r['coverage']['resolved'],1)

    def test_duplicate_and_orphan(self):
        self.refuse([pred(),pred()],[],'INTEL_REFUSED_DUPLICATE')
        self.refuse([pred()],[resolved(),resolved()],'INTEL_REFUSED_DUPLICATE')
        self.refuse([pred()],[resolved(prediction_id='other')],'INTEL_REFUSED_REFERENCE')

    def test_bins_bounds_and_types(self):
        for bins in [0,101,True,1.5,'10']: self.refuse([pred()],[resolved()],'INTEL_REFUSED_SCHEMA',bins=bins)
        for bins in [1,100]:self.assertEqual(len(m.score_predictions([pred()],[resolved()],bins=bins)['reliability_bins']),bins)
        self.refuse([pred()],[resolved()],'INTEL_REFUSED_SCHEMA',calibrated=1)

    def test_no_input_mutation(self):
        p=[pred()];y=[resolved()];old=copy.deepcopy((p,y));m.score_predictions(p,y)
        self.assertEqual((p,y),old)

    def test_policy_called(self):
        from unittest.mock import patch
        with patch.object(m.policy, 'classify', return_value={'decision':'refuse','code':'POLICY_REFUSED_TEST'}):
            self.refuse([pred()],[resolved()],'POLICY_REFUSED_TEST')

    def test_small_sample_threshold_and_wording(self):
        self.assertEqual(m.MIN_CALIBRATION_SAMPLE,20)
        for n,label in [(19,'insufficient_sample'),(20,'descriptive_reliability_only')]:
            ps=[pred(prediction_id='p'+str(i)) for i in range(n)]
            ys=[resolved(prediction_id='p'+str(i)) for i in range(n)]
            r=m.score_predictions(ps,ys)
            self.assertEqual(r['scored_n'],n);self.assertEqual(r['calibration_label'],label)
            self.assertNotIn('calibrated',r['status'])
            if n<20:self.assertIn('no calibration claim',r['small_sample_caveat'])
            else:self.assertIsNone(r['small_sample_caveat'])

    def test_exact_probability_bin_edges(self):
        ps=[pred(prediction_id='p'+str(i),probability=p) for i,p in enumerate([0,.25,.5,.75,1])]
        ys=[resolved(prediction_id='p'+str(i),outcome=False) for i in range(5)]
        r=m.score_predictions(ps,ys,bins=4)
        self.assertEqual([b['count'] for b in r['reliability_bins']],[1,1,1,2])
        self.assertAlmostEqual(r['brier_score'],.375)
        self.assertAlmostEqual(r['sharpness'],.125)

    def test_empty_bin_is_null(self):
        r=m.score_predictions([pred()],[resolved()],bins=10)
        self.assertIsNone(r['reliability_bins'][0]['mean_probability'])
        self.assertIsNone(r['reliability_bins'][0]['observed_rate'])

    def test_whitespace_horizon(self):
        self.refuse([pred(horizon='   ')],[],'INTEL_REFUSED_NOHORIZON')

    def test_large_int_and_schema_fields(self):
        self.refuse([pred(probability=10**400)],[],'INTEL_REFUSED_SCHEMA')
        self.refuse([pred(extra='metadata')],[],'INTEL_REFUSED_SCHEMA')
        self.refuse({},[],'INTEL_REFUSED_SCHEMA')
        self.refuse([pred()],[resolved(extra=True)],'INTEL_REFUSED_SCHEMA')

    def test_text_type_and_limits(self):
        for value in [None,[],True,'','x'*4097,'null\x00byte']:
            self.refuse([pred(claim=value)],[],'INTEL_REFUSED_SCHEMA')
        self.assertEqual(m.score_predictions([pred(claim='x'*4096)],[resolved()])['scored_n'],1)

    def test_supplied_data_capacity_boundary(self):
        ps=[pred(prediction_id='p'+str(i)) for i in range(10000)]
        self.assertEqual(m.score_predictions(ps,[],calibrated=False)['coverage']['predictions'],10000)
        ps.append(pred(prediction_id='over'))
        self.refuse(ps,[],'INTEL_REFUSED_LIMIT',calibrated=False)



class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'ledger.jsonl'
        self.ledger=m.ForecastLedger(self.path, tenant_id='tenant-a')
    def tearDown(self):self.tmp.cleanup()
    def append(self, **kw):
        p=pred(**kw);del p['prediction_id'];return self.ledger.append_prediction(**p)

    def test_append_resolve_reload(self):
        p=self.append();before=self.path.read_bytes()
        y=self.ledger.resolve(p['prediction_id'],outcome=True,resolved_at='2026-10-12T01:00:00Z')
        self.assertTrue(self.path.read_bytes().startswith(before))
        new=m.ForecastLedger(self.path,tenant_id='tenant-a')
        self.assertAlmostEqual(new.report()['brier_score'],.04)
        self.assertEqual(y['prediction_id'],p['prediction_id'])

    def test_idempotence_and_conflicting_resolution(self):
        p=self.append();before=self.path.read_bytes();self.assertEqual(self.append(),p);self.assertEqual(self.path.read_bytes(),before)
        y=self.ledger.resolve(p['prediction_id'],outcome=False,resolved_at='2026-10-12T01:00:00Z');before=self.path.read_bytes()
        self.assertEqual(self.ledger.resolve(p['prediction_id'],outcome=False,resolved_at='2026-10-12T01:00:00Z'),y)
        self.assertEqual(self.path.read_bytes(),before)
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_CONFLICT'):
            self.ledger.resolve(p['prediction_id'],outcome=True,resolved_at='2026-10-12T01:00:00Z')

    def test_tenant_and_tampering(self):
        self.append()
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_TENANT'):
            m.ForecastLedger(self.path,tenant_id='tenant-b').report(calibrated=False)
        s=self.path.read_text();self.path.write_text(s.replace('Event occurs','Event altered'))
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_INTEGRITY'):self.ledger.report(calibrated=False)

    def test_partial_line_refuses_without_mutation(self):
        self.append()
        with self.path.open('ab') as f:f.write(b'{')
        before=self.path.read_bytes()
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_INTEGRITY'):self.append(claim='other')
        self.assertEqual(self.path.read_bytes(),before)

    def test_concurrent_same_prediction_once(self):
        with ThreadPoolExecutor(max_workers=8) as pool: result=list(pool.map(lambda _:self.append(),range(16)))
        self.assertEqual(len({p['prediction_id'] for p in result}),1)
        self.assertEqual(self.ledger.report(calibrated=False)['coverage']['predictions'],1)

    def test_symlink_refused(self):
        self.path.unlink();target=Path(self.tmp.name)/'target';target.write_text('')
        self.path.symlink_to(target)
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_PATH'):self.ledger.report(calibrated=False)

    def test_future_resolution_not_precomputed(self):
        p=self.append()
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_UNSCORED'):self.ledger.report()
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_TIME'):
            self.ledger.resolve(p['prediction_id'],outcome=True,resolved_at='2026-10-11T01:00:00Z')


    def test_normalized_id_content_binding(self):
        p=self.append()
        expected=m.digest({k:v for k,v in p.items() if k!='prediction_id'})
        self.assertEqual(p['prediction_id'],expected)
        q=self.append(made_at='2026-10-11T05:30:00+05:30')
        self.assertEqual(q,p)
        self.assertNotEqual(self.append(claim='different')['prediction_id'],p['prediction_id'])

    def test_record_policy_precedes_file_mutation(self):
        from unittest.mock import patch
        before=self.path.read_bytes()
        with patch.object(m.policy,'classify',return_value={'decision':'refuse','code':'POLICY_REFUSED_TEST'}):
            with self.assertRaisesRegex(m.ForecastRefusal,'POLICY_REFUSED_TEST'):self.append()
        self.assertEqual(self.path.read_bytes(),before)

    def test_unknown_resolution_and_duplicate_chain(self):
        p=self.append()
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_REFERENCE'):
            self.ledger.resolve('unknown',outcome=True,resolved_at='2026-10-12T01:00:00Z')
        self.ledger.resolve(p['prediction_id'],outcome=True,resolved_at='2026-10-12T01:00:00Z')
        events=[json.loads(line) for line in self.path.read_text().splitlines()]
        body={'seq':len(events),'prev':events[-1]['sha256'],'kind':'resolution','data':events[-1]['data']}
        event=dict(body,sha256=m.digest(body))
        with self.path.open('a') as f:f.write(m.canonical(event)+'\n')
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_INTEGRITY'):self.ledger.report()

    def test_nonregular_path_refused(self):
        self.path.unlink();os.mkfifo(self.path)
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_PATH'):self.ledger.report(calibrated=False)

    def test_chain_sequence_and_header_guards(self):
        self.append();events=[json.loads(line) for line in self.path.read_text().splitlines()]
        for key,value in [('seq',True),('prev','bad'),('sha256','0'*64)]:
            changed=copy.deepcopy(events);changed[1][key]=value
            self.path.write_text(''.join(m.canonical(e)+'\n' for e in changed))
            with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_INTEGRITY'):self.ledger.report(calibrated=False)
        self.path.write_text(''.join(m.canonical(e)+'\n' for e in events))


    def test_initialization_policy_no_files_on_refusal(self):
        from unittest.mock import patch
        path=Path(self.tmp.name)/'new-ledger'
        with patch.object(m.policy,'classify',return_value={'decision':'refuse','code':'POLICY_REFUSED_TEST'}):
            with self.assertRaisesRegex(m.ForecastRefusal,'POLICY_REFUSED_TEST'):
                m.ForecastLedger(path,tenant_id='tenant-a')
        self.assertFalse(path.exists())

    def test_valid_json_without_terminal_newline(self):
        self.append();self.path.write_bytes(self.path.read_bytes().rstrip(b'\n'))
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_INTEGRITY'):self.ledger.report(calibrated=False)

    def test_wrong_integer_sequence_even_if_rehashed(self):
        self.append();events=[json.loads(line) for line in self.path.read_text().splitlines()]
        events[1]['seq']=8
        events[1]['sha256']=m.digest({k:events[1][k] for k in ['seq','prev','kind','data']})
        self.path.write_text(''.join(m.canonical(e)+'\n' for e in events))
        with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_INTEGRITY'):self.ledger.report(calibrated=False)


    def test_fsync_append_and_event_byte_caps(self):
        from unittest.mock import patch
        p=self.append();before=self.path.read_bytes()
        with patch.object(m,'MAX_EVENTS',2):
            with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_LIMIT'):
                self.ledger.resolve(p['prediction_id'],outcome=True,resolved_at='2026-10-12T01:00:00Z')
        self.assertEqual(self.path.read_bytes(),before)
        with patch.object(m,'MAX_BYTES',len(before)):
            with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_LIMIT'):self.append(claim='other')
        self.assertEqual(self.path.read_bytes(),before)
        with patch.object(m.os,'fsync',wraps=m.os.fsync) as sync:
            self.ledger.resolve(p['prediction_id'],outcome=True,resolved_at='2026-10-12T01:00:00Z')
            sync.assert_called_once()

    def test_prediction_cap_idempotence_before_limit(self):
        from unittest.mock import patch
        p=self.append()
        with patch.object(m,'MAX_PREDICTIONS',1):
            self.assertEqual(self.append(),p)
            with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_LIMIT'):self.append(claim='other')

    def test_header_kind_version_and_fields(self):
        original=self.path.read_bytes()
        for change in [('kind','prediction'),('version',2),('version',True)]:
            event=json.loads(original)
            if change[0]=='kind':event['kind']=change[1]
            else:event['data'][change[0]]=change[1]
            event['sha256']=m.digest({k:event[k] for k in ['seq','prev','kind','data']})
            self.path.write_text(m.canonical(event)+'\n')
            with self.assertRaisesRegex(m.ForecastRefusal,'INTEL_REFUSED_INTEGRITY'):self.ledger.report(calibrated=False)
        self.path.write_bytes(original)

    def test_read_policy_refusal(self):
        from unittest.mock import patch
        with patch.object(m.policy,'classify',return_value={'decision':'refuse','code':'POLICY_REFUSED_TEST'}):
            with self.assertRaisesRegex(m.ForecastRefusal,'POLICY_REFUSED_TEST'):self.ledger.report(calibrated=False)

if __name__=='__main__':unittest.main()
