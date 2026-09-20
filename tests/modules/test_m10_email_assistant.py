"""Offline tests for module 10 (Email Assistant), including the
approval-gating and tenant-isolation safety paths."""

import asyncio
import base64
import json
import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalRequest
from app.core.token_crypto import TokenCipher
from app.modules.m10_email_assistant.classifier import (
    ClassifierInput,
    RuleBasedClassifier,
)
from app.modules.m10_email_assistant.extraction import (
    extract_actions,
    heuristic_extract,
    parse_action_json,
)
from app.modules.m10_email_assistant.gmail import GmailRawMessage, WatchInfo, parse_gmail_message
from app.modules.m10_email_assistant.schemas import EmailCategory
from app.modules.m10_email_assistant.service import (
    PubSubVerificationError,
    Service,
)
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository

MASTER = "test-master-secret"


class FakeGmailClient:
    def __init__(self, profile=None, history=None, messages=None):
        self.profile = profile or {"emailAddress": "me@example.com", "historyId": "100"}
        self.history = history or {}
        self.messages = messages or {}
        self.watch_calls = []

    async def get_profile(self, access_token):
        return self.profile

    async def list_history(self, access_token, start_history_id):
        return self.history.get(start_history_id, [])

    async def get_message(self, access_token, message_id):
        return self.messages[message_id]

    async def watch(self, access_token, topic):
        self.watch_calls.append(topic)
        return WatchInfo(history_id="200", expiration_ms=1730000000000)


class ApprovalSpy:
    def __init__(self):
        self.items = []

    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        self.items.append(item)
        return item


async def fake_generate(prompt: str, provider: str, model: str | None):
    if prompt.startswith("Extract action items"):
        return model or "test-model", "[]"
    return model or "test-model", "Subject: Re: hello\nThanks, I will handle it."


def raw_message(gmail_id, subject, sender="someone@example.com", snippet="snip",
                body="body text", labels=None, headers=None, thread="t1"):
    return GmailRawMessage(
        gmail_id=gmail_id, thread_id=thread, history_id="101", subject=subject,
        sender=sender, recipients=["me@example.com"], snippet=snippet, body_text=body,
        received_at=1730000000.0, labels=labels or ["INBOX"], headers=headers or {},
    )


def make_service(tmp_path, tenant="tenant-a", gmail=None, transport=None):
    engine = create_engine(f"sqlite:///{tmp_path}/{tenant}.db")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    repo = SqlEmailRepository(tenant, sessions)
    approvals = ApprovalSpy()
    client = httpx.AsyncClient(transport=transport or httpx.MockTransport(
        lambda req: httpx.Response(200, json={"access_token": "at", "expires_in": 3600})))
    service = Service(
        repo, approvals, gmail or FakeGmailClient(), client,
        cipher=TokenCipher(tenant, master_secret=MASTER),
        google_client_id="cid", google_client_secret="sec",
        pubsub_verification_token="good-token",
        llm_generate=fake_generate,
    )
    return service, repo, approvals, client


def push_envelope(email="me@example.com", history_id="105"):
    data = base64.urlsafe_b64encode(
        json.dumps({"emailAddress": email, "historyId": history_id}).encode()
    ).decode()
    return {"message": {"data": data, "messageId": "1"}, "subscription": "sub"}


# -- OAuth + token storage ---------------------------------------------------

def test_connect_account_stores_refresh_token_encrypted(tmp_path):
    def handler(request):
        assert request.url.path == "/token"
        return httpx.Response(200, json={
            "access_token": "at", "refresh_token": "rt-secret", "expires_in": 3600})

    service, repo, _, client = make_service(tmp_path, transport=httpx.MockTransport(handler))
    view = asyncio.run(service.connect_account("auth-code", "https://app/callback"))
    assert view.email_address == "me@example.com"
    row = repo.get_account_by_email("me@example.com")
    assert row.encrypted_refresh_token != "rt-secret"
    assert service.cipher.decrypt(row.encrypted_refresh_token) == "rt-secret"
    asyncio.run(client.aclose())


def test_authorization_url_requests_offline_access(tmp_path):
    service, _, _, client = make_service(tmp_path)
    url = service.authorization_url("https://app/callback", "state-1")
    assert "client_id=cid" in url and "access_type=offline" in url and "state=state-1" in url
    asyncio.run(client.aclose())


# -- Pub/Sub + ingestion --------------------------------------------------------

def test_pubsub_rejects_wrong_verification_token(tmp_path):
    service, _, _, client = make_service(tmp_path)
    with pytest.raises(PubSubVerificationError):
        service.decode_push(push_envelope(), "wrong-token")
    asyncio.run(client.aclose())


def test_ingestion_is_idempotent_and_checkpoints(tmp_path):
    messages = {
        "m1": raw_message("m1", "Action required: confirm your spot"),
        "m2": raw_message("m2", "Weekly digest", headers={"list-unsubscribe": "<https://x/unsub>"}),
    }
    gmail = FakeGmailClient(history={"100": ["m1", "m2"]}, messages=messages)
    service, repo, approvals, client = make_service(tmp_path, gmail=gmail)
    cipher = service.cipher
    repo.save_account(account_id="acc1", email_address="me@example.com",
                      encrypted_refresh_token=cipher.encrypt("rt"), history_id="100",
                      watch_expiration=None)

    result = asyncio.run(service.handle_push(push_envelope(), "good-token"))
    assert result.fetched == 2 and result.new_messages == 2
    assert repo.get_account_by_email("me@example.com").history_id == "105"

    again = asyncio.run(service.handle_push(push_envelope(), "good-token"))
    assert again.new_messages == 0  # idempotent on (tenant, gmail_id)
    asyncio.run(client.aclose())


def test_actionable_email_drafts_reply_through_approval_only(tmp_path):
    messages = {"m1": raw_message("m1", "Action required: confirm your participation")}
    gmail = FakeGmailClient(history={"100": ["m1"]}, messages=messages)
    service, repo, approvals, client = make_service(tmp_path, gmail=gmail)
    repo.save_account(account_id="acc1", email_address="me@example.com",
                      encrypted_refresh_token=service.cipher.encrypt("rt"),
                      history_id="100", watch_expiration=None)
    result = asyncio.run(service.handle_push(push_envelope(), "good-token"))
    assert result.drafts_proposed == 1

    assert len(approvals.items) == 1
    item = approvals.items[0]
    assert item.module_id == 10 and item.action_type == "send_email_reply"
    assert item.status.value == "pending"
    assert item.payload["to"] == "someone@example.com"
    drafts = service.list_drafts()
    assert len(drafts) == 1 and drafts[0].status == "pending_approval"
    # The module exposes no send path at all.
    assert not hasattr(service, "send")
    asyncio.run(client.aclose())


def test_newsletter_is_not_actionable_and_keeps_unsubscribe_link(tmp_path):
    messages = {"m1": raw_message("m1", "Your weekly digest",
                                  headers={"list-unsubscribe": "<https://x/unsub>"})}
    gmail = FakeGmailClient(history={"100": ["m1"]}, messages=messages)
    service, repo, approvals, client = make_service(tmp_path, gmail=gmail)
    repo.save_account(account_id="acc1", email_address="me@example.com",
                      encrypted_refresh_token=service.cipher.encrypt("rt"),
                      history_id="100", watch_expiration=None)
    result = asyncio.run(service.handle_push(push_envelope(), "good-token"))
    assert result.drafts_proposed == 0 and approvals.items == []
    stored = service.list_messages()[0]
    assert stored.category == EmailCategory.NEWSLETTER
    assert stored.unsubscribe_url == "https://x/unsub"
    asyncio.run(client.aclose())


def test_tenant_isolation(tmp_path):
    service_a, repo_a, _, client_a = make_service(tmp_path, tenant="tenant-a")
    service_b, repo_b, _, client_b = make_service(tmp_path, tenant="tenant-b")
    repo_a.save_message(
        message_id="x", account_id="acc", gmail_id="g1", thread_id="t", history_id="1",
        subject="s", sender="s@x.com", recipients=[], snippet="", body_text="",
        received_at=None, labels=[], headers={}, category="personal",
        category_confidence=0.5, embedding=None, unsubscribe_url=None)
    assert repo_b.has_message("g1") is False
    assert service_b.list_messages() == []
    asyncio.run(client_a.aclose())
    asyncio.run(client_b.aclose())


# -- classification ---------------------------------------------------------------

@pytest.mark.parametrize("subject,sender,labels,headers,expected", [
    ("Your application to the MIT scholarship", "a@b.com", [], {}, EmailCategory.OPPORTUNITY),
    ("Re: your research question", "prof@stanford.edu", [], {}, EmailCategory.PROFESSOR_REPLY),
    ("Let's collaborate on a joint project", "peer@lab.com", [], {}, EmailCategory.COLLABORATION),
    ("Weekly digest", "news@site.com", [], {"list-unsubscribe": "<https://x>"}, EmailCategory.NEWSLETTER),
    ("dinner tonight?", "mom@family.com", [], {}, EmailCategory.PERSONAL),
    ("You won a prize", "x@spam.com", ["SPAM"], {}, EmailCategory.SPAM),
    ("Action required: verify your account", "no-reply@bank.com", [], {}, EmailCategory.ACTION_REQUIRED),
])
def test_rule_based_classifier_covers_all_seven_spec_categories(
        subject, sender, labels, headers, expected):
    result = RuleBasedClassifier().classify(
        ClassifierInput(subject=subject, sender=sender, snippet=subject, labels=labels, headers=headers))
    assert result.category == expected
    assert 0.0 < result.confidence <= 1.0


# -- action extraction ---------------------------------------------------------

def test_parse_action_json_validates_spec_schema():
    text = '```json\n[{"action": "Submit the form", "deadline": "2026-09-25T17:00:00Z", "related_entity": "MIT"}]\n```'
    items = parse_action_json(text)
    assert items[0].action == "Submit the form"
    assert items[0].deadline is not None and items[0].related_entity == "MIT"


def test_extraction_retries_then_falls_back():
    async def bad_then_good(prompt, provider, model):
        if "Previous output" in prompt:
            return "m", '[{"action": "Reply to Sarah", "deadline": null, "related_entity": "Sarah"}]'
        return "m", "not json at all"

    items = asyncio.run(extract_actions(
        bad_then_good, provider="openai", model=None, subject="s", body="b"))
    assert items[0].action == "Reply to Sarah"

    async def always_bad(prompt, provider, model):
        return "m", "garbage"

    fallback = asyncio.run(extract_actions(
        always_bad, provider="openai", model=None,
        subject="Reminder", body="Please submit the report by Friday."))
    assert fallback and "submit the report" in fallback[0].action
    assert fallback[0].deadline is not None  # heuristic parsed "by Friday"


def test_heuristic_extracts_deadline():
    items = heuristic_extract("Grant application", "Please complete the form by 2026-10-01.")
    assert items and items[0].deadline is not None


# -- advancement pass ------------------------------------------------------------

def test_priority_inbox_ranks_frequent_senders_higher(tmp_path):
    service, repo, _, client = make_service(tmp_path)
    now = datetime.now(timezone.utc)
    for i in range(3):
        repo.save_message(
            message_id=f"a{i}", account_id="acc", gmail_id=f"ga{i}", thread_id="t",
            history_id="1", subject="s", sender="frequent@x.com", recipients=[],
            snippet="", body_text="", received_at=now, labels=[], headers={},
            category="action_required", category_confidence=0.9, embedding=None,
            unsubscribe_url=None)
    repo.save_message(
        message_id="b0", account_id="acc", gmail_id="gb0", thread_id="t",
        history_id="1", subject="s", sender="rare@x.com", recipients=[],
        snippet="", body_text="", received_at=now, labels=[], headers={},
        category="action_required", category_confidence=0.9, embedding=None,
        unsubscribe_url=None)
    top = service.priority_inbox()[0]
    assert top.message.sender == "frequent@x.com"
    asyncio.run(client.aclose())


def test_follow_ups_due_filters_by_deadline_window(tmp_path):
    service, repo, _, client = make_service(tmp_path)
    now = datetime.now(timezone.utc)
    repo.save_action_items("m1", [
        {"id": "i1", "action": "soon", "deadline": now + timedelta(hours=12),
         "related_entity": None, "confidence": 0.5},
        {"id": "i2", "action": "later", "deadline": now + timedelta(hours=200),
         "related_entity": None, "confidence": 0.5},
    ])
    due = service.follow_ups_due(within_hours=48)
    assert [item["action"] for item in due] == ["soon"]
    asyncio.run(client.aclose())


def test_watch_renewal_only_renews_expiring_accounts(tmp_path):
    gmail = FakeGmailClient()
    service, repo, _, client = make_service(tmp_path, gmail=gmail)
    cipher = service.cipher
    repo.save_account(account_id="old", email_address="old@example.com",
                      encrypted_refresh_token=cipher.encrypt("rt"), history_id="1",
                      watch_expiration=datetime.now(timezone.utc) + timedelta(hours=2))
    repo.save_account(account_id="fresh", email_address="fresh@example.com",
                      encrypted_refresh_token=cipher.encrypt("rt"), history_id="1",
                      watch_expiration=datetime.now(timezone.utc) + timedelta(days=6))
    result = asyncio.run(service.renew_watches("projects/x/topics/y"))
    assert result.renewed == ["old@example.com"]
    assert result.skipped == ["fresh@example.com"]
    asyncio.run(client.aclose())


# -- gmail payload parsing ---------------------------------------------------------

def test_parse_gmail_message_full_payload():
    data = {
        "id": "m1", "threadId": "t1", "historyId": "9", "internalDate": "1730000000000",
        "labelIds": ["INBOX"], "snippet": "snip",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Hello"},
                {"name": "From", "value": "a@b.com"},
                {"name": "To", "value": "me@example.com, other@example.com"},
            ],
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(b"real body").decode()},
        },
    }
    raw = parse_gmail_message(data)
    assert raw.subject == "Hello" and raw.sender == "a@b.com"
    assert raw.body_text == "real body"
    assert raw.recipients == ["me@example.com", "other@example.com"]


# -- routes -------------------------------------------------------------------------

def test_pubsub_route_rejects_bad_token(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_TOKEN_KEY", MASTER)
    monkeypatch.setenv("ATLAS_PUBSUB_VERIFICATION_TOKEN", "good-token")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m10_email_assistant.routes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.post(
        "/email-assistant/pubsub?token=wrong",
        json=push_envelope(),
        headers={"x-atlas-tenant": "t1", "x-atlas-actor": "u1"},
    )
    assert response.status_code == 403
