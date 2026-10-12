"""Actual local tracked-file errors and independent repository bindings."""
import subprocess
from test_repository_evidence_binding import setup
from app.modules.instinct_doc.repo_register_p253 import bind_local_repositories


def test_tracked_symlink_error_does_not_promote_or_erase_other_entry(tmp_path):
    register,binding=setup(tmp_path)
    repo=tmp_path/'repo'
    clone=tmp_path/'healthy'
    subprocess.run(['git','clone','-q',repo.as_uri(),str(clone)],check=True)
    (repo/'link.py').symlink_to(repo/'code.py')
    subprocess.run(['git','-C',str(repo),'add','link.py'],check=True)
    other=dict(binding,entry_id='b',local_path='healthy',row_ids=['other-row'],project_ids=['other-project'])
    result=bind_local_repositories(register,tmp_path,[binding,other])
    broken,healthy=result['entries']
    assert broken['status']=='UNVERIFIED'
    assert broken['snapshot']['errors']
    assert broken['snapshot']['errors'][0]['path']=='link.py'
    assert broken['snapshot']['tracked_files']==1
    assert healthy['status']=='LOCAL-SNAPSHOT'
    assert healthy['snapshot']['errors']==[]
    assert result['counts']=={'LOCAL-SNAPSHOT':1,'UNVERIFIED':1}
    assert result['unbound_entry_ids']==[]
    assert result['repository_references']['b']=={'project_ids':['other-project','project'],'row_ids':['other-row']}
    assert not healthy['remote_verified'] and not healthy['ownership_verified']
    assert 'origin' not in healthy['snapshot']
    assert 'origin_sha256' not in healthy['snapshot']


def test_origin_configured_is_presence_not_locator_identity(tmp_path):
    register,binding=setup(tmp_path)
    repo=tmp_path/'repo'
    subprocess.run(['git','-C',str(repo),'remote','set-url','origin','https://example.invalid/different'],check=True)
    row=bind_local_repositories(register,tmp_path,[binding])['entries'][0]
    assert row['snapshot']['origin_configured'] is True
    assert row['snapshot']['tree_digest']
    assert 'different' not in str(row)
    assert row['remote_verified'] is False and row['ownership_verified'] is False
