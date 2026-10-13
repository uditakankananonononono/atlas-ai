"""Actual hermetic Git repositories and bundle restoration, no remote calls."""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from app.modules.instinct_doc.repository_release_g123 import build_release, replay_release


def git(root, *args):
    return subprocess.run(['git','-C',str(root),*args], capture_output=True, check=True).stdout


def repo(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    git(root,'init','-q')
    git(root,'config','user.name','Fixture')
    git(root,'config','user.email','fixture@example.invalid')
    (root/'file.txt').write_bytes(b'actual committed bytes\n')
    git(root,'add','file.txt');git(root,'commit','-qm','fixture')
    return root


def test_actual_bundle_restores_committed_files(tmp_path):
    root=repo(tmp_path)
    out=tmp_path/'release'
    result=build_release(root,out)
    assert result['status']=='LOCAL-RESTORE-REPLAYED'
    assert result['head']==git(root,'rev-parse','HEAD').decode().strip()
    assert result['files']=={'file.txt':hashlib.sha256(b'actual committed bytes\n').hexdigest()}
    assert Path(result['bundle_path']).is_file()
    assert Path(result['manifest_path']).is_file()
    assert result['remote_verified'] is False
    again=replay_release(out)
    assert again['head']==result['head']
    assert again['files']==result['files']


def test_changed_bundle_refused(tmp_path):
    root=repo(tmp_path);out=tmp_path/'release';build_release(root,out)
    with (out/'repository.bundle').open('ab') as f:f.write(b'changed')
    with pytest.raises(ValueError,match='bundle_hash'):
        replay_release(out)


def test_changed_manifest_expected_files_refused(tmp_path):
    root=repo(tmp_path);out=tmp_path/'release';build_release(root,out)
    p=out/'manifest.json';s=json.loads(p.read_text());s['files']['file.txt']='0'*64;p.write_text(json.dumps(s))
    with pytest.raises(ValueError,match='restored_content'):
        replay_release(out)


@pytest.mark.parametrize('dirty',['tracked','untracked','deleted','staged'])
def test_dirty_repo_never_produces_release(tmp_path,dirty):
    root=repo(tmp_path)
    if dirty=='tracked':(root/'file.txt').write_text('changed')
    if dirty=='untracked':(root/'new.txt').write_text('untracked')
    if dirty=='deleted':(root/'file.txt').unlink()
    if dirty=='staged':
        (root/'file.txt').write_text('staged');git(root,'add','file.txt')
    with pytest.raises(ValueError,match='dirty'):
        build_release(root,tmp_path/'release')
    assert not (tmp_path/'release').exists()


def test_symlink_tracked_files_refused(tmp_path):
    root=repo(tmp_path);(root/'link').symlink_to('file.txt');git(root,'add','link');git(root,'commit','-qm','symlink')
    with pytest.raises(ValueError,match='unsupported_mode'):
        build_release(root,tmp_path/'release')


def test_preexisting_output_unchanged(tmp_path):
    root=repo(tmp_path);out=tmp_path/'release';out.mkdir();(out/'keep').write_text('keep')
    with pytest.raises(ValueError,match='output_exists'):
        build_release(root,out)
    assert (out/'keep').read_text()=='keep'


def test_subdirectory_input_refused(tmp_path):
    root=repo(tmp_path);(root/'nested').mkdir()
    with pytest.raises(ValueError,match='top_level'):
        build_release(root/'nested',tmp_path/'release')


def test_executable_mode_and_odd_filename_roundtrip(tmp_path):
    root=repo(tmp_path);p=root/'odd\nname.sh';p.write_text('#!/bin/sh\necho safe\n');p.chmod(0o755)
    git(root,'add','.');git(root,'commit','-qm','odd file')
    result=build_release(root,tmp_path/'release')
    assert result['modes']['odd\nname.sh']=='100755'
    assert len(result['files'])==2


def test_manifest_path_escape_refused(tmp_path):
    root=repo(tmp_path);out=tmp_path/'release';build_release(root,out)
    p=out/'manifest.json';s=json.loads(p.read_text());s['files']['../escape']='0'*64;p.write_text(json.dumps(s))
    with pytest.raises(ValueError,match='unsafe_manifest'):
        replay_release(out)


def test_head_tampering_refused(tmp_path):
    root=repo(tmp_path);out=tmp_path/'release';build_release(root,out)
    p=out/'manifest.json';s=json.loads(p.read_text());s['head']='0'*40;p.write_text(json.dumps(s))
    with pytest.raises(ValueError,match='restored_content'):
        replay_release(out)


def test_source_change_during_replay_refuses_and_cleans_output(tmp_path,monkeypatch):
    import app.modules.instinct_doc.repository_release_g123 as module
    root=repo(tmp_path);out=tmp_path/'release'
    original=module.replay_release
    def changed(output):
        result=original(output)
        (root/'file.txt').write_text('changed during restore')
        return result
    monkeypatch.setattr(module,'replay_release',changed)
    with pytest.raises(ValueError,match='source_changed'):
        build_release(root,out)
    assert not out.exists()
    assert not list(tmp_path.glob('.atlas-release-*'))


def test_ambient_git_redirect_does_not_change_source(tmp_path,monkeypatch):
    root=repo(tmp_path)
    wrong=tmp_path/'wrong';wrong.mkdir()
    monkeypatch.setenv('GIT_DIR',str(wrong))
    monkeypatch.setenv('GIT_WORK_TREE',str(wrong))
    result=build_release(root,tmp_path/'release')
    assert 'file.txt' in result['files']


def test_bundle_does_not_run_repository_hooks(tmp_path):
    root=repo(tmp_path);marker=tmp_path/'ran-hook'
    hook=root/'.git/hooks/post-checkout'
    hook.write_text('#!/bin/sh\ntouch '+str(marker)+'\n');hook.chmod(0o755)
    build_release(root,tmp_path/'release')
    assert not marker.exists()


def test_new_untracked_source_during_replay_refuses(tmp_path,monkeypatch):
    import app.modules.instinct_doc.repository_release_g123 as module
    root=repo(tmp_path);out=tmp_path/'release';original=module.replay_release
    def changed(output):
        result=original(output);(root/'not-in-bundle').write_text('new');return result
    monkeypatch.setattr(module,'replay_release',changed)
    with pytest.raises(ValueError,match='source_changed'):
        build_release(root,out)
    assert not out.exists()


@pytest.mark.parametrize('driver',['clean','process'])
def test_repository_defined_filters_refused_without_execution(tmp_path,driver):
    root=repo(tmp_path);marker=tmp_path/'filter-ran'
    # Commit attributes before defining the driver, so fixture setup never runs it.
    (root/'.gitattributes').write_text('file.txt filter=probe\n')
    git(root,'add','.gitattributes');git(root,'commit','-qm','attributes')
    git(root,'config',f'filter.probe.{driver}',f'touch {marker}; cat')
    (root/'file.txt').touch()
    with pytest.raises(ValueError,match='repository_filter'):
        build_release(root,tmp_path/'release')
    assert not marker.exists()
    assert not (tmp_path/'release').exists()


def test_filter_included_from_local_config_refused(tmp_path):
    root=repo(tmp_path);marker=tmp_path/'filter-ran'
    (root/'.gitattributes').write_text('file.txt filter=probe\n')
    git(root,'add','.gitattributes');git(root,'commit','-qm','attrs')
    config=tmp_path/'extra.conf';config.write_text(f'[filter "probe"]\n clean = touch {marker}; cat\n')
    git(root,'config','include.path',str(config))
    with pytest.raises(ValueError,match='repository_filter'):
        build_release(root,tmp_path/'release')
    assert not marker.exists()
