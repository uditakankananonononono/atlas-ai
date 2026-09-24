"""M10 send-reply drift probe wired into the M00 impact preview.

Real M00 service, real M10 tables, real HTTP reader/token code against a mock
Gmail + OAuth server (httpx.MockTransport). No network.
"""
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center import impact
from app.modules.m00_approval_center.service import ApprovalBroadcaster, Service as ApprovalService
from app.modules.m10_email_assistant import drift_probe as dp
from app.modules.m10_email_assistant.sql_repository import EmailDraftRow, EmailMessageRow, GmailAccountRow

NOW = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)
OWNER = "udita@example.com"


def msg(mid, date, sender, labels=("INBOX",), reply_to=None):
    headers = [{"name": "From", "value": sender}, {"name": "Subject", "value": "RA role"}]
    if reply_to:
        headers.append({"name": "Reply-To", "value": reply_to})
    return {"id": mid, "internalDate": str(date), "labelIds": list(labels), "payload": {"headers": headers}}


class Gmail:
    """Mutable fake of the external world, served over HTTP."""

    def __init__(self):
        self.thread = [msg("g-1", 1000, f"Udita <{OWNER}>", ("SENT",)),
                       msg("g-2", 2000, "Prof Rao <rao@uni.edu>", reply_to="lab@uni.edu")]
        self.token_status = 200
        self.requests = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "oauth2.googleapis.com":
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_grant"})
            assert b"refresh_token=refresh-secret" in request.content
            return httpx.Response(200, json={"access_token": "live-token", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer live-token"
        assert request.url.path.endswith("/threads/th-1")
        return httpx.Response(200, json={"id": "th-1", "messages": list(self.thread)})


class Cipher:
    def decrypt(self, value):
        assert value == "enc:refresh-secret"
        return "refresh-secret"


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/db.sqlite", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add(GmailAccountRow(tenant_id="t1", id="acct-1", email_address=OWNER, encrypted_refresh_token="enc:refresh-secret",
                               created_at=NOW, updated_at=NOW))
        db.add(EmailMessageRow(tenant_id="t1", id="m-2", account_id="acct-1", gmail_id="g-2", thread_id="th-1",
                               subject="RA role", sender="rao@uni.edu", created_at=NOW))
        db.add(EmailDraftRow(tenant_id="t1", id="d-1", message_id="m-2", approval_id="pending", to="rao@uni.edu",
                             subject="Re: RA role", body="Thank you, I can start in October.", model="m", created_at=NOW))
    gmail = Gmail()
    client = httpx.Client(transport=httpx.MockTransport(gmail.handler))
    probe = dp.SendReplyProbe(reader=dp.HttpThreadReader(client),
                              tokens=dp.RefreshTokenSource(client, client_id="cid", client_secret="csec", cipher_factory=lambda _: Cipher()),
                              session_factory=sessions)
    registry = impact.ProbeRegistry()
    dp.register(registry, probe)
    approvals = ApprovalService(session_factory=sessions, broadcaster=ApprovalBroadcaster(), clock=lambda: NOW)
    return approvals, registry, gmail, sessions


PAYLOAD = {"tenant_id": "t1", "draft_id": "d-1", "message_id": "m-2", "gmail_id": "g-2", "thread_id": "th-1",
           "to": "rao@uni.edu", "subject": "Re: RA role", "body": "Thank you, I can start in October."}


def approve(approvals, registry):
    view = approvals.submit(module_id=10, action_type="send_email_reply", payload=PAYLOAD, user_id="t1")
    captured = impact.capture_review_state(approvals, view["id"], registry=registry)
    assert captured["probe"] == "10:send_email_reply"
    approvals.decide(view["id"], ApprovalStatus.APPROVED, decided_by="t1")
    return view["id"]


def consume(approvals, registry, aid):
    return impact.consume_effect_checked(approvals, aid, module_id=10, action_type="send_email_reply", payload=PAYLOAD,
                                         user_id="t1", effect_id="send-1", actor="worker", registry=registry)


def test_state_document_is_what_a_reviewer_needs(env):
    approvals, registry, gmail, _ = env
    aid = approve(approvals, registry)
    preview = impact.impact_preview(approvals, aid, registry=registry)
    state = preview["current"]["state"]
    assert state["thread"]["message_count"] == 2 and state["thread"]["latest_message_id"] == "g-2"
    assert state["thread"]["owner_replied_after_target"] is False
    assert state["reply_target"] == {"gmail_id": "g-2", "present": True, "trashed": False, "reply_to": "lab@uni.edu"}
    assert state["draft"]["to"] == "rao@uni.edu" and len(state["draft"]["body_sha256"]) == 64
    assert "Thank you" not in str(state)  # body is hashed, not copied
    thread_call = [r for r in gmail.requests if "threads" in r.url.path][0]
    assert thread_call.url.params["format"] == "metadata"
    assert "Reply-To" in thread_call.url.params.get_list("metadataHeaders")


def test_unchanged_thread_consumes(env):
    approvals, registry, _, _ = env
    permit = consume(approvals, registry, approve(approvals, registry))
    assert permit["state_verdict"] == "unchanged" and permit["state_hash"]


def test_new_reply_in_thread_blocks_send(env):
    approvals, registry, gmail, _ = env
    aid = approve(approvals, registry)
    gmail.thread.append(msg("g-3", 3000, "Prof Rao <rao@uni.edu>"))
    with pytest.raises(impact.StateDriftError) as err:
        consume(approvals, registry, aid)
    paths = {d["path"] for d in err.value.drift}
    assert "thread.latest_message_id" in paths and "thread.message_count" in paths


def test_owner_already_replied_in_gmail_blocks_send(env):
    approvals, registry, gmail, _ = env
    aid = approve(approvals, registry)
    gmail.thread.append(msg("g-4", 4000, f"Udita <{OWNER}>", ("SENT",)))
    with pytest.raises(impact.StateDriftError) as err:
        consume(approvals, registry, aid)
    assert any(d["path"] == "thread.owner_replied_after_target" and d["after"] is True for d in err.value.drift)


def test_edited_draft_blocks_send(env):
    approvals, registry, _, sessions = env
    aid = approve(approvals, registry)
    with sessions.begin() as db:
        db.execute(update(EmailDraftRow).where(EmailDraftRow.id == "d-1").values(body="Actually, November."))
    with pytest.raises(impact.StateDriftError) as err:
        consume(approvals, registry, aid)
    assert {d["path"] for d in err.value.drift} == {"draft.body_sha256"}


def test_reply_to_change_blocks_send(env):
    approvals, registry, gmail, _ = env
    aid = approve(approvals, registry)
    gmail.thread[1] = msg("g-2", 2000, "Prof Rao <rao@uni.edu>", reply_to="someone-else@evil.test")
    with pytest.raises(impact.StateDriftError):
        consume(approvals, registry, aid)


def test_revoked_token_fails_closed(env):
    approvals, registry, gmail, _ = env
    aid = approve(approvals, registry)
    gmail.token_status = 400
    with pytest.raises(dp.ProbeUnavailable, match="reconnect"):
        consume(approvals, registry, aid)
    assert approvals.get(aid)["status"] in {"approved", ApprovalStatus.APPROVED}  # no permit issued


def test_unknown_message_fails_closed(env):
    approvals, registry, _, _ = env
    probe = registry.find(10, "send_email_reply")[1]
    with pytest.raises(dp.ProbeUnavailable):
        probe({**PAYLOAD, "message_id": "nope"})
    with pytest.raises(dp.ProbeUnavailable):
        probe({**PAYLOAD, "tenant_id": "other-tenant"})


def test_module_import_registers_global_probe():
    import app.modules.m10_email_assistant  # noqa: F401

    found = impact.PROBES.find(10, "send_email_reply")
    assert found is not None and found[0] == "10:send_email_reply"
    assert isinstance(found[1], dp.SendReplyProbe)
    dp.register()  # idempotent
    assert sum(1 for p in impact.PROBES._probes if p[0] == "send_email_reply" and p[1] == 10) == 1


# -- drafting captures the review snapshot automatically ------------------------


def _draft_env(tmp_path, capturer):
    import asyncio
    from tests.modules.test_m10_email_assistant import FakeGmailClient, make_service, push_envelope, raw_message

    messages = {"m1": raw_message("m1", "Action required: confirm your participation")}
    service, repo, approvals, client = make_service(tmp_path, gmail=FakeGmailClient(history={"100": ["m1"]}, messages=messages))

    class DurableIds:
        items = []

        def put(self, item, *, user_id=None):
            stored = item.model_copy(update={"id": "m00-durable-id"})
            self.items.append(stored)
            return stored

    service.approval_sink = DurableIds()
    service.review_state_capturer = capturer
    repo.save_account(account_id="acc1", email_address="me@example.com",
                      encrypted_refresh_token=service.cipher.encrypt("rt"), history_id="100", watch_expiration=None)
    asyncio.run(service.handle_push(push_envelope(), "good-token"))
    asyncio.run(client.aclose())
    return service, repo


def test_draft_links_durable_approval_id_and_captures_review_state(tmp_path):
    captured = []
    service, _ = _draft_env(tmp_path, captured.append)
    draft = service.list_drafts()[0]
    assert draft.approval_id == "m00-durable-id"  # not the provisional uuid
    assert captured == ["m00-durable-id"]


def test_capture_failure_does_not_block_drafting_and_is_logged(tmp_path):
    def boom(_):
        raise dp.ProbeUnavailable("Gmail unreachable: ConnectError")

    service, repo = _draft_env(tmp_path, boom)
    draft = service.list_drafts()[0]
    events = [e.event for e in repo.events(draft.id)]
    assert "review_state_capture_failed" in events


def test_routes_wire_the_m00_capturer():
    from app.modules.m10_email_assistant import routes

    assert callable(routes._capture_review_state)
