from test_repository_evidence_binding import setup
from app.modules.instinct_doc.repo_register_p253 import bind_local_repositories


def test_internal_parent_traversal_still_refused(tmp_path):
    register,binding=setup(tmp_path)
    binding['local_path']='repo/../repo'
    row=bind_local_repositories(register,tmp_path,[binding])['entries'][0]
    assert row['status']=='UNVERIFIED'
