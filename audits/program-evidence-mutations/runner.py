"""Mutation receipts for trusted local checkouts: rc1 plus FAILED test IDs.
FAILED includes product KeyError/RuntimeError, not just assertions. Text containing
ERROR-space or ERROR-at is rejected; timeout is uncredited. Mixed FAILED plus SKIP
is not rejected. Counts measure failure sensitivity, not assertion-only kills.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(config):
    output = Path(__file__).parent / ('row' + str(config['row']))
    output.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT/'backend'), PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, '-m', 'pytest', '--noconftest', '-p', 'no:cacheprovider',
               *config['tests'], '-q', '-rf', '--tb=short']
    def invoke(label):
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
            text = result.stdout + result.stderr
            failed = [line.split(' - ')[0][7:] for line in text.splitlines() if line.startswith('FAILED ')]
            verdict = 'SURVIVED' if result.returncode == 0 else 'CAUGHT' if result.returncode == 1 and failed and 'ERROR ' not in text and 'ERROR at' not in text else 'INVALID'
            code = result.returncode
        except subprocess.TimeoutExpired as exc:
            text, failed, verdict, code = 'TIMEOUT', [], 'INVALID', None
        (output/(label+'.log')).write_text('\n'.join(line.rstrip() for line in text.splitlines())+'\n')
        return {'returncode':code,'verdict':verdict,'failed_test_ids':failed,'log':label+'.log'}
    baseline = invoke('baseline')
    if baseline['returncode'] != 0:
        raise RuntimeError('baseline must pass; see ' + str(output))
    receipts = []
    for mutant in config['mutants']:
        path = ROOT/mutant['file']
        original = path.read_bytes()
        before = sha(original)
        old, new = mutant['old'], mutant['new']
        if original.decode().count(old) != 1:
            receipts.append({'id':mutant['id'],'verdict':'NOT-APPLICABLE','reason':'exact target must occur once'})
            continue
        changed = original.decode().replace(old,new,1).encode()
        path.write_bytes(changed)
        try:
            result = invoke(mutant['id'])
        finally:
            path.write_bytes(original)
        restored = sha(path.read_bytes()) == before
        if not restored:
            raise RuntimeError('restore digest mismatch')
        receipts.append(dict(id=mutant['id'], target=mutant['file'], before_sha256=before,
                             mutant_sha256=sha(changed), restored_sha256=sha(path.read_bytes()),
                             restore_verified=restored, **result))
    after = invoke('restored-baseline')
    result = {'row':config['row'],'command':['python', *command[1:]],
              'portable_path_normalization':'portable-path-normalized: command[0] replaced for delivery; interpreter identity remains execution-environment metadata','baseline':baseline,'restored_baseline':after,
              'mutants':receipts,'counts':{state:sum(r['verdict']==state for r in receipts) for state in ('CAUGHT','SURVIVED','INVALID','NOT-APPLICABLE')},
              'evidence_tier':config['tier'], 'limits':config['limits']}
    (output/'receipts.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'row':config['row'],'counts':result['counts'],'restored_baseline_exit':after['returncode']}))
    return result


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[1]).read_text()))
