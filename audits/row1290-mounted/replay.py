"""Replay exact row1290 mounted selector; retain failed IDs and verify restoration.

Usage: python audits/row1290-mounted/replay.py OUTPUT_DIRECTORY
Run in the repository root, with the desired interpreter and installed deps.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SELECTOR = 'tests/modules/test_row1290_mounted.py'
CONFIG = ROOT / 'audits/row1290-mounted/mutations.json'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run(out, name):
    cmd = [sys.executable, '-m', 'pytest', SELECTOR, '-q']
    p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / (name+'.log')).write_bytes(p.stdout)
    text = p.stdout.decode(errors='replace')
    return {'command': cmd, 'exit_code': p.returncode, 'log_sha256': sha(p.stdout),
            'failed_ids': [line[7:].split(' - ', 1)[0] for line in text.splitlines() if line.startswith('FAILED ')],
            'summary': next((s for s in reversed(text.splitlines()) if re.search(r'\d+ (passed|failed|error)',s)), '')}


def main():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    receipt = {'selector': SELECTOR, 'mutations': [], 'config_sha256': sha(CONFIG.read_bytes())}
    receipt['baseline'] = run(out, 'baseline')
    if receipt['baseline']['exit_code']:
        receipt['status'] = 'INVALID_BASELINE'
    else:
        for mutation in json.loads(CONFIG.read_text()):
            path = ROOT / mutation['path']
            original = path.read_bytes()
            entry = {'id': mutation['id'], 'path': mutation['path'], 'before_sha256': sha(original)}
            if original.count(mutation['old'].encode()) != 1:
                entry['status'] = 'INVALID'
                entry['reason'] = 'replacement is not unique'
            else:
                changed = original.replace(mutation['old'].encode(), mutation['new'].encode())
                try:
                    path.write_bytes(changed)
                    entry['mutated_sha256'] = sha(changed)
                    entry.update(run(out, mutation['id']))
                    entry['status'] = ('CAUGHT' if entry['exit_code'] == 1 and entry['failed_ids'] and ' ERROR ' not in (out/(mutation['id']+'.log')).read_text()
                                       else 'SURVIVED' if entry['exit_code'] == 0 else 'INVALID')
                finally:
                    path.write_bytes(original)
            entry['after_sha256'] = sha(path.read_bytes())
            entry['restore_verified'] = entry['after_sha256'] == entry['before_sha256']
            receipt['mutations'].append(entry)
            (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
            if not entry['restore_verified']:
                raise RuntimeError('source restoration failed')
        receipt['restored'] = run(out, 'restored')
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'baseline': receipt['baseline']['exit_code'], 'counts': {s: sum(m['status']==s for m in receipt['mutations']) for s in ['CAUGHT','SURVIVED','INVALID']}, 'restored': receipt.get('restored',{}).get('exit_code')}))


if __name__ == '__main__':
    main()
