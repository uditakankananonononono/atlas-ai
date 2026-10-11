import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
import stat
import os

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




class AuditRepairTests(unittest.TestCase):
    setUp=DeliverableTests.setUp
    artifact=DeliverableTests.artifact

    def test_invalid_text_and_controls(self):
        for value in [None, 1, '', ' ', 'x'*2001, 'x'+chr(31), 'x'+chr(127)]:
            with self.subTest(value=value), self.assertRaises(m.ContractError):m._text(value)
        m._text('x'*2000);m._text('x y')

    def test_refs_targets_containers_rows_sha_benchmark(self):
        cases=[('source_lines',['bad']),('source_lines',[1]),('source_lines','P1|L1'),('requested_targets',{}),('requested_targets',[]),('requested_targets',{'datasets':1,'project_tools':2,'program_tools':3,'extra':0}),('artifacts',{}),('artifacts',()),('artifacts',[dict(self.artifact(),extra=1)]),('artifacts',[None]),('artifacts',[self.artifact(sha256='G'*64)]),('artifacts',[self.artifact(sha256='a'*63)]),('artifacts',[self.artifact(sha256=1)]),('benchmark',{}),('benchmark',[])]
        for key,value in cases:
            s=spec_data();s[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(m.ContractError):m.validate_spec(s)
        b={'comparator':'tool','metric':'score','dataset_artifact_id':'artifact-one','result_artifact_id':'artifact-one','protocol':'plan'}
        for key in b:
            x=dict(b);x[key]='bad'+chr(31)
            s=spec_data([self.artifact()]);s['benchmark']=x
            with self.subTest(key=key),self.assertRaises(m.ContractError):m.validate_spec(s)
        s=spec_data([self.artifact()]);s['benchmark']=dict(b,extra='x')
        with self.assertRaises(m.ContractError):m.validate_spec(s)
        # Distinct ids and paths make only the list bound cause rejection.
        s=spec_data([self.artifact(id='a'+str(i),path='f'+str(i)) for i in range(10001)])
        with self.assertRaises(m.ContractError):m.validate_spec(s)

    def measured(self,before=None,after=None,chunks=None,bound=10,error=None,path='out.txt'):
        initial=SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_size=3,st_mtime_ns=1,st_ctime_ns=2,st_dev=1,st_ino=2)
        before=before or initial;after=after or initial
        row=self.artifact(path=path,sha256=hashlib.sha256(b'abc').hexdigest())
        with mock.patch.object(m.os,'dup',return_value=20),mock.patch.object(m.os,'open',side_effect=error or ([30] if '/' not in path else [25,30])) as opened,mock.patch.object(m.os,'fstat',side_effect=[before,after]),mock.patch.object(m.os,'read',side_effect=chunks or [b'abc',b'']) as read,mock.patch.object(m.os,'close') as close:
            result=m._measure(10,row,bound)
            return result,read.call_args_list,close.call_args_list,opened.call_args_list

    def test_regular_device_fifo_directory_classification(self):
        for mode in [stat.S_IFCHR,stat.S_IFBLK,stat.S_IFIFO,stat.S_IFDIR,stat.S_IFSOCK]:
            before=SimpleNamespace(st_mode=mode,st_size=3)
            r,reads,closes,_=self.measured(before=before)
            self.assertEqual(r,('NOT_REGULAR_FILE',None,None));self.assertEqual(reads,[])
            self.assertEqual(closes,[mock.call(30),mock.call(20)])

    def test_static_oversize_has_no_read_and_status(self):
        before=SimpleNamespace(st_mode=stat.S_IFREG,st_size=11)
        r,reads,closes,_=self.measured(before=before,bound=10)
        self.assertEqual(r,('TOO_LARGE',None,None));self.assertEqual(reads,[])
        self.assertEqual(closes,[mock.call(30),mock.call(20)])

    def test_oversize_while_read_and_chunk_request(self):
        r,reads,closes,_=self.measured(chunks=[b'ab',b'cd'],bound=3)
        self.assertEqual(r,('TOO_LARGE',None,None))
        self.assertEqual(reads,[mock.call(30,4),mock.call(30,2)])
        self.assertEqual(closes,[mock.call(30),mock.call(20)])

    def test_before_after_race_fields_and_short_read(self):
        for field,value in [('st_size',4),('st_mtime_ns',2),('st_ctime_ns',3)]:
            after=SimpleNamespace(st_mode=stat.S_IFREG,st_size=3,st_mtime_ns=1,st_ctime_ns=2,st_dev=1,st_ino=2)
            setattr(after,field,value)
            r,_,closes,_=self.measured(after=after)
            self.assertEqual(r,('CHANGED_DURING_READ',None,None));self.assertEqual(closes,[mock.call(30),mock.call(20)])
        r,_,_,_=self.measured(chunks=[b'ab',b''])
        self.assertEqual(r,('CHANGED_DURING_READ',None,None))

    def test_fd_cleanup_success_fail_open_nested_and_read(self):
        r,_,closes,_=self.measured()
        self.assertEqual(r[0],'FILE_HASH_MATCH');self.assertEqual(closes,[mock.call(30),mock.call(20)])
        r,_,closes,_=self.measured(error=OSError('denied'))
        self.assertEqual(r,('UNREADABLE_OR_UNSAFE',None,None));self.assertEqual(closes,[mock.call(20)])
        r,_,closes,opened=self.measured(path='nested/file')
        self.assertEqual(closes,[mock.call(20),mock.call(30),mock.call(25)])
        self.assertTrue(opened[0].args[1]&os.O_DIRECTORY);self.assertTrue(opened[0].args[1]&os.O_NOFOLLOW)
        self.assertTrue(opened[1].args[1]&os.O_NOFOLLOW);self.assertTrue(opened[1].args[1]&os.O_NONBLOCK)
        r,_,closes,_=self.measured(chunks=[OSError('read failure')])
        self.assertEqual(r[0],'UNREADABLE_OR_UNSAFE');self.assertEqual(closes,[mock.call(30),mock.call(20)])

    def test_real_nested_exact_fifo_symlink_root(self):
        (self.root/'nested').mkdir();(self.root/'nested/file').write_bytes(b'abc')
        s=spec_data([self.artifact(path='nested/file',sha256=hashlib.sha256(b'abc').hexdigest())])
        self.assertEqual(m.check_deliverables(self.root,s,max_file_bytes=3)['measured_artifact_count'],1)
        self.assertEqual(m.check_deliverables(self.root,s,max_file_bytes=2)['artifacts'][0]['status'],'TOO_LARGE')
        os.mkfifo(self.root/'fifo')
        self.assertEqual(m.check_deliverables(self.root,spec_data([self.artifact(path='fifo')]))['artifacts'][0]['status'],'NOT_REGULAR_FILE')
        (self.root/'link').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(m.ContractError):m.check_deliverables(self.root/'link',s)


if __name__ == '__main__':unittest.main()
