from test_executed_acceptance import repo
from app.modules.instinct_doc.executed_acceptance import audit_selected_checks


def test_every_blocker_status_unverified(repo):
    root,check=repo
    out=audit_selected_checks(root,'source.txt',[check])
    assert all(row['status']=='UNVERIFIED' for row in out['blockers'])
