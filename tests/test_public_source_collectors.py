import asyncio
from datetime import datetime, timezone
import pytest
from app.collectors.public_sources import (
    CollegeScorecardCollector, GrantsGovCollector, SourcePayloadError,
)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


class FakeTransport:
    def __init__(self, *, get=None, post=None):
        self.get = get
        self.post = post
        self.calls = []

    async def get_json(self, url, *, params=None, headers=None):
        self.calls.append(("GET", url, params, headers))
        return self.get

    async def post_json(self, url, *, body, headers=None):
        self.calls.append(("POST", url, body, headers))
        return self.post


def run(coro):
    return asyncio.run(coro)


def test_grants_gov_maps_provenance_deadline_amounts_and_cursor():
    transport = FakeTransport(post={"data": {"hitCount": 2, "oppHits": [{
        "id": "ABC-1", "title": "Open science award", "agencyName": "NSF",
        "closeDate": "2026-12-31", "awardFloor": "1,000", "awardCeiling": 5000,
        "lastUpdatedDate": "2026-09-19T10:00:00Z", "oppStatus": "posted",
    }]}})
    page = run(GrantsGovCollector(transport, clock=lambda: NOW).search("science", page_size=1))
    record = page.records[0]
    assert record.external_id == "grants-gov:ABC-1"
    assert record.deadline.isoformat() == "2026-12-31"
    assert (record.amount_min, record.amount_max, record.currency) == (1000, 5000, "USD")
    assert record.provenance.source_updated_at.isoformat() == "2026-09-19T10:00:00+00:00"
    assert record.provenance.record_url == "https://www.grants.gov/search-results-detail/ABC-1"
    assert page.next_cursor == "1"
    assert transport.calls[0][2]["keyword"] == "science"


def test_grants_gov_rejects_malformed_payload_and_invalid_page_size():
    collector = GrantsGovCollector(FakeTransport(post={}), clock=lambda: NOW)
    with pytest.raises(SourcePayloadError):
        run(collector.search())
    with pytest.raises(ValueError):
        run(collector.search(page_size=0))


def test_college_scorecard_maps_official_school_record_and_paginates():
    transport = FakeTransport(get={"metadata": {"total": 3}, "results": [{
        "id": 166027, "school.name": "Example University", "school.city": "Boston",
        "school.state": "ma", "school.school_url": "example.edu",
        "latest.student.size": "1200", "latest.cost.avg_net_price.overall": 23456,
        "latest.completion.rate_suppressed.overall": 0.81,
    }]})
    page = run(CollegeScorecardCollector(
        transport, api_key="secret", clock=lambda: NOW
    ).search("Example", state="ma", page_size=1))
    record = page.records[0]
    assert record.external_id == "college-scorecard:166027"
    assert record.kind == "university"
    assert record.attributes["student_size"] == 1200
    assert record.url == "https://collegescorecard.ed.gov/school/?id=166027"
    assert record.provenance.source_id == "college-scorecard"
    assert page.next_cursor == "1"
    params = transport.calls[0][2]
    assert params["school.name"] == "Example"
    assert params["school.state"] == "MA"
    assert params["api_key"] == "secret"


def test_college_scorecard_requires_key_and_schema():
    with pytest.raises(ValueError):
        CollegeScorecardCollector(FakeTransport(), api_key=" ")
    collector = CollegeScorecardCollector(FakeTransport(get={"results": None}), api_key="x")
    with pytest.raises(SourcePayloadError):
        run(collector.search())
