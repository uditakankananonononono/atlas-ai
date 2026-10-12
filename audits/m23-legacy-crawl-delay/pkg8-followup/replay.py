"""Replay two pkg8 probes on a trusted checkout; never use transport=None.
The old function BODY comes from pinned Git71533733. Keep the current signature
so kwargs calls reach old behavior instead of failing only at argument binding.
Full logs and per-probe restore hashes are retained; historical receipts untouched.
"""
import ast,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
TARGET=ROOT/'backend/app/modules/m23_study_abroad/admitted_cases.py'
PIN='71533733'
SELECTORS=['tests/modules/test_m23_admitted_cases_legacy_delegation.py','tests/modules/test_m23_admitted_cases_crawl_delay.py','tests/modules/test_m23_admitted_cases_bounded.py','tests/modules/test_m23_admitted_cases.py']
def sha(raw):return hashlib.sha256(raw).hexdigest()
def run(label,selectors):
    env=dict(os.environ,PYTHONPATH=os.pathsep.join(['backend',str(OUT)]),ATLAS_DEV_NO_AUTH='1',ATLAS_ENV='development',PYTHONDONTWRITEBYTECODE='1')
    cmd=[sys.executable,'-B','-m','pytest','-p','no:cacheprovider','-p','socket_deny',*selectors,'-q','-rf']
    p=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
    text=p.stdout+p.stderr;(OUT/(label+'.log')).write_text(text)
    failed=[x[7:].split(' - ')[0] for x in text.splitlines() if x.startswith('FAILED ')]
    return {'returncode':p.returncode,'failed_ids':failed,'command':['python',*cmd[1:]],'portable_path_normalization':'portable-path-normalized: interpreter only','log':label+'.log','log_sha256':sha(text.encode()),'caught':p.returncode==1 and bool(failed)}
def main():
    raw=TARGET.read_bytes();src=raw.decode()
    old=subprocess.check_output(['git','show',PIN+':backend/app/modules/m23_study_abroad/admitted_cases.py'],cwd=ROOT,text=True)
    old_fn=next(n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name=='fetch_case_metadata')
    new_fn=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=='fetch_case_metadata')
    body='\n'.join(old.splitlines()[old_fn.body[0].lineno-1:old_fn.end_lineno])+'\n'
    (OUT/'legacy-body.txt').write_text(body)
    lines=src.splitlines(keepends=True)
    true_old=''.join(lines[:new_fn.body[0].lineno-1])+body+''.join(lines[new_fn.end_lineno:])
    report={'base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'prior_source_pin':subprocess.check_output(['git','rev-parse',PIN],cwd=ROOT,text=True).strip(),'target_before_sha256':sha(raw),'old_body_sha256':sha(body.encode()),'limits':['body-only restoration, current signature retained','MockTransport plus socket-deny, no live HTTP acceptance','rc1 plus FAILED is crash-inclusive sensitivity, not intended-failure-only'],'baseline':run('baseline',SELECTORS),'probes':[]}
    assert report['baseline']['returncode']==0
    mutants=[('L8-true-legacy-body',true_old,SELECTORS),('L2-kwargs-sentinel',src.replace('return fetch_case_metadata_bounded(case_id, transport, **kwargs)','return fetch_case_metadata_bounded(case_id, transport)',1),[SELECTORS[0]+'::test_legacy_helper_is_a_pure_delegate_to_the_bounded_helper'])]
    for label,mutated,selectors in mutants:
        try:
            TARGET.write_text(mutated)
            item=run(label,selectors)
        finally:
            TARGET.write_bytes(raw)
        item.update(id=label,restore_sha256=sha(TARGET.read_bytes()),restore_verified=TARGET.read_bytes()==raw)
        assert item['restore_verified'] and item['caught'],item
        report['probes'].append(item)
    report['restored_baseline']=run('restored-baseline',SELECTORS)
    assert report['restored_baseline']['returncode']==0
    (OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
