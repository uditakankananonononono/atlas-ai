from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {'X-Atlas-Tenant': 'lab', 'X-Atlas-Actor': 'owner'}
URL = '/api/v1/email-assistant/promise-tracker'


def test_tracks_only_owner_promises_and_never_creates_followup():
    payload = {
        'thread_id':'thread-1', 'as_of':'2026-09-22T02:00:00Z', 'due_soon_hours':48,
        'messages':[
            {'message_id':'other','direction':'other','sent_at':'2026-09-21T10:00:00Z','body':"I'll send the dataset tomorrow."},
            {'message_id':'owner-a','direction':'owner','sent_at':'2026-09-21T10:00:00Z','body':"I'll review the protocol by tomorrow. I will send comments by 2026-09-30."},
            {'message_id':'owner-b','direction':'owner','sent_at':'2026-09-20T09:00:00Z','body':'Let me upload the appendix by 2026-09-21.'},
        ],
    }
    response = client.post(URL, json=payload, headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body['tenant_id'] == 'lab' and body['promise_count'] == 3
    assert body['due_soon_count'] == 1 and body['overdue_count'] == 1
    assert all(row['source_message_id'] != 'other' for row in body['promises'])
    assert all(row['follow_up_requires_owner_approval'] is True for row in body['promises'])
    assert any(row['follow_up_proposed'] is False for row in body['promises'])
    assert len(body['tracker_sha256']) == 64 and 'does not create' in body['boundary']


def test_rejects_duplicate_ids_and_naive_times():
    message = {'message_id':'same','direction':'owner','sent_at':'2026-09-21T10:00:00Z','body':'I will review this.'}
    response = client.post(URL, json={'thread_id':'t','messages':[message,message]}, headers=HEADERS)
    assert response.status_code == 422 and 'duplicate message_id' in response.text
    message['message_id'] = 'one'; message['sent_at'] = '2026-09-21T10:00:00'
    response = client.post(URL, json={'thread_id':'t','messages':[message]}, headers=HEADERS)
    assert response.status_code == 422 and 'timezone-aware' in response.text
