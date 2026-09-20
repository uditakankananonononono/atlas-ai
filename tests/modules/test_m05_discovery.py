"""Offline tests for university/lab discovery (registry + robots-respecting collector)."""

import asyncio

import httpx
import pytest

from app.modules.m05_outreach_manager.discovery import (
    DiscoveryError,
    LabDiscoveryService,
    LabEntry,
    LabPageCollector,
    LabRegistry,
    RobotsCache,
    RobotsDisallowedError,
    USER_AGENT,
)

ROBOTS_ALLOW = "User-agent: *\nAllow: /\n"
ROBOTS_DENY = "User-agent: *\nDisallow: /\n"
LAB_HTML = """
<html><head><title>Rao Lab - Spatial Transcriptomics</title></head>
<body>
<h1>Rao Lab</h1>
<h2>Research</h2>
<p>We study spatial transcriptomics.</p>
<a href="mailto:rao@example.edu">Contact Dr. Rao</a>
<a href="mailto:lab-manager@example.edu">Lab manager</a>
<a href="https://example.edu/people">Our team</a>
<a href="/members">Members</a>
<a href="https://example.edu/publications">Publications</a>
</body></html>
"""


def make_transport(robots_body=ROBOTS_ALLOW, page_body=LAB_HTML, page_status=200, recorder=None, content_type="text/html; charset=utf-8"):
    def handler(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots_body)
        return httpx.Response(page_status, text=page_body, headers={"content-type": content_type})

    return httpx.MockTransport(handler)


def test_packaged_registry_loads_and_searches():
    registry = LabRegistry.load()
    entries = registry.all()
    assert len(entries) >= 10
    assert all(entry.url.startswith("https://") for entry in entries)
    assert len({entry.url for entry in entries}) == len(entries)

    hits = registry.search(topics=["spatial transcriptomics"])
    assert hits
    assert any("Broad" in hit.university or "Sanger" in hit.university for hit in hits)

    named = registry.search(query="csail")
    assert named and "CSAIL" in named[0].lab_name

    assert registry.search(query="no-such-lab-xyz") == []


def test_registry_rejects_non_https_and_duplicates(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        '{"entries": [{"university": "U", "department": "D", "lab_name": "L", "topics": [], "url": "http://insecure.example"}]}'
    )
    with pytest.raises(ValueError, match="https"):
        LabRegistry.load(bad)

    dup = tmp_path / "dup.json"
    dup.write_text(
        '{"entries": ['
        '{"university": "U", "department": "D", "lab_name": "L1", "topics": [], "url": "https://a.example"},'
        '{"university": "U", "department": "D", "lab_name": "L2", "topics": [], "url": "https://a.example"}'
        "]}"
    )
    with pytest.raises(ValueError, match="duplicate"):
        LabRegistry.load(dup)


def test_collector_extracts_public_contact_surface():
    requests = []
    client = httpx.AsyncClient(transport=make_transport(recorder=requests), base_url="https://example.edu")
    collector = LabPageCollector(client)

    page = asyncio.run(collector.collect("https://example.edu/lab"))

    assert page.title == "Rao Lab - Spatial Transcriptomics"
    assert "Rao Lab" in page.headings
    assert sorted(page.emails) == ["lab-manager@example.edu", "rao@example.edu"]
    assert "https://example.edu/people" in page.member_links
    assert "https://example.edu/members" in page.member_links
    assert "https://example.edu/publications" not in page.member_links

    page_request = next(r for r in requests if r.url.path == "/lab")
    assert page_request.headers["user-agent"] == USER_AGENT
    assert any(r.url.path == "/robots.txt" for r in requests)
    asyncio.run(client.aclose())


def test_robots_disallow_blocks_the_fetch():
    requests = []
    client = httpx.AsyncClient(transport=make_transport(robots_body=ROBOTS_DENY, recorder=requests))
    collector = LabPageCollector(client)

    with pytest.raises(RobotsDisallowedError, match="robots.txt disallows"):
        asyncio.run(collector.collect("https://example.edu/lab"))

    assert [r.url.path for r in requests] == ["/robots.txt"]
    asyncio.run(client.aclose())


def test_robots_404_means_everything_allowed():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text=LAB_HTML, headers={"content-type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    collector = LabPageCollector(client)
    page = asyncio.run(collector.collect("https://example.edu/lab"))
    assert page.title is not None
    asyncio.run(client.aclose())


def test_non_html_and_http_errors_are_clear_failures():
    client = httpx.AsyncClient(
        transport=make_transport(page_body="PK\x03\x04", content_type="application/zip")
    )
    collector = LabPageCollector(client)
    with pytest.raises(DiscoveryError, match="not HTML"):
        asyncio.run(collector.collect("https://example.edu/file"))
    asyncio.run(client.aclose())

    client = httpx.AsyncClient(transport=make_transport(page_status=500))
    collector = LabPageCollector(client)
    with pytest.raises(DiscoveryError, match="\\(500\\)"):
        asyncio.run(collector.collect("https://example.edu/lab"))
    asyncio.run(client.aclose())


def test_only_https_pages_are_collected():
    collector = LabPageCollector(httpx.AsyncClient())
    with pytest.raises(DiscoveryError, match="https"):
        asyncio.run(collector.collect("http://example.edu/lab"))


def test_robots_cache_fetches_once_per_origin():
    requests = []
    client = httpx.AsyncClient(transport=make_transport(recorder=requests))
    collector = LabPageCollector(client)
    asyncio.run(collector.collect("https://example.edu/lab"))
    asyncio.run(collector.collect("https://example.edu/other"))
    robots_hits = [r for r in requests if r.url.path == "/robots.txt"]
    assert len(robots_hits) == 1
    asyncio.run(client.aclose())


def test_discover_lab_contacts_returns_provenance_without_name_guessing():
    client = httpx.AsyncClient(transport=make_transport())
    service = LabDiscoveryService(LabRegistry.load(), LabPageCollector(client))
    result = asyncio.run(service.discover_lab_contacts("https://example.edu/lab"))
    emails = {item["email"] for item in result["emails"]}
    assert emails == {"rao@example.edu", "lab-manager@example.edu"}
    assert all(item["source_url"] == "https://example.edu/lab" for item in result["emails"])
    assert "https://example.edu/people" in result["member_pages"]
    asyncio.run(client.aclose())
