import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[2] / 'backend/app/core/project_deliverable_contract.py'
spec = importlib.util.spec_from_file_location('project_deliverable_contract', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def spec_data(artifacts=None):
    return {'project_id': 'atlas', 'domain': 'software', 'source_lines': ['P76|L64', 'P84|L72'], 'repository': 'https://example.test/atlas', 'requested_targets': {'datasets': 120, 'project_tools': 40, 'program_tools': 200}, 'artifacts': artifacts or [], 'benchmark': None}


class DeliverableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'out.txt').write_bytes(b'real local output\n')
        self.digest = hashlib.sha256(b'real local output\n').hexdigest()

    def artifact(self, **updates):
        x = {'id': 'artifact-one', 'kind': 'dataset', 'path': 'out.txt', 'sha256': self.digest}
        x.update(updates); return x

    def test_empty_does_not_meet_targets(self):
        r = m.check_deliverables(self.root, spec_data())
        self.assertEqual(r['measured_artifact_count'], 0)
        self.assertEqual(r['requested_targets']['datasets'], 120)
        self.assertEqual(r['dataset_use'], 'UNVERIFIED')
        self.assertEqual(r['tool_execution'], 'UNVERIFIED')
        self.assertEqual(r['external_validation'], 'UNVERIFIED')
        self.assertEqual(r['sota'], 'UNVERIFIED')
        self.assertFalse(r['doc_lines_fulfilled'])

    def test_hash_bound_measured_count_not_reality(self):
        r = m.check_deliverables(self.root, spec_data([self.artifact()]))
        self.assertEqual(r['measured_artifact_count'], 1)
        self.assertEqual(r['measured_artifact_counts']['dataset'], 1)
        self.assertEqual(r['artifacts'][0]['status'], 'FILE_HASH_MATCH')
        self.assertEqual(r['dataset_use'], 'UNVERIFIED')
        self.assertEqual(r['repository_created'], 'UNVERIFIED')

    def test_missing_mismatch_empty_are_not_counted(self):
        for a in [self.artifact(path='missing'), self.artifact(sha256='0'*64)]:
            r = m.check_deliverables(self.root, spec_data([a]))
            self.assertEqual(r['measured_artifact_count'], 0)
        (self.root/'out.txt').write_bytes(b'')
        a = self.artifact(sha256=hashlib.sha256(b'').hexdigest())
        self.assertEqual(m.check_deliverables(self.root, spec_data([a]))['measured_artifact_count'], 0)

    def test_duplicate_ids_and_paths_rejected(self):
        for a in [self.artifact(), self.artifact(id='second')]:
            with self.assertRaises(m.ContractError):
                m.check_deliverables(self.root, spec_data([self.artifact(), a]))

    def test_same_content_deduplicated(self):
        (self.root/'copy.txt').write_bytes((self.root/'out.txt').read_bytes())
        r = m.check_deliverables(self.root, spec_data([self.artifact(), self.artifact(id='copy', path='copy.txt')]))
        self.assertEqual(r['measured_artifact_count'], 1)
        self.assertEqual(r['artifacts'][1]['status'], 'DUPLICATE_CONTENT')

    def test_hardlink_identity_deduplicated(self):
        import os
        os.link(self.root/'out.txt', self.root/'hard.txt')
        r = m.check_deliverables(self.root, spec_data([self.artifact(), self.artifact(id='hard', path='hard.txt', kind='tool')]))
        self.assertEqual(r['measured_artifact_count'], 1)
        self.assertEqual(r['measured_artifact_counts']['tool'], 0)

    def test_paths_cannot_escape(self):
        for path in ['../out.txt', '/etc/passwd', 'x/../out.txt', '.', 'x\\y']:
            with self.subTest(path=path), self.assertRaises(m.ContractError):
                m.check_deliverables(self.root, spec_data([self.artifact(path=path)]))

    def test_symlink_and_directory_not_files(self):
        (self.root/'link').symlink_to(self.root/'out.txt')
        (self.root/'dir').mkdir()
        for path in ['link', 'dir']:
            r = m.check_deliverables(self.root, spec_data([self.artifact(path=path)]))
            self.assertEqual(r['measured_artifact_count'], 0)
        (self.root/'parent').symlink_to(self.root, target_is_directory=True)
        self.assertEqual(m.check_deliverables(self.root, spec_data([self.artifact(path='parent/out.txt')]))['measured_artifact_count'], 0)

    def test_limits(self):
        self.assertEqual(m.check_deliverables(self.root, spec_data([self.artifact()]), max_file_bytes=1)['measured_artifact_count'], 0)
        for n in [0, True, -1]:
            with self.assertRaises(m.ContractError):
                m.check_deliverables(self.root, spec_data(), max_file_bytes=n)

    def test_schema_rejects_science_and_bad_targets(self):
        for key, val in [('domain', 'science'), ('project_id', '../bad'), ('source_lines', []), ('requested_targets', {'datasets': True, 'project_tools': 1, 'program_tools': 1}), ('repository', 'file:///tmp/repo')]:
            s = spec_data(); s[key] = val
            with self.subTest(key=key), self.assertRaises(m.ContractError):m.validate_spec(s)
        s=spec_data();s['extra']=1
        with self.assertRaises(m.ContractError):m.validate_spec(s)
        with self.assertRaises(m.ContractError):m.validate_spec(spec_data([self.artifact(kind='magic')]))

    def test_benchmark_is_declared_metadata_only(self):
        s=spec_data([self.artifact(kind='benchmark_output')])
        s['benchmark']={'comparator': 'Declared tool', 'metric': 'accuracy', 'dataset_artifact_id': 'artifact-one', 'result_artifact_id': 'artifact-one', 'protocol': 'Caller protocol'}
        r=m.check_deliverables(self.root,s)
        self.assertEqual(r['benchmark_metadata'], s['benchmark'])
        self.assertEqual(r['benchmark_execution'], 'UNVERIFIED')
        self.assertEqual(r['sota'], 'UNVERIFIED')
        s['benchmark']['result_artifact_id']='unknown'
        with self.assertRaises(m.ContractError):m.validate_spec(s)

    def test_no_input_mutation_or_repository_writes(self):
        s=spec_data([self.artifact()]); old=copy.deepcopy(s)
        before=list(self.root.iterdir())
        r=m.check_deliverables(self.root,s)
        self.assertEqual(s,old);self.assertEqual(list(self.root.iterdir()),before)
        r['requested_targets']['datasets']=0
        self.assertEqual(s['requested_targets']['datasets'],120)


if __name__ == '__main__':unittest.main()
