"""J1: deeply nested JSON in a ledger line refuses INTEGRITY instead of raising RecursionError."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
SOURCE = Path(os.environ.get('J1_SOURCE', ROOT / 'backend/app/modules/m20_general_cognitive_worker/j1_forecast.py'))
spec = importlib.util.spec_from_file_location('j1_rec', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

T0, T1 = '2026-10-11T00:00:00Z', '2026-10-12T00:00:00Z'


class DeepNesting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'ledger.jsonl'
        self.ledger = m.ForecastLedger(self.path, tenant_id='tenant-a')
        self.ledger.append_prediction(claim='c', probability=.8, horizon=T1, source='s', made_at=T0)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, depth):
        good = self.path.read_bytes()
        self.path.write_bytes(good + b'[' * depth + b']' * depth + b'\n')
        bad = self.path.read_bytes()
        for fn in (lambda: self.ledger.report(calibrated=False),
                   lambda: self.ledger.append_prediction(claim='n', probability=.5, horizon=T1, source='s', made_at=T0),
                   lambda: m.ForecastLedger(self.path, tenant_id='tenant-a')):
            with self.assertRaises(m.ForecastRefusal) as cm:  # a bare RecursionError fails here
                fn()
            self.assertEqual(cm.exception.code, 'INTEL_REFUSED_INTEGRITY', depth)
        self.assertEqual(self.path.read_bytes(), bad)  # refused, never repaired
        self.path.write_bytes(good)
        self.assertEqual(self.ledger.report(calibrated=False)['coverage']['predictions'], 1)

    def test_deeply_nested_line_is_integrity(self):
        self.check(100000)

    def test_nested_just_past_recursion_limit_is_integrity(self):
        self.check(sys.getrecursionlimit() + 50)

    def test_nested_object_data_is_integrity(self):
        depth = 100000
        line = b'{"seq":1,"prev":"x","kind":"prediction","data":' + b'{"a":' * depth + b'1' + b'}' * depth + b',"sha256":"y"}\n'
        self.path.write_bytes(self.path.read_bytes() + line)
        with self.assertRaises(m.ForecastRefusal) as cm:
            self.ledger.report(calibrated=False)
        self.assertEqual(cm.exception.code, 'INTEL_REFUSED_INTEGRITY')


if __name__ == '__main__':
    unittest.main()
