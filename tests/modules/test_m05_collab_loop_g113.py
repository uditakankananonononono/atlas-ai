"""G113: collab_loop - full contact-to-collaboration runtime, approval gate."""
from __future__ import annotations

import pytest

from app.modules.m05_outreach_manager import collab_loop as cl


def _pipeline():
    p = cl.create_pipeline()
    cl.add_contact(p, "c1", "Asha Rao", "email", "DesignLab", "2026-10-01")
    return p


def _researched():
    p = _pipeline()
    cl.research(p, "c1", {"role": "industrial designer", "recent_work": "the Fold lamp launch",
                          "interest": "sustainable materials"}, "2026-10-02")
    return p


def test_full_loop_to_collaboration():
    p = _researched()
    cl.draft(p, "c1", "design", "a modular desk organizer", "2026-10-03")
    cl.submit_for_approval(p, "c1", "2026-10-03")
    cl.approve(p, "c1", "tok", "2026-10-04")
    cl.mark_sent(p, "c1", "msg-1", "2026-10-04")
    cl.record_reply(p, "c1", "Love this, let's talk", "2026-10-05")
    cl.negotiate(p, "c1", "2026-10-06", "scope")
    brief = cl.start_collaboration(p, "c1", {"project": "Eco-desk",
                                             "roles": {"owner": "build", "asha": "design"},
                                             "next_steps": ["sketches"]}, "2026-10-07")
    assert brief["project"] == "Eco-desk"
    r = cl.report(p, "2026-10-12")
    assert r["counts"]["collaborating"] == 1
    assert r["funnel"] == {"sent": 1, "replied": 1, "collaborating": 1,
                           "reply_rate": 1.0, "collab_rate": 1.0}


def test_draft_uses_only_supplied_evidence():
    p = _researched()
    d = cl.draft(p, "c1", "design", "a modular desk organizer", "2026-10-03")
    assert "Fold lamp launch" in d["body"] and "sustainable materials" in d["body"]
    assert "industrial designer" in d["body"]
    assert d["personalization_sources"]


def test_draft_refuses_without_evidence():
    p = _pipeline()
    with pytest.raises(ValueError, match="REACH_REFUSED_NO_EVIDENCE"):
        cl.draft(p, "c1", "help", "anything", "2026-10-02")


def test_send_requires_owner_approval():
    p = _researched()
    cl.draft(p, "c1", "help", "a hard bug", "2026-10-03")
    cl.submit_for_approval(p, "c1", "2026-10-03")
    with pytest.raises(ValueError, match="REACH_REFUSED_NOT_APPROVED"):
        cl.mark_sent(p, "c1", "msg-1", "2026-10-04")
    p2 = _researched()
    cl.draft(p2, "c1", "help", "a hard bug", "2026-10-03")
    with pytest.raises(ValueError, match="REACH_REFUSED_BAD_TRANSITION"):
        cl.approve(p2, "c1", "tok", "2026-10-03")  # drafted, never submitted


def test_invalid_transitions_refuse():
    p = _pipeline()
    with pytest.raises(ValueError, match="REACH_REFUSED_BAD_TRANSITION"):
        cl.negotiate(p, "c1", "2026-10-02", "too early")
    with pytest.raises(ValueError, match="REACH_REFUSED_NOT_FOUND"):
        cl.research(p, "ghost", {"role": "x", "recent_work": "y", "interest": "z"}, "2026-10-02")


def test_reply_classification_real():
    assert cl.classify_reply("This sounds great, count me in!") == "positive"
    assert cl.classify_reply("Not interested, please stop") == "negative"
    assert cl.classify_reply("Interesting - how much would it cost?") == "question"
    assert cl.classify_reply("ok noted") == "neutral"


def test_negative_reply_closes_to_lost():
    p = _researched()
    cl.draft(p, "c1", "help", "x", "2026-10-03")
    cl.submit_for_approval(p, "c1", "2026-10-03")
    cl.approve(p, "c1", "tok", "2026-10-04")
    cl.mark_sent(p, "c1", "m", "2026-10-04")
    out = cl.record_reply(p, "c1", "No thanks, remove me", "2026-10-05")
    assert out["suggested_next"] == "stop"
    assert p["contacts"]["c1"]["state"] == "lost"


def test_follow_ups_due_after_cadence():
    p = _researched()
    cl.draft(p, "c1", "help", "x", "2026-10-01")
    cl.submit_for_approval(p, "c1", "2026-10-01")
    cl.approve(p, "c1", "tok", "2026-10-01")
    cl.mark_sent(p, "c1", "m", "2026-10-01")
    assert cl.follow_ups_due(p, "2026-10-03") == []
    due = cl.follow_ups_due(p, "2026-10-07")
    assert due == [{"contact_id": "c1", "state": "sent", "days_since_touch": 6,
                    "action": "send_followup"}]
