"""Static integration evidence cannot authenticate working external use."""
import pytest
from app.modules.instinct_doc.integrations_register_p255 import create_register, append, bind_local_evidence


def setup(tmp_path):
    (tmp_path / 'adapter.py').write_text('def adapter(): pass\n')
    (tmp_path / 'use.json').write_text('{"status":"VERIFIED"}')
    r = create_register()
    for ident in ['one', 'two']:
        r = append(r, dict(id=ident, project_id='project', name=ident, purpose='fixture', status='active'))
    b = dict(entry_id='one', adapter_path='adapter.py', use_evidence_path='use.json', row_ids=['row'], project_ids=['project'])
    return r, b


def test_local_artifacts_do_not_authenticate_live_use(tmp_path):
    r, b = setup(tmp_path)
    out = bind_local_evidence(r, tmp_path, [b])
    assert out['counts'] == {'DECLARED-ONLY': 1, 'UNVERIFIED': 1}
    assert out['unbound_entry_ids'] == ['two']
    assert out['entries'][0]['adapter_sha256']
    assert not out['entries'][0]['live_working_use_verified']
    assert out['working_external_tool_count'] is None
    assert out['integration_references']['one']['row_ids'] == ['row']


@pytest.mark.parametrize('path', ['', 'absent', '../escape', '/etc/passwd'])
def test_missing_unsafe_use_unverified(tmp_path, path):
    r, b = setup(tmp_path)
    b['use_evidence_path'] = path
    assert bind_local_evidence(r, tmp_path, [b])['entries'][0]['status'] == 'UNVERIFIED'


def test_declared_active_and_fake_receipt_cannot_verify(tmp_path):
    r, b = setup(tmp_path)
    out = bind_local_evidence(r, tmp_path, [b])
    assert out['entries'][0]['declared_status'] == 'active'
    assert out['entries'][0]['status'] == 'DECLARED-ONLY'
    b['status'] = 'VERIFIED'
    with pytest.raises(ValueError, match='bad_fields'):
        bind_local_evidence(r, tmp_path, [b])


def test_duplicate_binding_refused(tmp_path):
    r, b = setup(tmp_path)
    with pytest.raises(ValueError, match='duplicate'):
        bind_local_evidence(r, tmp_path, [b, b])


def test_exact_hash_and_content_change(tmp_path):
    import hashlib
    r, b = setup(tmp_path)
    first = bind_local_evidence(r, tmp_path, [b])['entries'][0]
    assert first['adapter_sha256'] == hashlib.sha256(b'def adapter(): pass\n').hexdigest()
    assert first['use_evidence_sha256'] == hashlib.sha256(b'{"status":"VERIFIED"}').hexdigest()
    (tmp_path / 'adapter.py').write_bytes(b'changed')
    second = bind_local_evidence(r, tmp_path, [b])['entries'][0]
    assert second['adapter_sha256'] == hashlib.sha256(b'changed').hexdigest()
    assert second['adapter_sha256'] != first['adapter_sha256']


def test_nul_path_per_file_error(tmp_path):
    r, b = setup(tmp_path)
    b['adapter_path'] = 'bad\x00path'
    out = bind_local_evidence(r, tmp_path, [b])
    assert out['entries'][0]['status'] == 'UNVERIFIED'
    assert 'adapter_path' in out['entries'][0]['file_errors']
    assert out['entries'][1]['status'] == 'UNVERIFIED'
