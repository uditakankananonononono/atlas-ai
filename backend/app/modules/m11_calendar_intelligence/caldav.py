"""CalDAV client for external calendars (Outlook, Apple, Fastmail, ...).

Spec reference: "External calendars (Outlook, Apple) via CalDAV."
Read-only calendar-query REPORT; all HTTP through an injected client.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Protocol

import httpx

from .ics import IcsEvent, format_ics_dt, parse_ics_events


class UpstreamServiceError(RuntimeError):
    pass


class CalDAVClient(Protocol):
    async def fetch_events(self, calendar_url: str, start: datetime, end: datetime) -> list[IcsEvent]: ...


_REPORT_BODY = """<?xml version="1.0" encoding="utf-8"?>
<c:calendar-query xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:d="DAV:">
  <d:prop><d:getetag/><c:calendar-data/></d:prop>
  <c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT">
    <c:time-range start="{start}" end="{end}"/>
  </c:comp-filter></c:comp-filter></c:filter>
</c:calendar-query>"""

_NS_D = "DAV:"
_NS_C = "urn:ietf:params:xml:ns:caldav"


class HttpxCalDAVClient:
    """Live CalDAV client using basic auth (app passwords)."""

    def __init__(self, client: httpx.AsyncClient, username: str, password: str) -> None:
        self._client = client
        self._auth = (username, password)

    async def fetch_events(self, calendar_url: str, start: datetime, end: datetime) -> list[IcsEvent]:
        body = _REPORT_BODY.format(start=format_ics_dt(start), end=format_ics_dt(end))
        response = await self._client.request(
            "REPORT",
            calendar_url,
            content=body,
            auth=self._auth,
            headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
        )
        if response.is_error:
            raise UpstreamServiceError(f"CalDAV REPORT failed ({response.status_code})")
        return parse_multistatus(response.text)


def parse_multistatus(xml_text: str) -> list[IcsEvent]:
    """Extract every VEVENT from a CalDAV multistatus response."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise UpstreamServiceError(f"invalid CalDAV XML: {exc}") from exc
    events: list[IcsEvent] = []
    for calendar_data in root.iter(f"{{{_NS_C}}}calendar-data"):
        if calendar_data.text:
            events.extend(parse_ics_events(calendar_data.text))
    return events
