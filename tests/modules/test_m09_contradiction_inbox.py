from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {'X-Atlas-Tenant': 'tenant-science', 'X-Atlas-Actor': 'researcher'}


def test_contradiction_inbox_tracks_freshness_confidence_and_explicit_decision():
    payload = {
        'as_of': '2026-09-22T00:00:00Z', 'stale_after_days': 30,
        'evidence': [
            {'evidence_id':'doi-old','claim_key':'sample size','value':'120','source_uri':'https://doi.org/old','observed_at':'2026-07-01T00:00:00Z','confidence':.95},
            {'evidence_id':'registry-new','claim_key':'Sample Size','value':'150','source_uri':'https://example.org/registry','observed_at':'2026-09-20T00:00:00Z','confidence':.9},
            {'evidence_id':'same','claim_key':'species','value':'Arabidopsis','source_uri':'https://example.org/data','observed_at':'2026-09-21T00:00:00Z','confidence':.8},
        ],
        'decisions':[{'claim_key':'sample size','action':'retain_both','rationale':'Protocol and final registry report different stages.'}],
    }
    result = client.post('/api/v1/knowledge-workspace/contradiction-inbox', json=payload, headers=HEADERS)
    assert result.status_code == 200
    body = result.json()
    assert body['tenant_id'] == 'tenant-science'
    assert (body['contradiction_count'], body['decided_count'], body['unresolved_count']) == (1, 1, 0)
    item = body['inbox'][0]
    assert item['decision']['action'] == 'retain_both'
    assert item['recommended_review_order'][0] == 'registry-new'
    assert next(row for row in item['evidence'] if row['evidence_id']=='doi-old')['stale'] is True
    assert len(body['inbox_sha256']) == 64 and 'does not authenticate' in body['boundary']


def test_contradiction_inbox_rejects_invalid_preference_and_duplicate_evidence():
    base = {
        'evidence': [
            {'evidence_id':'a','claim_key':'dose','value':'10 mg','source_uri':'https://example.org/a','observed_at':'2026-09-20T00:00:00Z','confidence':.8},
            {'evidence_id':'b','claim_key':'dose','value':'20 mg','source_uri':'https://example.org/b','observed_at':'2026-09-21T00:00:00Z','confidence':.9},
        ],
        'decisions':[{'claim_key':'dose','action':'prefer','preferred_evidence_id':'missing','rationale':'newer'}],
    }
    response = client.post('/api/v1/knowledge-workspace/contradiction-inbox', json=base, headers=HEADERS)
    assert response.status_code == 422 and 'not part' in response.text
    base['evidence'][1]['evidence_id'] = 'a'
    base['decisions'] = []
    response = client.post('/api/v1/knowledge-workspace/contradiction-inbox', json=base, headers=HEADERS)
    assert response.status_code == 422 and 'duplicate evidence_id' in response.text
