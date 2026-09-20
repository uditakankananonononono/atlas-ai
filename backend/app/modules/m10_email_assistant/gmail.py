"""Gmail API + OAuth 2.0 clients with injected HTTP transport.

Spec reference: "Uses OAuth 2.0 to access Gmail API with push notifications
(Google Cloud Pub/Sub)." All network calls go through an injected
httpx.AsyncClient so tests run offline against MockTransport.
"""

from __future__ import annotations

import base64
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

GMAIL_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
# Read-only metadata + modify for labels; sending is deliberately NOT in
# scope: this module drafts, the approval-gated dispatcher sends.
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
)


class UpstreamServiceError(RuntimeError):
    """Raised when the Gmail or OAuth endpoint cannot satisfy a request."""


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_in: int


@dataclass
class GmailRawMessage:
    gmail_id: str
    thread_id: str | None
    history_id: str | None
    subject: str
    sender: str
    recipients: list[str]
    snippet: str
    body_text: str
    received_at: float | None  # epoch seconds
    labels: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class WatchInfo:
    history_id: str
    expiration_ms: int


class GmailClient(Protocol):
    """Storage/network boundary for Gmail; fake implementations plug in."""

    async def get_profile(self, access_token: str) -> dict[str, Any]: ...
    async def list_history(self, access_token: str, start_history_id: str) -> list[str]: ...
    async def get_message(self, access_token: str, message_id: str) -> GmailRawMessage: ...
    async def watch(self, access_token: str, topic: str) -> WatchInfo: ...


def build_authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{OAUTH_AUTH_URL}?{query}"


async def exchange_code(
    client: httpx.AsyncClient,
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    token_url: str = OAUTH_TOKEN_URL,
) -> OAuthTokens:
    response = await client.post(
        token_url,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if response.is_error:
        raise UpstreamServiceError(f"OAuth code exchange failed ({response.status_code})")
    data = response.json()
    return OAuthTokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=int(data.get("expires_in", 3600)),
    )


async def refresh_access_token(
    client: httpx.AsyncClient,
    *,
    refresh_token: str,
    client_id: str,
    client_secret: str,
    token_url: str = OAUTH_TOKEN_URL,
) -> str:
    response = await client.post(
        token_url,
        data={
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        },
    )
    if response.is_error:
        raise UpstreamServiceError(f"OAuth token refresh failed ({response.status_code})")
    return response.json()["access_token"]


def _header_map(headers: list[dict[str, str]]) -> dict[str, str]:
    return {h["name"].lower(): h.get("value", "") for h in headers}


def _decode_body(data: str | None) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _first_plain_text(payload: dict[str, Any]) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return _decode_body(payload["body"]["data"])
    for part in payload.get("parts", []) or []:
        text = _first_plain_text(part)
        if text:
            return text
    return _decode_body(payload.get("body", {}).get("data"))


def parse_gmail_message(data: dict[str, Any]) -> GmailRawMessage:
    """Convert a users.messages.get (format=full) payload to a raw message."""
    payload = data.get("payload", {})
    headers = _header_map(payload.get("headers", []))
    internal_ms = data.get("internalDate")
    return GmailRawMessage(
        gmail_id=data["id"],
        thread_id=data.get("threadId"),
        history_id=data.get("historyId"),
        subject=headers.get("subject", "(no subject)"),
        sender=headers.get("from", ""),
        recipients=[r.strip() for r in headers.get("to", "").split(",") if r.strip()],
        snippet=data.get("snippet", ""),
        body_text=_first_plain_text(payload) or data.get("snippet", ""),
        received_at=(int(internal_ms) / 1000.0) if internal_ms else None,
        labels=list(data.get("labelIds", []) or []),
        headers=headers,
    )


class HttpxGmailClient:
    """Live Gmail client; base URLs are injectable for tests."""

    def __init__(self, client: httpx.AsyncClient, base_url: str = GMAIL_BASE_URL) -> None:
        self._client = client
        self._base = base_url.rstrip("/")

    def _headers(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def get_profile(self, access_token: str) -> dict[str, Any]:
        response = await self.client_get("/profile", access_token)
        return response

    async def client_get(self, path: str, access_token: str, params: dict | None = None) -> Any:
        response = await self._client.get(
            f"{self._base}{path}", headers=self._headers(access_token), params=params
        )
        if response.is_error:
            raise UpstreamServiceError(f"Gmail GET {path} failed ({response.status_code})")
        return response.json()

    async def list_history(self, access_token: str, start_history_id: str) -> list[str]:
        data = await self.client_get(
            "/history",
            access_token,
            params={
                "startHistoryId": start_history_id,
                "historyTypes": "messageAdded",
                "maxResults": 500,
            },
        )
        ids: list[str] = []
        for record in data.get("history", []) or []:
            for added in record.get("messagesAdded", []) or []:
                message = added.get("message", {})
                if message.get("id"):
                    ids.append(message["id"])
        return ids

    async def get_message(self, access_token: str, message_id: str) -> GmailRawMessage:
        data = await self.client_get(
            f"/messages/{message_id}", access_token, params={"format": "full"}
        )
        return parse_gmail_message(data)

    async def watch(self, access_token: str, topic: str) -> WatchInfo:
        response = await self._client.post(
            f"{self._base}/watch",
            headers=self._headers(access_token),
            json={"topicName": topic, "labelIds": ["INBOX"]},
        )
        if response.is_error:
            raise UpstreamServiceError(f"Gmail watch failed ({response.status_code})")
        data = response.json()
        return WatchInfo(history_id=str(data["historyId"]), expiration_ms=int(data["expiration"]))
