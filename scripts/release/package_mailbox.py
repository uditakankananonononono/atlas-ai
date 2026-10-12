"""Create a verified git-am mailbox and external, non-self-referential receipt.

Runs only explicitly named repository test files. This is a local release
packager, not authorization to publish, push or run external effects.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

IDENTITY = ('Instinct', 'agent@instinct.com')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def package(repo, base, head, selectors, python, output, timeout=120):
    repo = Path(repo).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('output already exists; refuse to overwrite evidence')
    base = git(repo, 'rev-parse', '--verify', base + '^{commit}')
    head = git(repo, 'rev-parse', '--verify', head + '^{commit}')
    subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', base, head], check=True)
    commits = git(repo, 'rev-list', '--reverse', base + '..' + head).splitlines()
    if not commits:
        raise ValueError('empty release range')
    for commit in commits:
        identity = git(repo, 'show', '-s', '--format=%an%n%ae%n%cn%n%ce', commit).splitlines()
        if identity != [*IDENTITY, *IDENTITY]:
            raise ValueError('release commit identity mismatch')
    if not selectors:
        raise ValueError('explicit test files required')
    for selector in selectors:
        path = Path(selector)
        if path.is_absolute() or '..' in path.parts or not selector.startswith('tests/') or path.suffix != '.py':
            raise ValueError('selector must be an explicit repository test file')
        if not (repo / path).is_file():
            raise ValueError('test file missing')
    if git(repo, 'status', '--porcelain'):
        raise ValueError('release checkout must be clean')
    if git(repo, 'rev-parse', 'HEAD') != head:
        raise ValueError('test checkout must match release head')
    output.mkdir(parents=True)
    argv = [python, '-m', 'pytest', '--noconftest', *selectors, '-q']
    env = dict(os.environ, PYTHONPATH='backend', ATLAS_DEV_NO_AUTH='1', ATLAS_ENV='development')
    log = output / 'selector.log'
    timed_out = False
    with log.open('wb') as stream:
        try:
            run = subprocess.run(argv, cwd=repo, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            returncode = run.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = None
    mailbox = output / 'repair.mbox'
    with mailbox.open('wb') as stream:
        subprocess.run(['git', '-C', str(repo), 'format-patch', '--stdout', '--full-index', '--binary', base + '..' + head], stdout=stream, check=True)
    with tempfile.TemporaryDirectory(prefix='mailbox-check-') as root:
        checkout = Path(root) / 'checkout'
        subprocess.run(['git', '-C', str(repo), 'worktree', 'add', '--detach', str(checkout), base], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            subprocess.run(['git', '-C', str(checkout), '-c', 'user.name=Instinct', '-c', 'user.email=agent@instinct.com', 'am', str(mailbox)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            applied = git(checkout, 'rev-list', base + '..HEAD').splitlines()
            if len(applied) != len(commits):
                raise ValueError('git-am commit count mismatch')
            for commit in applied:
                identity = git(checkout, 'show', '-s', '--format=%an%n%ae%n%cn%n%ce', commit).splitlines()
                if identity != [*IDENTITY, *IDENTITY]:
                    raise ValueError('git-am identity mismatch')
            actual_tree = git(checkout, 'rev-parse', 'HEAD^{tree}')
            if actual_tree != git(repo, 'rev-parse', head + '^{tree}'):
                raise ValueError('git-am composition tree mismatch')
        finally:
            subprocess.run(['git', '-C', str(repo), 'worktree', 'remove', '--force', str(checkout)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    receipt = {
        'schema': 1, 'base_commit': base, 'base_tree': git(repo, 'rev-parse', base + '^{tree}'),
        'result_commit': head, 'result_tree': actual_tree, 'commits': commits,
        'mailbox_sha256': sha256(mailbox), 'selector_log_sha256': sha256(log),
        'selector_argv': argv, 'selector_environment': {'PYTHONPATH': 'backend', 'ATLAS_DEV_NO_AUTH': '1', 'ATLAS_ENV': 'development'},
        'python_version': subprocess.check_output([python, '--version'], text=True).strip(),
        'test_result': 'UNTESTED-TIMEOUT' if timed_out else ('PASS' if returncode == 0 else 'FAIL'),
        'returncode': returncode, 'timeout_seconds': timeout,
        'git_am_tree_verified': True, 'identity': {'author': list(IDENTITY), 'committer': list(IDENTITY)},
        'untested': ['historical mutation batteries not rerun', 'repository-wide regression', 'live integrations and provider effects', 'timeout descendants: trusted local test process only, no process-group isolation'],
    }
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='.')
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', default='HEAD')
    parser.add_argument('--selector', action='append', required=True)
    parser.add_argument('--python', default='python')
    parser.add_argument('--output', required=True)
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    receipt = package(args.repo, args.base, args.head, args.selector, args.python, args.output, args.timeout)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt['test_result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
