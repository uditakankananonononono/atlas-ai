from test_executed_acceptance import repo
from app.modules.instinct_doc.executed_acceptance import audit_selected_checks


def test_each_semantic_flag_false_despite_scoped_pass(repo):
    root,check=repo
    out=audit_selected_checks(root,'source.txt',[check])
    assert all(row['semantic_fulfillment_verified'] is False for row in out['lines'])
