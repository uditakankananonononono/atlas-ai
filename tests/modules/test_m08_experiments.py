from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m08_startup_growth.experiments import ExperimentBoard, ExperimentNotFound, ExperimentRefused

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
FREE = [{"name": "Reddit r/SaaS post"}, {"name": "Tally form", "note": "free tier"}]


class Approvals:
    def __init__(self):
        self.items = []

    def put(self, item, *, user_id=None):
        self.items.append((item, user_id))
        return item


def board(tmp_path, tenant="t1"):
    e = create_engine(f"sqlite:///{tmp_path/'x.db'}"); Base.metadata.create_all(e)
    now, appr = [T0], Approvals()
    return ExperimentBoard(tenant, approvals=appr, session_factory=sessionmaker(bind=e), clock=lambda: now[0]), now, appr, e


def card(b, **kw):
    args = dict(title="Waitlist from Reddit", hypothesis="If we post the demo in r/SaaS, at least 5% of visitors join the waitlist.",
                metric="waitlist signups / visitors", success_rate=0.05, max_days=14, max_effort_hours=6, tools=FREE)
    args.update(kw)
    return b.create(**args)


def test_paid_tools_are_refused_on_the_card(tmp_path):
    b, *_ = board(tmp_path)
    for tools in ([{"name": "Instagram boosted post"}], [{"name": "Newsletter swap", "cost_minor": 2000}],
                  [{"name": "Google Ads"}], [{"name": "Creator shoutout", "note": "sponsored"}]):
        with pytest.raises(ExperimentRefused, match="free tools only"):
            card(b, tools=tools)
    assert b.board()["total"] == 0


def test_observations_drive_suggestion_and_decision_needs_reason(tmp_path):
    b, now, *_ = board(tmp_path)
    c = card(b)
    assert c["state"] == "running" and c["suggestion"] == "no_data"
    c = b.observe(c["id"], exposures=400, conversions=40, effort_hours=2, source="Plausible")
    assert c["result"]["rate"] == 0.1 and c["suggestion"] == "success" and c["state"] == "needs_decision"
    with pytest.raises(ExperimentRefused):
        b.decide(c["id"], decision="continue", reason="")
    c = b.decide(c["id"], decision="scale_free", reason="10% beats the 5% bar; try two more free subreddits")
    assert c["decisions"][-1]["suggested"] == "success"


def test_cap_blocks_continue_until_extended_with_reason(tmp_path):
    b, now, *_ = board(tmp_path)
    c = card(b)
    b.observe(c["id"], exposures=60, conversions=3, effort_hours=6.5)
    c = b.get(c["id"])
    assert c["cap"]["hit"] == ["effort"] and c["suggestion"] == "stop_inconclusive"
    with pytest.raises(ExperimentRefused, match="cap reached"):
        b.decide(c["id"], decision="continue", reason="want more data")
    with pytest.raises(ExperimentRefused):
        b.extend_cap(c["id"], add_effort_hours=3, reason="")
    b.extend_cap(c["id"], add_effort_hours=3, reason="one more weekend post is cheap")
    now[0] = T0 + timedelta(days=15)
    with pytest.raises(ExperimentRefused, match="time"):
        b.decide(c["id"], decision="continue", reason="still want more")
    c = b.decide(c["id"], decision="stop", reason="inconclusive at cap; not worth more time")
    assert c["state"] == "stopped" and b.board()["columns"]["stopped"][0]["id"] == c["id"]
    with pytest.raises(ExperimentRefused):
        b.observe(c["id"], exposures=1, conversions=0)


def test_paid_idea_is_only_a_proposal_and_nothing_spends(tmp_path):
    b, now, appr, _ = board(tmp_path)
    c = card(b)
    b.observe(c["id"], exposures=200, conversions=20)
    out = b.propose_paid(c["id"], description="$50 Reddit ads test", estimated_cost_minor=5000, currency="USD",
                         rationale="free post converted at 10%")
    item, user = appr.items[0]
    assert out["status"] == "pending_owner_decision" and user == "t1"
    assert item.action_type == "paid_experiment_proposal" and item.payload["execution"].startswith("none")
    assert item.payload["evidence"]["conversions"] == 20
    got = b.get(c["id"])
    assert got["paid_proposals"][0]["approval_id"] == out["approval_id"] and got["tools"] == [
        {"name": "Reddit r/SaaS post", "cost_minor": 0, "note": ""}, {"name": "Tally form", "cost_minor": 0, "note": "free tier"}]
    assert b.board()["spend_executed_minor"] == 0


def test_validation_and_tenant_isolation(tmp_path):
    b, _, appr, e = board(tmp_path)
    with pytest.raises(ExperimentRefused):
        card(b, success_rate=5)
    c = card(b)
    with pytest.raises(ExperimentRefused):
        b.observe(c["id"], exposures=3, conversions=4)
    other = ExperimentBoard("t2", approvals=appr, session_factory=sessionmaker(bind=e))
    with pytest.raises(ExperimentNotFound):
        other.get(c["id"])
    assert other.board()["total"] == 0


def test_http_routes(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m08_startup_growth import routes
    monkeypatch.setenv("ATLAS_ENV", "development")
    app = FastAPI(); app.include_router(routes.router)
    cl = TestClient(app)
    bad = cl.post("/startup-growth/experiments", json={"title": "x", "hypothesis": "Boosting will add signups fast.", "metric": "signups",
                                                        "success_rate": 0.1, "max_days": 7, "max_effort_hours": 2,
                                                        "tools": [{"name": "Facebook ads"}]})
    assert bad.status_code == 422 and "free tools only" in bad.text
    ok = cl.post("/startup-growth/experiments", json={"title": "x", "hypothesis": "A launch post brings 3% signups.", "metric": "signups",
                                                       "success_rate": 0.03, "max_days": 7, "max_effort_hours": 2,
                                                       "tools": [{"name": "Hacker News Show HN"}]})
    assert ok.status_code == 201, ok.text
    eid = ok.json()["id"]
    r = cl.post(f"/startup-growth/experiments/{eid}/observations", json={"exposures": 100, "conversions": 1})
    assert r.status_code == 200 and r.json()["result"]["conversions"] == 1
