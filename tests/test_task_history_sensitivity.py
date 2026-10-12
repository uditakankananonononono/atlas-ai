"""Actual local shallow Git history; no remote ownership or semantic completion."""
import subprocess
from app.modules.instinct_doc.repo_evidence import source_inventory, task_progress
from test_task_progress_evidence import repo


def test_depth_one_clone_discloses_history_boundary(repo, tmp_path):
    root, selector = repo
    (root/'code.py').write_text('x=2\n')
    subprocess.run(['git','-C',str(root),'add','.'],check=True)
    subprocess.run(['git','-C',str(root),'commit','-qm','second'],check=True)
    clone=root.parent/(root.name+'-shallow')
    subprocess.run(['git','clone','-q','--depth','1',root.as_uri(),str(clone)],check=True)
    line=source_inventory(clone,'source.txt')['rows'][0]
    selector=dict(selector,line_id=line['id'],line_sha256=line['sha256'])
    result=task_progress(clone,'source.txt',[selector],limit=100)
    assert result['shallow_history'] is True
    assert result['history_may_be_truncated'] is True
    assert result['commits_inspected']==1
    event=result['tasks'][0]['events'][0]
    assert event['root_or_shallow_boundary'] is True
    assert event['status']=='ROOT_OR_BOUNDARY_SNAPSHOT'
    assert event['commit_at']
    assert event['task_time_anchor_verified'] is False
    assert result['tasks'][0]['completion_verified'] is False
