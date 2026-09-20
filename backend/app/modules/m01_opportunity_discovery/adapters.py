"""Adapters for official opportunity APIs.

Endpoints are official Grants.gov, SAM.gov and TED Search APIs. SAM.gov requires
an API key supplied by the deployer; no credentials are embedded or logged.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Protocol
from urllib.parse import urlencode

from .http import JsonTransport, UrllibJsonTransport
from .models import Opportunity, OpportunityKind, SearchQuery
from .normalization import canonical_url, clean_text, make_provenance, parse_date, parse_money


class OpportunityAdapter(Protocol):
    name: str
    def search(self, query: SearchQuery) -> list[Opportunity]: ...


def _values(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(x.strip() for x in value.replace(";", ",").split(",") if x.strip())
    if isinstance(value, Mapping):
        return tuple(clean_text(x) for x in value.values() if clean_text(x))
    if isinstance(value, Iterable):
        return tuple(clean_text(x.get("name", x.get("value", "")) if isinstance(x, Mapping) else x) for x in value if clean_text(x))
    return (clean_text(value),)


@dataclass(slots=True)
class GrantsGovAdapter:
    transport: JsonTransport = None  # type: ignore[assignment]
    name: str = "grants.gov"
    endpoint: str = "https://api.grants.gov/v1/api/search2"

    def __post_init__(self) -> None:
        self.transport = self.transport or UrllibJsonTransport()

    def search(self, query: SearchQuery) -> list[Opportunity]:
        raw = self.transport.request("POST", self.endpoint, body={"keyword": query.text, "rows": query.limit, "oppStatuses": "forecasted|posted"})
        container = raw.get("data", raw) if isinstance(raw, Mapping) else {}
        rows = container.get("oppHits") or container.get("opportunities") or container.get("hits") or []
        fetched = datetime.now(timezone.utc)
        result = []
        for row in rows[: query.limit]:
            sid = clean_text(row.get("id") or row.get("opportunityNumber") or row.get("oppNum"))
            if not sid:
                continue
            url = clean_text(row.get("url") or f"https://www.grants.gov/search-results-detail/{sid}")
            result.append(Opportunity(
                id=f"grants-gov:{sid}", title=clean_text(row.get("title") or row.get("opportunityTitle")),
                description=clean_text(row.get("synopsis") or row.get("description")), kind=OpportunityKind.GRANT,
                sponsor=clean_text(row.get("agencyName") or row.get("agency")), source_status=clean_text(row.get("oppStatus") or row.get("status")),
                open_date=parse_date(row.get("openDate") or row.get("postDate")), close_date=parse_date(row.get("closeDate")),
                amount_min=parse_money(row.get("awardFloor")), amount_max=parse_money(row.get("awardCeiling")), currency="USD",
                countries=("US",), eligibility=_values(row.get("eligibilities") or row.get("eligibility")),
                tags=_values(row.get("category") or row.get("fundingCategories")), canonical_url=canonical_url(url),
                provenance=(make_provenance(self.name, sid, url, row, fetched),), updated_at=None,
                metadata={"opportunity_number": clean_text(row.get("opportunityNumber") or row.get("oppNum"))},
            ))
        return result


@dataclass(slots=True)
class SamGovAdapter:
    api_key: str
    transport: JsonTransport = None  # type: ignore[assignment]
    name: str = "sam.gov"
    endpoint: str = "https://api.sam.gov/opportunities/v2/search"

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("SAM.gov API key is required")
        self.transport = self.transport or UrllibJsonTransport()

    def search(self, query: SearchQuery) -> list[Opportunity]:
        params = {"api_key": self.api_key, "limit": min(query.limit, 1000), "q": query.text}
        raw = self.transport.request("GET", f"{self.endpoint}?{urlencode(params)}")
        rows = raw.get("opportunitiesData", []) if isinstance(raw, Mapping) else []
        fetched = datetime.now(timezone.utc)
        result = []
        for row in rows[: query.limit]:
            sid = clean_text(row.get("noticeId") or row.get("solicitationNumber"))
            if not sid:
                continue
            url = clean_text(row.get("uiLink") or f"https://sam.gov/opp/{sid}/view")
            award = row.get("award") or {}
            result.append(Opportunity(
                id=f"sam-gov:{sid}", title=clean_text(row.get("title")), description=clean_text(row.get("description")),
                kind=OpportunityKind.PROCUREMENT, sponsor=clean_text(row.get("fullParentPathName") or row.get("department") or row.get("office")),
                source_status=clean_text(row.get("type") or row.get("active")), open_date=parse_date(row.get("postedDate")), close_date=parse_date(row.get("responseDeadLine")),
                amount_min=None, amount_max=parse_money(award.get("amount") if isinstance(award, Mapping) else None), currency="USD",
                countries=("US",), eligibility=_values(row.get("typeOfSetAsideDescription")), tags=_values(row.get("naicsCode")),
                canonical_url=canonical_url(url), provenance=(make_provenance(self.name, sid, url, row, fetched),),
                updated_at=None, metadata={"solicitation_number": clean_text(row.get("solicitationNumber"))},
            ))
        return result


@dataclass(slots=True)
class TedAdapter:
    transport: JsonTransport = None  # type: ignore[assignment]
    name: str = "ted.europa.eu"
    endpoint: str = "https://api.ted.europa.eu/v3/notices/search"

    def __post_init__(self) -> None:
        self.transport = self.transport or UrllibJsonTransport()

    def search(self, query: SearchQuery) -> list[Opportunity]:
        body = {"query": query.text, "page": 1, "limit": min(query.limit, 100), "fields": ["publication-number", "notice-title", "buyer-name", "deadline", "publication-date", "estimated-value", "place-of-performance", "notice-type"]}
        raw = self.transport.request("POST", self.endpoint, body=body)
        rows = (raw.get("notices") or raw.get("results") or []) if isinstance(raw, Mapping) else []
        fetched = datetime.now(timezone.utc)
        result = []
        for row in rows[: query.limit]:
            sid = clean_text(row.get("publication-number") or row.get("publicationNumber") or row.get("id"))
            if not sid:
                continue
            url = f"https://ted.europa.eu/en/notice/-/detail/{sid}"
            value = row.get("estimated-value") or row.get("estimatedValue") or {}
            amount = value.get("value") if isinstance(value, Mapping) else value
            currency = value.get("currency") if isinstance(value, Mapping) else "EUR"
            result.append(Opportunity(
                id=f"ted:{sid}", title=clean_text(row.get("notice-title") or row.get("title")), description=clean_text(row.get("description")),
                kind=OpportunityKind.PROCUREMENT, sponsor=clean_text(row.get("buyer-name") or row.get("buyerName")), source_status=clean_text(row.get("notice-type") or "published"),
                open_date=parse_date(row.get("publication-date") or row.get("publicationDate")), close_date=parse_date(row.get("deadline")),
                amount_min=None, amount_max=parse_money(amount), currency=clean_text(currency) or "EUR", countries=_values(row.get("place-of-performance") or row.get("placeOfPerformance")),
                eligibility=(), tags=_values(row.get("cpv")), canonical_url=url, provenance=(make_provenance(self.name, sid, url, row, fetched),), updated_at=None,
            ))
        return result
