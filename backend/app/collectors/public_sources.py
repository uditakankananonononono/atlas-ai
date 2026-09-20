"""Public-source collectors with explicit provenance and freshness metadata.

Collectors in this module deliberately contain no browser/login automation.  Network I/O
is injected through ``JsonTransport`` so production can use the application's HTTP client
and tests can remain deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlencode


Json = Mapping[str, Any]


class JsonTransport(Protocol):
    async def get_json(
        self, url: str, *, params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Json: ...

    async def post_json(
        self, url: str, *, body: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Json: ...


@dataclass(frozen=True, slots=True)
class Provenance:
    source_id: str
    source_name: str
    official_url: str
    record_url: str
    retrieved_at: datetime
    source_updated_at: datetime | None = None
    license_url: str | None = None

    def __post_init__(self) -> None:
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if self.source_updated_at is not None and self.source_updated_at.tzinfo is None:
            raise ValueError("source_updated_at must be timezone-aware")
        if not self.official_url.startswith("https://") or not self.record_url.startswith("https://"):
            raise ValueError("provenance URLs must use HTTPS")


@dataclass(frozen=True, slots=True)
class PublicRecord:
    external_id: str
    kind: str
    title: str
    summary: str | None
    organization: str | None
    deadline: date | None
    amount_min: int | None
    amount_max: int | None
    currency: str | None
    url: str
    provenance: Provenance
    attributes: Mapping[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        stable = {
            "external_id": self.external_id,
            "kind": self.kind,
            "title": self.title,
            "summary": self.summary,
            "organization": self.organization,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "amount_min": self.amount_min,
            "amount_max": self.amount_max,
            "currency": self.currency,
            "url": self.url,
            "attributes": self.attributes,
        }
        encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CollectionPage:
    records: tuple[PublicRecord, ...]
    retrieved_at: datetime
    next_cursor: str | None
    raw_count: int


class SourcePayloadError(ValueError):
    """The official source responded, but its payload did not match its public schema."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "").replace("$", "")))
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed_date = _date(text)
        return datetime.combine(parsed_date, datetime.min.time(), timezone.utc) if parsed_date else None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


class GrantsGovCollector:
    """Adapter for Grants.gov's documented public search API."""

    source_id = "grants-gov"
    endpoint = "https://api.grants.gov/v1/api/search2"
    official_url = "https://www.grants.gov/"

    def __init__(self, transport: JsonTransport, *, clock=_utcnow) -> None:
        self._transport = transport
        self._clock = clock

    async def search(
        self, query: str = "", *, page_size: int = 25, cursor: str | None = None,
        funding_categories: Sequence[str] = (),
    ) -> CollectionPage:
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        offset = int(cursor or "0")
        body: dict[str, Any] = {
            "keyword": query.strip(), "oppStatuses": "forecasted|posted",
            "rows": page_size, "startRecordNum": offset,
        }
        if funding_categories:
            body["fundingCategories"] = "|".join(funding_categories)
        payload = await self._transport.post_json(
            self.endpoint, body=body, headers={"Accept": "application/json"}
        )
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise SourcePayloadError("Grants.gov payload has no data object")
        rows = data.get("oppHits", data.get("opportunities", []))
        if not isinstance(rows, list):
            raise SourcePayloadError("Grants.gov opportunity list is not an array")
        retrieved_at = self._clock()
        records = tuple(self._map(row, retrieved_at) for row in rows if isinstance(row, Mapping))
        total = _int(data.get("hitCount", data.get("totalRecords")))
        next_offset = offset + len(rows)
        next_cursor = str(next_offset) if rows and (total is None or next_offset < total) else None
        return CollectionPage(records, retrieved_at, next_cursor, len(rows))

    def _map(self, row: Json, retrieved_at: datetime) -> PublicRecord:
        number = _text(row.get("number") or row.get("oppNumber") or row.get("id"))
        title = _text(row.get("title") or row.get("oppTitle"))
        if not number or not title:
            raise SourcePayloadError("Grants.gov record is missing number or title")
        record_url = f"https://www.grants.gov/search-results-detail/{number}"
        return PublicRecord(
            external_id=f"grants-gov:{number}", kind="grant", title=title,
            summary=_text(row.get("description") or row.get("synopsis")),
            organization=_text(row.get("agencyName") or row.get("agency")),
            deadline=_date(row.get("closeDate") or row.get("closeDateDisplay")),
            amount_min=_int(row.get("awardFloor")), amount_max=_int(row.get("awardCeiling")),
            currency="USD" if row.get("awardFloor") is not None or row.get("awardCeiling") is not None else None,
            url=record_url,
            provenance=Provenance(
                source_id=self.source_id, source_name="Grants.gov", official_url=self.official_url,
                record_url=record_url, retrieved_at=retrieved_at,
                source_updated_at=_datetime(row.get("lastUpdatedDate") or row.get("updatedDate")),
            ),
            attributes={
                "opportunity_status": _text(row.get("oppStatus") or row.get("status")),
                "funding_instrument": _text(row.get("fundingInstrumentType")),
                "eligibility": row.get("eligibilities") or row.get("eligibility"),
            },
        )


class CollegeScorecardCollector:
    """Adapter for the U.S. Department of Education College Scorecard API."""

    source_id = "college-scorecard"
    endpoint = "https://api.data.gov/ed/collegescorecard/v1/schools"
    official_url = "https://collegescorecard.ed.gov/data/"
    fields = (
        "id,school.name,school.city,school.state,school.school_url,school.ownership,"
        "latest.student.size,latest.cost.avg_net_price.overall,latest.completion.rate_suppressed.overall"
    )

    def __init__(self, transport: JsonTransport, *, api_key: str, clock=_utcnow) -> None:
        if not api_key.strip():
            raise ValueError("College Scorecard requires a data.gov API key")
        self._transport = transport
        self._api_key = api_key
        self._clock = clock

    async def search(
        self, query: str = "", *, state: str | None = None, page_size: int = 25,
        cursor: str | None = None,
    ) -> CollectionPage:
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        page = int(cursor or "0")
        params: dict[str, Any] = {
            "api_key": self._api_key, "fields": self.fields,
            "per_page": page_size, "page": page,
        }
        if query.strip():
            params["school.name"] = query.strip()
        if state:
            params["school.state"] = state.strip().upper()
        payload = await self._transport.get_json(
            self.endpoint, params=params, headers={"Accept": "application/json"}
        )
        rows = payload.get("results")
        if not isinstance(rows, list):
            raise SourcePayloadError("College Scorecard payload has no results array")
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        total = _int(metadata.get("total"))
        retrieved_at = self._clock()
        records = tuple(self._map(row, retrieved_at) for row in rows if isinstance(row, Mapping))
        consumed = (page * page_size) + len(rows)
        next_cursor = str(page + 1) if rows and (total is None or consumed < total) else None
        return CollectionPage(records, retrieved_at, next_cursor, len(rows))

    def _map(self, row: Json, retrieved_at: datetime) -> PublicRecord:
        unit_id = _text(row.get("id"))
        title = _text(row.get("school.name"))
        if not unit_id or not title:
            raise SourcePayloadError("College Scorecard record is missing id or school.name")
        record_url = f"https://collegescorecard.ed.gov/school/?{urlencode({'id': unit_id})}"
        return PublicRecord(
            external_id=f"college-scorecard:{unit_id}", kind="university", title=title,
            summary=None, organization=title, deadline=None, amount_min=None,
            amount_max=None, currency=None, url=record_url,
            provenance=Provenance(
                source_id=self.source_id, source_name="U.S. Department of Education College Scorecard",
                official_url=self.official_url, record_url=record_url, retrieved_at=retrieved_at,
            ),
            attributes={
                "city": _text(row.get("school.city")), "state": _text(row.get("school.state")),
                "website": _text(row.get("school.school_url")),
                "ownership": row.get("school.ownership"),
                "student_size": _int(row.get("latest.student.size")),
                "average_net_price": _int(row.get("latest.cost.avg_net_price.overall")),
                "completion_rate": row.get("latest.completion.rate_suppressed.overall"),
            },
        )
