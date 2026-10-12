"""Replay two pkg8 probes on a trusted checkout; never use transport=None.
The old function BODY is hash-checked retained evidence from historical Git71533733. Keep the current signature
so kwargs calls reach old behavior instead of failing only at argument binding.
Full logs and per-probe restore hashes are retained; historical receipts untouched.
"""
import ast,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
TARGET=ROOT/'backend/app/modules/m23_study_abroad/admitted_cases.py'
PIN='715337337dc704cf18085128fef3ad24f8e88021'
BODY_SHA256='76e00134fa6e9d61c9e68c03747aef5d43d21074fa58fd0c70050f064c2cc9af'
SELECTORS=['tests/modules/test_m23_admitted_cases_legacy_delegation.py','tests/modules/test_m23_admitted_cases_crawl_delay.py','tests/modules/test_m23_admitted_cases_bounded.py','tests/modules/test_m23_admitted_cases.py']
def sha(raw):return hashlib.sha256(raw).hexdigest()
def run(label,selectors):
    env=dict(os.environ,PYTHONPATH=os.pathsep.join(['backend',str(OUT)]),ATLAS_DEV_NO_AUTH='1',ATLAS_ENV='development',PYTHONDONTWRITEBYTECODE='1')
    cmd=[sys.executable,'-B','-m','pytest','-p','no:cacheprovider','-p','socket_deny',*selectors,'-q','-rf']
    p=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
    text=p.stdout+p.stderr;(OUT/(label+'.log')).write_text(text)
    failed=[x[7:].split(' - ')[0] for x in text.splitlines() if x.startswith('FAILED ')]
    return {'returncode':p.returncode,'failed_ids':failed,'command':['python',*cmd[1:]],'portable_path_normalization':'portable-path-normalized: interpreter only','log':label+'.log','log_sha256':sha(text.encode()),'caught':p.returncode==1 and bool(failed)}
def load_legacy_body():
    raw=(OUT/'legacy-body.txt').read_bytes()
    if sha(raw)!=BODY_SHA256:raise ValueError('retained legacy body SHA mismatch')
    body=raw.decode()
    found=subprocess.run(['git','show',PIN+':backend/app/modules/m23_study_abroad/admitted_cases.py'],cwd=ROOT,capture_output=True,text=True)
    comparison='unavailable'
    if found.returncode==0:
        old=found.stdout
        fn=next(n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name=='fetch_case_metadata')
        derived='\n'.join(old.splitlines()[fn.body[0].lineno-1:fn.end_lineno])+'\n'
        if derived!=body:raise ValueError('available historical body disagrees with retained bytes')
        comparison='matched'
    return body,comparison

def kwargs_mutant(src):
    old='return fetch_case_metadata_bounded(case_id, transport, **kwargs)'
    if src.count(old)!=1:raise ValueError('delegate replacement site must occur exactly once')
    return src.replace(old,'return fetch_case_metadata_bounded(case_id, transport)',1)

def main():
    raw=TARGET.read_bytes();src=raw.decode()
    body,comparison=load_legacy_body()
    new_fn=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=='fetch_case_metadata')
    lines=src.splitlines(keepends=True)
    true_old=''.join(lines[:new_fn.body[0].lineno-1])+body+''.join(lines[new_fn.end_lineno:])
    report={'base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'prior_source_pin':PIN,'historical_body_comparison':comparison,'target_before_sha256':sha(raw),'old_body_sha256':sha(body.encode()),'limits':['body-only restoration, current signature retained','MockTransport plus socket-deny, no live HTTP acceptance','rc1 plus FAILED is crash-inclusive sensitivity, not intended-failure-only'],'baseline':run('baseline',SELECTORS),'probes':[]}
    assert report['baseline']['returncode']==0
    mutants=[('L8-true-legacy-body',true_old,SELECTORS),('L2-kwargs-sentinel',kwargs_mutant(src),[SELECTORS[0]+'::test_legacy_helper_is_a_pure_delegate_to_the_bounded_helper'])]
    for label,mutated,selectors in mutants:
        try:
            TARGET.write_text(mutated)
            item=run(label,selectors)
        finally:
            TARGET.write_bytes(raw)
        item.update(id=label,mutant_sha256=sha(mutated.encode()),restore_sha256=sha(TARGET.read_bytes()),restore_verified=TARGET.read_bytes()==raw)
        assert item['restore_verified'] and item['caught'],item
        report['probes'].append(item)
    report['restored_baseline']=run('restored-baseline',SELECTORS)
    assert report['restored_baseline']['returncode']==0
    (OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
