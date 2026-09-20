"""Offline tests for module 1 (Opportunity Discovery Engine).

All network transport is replaced by an injected fake fetcher; the BYOK
provider is monkeypatched; persistence runs on in-memory SQLite. No test
touches the real network, the shared approval database, or provider keys.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.models import ApprovalStatus
from app.core.providers import ProviderError
from app.modules.m01_opportunity_discovery.routes import get_service, router
from app.modules.m01_opportunity_discovery.schemas import OpportunityType, ProfileIn
from app.modules.m01_opportunity_discovery.service import (
    DEFAULT_SOURCES,
    Service,
    Source,
    parse_deadline,
    tag_type,
)

RSS_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test feed</title>
<item>
  <title>Global Machine Learning Hackathon 2026</title>
  <link>https://example.org/ml-hackathon</link>
  <description>Build machine learning models. $50,000 prize pool. Deadline: 2026-12-01.</description>
  <pubDate>Sat, 19 Sep 2026 10:00:00 +0000</pubDate>
</item>
<item>
  <title>Community Garden Cooking Show</title>
  <link>https://example.org/cooking</link>
  <description>A neighbourhood cooking event.</description>
</item>
</channel></rss>
"""

GITHUB_PAYLOAD = b"""{"items": [
  {"full_name": "org/ml-competition-kit", "html_url": "https://github.com/org/ml-competition-kit",
   "description": "Starter kit for a machine learning competition", "topics": ["competition", "machine-learning"],
   "pushed_at": "2026-09-18T09:00:00Z"}
]}"""

ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <title>Undergraduate Research Fellowship</title>
  <link rel="alternate" href="https://example.org/fellowship"/>
  <summary>Funded research fellowship for undergraduates. Apply by March 1, 2027.</summary>
  <updated>2026-09-15T08:00:00Z</updated>
</entry>
</feed>
"""

PROFILE = ProfileIn(
    interests=["machine learning", "data science"],
    skills=["python", "machine learning"],
    past_successes=["won a machine learning competition"],
)


def memory_session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return sessionmaker(bind=engine, expire_on_commit=False)


class FakeApprovalStore:
    """Captures approval requests instead of writing to the shared database."""

    def __init__(self) -> None:
        self.requests = []

    def put(self, request):
        self.requests.append(request)
        return request


def make_service(fetcher, notifier=None):
    return Service(
        session_factory=memory_session_factory(),
        fetcher=fetcher,
        approval_putter=FakeApprovalStore().put,
        notifier=notifier,
    )


def two_source_fetcher(source: Source) -> bytes:
    if source.kind.value == "github_search":
        return GITHUB_PAYLOAD
    return RSS_FEED


# --- success paths ---------------------------------------------------------


def test_scan_stores_scores_and_tags():
    service = make_service(two_source_fetcher)
    sources = [s for s in DEFAULT_SOURCES if s.id in ("opportunity-desk-rss", "github-topics-api")]
    service._sources = tuple(sources)
    result = service.run_scan(profile=PROFILE)
    assert result.fetched == 2
    assert result.new == 3
    assert result.errors == []

    opportunities = service.list_opportunities()
    assert len(opportunities) == 3
    hackathon = next(o for o in opportunities if "Hackathon" in o.title)
    assert hackathon.opportunity_type == OpportunityType.HACKATHON
    assert "hackathon" in hackathon.tags
    assert hackathon.deadline is not None and hackathon.deadline.strftime("%Y-%m-%d") == "2026-12-01"
    # The ML-heavy items must outrank the irrelevant cooking event.
    cooking = next(o for o in opportunities if "Cooking" in o.title)
    assert hackathon.match_score > 0.0
    assert cooking.match_score == 0.0  # zero token overlap with the profile
    assert hackathon.match_score > cooking.match_score
    assert hackathon.expected_impact > 0.5  # prize money mentioned
    # Results are sorted best match first.
    scores = [o.match_score for o in opportunities]
    assert scores == sorted(scores, reverse=True)


def test_rescan_upserts_instead_of_duplicating():
    service = make_service(two_source_fetcher)
    service._sources = (DEFAULT_SOURCES[0],)
    first = service.run_scan(profile=PROFILE)
    second = service.run_scan(profile=PROFILE)
    assert first.new == 2 and first.updated == 0
    assert second.new == 0 and second.updated == 2
    assert len(service.list_opportunities()) == 2


def test_notifier_fires_only_above_threshold():
    seen = []
    service = make_service(two_source_fetcher, notifier=seen.append)
    service._sources = (DEFAULT_SOURCES[0],)
    result = service.run_scan(profile=PROFILE, notify_threshold=0.1)
    assert result.notified == len(seen) == 1  # only the ML hackathon scores >= 0.1
    assert seen[0].match_score >= 0.1

    seen2 = []
    service2 = make_service(two_source_fetcher, notifier=seen2.append)
    service2._sources = (DEFAULT_SOURCES[0],)
    service2.run_scan(profile=ProfileIn(interests=["underwater basket weaving"]), notify_threshold=0.8)
    assert seen2 == []  # nothing matches, nothing notified


def test_atom_feed_and_fellowship_tagging():
    service = make_service(lambda source: ATOM_FEED)
    service._sources = (
        Source(id="atom", name="Atom", kind=DEFAULT_SOURCES[0].kind, url="https://example.org/feed"),
    )
    result = service.run_scan(profile=ProfileIn(interests=["research fellowship"]))
    assert result.new == 1
    fellowship = service.list_opportunities()[0]
    assert fellowship.opportunity_type == OpportunityType.FELLOWSHIP
    assert fellowship.deadline is not None and fellowship.deadline.strftime("%Y-%m-%d") == "2027-03-01"


# --- failure / safety paths ------------------------------------------------


def test_failing_source_is_isolated():
    def flaky(source: Source) -> bytes:
        if source.kind.value == "github_search":
            raise ConnectionError("boom")
        return RSS_FEED

    service = make_service(flaky)
    service._sources = tuple(s for s in DEFAULT_SOURCES if s.id in ("opportunity-desk-rss", "github-topics-api"))
    result = service.run_scan(profile=PROFILE)
    assert result.fetched == 1
    assert len(result.errors) == 1 and "boom" in result.errors[0].error
    assert len(service.list_opportunities()) == 2  # the healthy source still landed


def test_malformed_feed_is_reported_not_raised():
    service = make_service(lambda source: b"not xml at all <")
    service._sources = (DEFAULT_SOURCES[0],)
    result = service.run_scan(profile=PROFILE)
    assert result.fetched == 0
    assert len(result.errors) == 1 and "malformed feed" in result.errors[0].error


def test_default_sources_are_compliant():
    """No self-bots, unofficial social wrappers, or ToS-violating scrapers ship by default."""

    for source in DEFAULT_SOURCES:
        haystack = f"{source.id} {source.url}".lower()
        for banned in ("discord", "selfbot", "self-bot", "instagram", "linkedin", "twitter", "x.com", "unstop"):
            assert banned not in haystack
        assert source.url.startswith("https://")


def test_digest_is_gated_behind_approval():
    approvals = FakeApprovalStore()
    service = Service(
        session_factory=memory_session_factory(),
        fetcher=two_source_fetcher,
        approval_putter=approvals.put,
    )
    service._sources = (DEFAULT_SOURCES[0],)
    service.run_scan(profile=PROFILE)
    items = service.top_opportunities(min_score=0.0, limit=5)
    body = service.render_digest(items)
    request = service.propose_digest(items=items, body=body, recipient="user@example.org")
    assert request.status == ApprovalStatus.PENDING
    assert request.module_id == 1
    assert request.action_type == "send_opportunity_digest_email"
    assert request.payload["execution_enabled"] is False
    assert request.payload["recipient"] == "user@example.org"
    assert len(request.payload["item_ids"]) == len(items)
    assert approvals.requests == [request]  # recorded, never sent


# --- route-level tests (service injected, network mocked) ------------------


@pytest.fixture()
def client():
    approvals = FakeApprovalStore()
    service = Service(
        session_factory=memory_session_factory(),
        fetcher=two_source_fetcher,
        approval_putter=approvals.put,
    )
    service._sources = tuple(s for s in DEFAULT_SOURCES if s.id in ("opportunity-desk-rss", "github-topics-api"))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app), service


def test_scan_and_list_routes(client):
    http, _ = client
    scan = http.post("/opportunity-discovery/scans", json={"profile": PROFILE.model_dump()})
    assert scan.status_code == 200
    assert scan.json()["new"] == 3
    listing = http.get("/opportunity-discovery/opportunities", params={"min_score": 0.05})
    assert listing.status_code == 200
    assert len(listing.json()) == 2  # the cooking event scores 0.0 and is filtered out
    listing_all = http.get("/opportunity-discovery/opportunities")
    assert len(listing_all.json()) == 3
    by_type = http.get("/opportunity-discovery/opportunities", params={"opportunity_type": "hackathon"})
    assert [o["opportunity_type"] for o in by_type.json()] == ["hackathon"]
    first = listing.json()[0]
    fetched = http.get(f"/opportunity-discovery/opportunities/{first['id']}")
    assert fetched.status_code == 200 and fetched.json()["id"] == first["id"]
    assert http.get("/opportunity-discovery/opportunities/nope").status_code == 404


def test_sources_route(client):
    http, _ = client
    response = http.get("/opportunity-discovery/sources")
    assert response.status_code == 200
    assert {s["id"] for s in response.json()} == {"opportunity-desk-rss", "github-topics-api"}


def test_digest_route_creates_pending_approval(client):
    http, _ = client
    http.post("/opportunity-discovery/scans", json={"profile": PROFILE.model_dump()})
    response = http.post("/opportunity-discovery/digests", json={"min_score": 0.05, "recipient": "u@example.org"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["item_count"] >= 1
    assert "Hackathon" in body["preview"]


def test_digest_route_uses_byok_llm_when_requested(client, monkeypatch):
    http, _ = client
    http.post("/opportunity-discovery/scans", json={"profile": PROFILE.model_dump()})
    calls = []

    async def fake_generate(prompt, provider, model=None):
        calls.append((prompt, provider, model))
        return "test-model", "Polished digest from the BYOK provider."

    monkeypatch.setattr("app.modules.m01_opportunity_discovery.routes.generate", fake_generate)
    response = http.post(
        "/opportunity-discovery/digests",
        json={"min_score": 0.05, "use_llm": True, "provider": "openai"},
    )
    assert response.status_code == 200
    assert response.json()["preview"].startswith("Polished digest")
    assert len(calls) == 1 and calls[0][1] == "openai"
    assert "machine learning" in calls[0][0].lower()  # prompt carries the opportunities


def test_digest_route_falls_back_when_byok_fails(client, monkeypatch):
    http, _ = client
    http.post("/opportunity-discovery/scans", json={"profile": PROFILE.model_dump()})

    async def failing_generate(prompt, provider, model=None):
        raise ProviderError("OPENAI_API_KEY is not configured")

    monkeypatch.setattr("app.modules.m01_opportunity_discovery.routes.generate", failing_generate)
    response = http.post(
        "/opportunity-discovery/digests",
        json={"min_score": 0.05, "use_llm": True},
    )
    assert response.status_code == 200
    assert "Hackathon" in response.json()["preview"]  # deterministic template, still gated


def test_digest_route_404_when_nothing_qualifies(client):
    http, _ = client
    http.post("/opportunity-discovery/scans", json={"profile": ProfileIn(interests=["nothing relevant"]).model_dump()})
    response = http.post("/opportunity-discovery/digests", json={"min_score": 0.99})
    assert response.status_code == 404


# --- pure helpers ----------------------------------------------------------


def test_deadline_parsing_formats():
    assert parse_deadline("Deadline: 2026-12-01").strftime("%Y-%m-%d") == "2026-12-01"
    assert parse_deadline("Apply by March 1, 2027.").strftime("%Y-%m-%d") == "2027-03-01"
    assert parse_deadline("no date here") is None


def test_type_tagging_precedence():
    opp_type, tags = tag_type("Global Hackathon", "a coding competition", OpportunityType.OTHER)
    assert opp_type == OpportunityType.HACKATHON
    assert "hackathon" in tags
