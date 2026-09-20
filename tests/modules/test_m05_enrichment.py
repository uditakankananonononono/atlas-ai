"""Offline tests for verified contact enrichment (Hunter.io / Clearbit adapters)."""

import asyncio

import httpx
import pytest

from app.modules.m05_outreach_manager.enrichment import (
    ClearbitClient,
    EnrichmentNotConfiguredError,
    EnrichmentService,
    HunterIoClient,
    UpstreamEnrichmentError,
)
from app.modules.m05_outreach_manager.schemas import ContactCreate
from app.modules.m05_outreach_manager.service import (
    ContactNotFoundError,
    InMemoryContactRepository,
    Service,
)


def make_contact(repo, **overrides):
    service = Service(repo, approval_sink=None, scholar=None)
    return service.create_contact(
        ContactCreate(project_id="atlas", name="Dr. Rao", **overrides)
    )


def hunter_transport(finder_payload, verifier_payload, recorder):
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.append(request)
        if request.url.path == "/v2/email-finder":
            return httpx.Response(200, json={"data": finder_payload})
        if request.url.path == "/v2/email-verifier":
            return httpx.Response(200, json={"data": verifier_payload})
        return httpx.Response(404, json={})

    return httpx.MockTransport(handler)


def test_finder_fills_empty_email_with_public_provenance():
    repo = InMemoryContactRepository()
    contact = make_contact(repo, institution="Example University")
    requests = []
    transport = hunter_transport(
        {
            "email": "rao@example.edu",
            "score": 91,
            "sources": [{"uri": "https://example.edu/people/rao"}],
        },
        {},
        requests,
    )
    client = httpx.AsyncClient(transport=transport)
    hunter = HunterIoClient(client, api_key="secret-key", base_url="https://hunter.test/v2")
    enrichment = EnrichmentService(repo, hunter)

    result = asyncio.run(enrichment.find_contact_email(contact.id, "example.edu"))

    assert result.email == "rao@example.edu"
    assert result.confidence == 91
    assert result.sources == ["https://example.edu/people/rao"]
    finder_request = next(r for r in requests if r.url.path == "/v2/email-finder")
    assert finder_request.url.params["domain"] == "example.edu"
    assert finder_request.url.params["first_name"] == "Dr."
    assert finder_request.url.params["last_name"] == "Rao"

    stored = repo.get(contact.id)
    assert stored.email == "rao@example.edu"
    assert stored.metadata["enrichment"]["finder"]["provider"] == "hunter"
    changes = repo.changes(contact.id)
    assert changes[-1].changes["event"] == "email_enriched"
    assert changes[-1].changes["sources"] == ["https://example.edu/people/rao"]
    assert stored.version == 2
    asyncio.run(client.aclose())


def test_finder_never_overwrites_an_existing_email():
    repo = InMemoryContactRepository()
    contact = make_contact(repo, email="known@example.edu")
    hunter = HunterIoClient(httpx.AsyncClient(), api_key="k", base_url="https://hunter.test/v2")
    enrichment = EnrichmentService(repo, hunter)

    with pytest.raises(ValueError, match="already has an email"):
        asyncio.run(enrichment.find_contact_email(contact.id, "example.edu"))
    assert repo.get(contact.id).email == "known@example.edu"


def test_finder_miss_is_recorded_without_changing_the_email():
    repo = InMemoryContactRepository()
    contact = make_contact(repo)
    transport = hunter_transport({"email": None, "score": 0, "sources": []}, {}, [])
    client = httpx.AsyncClient(transport=transport)
    hunter = HunterIoClient(client, api_key="k", base_url="https://hunter.test/v2")
    enrichment = EnrichmentService(repo, hunter)

    result = asyncio.run(enrichment.find_contact_email(contact.id, "example.edu"))

    assert result.email is None
    stored = repo.get(contact.id)
    assert stored.email is None
    assert stored.metadata["enrichment"]["finder_attempt"]["found"] is False
    assert repo.changes(contact.id)[-1].changes["event"] == "email_enrichment_miss"
    asyncio.run(client.aclose())


def test_verification_marks_only_valid_verdicts_as_verified():
    repo = InMemoryContactRepository()
    contact = make_contact(repo, email="rao@example.edu")
    transport = hunter_transport(
        {},
        {"status": "valid", "result": "deliverable", "score": 97, "regexp": True},
        [],
    )
    client = httpx.AsyncClient(transport=transport)
    hunter = HunterIoClient(client, api_key="k", base_url="https://hunter.test/v2")
    enrichment = EnrichmentService(repo, hunter)

    verdict = asyncio.run(enrichment.verify_contact_email(contact.id))

    assert verdict.status == "valid"
    stored = repo.get(contact.id)
    assert stored.metadata["enrichment"]["email_verified"] is True
    assert stored.metadata["enrichment"]["email_verification"]["provider"] == "hunter"
    assert repo.changes(contact.id)[-1].changes["status"] == "valid"
    asyncio.run(client.aclose())


def test_risky_verdict_is_not_treated_as_verified():
    repo = InMemoryContactRepository()
    contact = make_contact(repo, email="any@accept-all.example")
    transport = hunter_transport(
        {}, {"status": "accept_all", "result": "risky", "score": 50}, []
    )
    client = httpx.AsyncClient(transport=transport)
    hunter = HunterIoClient(client, api_key="k", base_url="https://hunter.test/v2")
    enrichment = EnrichmentService(repo, hunter)

    verdict = asyncio.run(enrichment.verify_contact_email(contact.id))

    assert verdict.status == "risky"
    assert repo.get(contact.id).metadata["enrichment"]["email_verified"] is False
    asyncio.run(client.aclose())


def test_missing_provider_key_is_a_clear_optional_dependency_error():
    hunter = HunterIoClient(httpx.AsyncClient(), api_key=None, base_url="https://hunter.test/v2")
    with pytest.raises(EnrichmentNotConfiguredError, match="HUNTER_API_KEY"):
        asyncio.run(hunter.verify_email(email="a@b.edu"))


def test_upstream_failure_carries_status_but_never_the_key():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"errors": [{"details": "invalid key"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    hunter = HunterIoClient(client, api_key="super-secret-key", base_url="https://hunter.test/v2")
    with pytest.raises(UpstreamEnrichmentError) as caught:
        asyncio.run(hunter.verify_email(email="a@b.edu"))
    assert "(401)" in str(caught.value)
    assert "super-secret-key" not in str(caught.value)
    asyncio.run(client.aclose())


def test_clearbit_profile_fills_only_empty_fields():
    repo = InMemoryContactRepository()
    contact = make_contact(repo, email="rao@example.edu")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/combined/find"
        assert request.headers["authorization"] == "Bearer cb-key"
        return httpx.Response(
            200,
            json={
                "person": {
                    "name": {"fullName": "Dr. Rao"},
                    "employment": {"name": "Example University", "title": "Professor"},
                    "location": "Boston, MA",
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    clearbit = ClearbitClient(client, api_key="cb-key")
    hunter = HunterIoClient(httpx.AsyncClient(), api_key="k")
    enrichment = EnrichmentService(repo, hunter, profiler=clearbit)

    profile = asyncio.run(enrichment.enrich_contact_profile(contact.id))

    assert profile.found is True
    stored = repo.get(contact.id)
    assert stored.institution == "Example University"
    assert stored.metadata["enrichment"]["profile"]["provider"] == "clearbit"
    assert repo.changes(contact.id)[-1].changes["filled"] == ["institution"]
    asyncio.run(client.aclose())


def test_clearbit_404_and_202_are_not_errors():
    clearbit_404 = ClearbitClient(
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404))),
        api_key="k",
    )
    profile = asyncio.run(clearbit_404.lookup_person(email="x@y.edu"))
    assert profile.found is False and profile.pending is False

    clearbit_202 = ClearbitClient(
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(202))),
        api_key="k",
    )
    profile = asyncio.run(clearbit_202.lookup_person(email="x@y.edu"))
    assert profile.found is False and profile.pending is True


def test_enrichment_of_unknown_contact_raises_not_found():
    repo = InMemoryContactRepository()
    hunter = HunterIoClient(httpx.AsyncClient(), api_key="k")
    enrichment = EnrichmentService(repo, hunter)
    with pytest.raises(ContactNotFoundError):
        asyncio.run(enrichment.verify_contact_email("missing-id"))
