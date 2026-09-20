"""Original skeleton acceptance tests (Lane F), kept passing verbatim in
unittest form: blueprint extraction preserves source URLs and prohibited
channels are rejected."""
import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m18_side_hustle_scraper.schemas import DiscoverIn
from app.modules.m18_side_hustle_scraper.service import Service


async def gen(prompt, *args):
    return "mock", json.dumps([{
        "title": "Tutoring", "steps": ["Interview 5 students"], "tools": ["calendar"],
        "complexity": 2, "time_to_first_dollar_days": 14, "automation_level": 10,
        "monetisation": ["sessions"], "source_urls": ["https://example.com/a"],
        "scam_signals": [], "assumptions": ["demand"],
    }])


class C:
    async def collect(self, q, l):
        return [{"url": "https://example.com/a", "text": "Interview students before offering tutoring."}]


class SkeletonTests(unittest.TestCase):
    def test_blueprint_keeps_sources(self):
        x = asyncio.run(Service(generate=gen, collectors={"youtube": C()}).discover(
            DiscoverIn(query="student business", platforms=["youtube"])))
        self.assertEqual(str(x[0].source_urls[0]), "https://example.com/a")

    def test_rejects_login_instagram(self):
        with self.assertRaises(ValueError):
            asyncio.run(Service(generate=gen, collectors={}).discover(
                DiscoverIn(query="student business", platforms=["instagram_login"])))


if __name__ == "__main__":
    unittest.main()
