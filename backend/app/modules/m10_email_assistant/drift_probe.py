"""M10 state probe for the M00 impact preview (first real drift probe).

An approved ``send_email_reply`` is only safe to send if the conversation the
reviewer saw is still the conversation that exists. This probe reads, without
side effects:

- the live Gmail thread (``threads.get`` metadata only): message count, the
  latest message, every message that arrived after the one being replied to,
  and whether the owner already replied from Gmail directly (SENT label or the
  connected address in From);
- the reply target itself: still in the thread, not trashed, current
  Reply-To/From (where the reply would really go);
- the stored Atlas draft: recipient, subject and a SHA-256 of the body, plus
  its status, so an edited or already-sent draft is caught.

M00 stores this state when the approval card is shown (``POST
/approval-center/requests/{id}/review-state``) and re-reads it before
``consume``; any difference blocks the send until a human re-reviews. If the
probe cannot read the live state (no account, revoked token, Gmail down), it
raises ``ProbeUnavailable`` and the consume fails closed.
"""
from __future__ import annotations

import hashlib
import os
import threading
from typing import Any, Callable, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.database import SessionLocal

from .gmail import GMAIL_BASE_URL, OAUTH_TOKEN_URL
from .sql_repository import EmailDraftRow, EmailMessageRow, GmailAccountRow

ACTION_TYPE = "send_email_reply"
MODULE_ID = 10
_METADATA_HEADERS = ("From", "To", "Cc", "Reply-To", "Subject", "Message-ID")


class ProbeUnavailable(RuntimeError):
    """Live state could not be read; callers must not treat the state as unchanged."""


class ThreadReader(Protocol):
    def get_thread(self, access_token: str, thread_id: str) -> dict[str, Any]: ...


class TokenSource(Protocol):
    def access_token(self, tenant_id: str, account: GmailAccountRow) -> str: ...


class HttpThreadReader:
    """Synchronous Gmail ``threads.get`` (format=metadata). Read-only scope suffices."""

    def __init__(self, client: httpx.Client | None = None, base_url: str = GMAIL_BASE_URL) -> None:
        self._client = client
        self._base = base_url.rstrip("/")

    def get_thread(self, access_token: str, thread_id: str) -> dict[str, Any]:
        client = self._client or httpx.Client(timeout=20)
        try:
            response = client.get(
                f"{self._base}/threads/{thread_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params=[("format", "metadata"), *[("metadataHeaders", h) for h in _METADATA_HEADERS]],
            )
        except httpx.HTTPError as exc:
            raise ProbeUnavailable(f"Gmail unreachable: {exc.__class__.__name__}") from exc
        finally:
            if self._client is None:
                client.close()
        if response.status_code == 404:
            return {"id": thread_id, "messages": [], "missing": True}
        if response.is_error:
            raise ProbeUnavailable(f"Gmail threads.get failed ({response.status_code})")
        return response.json()


class RefreshTokenSource:
    """Exchange the stored (encrypted) refresh token for a short-lived access token."""

    def __init__(self, client: httpx.Client | None = None, *, client_id: str | None = None,
                 client_secret: str | None = None, cipher_factory: Callable[[str], Any] | None = None,
                 token_url: str = OAUTH_TOKEN_URL) -> None:
        self._client = client
        self.client_id = client_id if client_id is not None else os.getenv("ATLAS_GOOGLE_CLIENT_ID", "")
        self.client_secret = client_secret if client_secret is not None else os.getenv("ATLAS_GOOGLE_CLIENT_SECRET", "")
        self._cipher_factory = cipher_factory
        self.token_url = token_url

    def _cipher(self, tenant_id: str) -> Any:
        if self._cipher_factory is not None:
            return self._cipher_factory(tenant_id)
        from app.core.token_crypto import TokenCipher

        return TokenCipher(tenant_id)

    def access_token(self, tenant_id: str, account: GmailAccountRow) -> str:
        if not self.client_id or not self.client_secret:
            raise ProbeUnavailable("Google OAuth client is not configured (ATLAS_GOOGLE_CLIENT_ID/SECRET)")
        try:
            refresh = self._cipher(tenant_id).decrypt(account.encrypted_refresh_token)
        except Exception as exc:
            raise ProbeUnavailable("stored Gmail refresh token cannot be decrypted") from exc
        client = self._client or httpx.Client(timeout=20)
        try:
            response = client.post(self.token_url, data={
                "refresh_token": refresh, "client_id": self.client_id,
                "client_secret": self.client_secret, "grant_type": "refresh_token"})
        except httpx.HTTPError as exc:
            raise ProbeUnavailable(f"Google OAuth unreachable: {exc.__class__.__name__}") from exc
        finally:
            if self._client is None:
                client.close()
        if response.is_error:
            raise ProbeUnavailable(f"Gmail token refresh failed ({response.status_code}); reconnect the account")
        return response.json()["access_token"]


def _headers(message: dict[str, Any]) -> dict[str, str]:
    return {h.get("name", "").lower(): h.get("value", "") for h in (message.get("payload") or {}).get("headers", []) or []}


def _address(value: str) -> str:
    value = value.strip()
    if "<" in value and ">" in value:
        value = value[value.rfind("<") + 1: value.rfind(">")]
    return value.strip().lower()


def _summary(message: dict[str, Any], owner: str) -> dict[str, Any]:
    headers = _headers(message)
    labels = sorted(message.get("labelIds") or [])
    return {
        "id": message.get("id"),
        "internal_date": str(message.get("internalDate", "")),
        "from": _address(headers.get("from", "")),
        "by_owner": "SENT" in labels or (bool(owner) and _address(headers.get("from", "")) == owner),
        "trashed": "TRASH" in labels,
    }


def reply_state(thread: dict[str, Any], *, target_gmail_id: str, owner_email: str,
                draft: EmailDraftRow | None) -> dict[str, Any]:
    """Pure: turn a Gmail thread + stored draft into the reviewed-state document."""
    owner = owner_email.strip().lower()
    messages = sorted(thread.get("messages") or [], key=lambda m: int(m.get("internalDate") or 0))
    summaries = [_summary(m, owner) for m in messages]
    target_index = next((i for i, m in enumerate(messages) if m.get("id") == target_gmail_id), None)
    after = summaries[target_index + 1:] if target_index is not None else []
    target_headers = _headers(messages[target_index]) if target_index is not None else {}
    latest = summaries[-1] if summaries else None
    return {
        "thread": {
            "thread_id": thread.get("id"),
            "exists": not thread.get("missing", False),
            "message_count": len(summaries),
            "latest_message_id": latest["id"] if latest else None,
            "latest_from": latest["from"] if latest else None,
            "messages_after_target": [{k: m[k] for k in ("id", "from", "by_owner")} for m in after],
            "owner_replied_after_target": any(m["by_owner"] for m in after),
        },
        "reply_target": {
            "gmail_id": target_gmail_id,
            "present": target_index is not None,
            "trashed": summaries[target_index]["trashed"] if target_index is not None else None,
            "reply_to": _address(target_headers.get("reply-to", "") or target_headers.get("from", "")),
        },
        "draft": None if draft is None else {
            "draft_id": draft.id,
            "to": _address(draft.to),
            "subject": draft.subject,
            "body_sha256": hashlib.sha256(draft.body.encode()).hexdigest(),
            "status": draft.status,
        },
    }


class SendReplyProbe:
    """Callable registered with M00: ``payload -> live state``."""

    def __init__(self, *, reader: ThreadReader | None = None, tokens: TokenSource | None = None,
                 session_factory: sessionmaker | Callable[[], Any] = SessionLocal) -> None:
        self.reader = reader or HttpThreadReader()
        self.tokens = tokens or RefreshTokenSource()
        self.sessions = session_factory

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = str(payload.get("tenant_id") or "").strip()
        thread_id, target, draft_id = payload.get("thread_id"), payload.get("gmail_id"), payload.get("draft_id")
        if not tenant_id or not target or not payload.get("message_id"):
            raise ProbeUnavailable("reply payload lacks tenant_id/message_id/gmail_id; cannot read live state")
        with self.sessions() as db:
            message = db.scalars(select(EmailMessageRow).where(
                EmailMessageRow.tenant_id == tenant_id, EmailMessageRow.id == payload["message_id"])).first()
            if message is None:
                raise ProbeUnavailable("source message is not stored for this tenant")
            account = db.scalars(select(GmailAccountRow).where(
                GmailAccountRow.tenant_id == tenant_id, GmailAccountRow.id == message.account_id)).first()
            draft = None if not draft_id else db.scalars(select(EmailDraftRow).where(
                EmailDraftRow.tenant_id == tenant_id, EmailDraftRow.id == draft_id)).first()
            if account is None:
                raise ProbeUnavailable("Gmail account for this message is no longer connected")
            if draft is not None:
                db.expunge(draft)
            db.expunge(account)
        if not thread_id:
            thread = {"id": None, "messages": [], "missing": True}
        else:
            thread = self.reader.get_thread(self.tokens.access_token(tenant_id, account), thread_id)
        return reply_state(thread, target_gmail_id=target, owner_email=account.email_address, draft=draft)


_REGISTERED = False
_REG_LOCK = threading.Lock()


def register(registry: Any | None = None, probe: SendReplyProbe | None = None) -> None:
    """Register the probe with M00 (idempotent for the global registry)."""
    global _REGISTERED
    from app.modules.m00_approval_center.impact import PROBES

    target = registry or PROBES
    if target is PROBES:
        with _REG_LOCK:
            if _REGISTERED:
                return
            _REGISTERED = True
    target.register(ACTION_TYPE, probe or SendReplyProbe(), module_id=MODULE_ID)
