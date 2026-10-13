"""Artifact/source byte binding, not declarations-as-truth."""
import pytest
from app.modules.instinct_doc.dataset_register_p254 import create_register, add_entry, bind_artifacts


def setup(tmp_path):
    (tmp_path / 'data.csv').write_bytes(b'id\n1\n')
    register = create_register()
    for ident, project in [('a', 'p1'), ('b', 'p2')]:
        register = add_entry(register, dict(id=ident, project_id=project, dataset='fixture', records=999,
                                          source='fixture-source', source_ref='fixture-ref'))
    binding = dict(entry_id='a', artifact_path='data.csv', row_ids=['row-1'], project_ids=['p1'])
    return register, binding


def test_every_declared_row_has_status(tmp_path):
    register, binding = setup(tmp_path)
    result = bind_artifacts(register, tmp_path, [binding])
    assert result['counts'] == {'VERIFIED': 0, 'DECLARED-ONLY': 0, 'UNVERIFIED': 2}
    assert result['entries'][0]['counted_records'] is None
    assert result['unbound_entry_ids'] == ['b']
    assert result['entries'][0]['declared_records'] == 999
    assert not result['entries'][0]['source_checked']


def test_executed_reader_required_for_verified(tmp_path):
    register, binding = setup(tmp_path)
    calls = []
    def reader(source, ref):
        calls.append((source, ref))
        return b'id\n1\n'
    result = bind_artifacts(register, tmp_path, [binding], source_reader=reader)
    assert calls == [('fixture-source', 'fixture-ref')]
    assert result['entries'][0]['provenance'] == 'UNVERIFIED'
    assert result['entries'][0]['counted_records'] is None
    assert result['entries'][0]['source_sha256'] == result['entries'][0]['artifact_sha256']


@pytest.mark.parametrize('value', [b'different', 'receipt', {'status': 'VERIFIED'}])
def test_mismatch_and_fake_receipts_refuse(tmp_path, value):
    register, binding = setup(tmp_path)
    result = bind_artifacts(register, tmp_path, [binding], source_reader=lambda *args: value)
    assert result['entries'][0]['provenance'] == 'UNVERIFIED'


@pytest.mark.parametrize('path', ['missing', '../escape', '/etc/passwd'])
def test_missing_or_unsafe_artifact_unverified(tmp_path, path):
    register, binding = setup(tmp_path)
    binding['artifact_path'] = path
    assert bind_artifacts(register, tmp_path, [binding])['entries'][0]['provenance'] == 'UNVERIFIED'


def test_crosslist_shared_artifact_references(tmp_path):
    register, binding = setup(tmp_path)
    other = dict(binding, entry_id='b', row_ids=['row-2'], project_ids=['p2'])
    result = bind_artifacts(register, tmp_path, [binding, other])
    references = next(iter(result['artifact_references'].values()))
    assert references == {'entry_ids': ['a', 'b'], 'project_ids': ['p1', 'p2'], 'row_ids': ['row-1', 'row-2']}


def test_supplied_verification_label_refused(tmp_path):
    register, binding = setup(tmp_path)
    binding['provenance'] = 'VERIFIED'
    with pytest.raises(ValueError, match='bad_fields'):
        bind_artifacts(register, tmp_path, [binding])


def test_source_reader_error_is_unverified(tmp_path):
    register, binding = setup(tmp_path)
    def unavailable(*args):
        raise OSError('unavailable')
    result = bind_artifacts(register, tmp_path, [binding], source_reader=unavailable)
    assert result['entries'][0]['provenance'] == 'UNVERIFIED'
    assert result['source_reader_injected']
    assert not result['source_authenticity_verified']


def test_symlink_artifact_rejected(tmp_path):
    register, binding = setup(tmp_path)
    (tmp_path / 'link').symlink_to(tmp_path / 'data.csv')
    binding['artifact_path'] = 'link'
    assert bind_artifacts(register, tmp_path, [binding])['entries'][0]['artifact_sha256'] is None


def test_local_separate_source_read_executes(tmp_path):
    register, binding = setup(tmp_path)
    (tmp_path / 'separate-source.csv').write_bytes(b'id\n1\n')
    result = bind_artifacts(register, tmp_path, [binding], source_reader=lambda *args: (tmp_path / 'separate-source.csv').read_bytes())
    assert result['entries'][0]['provenance'] == 'UNVERIFIED'
    assert result['entries'][0]['counted_records'] is None
    assert not result['source_authenticity_verified']


def test_empty_match_excluded_and_private_metadata_omitted(tmp_path):
    register, binding = setup(tmp_path)
    (tmp_path / 'data.csv').write_bytes(b'')
    row = bind_artifacts(register, tmp_path, [binding], source_reader=lambda *a: b'')['entries'][0]
    assert row['provenance'] == 'UNVERIFIED'
    assert row['empty_content_match']
    assert not row['source_authenticity_verified']
    assert 'source_metadata' not in row and 'artifact_path' not in row


def test_unexpected_reader_error_confined_to_row(tmp_path):
    register, binding = setup(tmp_path)
    def failed(*args):
        raise KeyError('unexpected')
    result = bind_artifacts(register, tmp_path, [binding], source_reader=failed)
    assert len(result['entries']) == 2
    assert result['entries'][0]['provenance'] == 'UNVERIFIED'
