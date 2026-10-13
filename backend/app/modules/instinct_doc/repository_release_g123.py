"""Group 123: produce and independently restore a local Git bundle artifact.

Reads trusted local checkouts; never executes repository code, checks out files,
contacts a remote, publishes a link or certifies project completion. Git bundle
history includes ancestor objects: review them before public disclosure.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

MAX_FILES = 50000
MAX_BYTES = 8000000
MAX_BUNDLE = 512000000


def _fail(reason):
    raise ValueError('REPORELEASE:' + reason)


def _env():
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_REPLACE_OBJECTS': '1'}


def _git(root, *args, limit=MAX_BYTES):
    # Disk capture avoids allocating unbounded stdout. Disk use is not quota-
    # contained; the process is trusted-local with a 30-second command deadline.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            result = subprocess.run(['git', '-c', 'core.fsmonitor=false',
                '-c', 'core.hooksPath=/dev/null', '-C', str(root), *args],
                env=_env(), stdout=out, stderr=err, timeout=30)
        except subprocess.TimeoutExpired:
            _fail('git_timeout')
        if result.returncode:
            _fail('git_failed')
        if out.tell() > limit:
            _fail('git_output_limit')
        out.seek(0)
        return out.read(limit+1)


def _digest_file(path, limit):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        _fail('unsafe_artifact')
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def _head(root):
    value = _git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value):
        _fail('bad_head')
    return value


def _contents(root, head):
    rows = _git(root, 'ls-tree', '-rz', '--full-tree', head).split(b'\0')
    files, modes = {}, {}
    for row in filter(None, rows):
        info, rawpath = row.split(b'\t', 1)
        mode, kind, object_id = info.decode().split()
        if mode not in ('100644', '100755') or kind != 'blob':
            _fail('unsupported_mode')
        path = rawpath.decode('utf-8')
        if not path or path.startswith('/') or '..' in Path(path).parts:
            _fail('unsafe_path')
        data = _git(root, 'cat-file', 'blob', object_id)
        files[path] = hashlib.sha256(data).hexdigest()
        modes[path] = mode
        if len(files) > MAX_FILES:
            _fail('file_limit')
    return files, modes


def _validate_manifest(s):
    keys = {'schema_version','head','files','modes','bundle_sha256','boundary'}
    if type(s) is not dict or set(s) != keys or s['schema_version'] != 1:
        _fail('unsafe_manifest')
    if not isinstance(s['head'], str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', s['head']):
        _fail('unsafe_manifest')
    if not isinstance(s['bundle_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', s['bundle_sha256']):
        _fail('unsafe_manifest')
    if type(s['files']) is not dict or not 1 <= len(s['files']) <= MAX_FILES:
        _fail('unsafe_manifest')
    if type(s['modes']) is not dict or s['modes'].keys() != s['files'].keys():
        _fail('unsafe_manifest')
    for name, digest in s['files'].items():
        if (not name or '\x00' in name or Path(name).is_absolute() or
            any(p in ('..','.git') for p in Path(name).parts) or
            not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}',digest) or
            s['modes'][name] not in ('100644','100755')):
            _fail('unsafe_manifest')


def replay_release(output):
    """Clone the bundle into a fresh bare repo and re-read restored object bytes.

    No worktree is created, so repository filters/hooks and executable files do
    not run. This proves local object restoration against this local manifest,
    not authenticity against a malicious writer controlling both artifacts.
    """
    output = Path(output)
    manifest_path = output/'manifest.json'
    if output.is_symlink() or manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > MAX_BYTES:
        _fail('unsafe_manifest')
    try:
        s=json.loads(manifest_path.read_text())
    except (ValueError, UnicodeError):
        _fail('unsafe_manifest')
    _validate_manifest(s)
    bundle=output/'repository.bundle'
    if _digest_file(bundle,MAX_BUNDLE) != s['bundle_sha256']:
        _fail('bundle_hash')
    with tempfile.TemporaryDirectory(prefix='atlas-restore-') as td:
        root=Path(td)/'restored.git'
        _git(td, 'clone','--bare','--no-local',str(bundle.resolve()),str(root))
        head=_head(root)
        files,modes=_contents(root,head)
        if head != s['head'] or files != s['files'] or modes != s['modes']:
            _fail('restored_content')
    return {'status':'LOCAL-RESTORE-REPLAYED','head':head,'files':files,'modes':modes,
            'remote_verified':False, 'bundle_path':str(bundle.resolve()),
            'manifest_path':str(manifest_path.resolve()),
            'boundary':'Actual local Git bundle restored and object bytes replayed; no hosted link, ownership or completion verification'}


def build_release(root, output):
    """Atomically produce a replayed bundle from a clean trusted local checkout."""
    root=Path(root).resolve(strict=True)
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():
        _fail('output_exists')
    if _git(root,'rev-parse','--show-toplevel').decode().strip() != str(root):
        _fail('top_level')
    if _git(root,'status','--porcelain','--untracked-files=all'):
        _fail('dirty')
    head=_head(root)
    files,modes=_contents(root,head)
    if not files:
        _fail('empty_repository')
    output.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.atlas-release-',dir=output.parent))
    try:
        bundle=staging/'repository.bundle'
        _git(root,'bundle','create',str(bundle),'HEAD')
        manifest={'schema_version':1,'head':head,'files':files,'modes':modes,
            'bundle_sha256':_digest_file(bundle,MAX_BUNDLE),
            'boundary':'Local committed bytes plus ancestor history; remote and ownership unverified'}
        (staging/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,ensure_ascii=True)+'\n')
        replay_release(staging)
        if _head(root) != head or _git(root,'status','--porcelain','--untracked-files=all'):
            _fail('source_changed')
        # Re-read local worktree bytes, not just object-store content.
        for name,digest in files.items():
            if _digest_file(root/name,MAX_BYTES) != digest:
                _fail('source_changed')
        if output.exists() or output.is_symlink():
            _fail('output_exists')
        os.rename(staging,output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return replay_release(output)
