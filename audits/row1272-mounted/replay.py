"""Real-conftest mounted production-site sensitivity, trusted local tests only."""
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

R = Path(__file__).resolve().parents[2]
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def execute(output, ids=None):
    os.chdir(R)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('evidence output exists')
    output.mkdir(parents=True)
    specpath = R / 'audits/row1272-mounted/operators.json'
    spec = json.loads(specpath.read_text())
    if ids:
        wanted = set(ids.split(','))
        known = {m['id'] for m in spec['mutations']}
        if not wanted <= known:
            raise ValueError('unknown operator id')
        spec['mutations'] = [m for m in spec['mutations'] if m['id'] in wanted]
    loader = importlib.util.spec_from_file_location('classifier', R / 'scripts/release/scoped_mutations.py')
    classifier = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(classifier)
    env = dict(os.environ, PYTHONPATH='backend', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               ATLAS_M10_TIMESTAMP_SCHEME='off')

    def run(name):
        with tempfile.TemporaryDirectory(prefix='row1272-pycache-') as cache:
            argv = [sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider',
                    *spec['selectors'], '-q', '-rf']
            proc = subprocess.run(argv, env=dict(env, PYTHONPYCACHEPREFIX=cache),
                                  capture_output=True, text=True, timeout=spec['timeout_seconds'])
        text = proc.stdout + proc.stderr
        (output / (name + '.log')).write_text(text)
        status, failed = classifier.classify(proc.returncode, text)
        return {'returncode': proc.returncode, 'status': status, 'failed_tests': failed,
                'argv': ['PYTHON3_12', *argv[1:]], 'log_sha256': sha(text.encode())}

    report = {'checkout': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
              'status': subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip(),
              'spec_sha256': sha(specpath.read_bytes()), 'baseline': run('baseline'), 'mutations': [],
              'limits': ['real unchanged conftest; no engine/application stubs',
                         'locally signed OIDC fixture, not external issuer proof',
                         'FAILED sensitivity, not assertion-only; no ERROR or SKIP credit',
                         'trusted local tests, not hostile process isolation']}
    if report['baseline']['returncode'] == 0 and report['baseline']['status'] == 'SURVIVED':
        for mutation in spec['mutations']:
            p = R / mutation['path']
            raw = p.read_bytes()
            text = raw.decode()
            item = {'id': mutation['id'], 'path': mutation['path'], 'source_sha256_before': sha(raw)}
            if text.count(mutation['old']) != 1:
                item.update(status='INVALID-SITE', restore_verified=True, restored_sha256=sha(raw))
            else:
                changed = text.replace(mutation['old'], mutation['new'], 1)
                (output / (mutation['id'] + '.diff')).write_text(''.join(difflib.unified_diff(
                    text.splitlines(keepends=True), changed.splitlines(keepends=True),
                    fromfile=mutation['path'], tofile=mutation['path'])))
                try:
                    p.write_text(changed)
                    item['mutated_sha256'] = sha(p.read_bytes())
                    try:
                        item.update(run(mutation['id']))
                    except subprocess.TimeoutExpired:
                        item.update(status='TIMEOUT-UNTESTED', returncode=None, failed_tests=[])
                finally:
                    p.write_bytes(raw)
                    item.update(restored_sha256=sha(p.read_bytes()), restore_verified=p.read_bytes() == raw)
                    if not item['restore_verified']:
                        raise RuntimeError('source restore failed')
            report['mutations'].append(item)
    report['all_caught'] = (report['baseline']['status'] == 'SURVIVED' and
                            bool(report['mutations']) and
                            all(m['status'] == 'CAUGHT' and m['restore_verified'] for m in report['mutations']))
    (output / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    parser.add_argument('--ids')
    args = parser.parse_args()
    result = execute(args.output, args.ids)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['all_caught'] else 1)
