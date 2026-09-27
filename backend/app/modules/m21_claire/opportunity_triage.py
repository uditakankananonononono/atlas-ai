"""Read-only Claire triage over M01 public listings with explicit uncertainty.

Discovery records are untrusted external data; they cannot select tools, grant
permission, prove eligibility or authorize sending/applying. This layer only
builds source-linked review cards for a human.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from app.modules.m01_opportunity_discovery.student_intelligence import search_and_analyze


def triage(platform_ids: list[str], query: str, *, per_platform: int = 10) -> dict:
    if not query.strip() or len(query) > 200:
        raise ValueError("a nonempty, bounded query is required")
    result = search_and_analyze(platform_ids, query, per_platform=per_platform)
    cards = []
    for item in result["items"]:
        link = urlsplit(item["url"])
        if link.scheme != "https" or not link.hostname or link.username or link.password:
            continue
        cards.append({
            "id": item["id"], "title": item["title"], "url": item["url"],
            "platform": item["platform"], "source_url": item["source_url"],
            "deadline_mentioned": item["deadline"], "award_mentioned": item["award"],
            "student_level_mentioned": item["student_level"], "region_mentioned": item["region"],
            "status": "needs_official_rules_and_owner_eligibility_review",
            "next_step": "open_official_listing_and_verify_rules",
            "application_submitted": False, "outreach_sent": False,
        })
    return {"cards": cards, "failures": result["failures"], "launch_only": result["launch_only"],
            "scanned_at": result["scanned_at"], "external_effects": [],
            "limits": "Public listing text is not official application rules or proof of eligibility. No form submission or outreach."}
