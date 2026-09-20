"""Focused pagination and failure tests for Google Calendar sync."""

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.modules.m11_calendar_intelligence.google_calendar import (
    HttpxGoogleCalendarClient,
    UpstreamServiceError,
)


def google_event(uid: str) -> dict:
    return {
        "id": uid,
        "summary": uid,
        "start": {"dateTime": "2026-09-21T09:00:00Z"},
        "end": {"dateTime": "2026-09-21T10:00:00Z"},
    }


def test_list_events_reads_every_page_before_returning_sync_token():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        if request.url.params.get("pageToken") == "page-2":
            return httpx.Response(200, json={
                "items": [google_event("second")], "nextSyncToken": "sync-final",
            })
        return httpx.Response(200, json={
            "items": [google_event("first")], "nextPageToken": "page-2",
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            page = await HttpxGoogleCalendarClient(http).list_events(
                "token", "primary", sync_token="sync-old", time_min=None
            )
            assert [event.uid for event in page.events] == ["first", "second"]
            assert page.next_sync_token == "sync-final"

    asyncio.run(run())
    assert seen[0]["syncToken"] == "sync-old"
    assert "pageToken" not in seen[0]
    assert seen[1]["syncToken"] == "sync-old"
    assert seen[1]["pageToken"] == "page-2"


def test_repeated_page_token_is_rejected_instead_of_looping():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [], "nextPageToken": "same"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(UpstreamServiceError, match="repeated a page token"):
                await HttpxGoogleCalendarClient(http).list_events(
                    "token", "primary", sync_token=None,
                    time_min=datetime(2026, 9, 1, tzinfo=timezone.utc),
                )

    asyncio.run(run())
