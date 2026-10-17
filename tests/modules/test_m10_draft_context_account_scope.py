"""Native qualification tests for the M10 account-safe draft-context candidate.

Runs the REAL Service._context_window / Service._draft_reply and the REAL
SqlEmailRepository.sender_messages against a real SQLite database, in the
repo's native pytest harness (tests/modules style, no stubbed app.* seams).

Covers the candidate claims:
- thread rows are filtered to the drafting account (repository.thread_messages
  is tenant+thread only, so an unscoped listing leaks a second account's mail
  into the LLM prompt),
- a same-sender fallback (tenant + account + sender, true newest 5) feeds the
  window when the thread yields little,
- no account context fails closed,
- thread-first ordering, dedupe, current-message exclusion and the max_chars
  cap are preserved.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalRequest
from app.core.token_crypto import TokenCipher
from app.modules.m10_email_assistant.classifier import Classification
from app.modules.m10_email_assistant.gmail import GmailRawMessage
from app.modules.m10_email_assistant.schemas import ActionItem, EmailCategory
from app.modules.m10_email_assistant.service import Service
from app.modules.m10_email_assistant.sql_repository import SqlEmailRepository

MASTER = "test-master-secret"
TENANT = "tenant-a"
ACC = "acc-1"
OTHER_ACC = "acc-2"
SENDER = "prof@example.edu"
BASE_TIME = datetime(2026, 10, 1, tzinfo=timezone.utc)


class ApprovalSpy:
    def __init__(self):
        self.items = []

    def put(self, item: ApprovalRequest, *, user_id=None) -> ApprovalRequest:
        self.items.append((item, user_id))
        return item


class PromptSpy:
    def __init__(self):
        self.prompts = []

    async def __call__(self, prompt, provider, model):
        self.prompts.append(prompt)
        return model or "test-model", "Subject: Re: hello\nThanks, I will handle it."


class FakeGmailClient:
    async def get_profile(self, access_token):
        return {"emailAddress": "me@example.com", "historyId": "100"}


def make_service(tmp_path, tenant=TENANT):
    engine = create_engine(f"sqlite:///{tmp_path}/{tenant}.db")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    repo = SqlEmailRepository(tenant, sessions)
    approvals = ApprovalSpy()
    prompts = PromptSpy()
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={"access_token": "at", "expires_in": 3600})))
    service = Service(
        repo, approvals, FakeGmailClient(), client,
        cipher=TokenCipher(tenant, master_secret=MASTER),
        google_client_id="cid", google_client_secret="sec",
        pubsub_verification_token="good-token",
        llm_generate=prompts,
    )
    return service, repo, approvals, prompts, client


def seed_message(repo, *, gmail_id, account_id=ACC, sender=SENDER, subject="subject",
                 snippet="snip", thread_id=None, received_at=None):
    repo.save_message(
        message_id=f"dbid-{gmail_id}", account_id=account_id, gmail_id=gmail_id,
        thread_id=thread_id, history_id=None, subject=subject, sender=sender,
        recipients=["me@example.com"], snippet=snippet, body_text="body",
        received_at=received_at or BASE_TIME, labels=[], headers={},
        category=None, category_confidence=0.0, embedding=None, unsubscribe_url=None)


def raw(gmail_id="current", thread_id="t1", sender=SENDER):
    return GmailRawMessage(
        gmail_id=gmail_id, thread_id=thread_id, history_id="101", subject="hello",
        sender=sender, recipients=["me@example.com"], snippet="snip", body_text="body text",
        received_at=1730000000.0, labels=["INBOX"], headers={})


# -- SQL level: SqlEmailRepository.sender_messages ----------------------------

def test_sender_messages_true_newest_five_after_filtering(tmp_path):
    _, repo, _, _, client = make_service(tmp_path)
    for i in range(8):  # oldest first
        seed_message(repo, gmail_id=f"m{i}", subject=f"match {i}",
                     received_at=BASE_TIME + timedelta(days=i))
    seed_message(repo, gmail_id="x1", account_id=OTHER_ACC, subject="other account",
                 received_at=BASE_TIME + timedelta(days=100))
    seed_message(repo, gmail_id="x3", sender="other@example.com", subject="other sender",
                 received_at=BASE_TIME + timedelta(days=102))
    got = repo.sender_messages(SENDER, ACC, limit=5)
    assert [r.subject for r in got] == [f"match {i}" for i in (7, 6, 5, 4, 3)]
    asyncio.run(client.aclose())


def test_sender_messages_account_and_sender_isolation(tmp_path):
    _, repo, _, _, client = make_service(tmp_path)
    seed_message(repo, gmail_id="m0", subject="mine")
    seed_message(repo, gmail_id="x1", account_id=OTHER_ACC, subject="other account")
    seed_message(repo, gmail_id="x3", sender="other@example.com", subject="other sender")
    got = repo.sender_messages(SENDER, ACC, limit=20)
    assert {r.subject for r in got} == {"mine"}
    asyncio.run(client.aclose())


def test_sender_messages_other_account_gets_its_own_rows(tmp_path):
    _, repo, _, _, client = make_service(tmp_path)
    seed_message(repo, gmail_id="m0", subject="mine")
    seed_message(repo, gmail_id="x1", account_id=OTHER_ACC, subject="other account")
    got = repo.sender_messages(SENDER, OTHER_ACC, limit=5)
    assert [r.subject for r in got] == ["other account"]
    asyncio.run(client.aclose())


def test_sender_messages_unknown_sender_empty(tmp_path):
    _, repo, _, _, client = make_service(tmp_path)
    seed_message(repo, gmail_id="m0", subject="mine")
    assert repo.sender_messages("nobody@x.com", ACC, limit=5) == []
    asyncio.run(client.aclose())


# -- Service level: _context_window --------------------------------------------

def test_context_window_excludes_cross_account_thread_rows(tmp_path):
    service, repo, _, _, client = make_service(tmp_path)
    seed_message(repo, gmail_id="t-mine", subject="my thread subject", thread_id="t1")
    seed_message(repo, gmail_id="t-foreign", account_id=OTHER_ACC,
                 subject="foreign thread subject", thread_id="t1",
                 received_at=BASE_TIME + timedelta(days=1))
    out = service._context_window(raw(), account_id=ACC)
    assert "my thread subject" in out
    assert "foreign thread subject" not in out
    asyncio.run(client.aclose())


def test_context_window_same_sender_fallback_account_scoped(tmp_path):
    service, repo, _, _, client = make_service(tmp_path)
    seed_message(repo, gmail_id="s-mine", subject="same account sender subject")
    seed_message(repo, gmail_id="s-foreign", account_id=OTHER_ACC,
                 subject="foreign sender subject")
    out = service._context_window(raw(thread_id=None), account_id=ACC)
    assert "same account sender subject" in out
    assert "foreign sender subject" not in out
    asyncio.run(client.aclose())


def test_context_window_fails_closed_without_account(tmp_path):
    service, repo, _, _, client = make_service(tmp_path)
    seed_message(repo, gmail_id="t-mine", subject="my thread subject", thread_id="t1")
    seed_message(repo, gmail_id="s-mine", subject="same account sender subject")
    assert service._context_window(raw(), account_id=None) == "(no prior context)"
    asyncio.run(client.aclose())


def test_context_window_thread_first_dedupe_and_current_excluded(tmp_path):
    service, repo, _, _, client = make_service(tmp_path)
    seed_message(repo, gmail_id="shared", subject="AAA shared subject", thread_id="t1",
                 received_at=BASE_TIME + timedelta(days=2))
    seed_message(repo, gmail_id="current", subject="current subject", thread_id="t1")
    seed_message(repo, gmail_id="s1", subject="ZZZ sender only subject",
                 received_at=BASE_TIME + timedelta(days=1))
    out = service._context_window(raw(), account_id=ACC)
    assert out.count("AAA shared subject") == 1  # appears in both halves, deduped
    assert "current subject" not in out
    assert out.index("AAA shared subject") < out.index("ZZZ sender only subject")
    asyncio.run(client.aclose())


def test_context_window_max_chars_cap_preserved(tmp_path):
    service, repo, _, _, client = make_service(tmp_path)
    for i in range(5):
        seed_message(repo, gmail_id=f"t{i}", subject=f"thread subject {i}",
                     snippet="x" * 300, thread_id="t1")
    seed_message(repo, gmail_id="s1", subject="sender subject")
    out = service._context_window(raw(), max_chars=200, account_id=ACC)
    assert len(out) <= 200
    assert "sender subject" not in out
    asyncio.run(client.aclose())


def test_context_window_sender_fallback_capped_at_five_newest(tmp_path):
    service, repo, _, _, client = make_service(tmp_path)
    for i in range(8):
        seed_message(repo, gmail_id=f"s{i}", subject=f"sender subject {i}",
                     received_at=BASE_TIME + timedelta(days=i))
    out = service._context_window(raw(thread_id=None), account_id=ACC)
    included = {i for i in range(8) if f"sender subject {i}" in out}
    assert included == {7, 6, 5, 4, 3}  # true newest five only
    positions = [out.index(f"sender subject {i}") for i in (7, 6, 5, 4, 3)]
    assert positions == sorted(positions)  # newest first inside the window
    asyncio.run(client.aclose())


# -- End to end: _draft_reply prompt -------------------------------------------

def classification():
    return Classification(category=EmailCategory.ACTION_REQUIRED, confidence=0.9)


def test_draft_reply_prompt_excludes_foreign_account_context(tmp_path):
    service, repo, approvals, prompts, client = make_service(tmp_path)
    seed_message(repo, gmail_id="t-mine", subject="my thread subject", thread_id="t1")
    seed_message(repo, gmail_id="t-foreign", account_id=OTHER_ACC,
                 subject="foreign thread subject", thread_id="t1")
    seed_message(repo, gmail_id="s-foreign", account_id=OTHER_ACC,
                 subject="foreign sender subject")
    view = asyncio.run(service._draft_reply("dbid-current", raw(), classification(),
                                            [ActionItem(action="send docs")], ACC))
    assert len(prompts.prompts) == 1
    prompt = prompts.prompts[0]
    assert "my thread subject" in prompt
    assert "foreign thread subject" not in prompt
    assert "foreign sender subject" not in prompt
    approval, _ = approvals.items[0]
    assert approval.payload["account_id"] == ACC
    assert approval.payload["draft_id"] == view.id
    assert view.account_id == ACC
    asyncio.run(client.aclose())


def test_draft_reply_without_account_fails_closed(tmp_path):
    service, repo, approvals, prompts, client = make_service(tmp_path)
    seed_message(repo, gmail_id="t-mine", subject="my thread subject", thread_id="t1")
    asyncio.run(service._draft_reply("dbid-current", raw(), classification(), [], None))
    assert "(no prior context)" in prompts.prompts[0]
    assert "my thread subject" not in prompts.prompts[0]
    asyncio.run(client.aclose())
