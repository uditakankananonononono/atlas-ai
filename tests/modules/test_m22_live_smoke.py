"""Opt-in live smoke for every M22 public source. Skipped unless ATLAS_M22_LIVE=1.

Spends one request per source (Software Heritage allows few anonymous calls).
Writes the per-source report to $ATLAS_M22_LIVE_REPORT (default /tmp/m22_live_report.json).
Asserts only the two delta sources must return results; every other source is
recorded, because third-party uptime must not turn this test flaky.
"""
import asyncio
import json
import os

import pytest

from test_m22_sources_extra import health  # same loader, no web stack needed

pytestmark = pytest.mark.skipif(os.environ.get("ATLAS_M22_LIVE") != "1", reason="set ATLAS_M22_LIVE=1 to hit live endpoints")


def test_live_report_all_sources():
    query = os.environ.get("ATLAS_M22_LIVE_QUERY", "python")
    report = asyncio.run(health.health_report(health.all_collectors(), query, timeout=25.0))
    path = os.environ.get("ATLAS_M22_LIVE_REPORT", "/tmp/m22_live_report.json")
    with open(path, "w") as fh:
        json.dump(report, fh, indent=2)
    by = {row["source"]: row for row in report["sources"]}
    for name in ("fyyd", "softwareheritage"):
        assert by[name]["status"] == "ok" and by[name]["count"] > 0, by[name]
    assert report["summary"]["ok"] >= 2
