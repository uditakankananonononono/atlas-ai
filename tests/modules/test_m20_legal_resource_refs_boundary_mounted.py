"""Pin resource_refs' 64-item limit on each dedicated mounted legal route."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

CASES = [
    (1300, {'row': 1300, 'as_of': '2026-10-12', 'entries': [{'element': 'dataset_provenance', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}),
    (1301, {'row': 1301, 'as_of': '2026-10-12', 'entries': [{'element': 'protocol', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}),
    (1302, {'row': 1302, 'as_of': '2026-10-12', 'entries': [{'element': 'document_hash', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}),
    (1303, {'row': 1303, 'as_of': '2026-10-12', 'entries': [{'element': 'matter_owner', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}),
    (1304, {'row': 1304, 'as_of': '2026-10-12', 'entries': [{'element': 'staffing', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}),
    (1305, {'batch_id': 'sample', 'entries': [{'entry_id': 'entry-1', 'matter_id': 'matter-A', 'hours': '1.5', 'rate': '20'}]}),
    (1306, {'row': 1306, 'as_of': '2026-10-12', 'entries': [{'element': 'scope', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}),
    (1307, {'row': 1307, 'as_of': '2026-10-12', 'entries': [{'element': 'deliverables', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}),
    (1308, {'row': 1308, 'as_of': '2026-10-12', 'entries': [{'element': 'artifact_provenance', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}),
    (1309, {'row': 1309, 'as_of': '2026-10-12', 'entries': [{'element': 'audience', 'status': 'supplied', 'source_ref': 'reference-A', 'entry_date': '2026-10-01'}]}),
]


@pytest.fixture(autouse=True)
def production_identity(monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH', '0')
    monkeypatch.setenv('ATLAS_ENV', 'production')


@pytest.mark.parametrize('row,data', CASES)
def test_resource_refs_count_boundary_over_mounted_legal_app(oidc_auth_headers, row, data):
    path = f'/api/v1/api/modules/20/legal/{row}/run'
    headers = oidc_auth_headers('tenant-a', 'owner')
    owned_ref = {'tenant_id': 'tenant-a'}

    with TestClient(app) as client:
        at_cap = client.post(path, json={'data': data, 'resource_refs': [owned_ref] * 64}, headers=headers)
        assert at_cap.status_code == 200, at_cap.text

        over_cap = client.post(path, json={'data': data, 'resource_refs': [owned_ref] * 65}, headers=headers)
        assert over_cap.status_code == 422, over_cap.text
        assert any(error.get('type') == 'too_long' for error in over_cap.json()['detail'])
