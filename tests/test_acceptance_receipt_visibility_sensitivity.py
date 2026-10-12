"""Controlled same-inventory/different-byte source change sensitivity."""
from test_executed_acceptance import repo
from app.modules.instinct_doc import executed_acceptance as mod


def test_actual_source_byte_hash_remains_required(repo,monkeypatch):
    root,check=repo;original_source=mod.source_inventory
    original=original_source(root,'source.txt');snap=mod.snapshot(root)
    monkeypatch.setattr(mod,'source_inventory',lambda *a:original)
    monkeypatch.setattr(mod,'snapshot',lambda *a:snap)
    def changed(*args):
        (root/'source.txt').write_bytes(b'different current bytes')
        return {'status':'SCOPED_PASS','head':snap['head'],'tree_digest':snap['tree_digest']}
    monkeypatch.setattr(mod,'execute_tests',changed)
    out=mod.audit_selected_checks(root,'source.txt',[check])
    assert out['source_stable_after_runs'] is False
    assert out['scoped_passing_lines']==0
