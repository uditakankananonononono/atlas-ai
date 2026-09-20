"""Google Calendar API client: watch channels + incremental sync.

Spec reference: "Google Calendar API with watch channels for real-time
updates." Sync uses syncToken; a 410 response means the token expired and a
full resync is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from .ics import IcsEvent

CALENDAR_BASE_URL = "https://www.googleapis.com/calendar/v3"


class UpstreamServiceError(RuntimeError):
    pass


class SyncTokenExpiredError(RuntimeError):
    """The stored syncToken is stale; the caller must do a full resync."""


@dataclass
class WatchInfo:
    channel_id: str
    resource_id: str
    expiration_ms: int | None


@dataclass
class EventPage:
    events: list[IcsEvent]
    next_sync_token: str | None


class GoogleCalendarClient(Protocol):
    async def watch(self, access_token: str, calendar_id: str, *, channel_id: str,
                    address: str, token: str) -> WatchInfo: ...
    async def list_events(self, access_token: str, calendar_id: str, *,
                          sync_token: str | None, time_min: datetime | None) -> EventPage: ...
    async def stop_channel(self, access_token: str, *, channel_id: str, resource_id: str) -> None: ...


def parse_google_event(data: dict[str, Any]) -> IcsEvent:
    def _parse(endpoint: dict[str, Any]) -> datetime | None:
        value = endpoint.get("dateTime") or endpoint.get("date")
        if not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    return IcsEvent(
        uid=data["id"],
        summary=data.get("summary", "(no title)"),
        start=_parse(data.get("start", {})),
        end=_parse(data.get("end", {})),
        location=data.get("location"),
        status=data.get("status", "confirmed").lower(),
        raw={},
    )


class HttpxGoogleCalendarClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str = CALENDAR_BASE_URL) -> None:
        self._client = client
        self._base = base_url.rstrip("/")

    def _headers(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def watch(self, access_token: str, calendar_id: str, *, channel_id: str,
                    address: str, token: str) -> WatchInfo:
        response = await self._client.post(
            f"{self._base}/calendars/{calendar_id}/events/watch",
            headers=self._headers(access_token),
            json={"id": channel_id, "type": "web_hook", "address": address, "token": token},
        )
        if response.is_error:
            raise UpstreamServiceError(f"Calendar watch failed ({response.status_code})")
        data = response.json()
        expiration = data.get("expiration")
        return WatchInfo(
            channel_id=data.get("id", channel_id),
            resource_id=data.get("resourceId", ""),
            expiration_ms=int(expiration) if expiration else None,
        )

    async def list_events(self, access_token: str, calendar_id: str, *,
                          sync_token: str | None, time_min: datetime | None) -> EventPage:
        params: dict[str, str] = {"singleEvents": "true", "maxResults": "250"}
        if sync_token:
            params["syncToken"] = sync_token
        elif time_min:
            params["timeMin"] = time_min.astimezone(timezone.utc).isoformat()
        response = await self._client.get(
            f"{self._base}/calendars/{calendar_id}/events",
            headers=self._headers(access_token), params=params,
        )
        if response.status_code == 410:
            raise SyncTokenExpiredError("sync token expired")
        if response.is_error:
            raise UpstreamServiceError(f"Calendar events.list failed ({response.status_code})")
        data = response.json()
        return EventPage(
            events=[parse_google_event(item) for item in data.get("items", []) or []],
            next_sync_token=data.get("nextSyncToken"),
        )

    async def stop_channel(self, access_token: str, *, channel_id: str, resource_id: str) -> None:
        response = await self._client.post(
            f"{self._base}/channels/stop",
            headers=self._headers(access_token),
            json={"id": channel_id, "resourceId": resource_id},
        )
        if response.is_error:
            raise UpstreamServiceError(f"Calendar channel stop failed ({response.status_code})")
