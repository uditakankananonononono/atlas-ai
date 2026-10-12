"""Exact single-site mutation runner for trusted local repository tests.

CAUGHT means rc=1 plus FAILED test IDs, with no ERROR/collection or skip outcome.
This is failed-test sensitivity, not an assertion-only exception classifier.
Timeouts, crashes, missing replacement sites, skips and collection errors are
not caught evidence. Every source restore is checked against its byte SHA256.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


def digest(raw):return hashlib.sha256(raw).hexdigest()


def classify(rc, text):
    failed=re.findall(r'^FAILED ([^\n]+?)(?: - |$)',text,re.M)
    errors=bool(re.search(r'^ERROR |collection error|ERROR collecting|Interrupted:',text,re.M))
    skipped=bool(re.search(r'\b\d+ skipped\b|^SKIPPED ',text,re.M))
    if rc==1 and failed and not errors and not skipped:return 'CAUGHT',failed
    if rc==0:
        if re.search(r'\b\d+ skipped\b',text):return 'SURVIVED-WITH-SKIPS',[]
        return 'SURVIVED',[]
    return 'INVALID',failed


def run_case(selectors, timeout, env):
    # JSON pytest bytecode caches can mask rapid equal-size source replacements.
    with tempfile.TemporaryDirectory(prefix='mutant-pycache-') as cache:
        runenv=dict(env,PYTHONPYCACHEPREFIX=cache)
        command=[sys.executable,'-m','pytest','--noconftest','-p','no:cacheprovider',*selectors,'-q','-rf']
        started=time.monotonic()
        try:
            run=subprocess.run(command,capture_output=True,text=True,env=runenv,timeout=timeout)
            text=run.stdout+run.stderr
            status,failed=classify(run.returncode,text)
            return {'argv':command,'returncode':run.returncode,'status':status,'failed_tests':failed,'seconds':time.monotonic()-started,'output':text}
        except subprocess.TimeoutExpired as exc:
            return {'argv':command,'returncode':None,'status':'TIMEOUT-UNTESTED','failed_tests':[],'seconds':time.monotonic()-started,'output':str(exc)}


def execute(spec_path, output):
    spec=json.loads(Path(spec_path).read_text());output=Path(output)
    if output.exists():raise ValueError('evidence output exists')
    output.mkdir(parents=True)
    env=dict(os.environ,PYTHONPATH='backend',ATLAS_DEV_NO_AUTH='1',ATLAS_ENV='development')
    env.update(spec.get('environment',{}))
    baseline=run_case(spec['selectors'],spec['timeout_seconds'],env)
    baseline['status']='PASS' if baseline['returncode']==0 and baseline['status']=='SURVIVED' else 'BASELINE-NOT-RELEASED'
    (output/'baseline.log').write_text(baseline.pop('output'))
    tracked=subprocess.run(['git','ls-files','-z','backend','scripts','tests','audits'],capture_output=True,check=True).stdout.split(b'\0')
    snapshot={}
    for entry in tracked:
        if entry:
            path=Path(os.fsdecode(entry))
            if path.is_file() and not path.is_symlink():snapshot[str(path)]=digest(path.read_bytes())
    identity={key:subprocess.check_output(['git',*args],text=True).strip() for key,args in {
        'head':['rev-parse','HEAD'],'head_tree':['rev-parse','HEAD^{tree}'],'status':['status','--porcelain']}.items()}
    report={'checkout':identity,'tracked_code_test_hashes':snapshot,'row':spec['row'],'spec_sha256':digest(Path(spec_path).read_bytes()),'baseline':baseline,'baseline_log_sha256':digest((output/'baseline.log').read_bytes()),'mutations':[],
            'environment':{k:env[k] for k in ['PYTHONPATH','ATLAS_DEV_NO_AUTH','ATLAS_ENV',*spec.get('environment',{})]},'limits':spec['limits']}
    if baseline['status']=='PASS':
        for mutation in spec['mutations']:
            path=Path(mutation['path']);raw=path.read_bytes();before=digest(raw);text=raw.decode()
            item={'id':mutation['id'],'path':str(path),'source_sha256_before':before}
            if text.count(mutation['old'])!=1:
                item.update(status='INVALID-SITE',restored_sha256=before,restore_verified=True)
            else:
                try:
                    path.write_text(text.replace(mutation['old'],mutation['new'],1))
                    run=run_case(spec['selectors'],spec['timeout_seconds'],env)
                    log=run.pop('output');(output/(mutation['id']+'.log')).write_text(log)
                    item.update(run,log_sha256=digest(log.encode()))
                finally:
                    path.write_bytes(raw)
                    item['restored_sha256']=digest(path.read_bytes());item['restore_verified']=item['restored_sha256']==before
                    if not item['restore_verified']:raise RuntimeError('source SHA restore failed')
            report['mutations'].append(item)
    report['all_caught']=baseline['status']=='PASS' and bool(report['mutations']) and all(m['status']=='CAUGHT' and m['restore_verified'] for m in report['mutations'])
    (output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('spec');parser.add_argument('output');args=parser.parse_args()
    result=execute(args.spec,args.output);print(json.dumps(result,indent=2));raise SystemExit(0 if result['all_caught'] else 1)
