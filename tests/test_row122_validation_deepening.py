"""Task selector exact boundaries on local Git fixtures, no completion proof."""
import subprocess
import pytest
from test_task_progress_evidence import repo
from app.modules.instinct_doc.repo_evidence import EvidenceError,task_progress

@pytest.mark.parametrize('case',['limit','selectors','paths','duplicates'])
def test_task_exact_upper_edges_and_unique_paths(repo,case):
    root,selector=repo;selectors=[selector];limit=100
    if case=='limit':limit=1001
    if case=='selectors':selectors=[dict(selector,task_id='T'+str(i)) for i in range(1001)]
    if case=='duplicates':selectors=[dict(selector,paths=['code.py','code.py'])]
    if case=='paths':
        paths=['file'+str(i)+'.py' for i in range(101)]
        for path in paths:(root/path).write_text('x=1\n')
        subprocess.run(['git','-C',str(root),'add','.'],check=True)
        subprocess.run(['git','-C',str(root),'commit','-qm','path-bound fixture'],check=True)
        selectors=[dict(selector,paths=paths)]
    with pytest.raises(EvidenceError):task_progress(root,'source.txt',selectors,limit=limit)
