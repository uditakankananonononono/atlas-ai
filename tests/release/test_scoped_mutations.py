import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('scoped_mutations',Path(__file__).resolve().parents[2]/'scripts/release/scoped_mutations.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('rc,text,status',[
 (1,'FAILED tests/test_x.py::test_x - AssertionError','CAUGHT'),
 (2,'ERROR collecting tests/test_x.py','INVALID'),
 (1,'FAILED tests/test_x.py::test_x - AssertionError\nERROR collecting tests/test_y.py','INVALID'),
 (1,'crashed process','INVALID'),(0,'1 passed','SURVIVED'),(0,'1 passed, 1 skipped','SURVIVED-WITH-SKIPS'),
 (5,'no tests ran','INVALID')])
def test_failed_only_classification(rc,text,status):assert module.classify(rc,text)[0]==status


def test_execute_restores_exact_source_sha_after_failed_mutation(tmp_path,monkeypatch):
    import hashlib,json
    monkeypatch.chdir(tmp_path)
    source=tmp_path/'source.py';source.write_text('value = 1\n')
    original=source.read_bytes()
    spec={'row':0,'selectors':['tests/fixture.py'],'timeout_seconds':1,'limits':['fixture'],
          'mutations':[{'id':'value','path':'source.py','old':'value = 1','new':'value = 2'}]}
    specfile=tmp_path/'spec.json';specfile.write_text(json.dumps(spec))
    count=[]
    def run(*args):
        count.append(1)
        return {'returncode':0 if len(count)==1 else 1,'status':'SURVIVED' if len(count)==1 else 'CAUGHT',
                'failed_tests':[] if len(count)==1 else ['tests/fixture.py::test_value'],'output':'fixture log'}
    monkeypatch.setattr(module,'run_case',run)
    out=module.execute(specfile,tmp_path/'output')
    assert source.read_bytes()==original
    assert out['all_caught'] is True
    assert out['mutations'][0]['source_sha256_before']==hashlib.sha256(original).hexdigest()
    assert out['mutations'][0]['restore_verified'] is True
