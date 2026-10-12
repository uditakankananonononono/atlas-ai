from test_executed_acceptance import repo
from app.modules.instinct_doc.executed_acceptance import audit_selected_checks


def test_dependency_scope_never_verified_by_selected_tests(repo):
    root,check=repo
    out=audit_selected_checks(root,'source.txt',[check])
    assert out['dependency_scope_verified'] is False
