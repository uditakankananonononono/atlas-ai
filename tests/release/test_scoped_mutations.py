import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('scoped_mutations',Path(__file__).resolve().parents[2]/'scripts/release/scoped_mutations.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('rc,text,status',[
 (1,'FAILED tests/test_x.py::test_x - AssertionError','CAUGHT'),
 (2,'ERROR collecting tests/test_x.py','INVALID'),
 (1,'FAILED tests/test_x.py::test_x - AssertionError\nERROR collecting tests/test_y.py','INVALID'),
 (1,'FAILED tests/test_x.py::test_x - AssertionError\n1 failed, 1 skipped','INVALID'),
 (1,'FAILED tests/test_x.py::test_x - AssertionError\nSKIPPED tests/test_y.py','INVALID'),
 (1,'crashed process','INVALID'),(0,'1 passed','SURVIVED'),(0,'1 passed, 1 skipped','SURVIVED-WITH-SKIPS'),
 (5,'no tests ran','INVALID')])
def test_failed_only_classification(rc,text,status):assert module.classify(rc,text)[0]==status


def test_execute_restores_exact_source_sha_after_failed_mutation(tmp_path,monkeypatch):
    import hashlib,json
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(['git','init','-q'],check=True)
    subprocess.run(['git','-c','user.name=Instinct','-c','user.email=agent@instinct.com','commit','--allow-empty','-qm','fixture'],check=True)
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


@pytest.mark.parametrize('skip_on_mutation', [False, True])
def test_execute_real_pytest_binds_checkout_hashes_and_rejects_fail_plus_skip(tmp_path, monkeypatch, skip_on_mutation):
    import hashlib, json, subprocess
    monkeypatch.chdir(tmp_path)
    (tmp_path/'scripts').mkdir()
    (tmp_path/'tests').mkdir()
    (tmp_path/'audits').mkdir()
    source=tmp_path/'scripts/value.py'
    source.write_text('value = 1\n')
    test=tmp_path/'tests/test_value.py'
    test.write_text('import runpy\nimport pytest\n'
                    'value = runpy.run_path("scripts/value.py")["value"]\n'
                    'def test_value():\n    assert value == 1\n'
                    'def test_companion():\n'
                    f'    if value == 2 and {skip_on_mutation!r}:\n        pytest.skip("mutated companion")\n'
                    '    assert True\n')
    specfile=tmp_path/'audits/spec.json'
    specfile.write_text(json.dumps({'row':0,'selectors':['tests/test_value.py'],
        'timeout_seconds':15,'limits':['trusted local fixture'],
        'mutations':[{'id':'value','path':'scripts/value.py','old':'value = 1','new':'value = 2'}]}))
    subprocess.run(['git','init','-q'],check=True)
    subprocess.run(['git','add','scripts','tests','audits'],check=True)
    subprocess.run(['git','-c','user.name=Instinct','-c','user.email=agent@instinct.com',
                    'commit','-qm','fixture'],check=True)
    expected={str(p.relative_to(tmp_path)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (source,test,specfile)}
    result=module.execute(specfile,tmp_path/'output')
    persisted=json.loads((tmp_path/'output/receipt.json').read_text())
    assert result == persisted
    assert persisted['baseline']['status']=='PASS'
    assert persisted['checkout']['head']==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    assert persisted['checkout']['head_tree']==subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()
    assert persisted['checkout']['status']=='?? output/'
    assert persisted['tracked_code_test_hashes']==expected
    mutation=persisted['mutations'][0]
    assert mutation['status']==('INVALID' if skip_on_mutation else 'CAUGHT')
    assert mutation['returncode']==1
    assert mutation['failed_tests']==['tests/test_value.py::test_value']
    assert persisted['all_caught'] is (not skip_on_mutation)
    assert mutation['restore_verified'] is True
    assert hashlib.sha256(source.read_bytes()).hexdigest()==expected['scripts/value.py']
    log=(tmp_path/'output/value.log').read_text()
    assert 'FAILED tests/test_value.py::test_value' in log
    assert ('1 skipped' in log) is skip_on_mutation
