"""Hermetic tests for instinct-doc group 2: dataset artifact evidence."""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_BACKEND = os.path.join(_REPO_ROOT, 'backend')
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

_PATH = os.path.join(_REPO_ROOT, 'backend', 'app', 'modules', 'instinct_doc',
                     'dataset_evidence_g2.py')
_spec = importlib.util.spec_from_file_location('app.modules.instinct_doc.dataset_evidence_g2', _PATH)
m = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = m
_spec.loader.exec_module(m)


class RepoTreeMixin(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self._td.name)
        (self.repo / 'data').mkdir()
        for i in range(3):
            (self.repo / 'data' / ('set%d.csv' % i)).write_text('a,b\n1,2\n')
        (self.repo / 'data' / 'notes.py').write_text('# not data')
        (self.repo / 'src').mkdir()
        (self.repo / 'src' / 'ignored.csv').write_text('x\n')

    def tearDown(self):
        self._td.cleanup()


class TestScan(RepoTreeMixin):
    def test_counts_data_artifacts(self):
        r = m.scan_repo(str(self.repo), target=2)
        self.assertEqual(r['artifact_count'], 3)
        self.assertEqual(r['by_extension'], {'.csv': 3})
        self.assertEqual(r['verdict'], 'EVIDENCE_AT_TARGET')

    def test_ignores_files_outside_data_dirs(self):
        r = m.scan_repo(str(self.repo))
        self.assertEqual(r['artifact_count'], 3)
        self.assertNotIn(os.path.join('src', 'ignored.csv'), r['evidence'])

    def test_ignores_non_data_extensions(self):
        (self.repo / 'data' / 'readme.md').write_text('hi')
        r = m.scan_repo(str(self.repo))
        self.assertEqual(r['by_extension'], {'.csv': 3})

    def test_nested_data_dir_case_insensitive(self):
        (self.repo / 'deep' / 'Datasets').mkdir(parents=True)
        (self.repo / 'deep' / 'Datasets' / 'x.jsonl').write_text('{}\n')
        r = m.scan_repo(str(self.repo))
        self.assertEqual(r['artifact_count'], 4)

    def test_below_target_verdict(self):
        r = m.scan_repo(str(self.repo), target=120)
        self.assertEqual(r['verdict'], 'EVIDENCE_BELOW_TARGET')

    def test_evidence_capped(self):
        for i in range(30):
            (self.repo / 'data' / ('extra%d.csv' % i)).write_text('x\n')
        r = m.scan_repo(str(self.repo))
        self.assertLessEqual(len(r['evidence']), m.MAX_EVIDENCE)
        self.assertEqual(r['artifact_count'], 33)

    def test_symlink_escape_not_counted(self):
        outside = pathlib.Path(self._td.name).parent / 'g2-outside.csv'
        outside.write_text('x\n')
        try:
            (self.repo / 'data' / 'link.csv').symlink_to(outside)
            r = m.scan_repo(str(self.repo))
            self.assertEqual(r['artifact_count'], 3)
        finally:
            outside.unlink()

    def test_missing_repo_refused(self):
        with self.assertRaisesRegex(ValueError, 'G2_REFUSED_NO_REPO'):
            m.scan_repo(str(self.repo / 'nope'))

    def test_bad_target_refused(self):
        for bad in (True, '120', 0, -5, None):
            with self.assertRaisesRegex(ValueError, 'G2_REFUSED_BAD_TYPE:target'):
                m.scan_repo(str(self.repo), target=bad)


class TestLedger(RepoTreeMixin):
    def test_multi_repo_ledger(self):
        second = self.repo / '..' / 'g2-second'
        second.mkdir(exist_ok=True)
        (second / 'datasets').mkdir(exist_ok=True)
        (second / 'datasets' / 'one.csv').write_text('x\n')
        try:
            out = m.ledger({'a-demo': str(self.repo), 'b-demo': str(second)}, target=2)
            self.assertEqual(out['projects_at_target'], 1)
            self.assertEqual(out['projects_below_target'], 1)
            self.assertEqual([r['project'] for r in out['repos']], ['a-demo', 'b-demo'])
        finally:
            (second / 'datasets' / 'one.csv').unlink()
            (second / 'datasets').rmdir()
            second.rmdir()

    def test_oversize_repos_refused(self):
        with self.assertRaisesRegex(ValueError, 'G2_REFUSED_OVERSIZE:repos'):
            m.ledger({'r%d' % i: str(self.repo) for i in range(m.MAX_REPOS + 1)})

    def test_empty_repos_refused(self):
        with self.assertRaisesRegex(ValueError, 'G2_REFUSED_EMPTY:repos'):
            m.ledger({})


class TestVerify(RepoTreeMixin):
    def test_verify_accepts_own_run(self):
        out = m.run({'demo': str(self.repo)}, target=2)
        self.assertEqual(out['status'], 'measured')
        self.assertTrue(out['verification']['verified'])

    def test_verify_rejects_tampered_count(self):
        out = m.run({'demo': str(self.repo)}, target=2)
        import copy
        tampered = copy.deepcopy(out['result'])
        tampered['repos'][0]['artifact_count'] += 1
        receipt = m.verify({'demo': str(self.repo)}, tampered)
        self.assertFalse(receipt['verified'])
        self.assertIn('repos', receipt['failed'])

    def test_verify_rejects_tampered_verdict(self):
        out = m.run({'demo': str(self.repo)}, target=120)
        tampered = dict(out['result'])
        tampered['repos'] = [dict(r, verdict='EVIDENCE_AT_TARGET') for r in out['result']['repos']]
        tampered['projects_at_target'] = 1
        tampered['projects_below_target'] = 0
        receipt = m.verify({'demo': str(self.repo)}, tampered)
        self.assertFalse(receipt['verified'])

    def test_verify_rejects_extra_key(self):
        out = m.run({'demo': str(self.repo)}, target=2)
        tampered = dict(out['result'], sneaky=True)
        receipt = m.verify({'demo': str(self.repo)}, tampered)
        self.assertFalse(receipt['verified'])
        self.assertIn('exact_keys', receipt['failed'])

    def test_verify_rejects_tampered_measure(self):
        out = m.run({'demo': str(self.repo)}, target=2)
        receipt = m.verify({'demo': str(self.repo)}, dict(out['result'], measure='full audit'))
        self.assertFalse(receipt['verified'])
        self.assertIn('measure', receipt['failed'])

    def test_verify_rejects_non_dict(self):
        receipt = m.verify({'demo': str(self.repo)}, 'junk')
        self.assertFalse(receipt['verified'])


class TestAuditor8Round(RepoTreeMixin):
    def test_realpath_dedupe_in_repo_symlink(self):
        """A symlink to another in-repo artifact must not count twice."""
        (self.repo / 'data' / 'alias.csv').symlink_to(self.repo / 'data' / 'set0.csv')
        r = m.scan_repo(str(self.repo))
        self.assertEqual(r['artifact_count'], 3)

    def test_tests_data_counts_as_presence(self):
        """tests/data artifacts count toward presence (stated floor)."""
        (self.repo / 'tests' / 'data').mkdir(parents=True)
        (self.repo / 'tests' / 'data' / 'fixture.json').write_text('{}')
        r = m.scan_repo(str(self.repo))
        self.assertEqual(r['artifact_count'], 4)

    def test_docstring_has_no_source_request_line(self):
        self.assertNotIn('Source request (instinct doc, group 2)', m.__doc__)


if __name__ == '__main__':
    unittest.main()
