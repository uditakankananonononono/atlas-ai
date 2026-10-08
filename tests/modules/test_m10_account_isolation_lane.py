"""Lane probe: M10 per-account isolation and draft->account binding.

Two Gmail accounts under ONE tenant. Real Service + real SQLite repository,
fake Gmail transport only. Tests assert the required property; a failing test
is a real finding, not a fixture problem."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_m10_email_assistant import (  # noqa: E402
    FakeGmailClient, make_service, push_envelope, raw_message)


def _two_accounts(tmp_path, messages, history):
    gmail = FakeGmailClient(history=history, messages=messages)
    service, repo, approvals, client = make_service(tmp_path, gmail=gmail)
    for acc, mail in (("acc-a", "a@example.com"), ("acc-b", "b@example.com")):
        repo.save_account(account_id=acc, email_address=mail,
                          encrypted_refresh_token=service.cipher.encrypt("rt"),
                          history_id="100", watch_expiration=None)
    return service, repo, approvals, client


def test_same_gmail_id_in_two_mailboxes_both_ingested(tmp_path):
    """Gmail message ids are unique per mailbox only. Mailbox B's message must
    not be dropped because mailbox A already holds the same id."""
    msgs = {"m1": raw_message("m1", "Action required: confirm")}
    service, repo, _, client = _two_accounts(
        tmp_path, msgs, {"100": ["m1"]})
    asyncio.run(service.handle_push(push_envelope("a@example.com"), "good-token"))
    res = asyncio.run(service.handle_push(push_envelope("b@example.com"), "good-token"))
    assert res.new_messages == 1, "mailbox B message dropped by tenant-wide gmail_id dedupe"
    asyncio.run(client.aclose())


def test_draft_approval_payload_binds_source_account(tmp_path):
    msgs = {"m1": raw_message("m1", "Action required: confirm")}
    service, repo, approvals, client = _two_accounts(
        tmp_path, msgs, {"100": ["m1"]})
    asyncio.run(service.handle_push(push_envelope("b@example.com"), "good-token"))
    payload = approvals.items[0][0].payload
    assert payload.get("account_id") == "acc-b", (
        f"approval payload has no source-account binding: keys={sorted(payload)}")
    asyncio.run(client.aclose())


def test_draft_view_exposes_source_account(tmp_path):
    msgs = {"m1": raw_message("m1", "Action required: confirm")}
    service, repo, _, client = _two_accounts(tmp_path, msgs, {"100": ["m1"]})
    asyncio.run(service.handle_push(push_envelope("a@example.com"), "good-token"))
    d = service.list_drafts()[0]
    assert getattr(d, "account_id", None) == "acc-a"
    asyncio.run(client.aclose())


def test_message_rows_keep_their_own_account(tmp_path):
    msgs = {"m1": raw_message("m1", "Hello there")}
    service, repo, _, client = _two_accounts(tmp_path, msgs, {"100": ["m1"]})
    asyncio.run(service.handle_push(push_envelope("a@example.com"), "good-token"))
    rows = repo.list_messages(category=None, limit=10)
    assert {r.account_id for r in rows} == {"acc-a"}
    asyncio.run(client.aclose())
