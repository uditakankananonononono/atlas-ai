"""Async facade + API tests for Module 18.

Runs under pytest (repo env: fastapi/pydantic present). The stubs/ directory
supplies local stand-ins for shared repo modules (app.core.providers,
app.modules.types) and is never delivered.
"""
import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m18_side_hustle_scraper.lane_freshness import FreshnessMonitor
from app.modules.m18_side_hustle_scraper.lane_pipeline import CollectionPipeline
from app.modules.m18_side_hustle_scraper.lane_ranking import BlueprintRanker
from app.modules.m18_side_hustle_scraper.lane_repository import SQLiteDocumentRepository
from app.modules.m18_side_hustle_scraper.schemas import CollectIn, DiscoverIn, RankIn, UserContext
from app.modules.m18_side_hustle_scraper.service import Service
from app.modules.m18_side_hustle_scraper.lane_validation import DocumentValidator


async def gen(prompt, *args):
    return "mock", json.dumps([{
        "title": "Tutoring", "steps": ["Interview 5 students"], "tools": ["calendar"],
        "complexity": 2, "time_to_first_dollar_days": 14, "automation_level": 10,
        "monetisation": ["sessions"], "source_urls": ["https://example.com/a"],
        "scam_signals": [], "assumptions": ["demand"],
    }])


class AsyncCollector:
    async def collect(self, query, limit):
        return [{"url": "https://example.com/a", "text": "Interview students before offering tutoring."}]


class SyncCollector:
    def __init__(self, docs):
        self._docs = docs

    def collect(self, query, limit):
        return list(self._docs)[:limit], []


def make_pipeline():
    repo = SQLiteDocumentRepository(":memory:")
    monitor = FreshnessMonitor(repo)
    docs = []
    from app.modules.m18_side_hustle_scraper.lane_models import RawDocument, RightsClass, SourceKind
    docs.append(RawDocument(
        id="s1", url="https://reddit.example.com/s1", platform="reddit", kind=SourceKind.REDDIT_JSON,
        rights=RightsClass.OFFICIAL_API, title="Tutoring income report",
        text="Step 1: interview students. Step 2: price at $20. Then build a booking page. "
             "Finally ask for referrals. Tools: calendar app, payment platform.",
        engagement={"score": 42.0, "comments": 9.0},
    ))
    pipeline = CollectionPipeline(
        repository=repo, validator=DocumentValidator(), ranker=BlueprintRanker(),
        monitor=monitor, collectors={"reddit": SyncCollector(docs)},
    )
    return pipeline


class SkeletonCompatTests(unittest.TestCase):
    def test_discover_unchanged_and_keeps_sources(self):
        service = Service(generate=gen, collectors={"youtube": AsyncCollector()})
        out = asyncio.run(service.discover(DiscoverIn(query="student business", platforms=["youtube"])))
        self.assertEqual(str(out[0].source_urls[0]), "https://example.com/a")

    def test_discover_rejects_prohibited_channel(self):
        service = Service(generate=gen, collectors={})
        with self.assertRaises(ValueError):
            asyncio.run(service.discover(DiscoverIn(query="student business", platforms=["instagram_login"])))


class PipelineFacadeTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = make_pipeline()
        self.service = Service(generate=gen, collectors={}, pipeline=self.pipeline, tenant_id="t1")

    def test_collect_then_rank(self):
        report = asyncio.run(self.service.collect(CollectIn(query="tutoring", platforms=["reddit"])))
        self.assertEqual(report.documents_new, 1)
        ranked = asyncio.run(self.service.ranked(RankIn(query="tutoring", user=UserContext(skills=["teaching"]))))
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].doc_id, "s1")
        self.assertTrue(ranked[0].breakdown)

    def test_refresh_and_freshness_report(self):
        asyncio.run(self.service.collect(CollectIn(query="tutoring", platforms=["reddit"])))
        refresh = asyncio.run(self.service.refresh(lambda url, kind: {"status": 200, "content_hash": "new-hash"}))
        self.assertEqual(refresh.changes_detected, 1)
        report = asyncio.run(self.service.freshness_report())
        self.assertEqual(report["watched"], 1)
        self.assertEqual(report["alive"], 1)

    def test_missing_pipeline_raises_runtime_error(self):
        service = Service(generate=gen, collectors={})
        with self.assertRaises(RuntimeError):
            asyncio.run(service.collect(CollectIn(query="tutoring", platforms=["reddit"])))


class ApiTests(unittest.TestCase):
    def test_router_endpoints(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from app.modules.m18_side_hustle_scraper import routes, spec
        except ImportError:
            self.skipTest("fastapi or shared repo stubs unavailable")
        app = FastAPI()
        app.include_router(routes.router, prefix="/api")
        client = TestClient(app)

        bad = client.post("/api/side-hustle-scraper/blueprints",
                          json={"query": "dance hacks", "platforms": ["tiktok_unofficial"]})
        self.assertEqual(bad.status_code, 422)

        collect = client.post("/api/side-hustle-scraper/collect",
                              json={"query": "tutoring", "platforms": ["reddit"]})
        self.assertEqual(collect.status_code, 200)
        body = collect.json()
        self.assertIn("documents_found", body)
        self.assertNotIn("collector_not_configured:reddit", body["platforms"][0]["errors"])

        rank = client.post("/api/side-hustle-scraper/rank", json={"query": "tutoring"})
        self.assertEqual(rank.status_code, 200)
        self.assertEqual(rank.json(), [])

        fresh = client.get("/api/side-hustle-scraper/freshness")
        self.assertEqual(fresh.status_code, 200)
        self.assertIn("watched", fresh.json())

        refresh = client.post("/api/side-hustle-scraper/refresh",headers={"x-atlas-tenant":"test-tenant"})
        self.assertEqual(refresh.status_code, 200)
        self.assertEqual(refresh.json()["sources_checked"], 0)

        self.assertEqual(spec.id, 18)
        self.assertEqual(spec.slug, "side-hustle-scraper")


if __name__ == "__main__":
    unittest.main()
