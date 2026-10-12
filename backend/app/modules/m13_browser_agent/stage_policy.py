"""Global stage refusals that every ApplicationFlow caller (M01 wrapper, M02 direct path) inherits.

Discovery-only scope: student-platform sources registered as RSS feeds (editorial/announcement
feeds) have no application form workflow, so no session opened for them may stage values.
The set is derived from the M01 registry at call time (lazy import: M01 imports M13, not the reverse
at module load), so a newly registered rss source is covered without touching this file.
"""
from __future__ import annotations


def stage_refusal(opportunity_kind: str, opportunity_id: str) -> str | None:
    if opportunity_kind != "student_platform" or not opportunity_id:
        return None
    from app.modules.m01_opportunity_discovery.student_platforms import BY_ID
    source = BY_ID.get(opportunity_id)
    if source is not None and source.mode == "rss":
        return "editorial discovery sources have no application form workflow; staging refused"
    return None
