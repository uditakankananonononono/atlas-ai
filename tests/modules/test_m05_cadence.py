from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m05_outreach_manager.campaigns import (
    CadenceBlockedError, CampaignService, InMemoryCampaignRepository,
)
from app.modules.m05_outreach_manager.schemas import ContactCreate
from app.modules.m05_outreach_manager.service import InMemoryContactRepository, Service


class Approvals:
    def __init__(self):
        self.items = []

    def put(self, item, *, user_id=None):
        self.items.append(item)
        return item


def setup(now, **meta):
    contacts, campaigns, approvals = InMemoryContactRepository(), InMemoryCampaignRepository(), Approvals()
    svc = CampaignService(campaigns, contacts, approvals, clock=lambda: now[0])
    people = Service(contacts, approvals, scholar=None)
    # two records for the same human in two projects
    a = people.create_contact(ContactCreate(project_id="labs", name="Dr. Rao", email="Rao@Example.edu", metadata=meta))
    b = people.create_contact(ContactCreate(project_id="grants", name="Dr. Rao", email="rao@example.edu", metadata=meta))
    c1 = svc.create_campaign(project_id="labs", name="Lab search", goal="Find a summer lab")
    c2 = svc.create_campaign(project_id="grants", name="Grant mentor", goal="Ask about a grant mentor")
    return svc, approvals, a, b, c1, c2


def send(svc, campaign, contact, **kw):
    m = svc.add_draft(campaign.id, contact.id, subject="Hi", body="Hello", **kw)
    svc.submit_for_approval(m.id)
    svc.record_decision(m.id, approved=True)
    return svc.mark_sent(m.id, thread_id=f"t-{m.id}")


def test_duplicate_across_campaigns_is_blocked_for_same_email():
    now = [datetime(2026, 9, 1, tzinfo=timezone.utc)]
    svc, _, a, b, c1, c2 = setup(now)
    first = svc.add_draft(c1.id, a.id, subject="Hi", body="Hello")
    svc.submit_for_approval(first.id)
    second = svc.add_draft(c2.id, b.id, subject="Hi again", body="Hello")
    with pytest.raises(CadenceBlockedError) as err:
        svc.submit_for_approval(second.id)
    codes = {r["code"] for r in err.value.decision["reasons"]}
    assert codes == {"duplicate"} and err.value.decision["person"] == "email:rao@example.edu"
    assert svc.get_message(second.id).status == "draft"


def test_cold_gap_then_allowed_and_decision_travels_with_approval():
    now = [datetime(2026, 9, 1, tzinfo=timezone.utc)]
    svc, approvals, a, b, c1, c2 = setup(now)
    send(svc, c1, a)
    now[0] += timedelta(days=2)
    m = svc.add_draft(c2.id, b.id, subject="Grant", body="Hello")
    decision = svc.cadence(m.id)
    assert not decision["allowed"] and decision["reasons"][0]["code"] == "too_soon"
    assert decision["next_allowed_at"] == datetime(2026, 9, 8, tzinfo=timezone.utc).isoformat()
    now[0] = datetime(2026, 9, 8, tzinfo=timezone.utc)
    svc.submit_for_approval(m.id)
    assert approvals.items[-1].payload["cadence"]["allowed"] is True


def test_warm_relationship_is_looser_and_cap_holds():
    now = [datetime(2026, 9, 1, tzinfo=timezone.utc)]
    svc, _, a, b, c1, c2 = setup(now, relationship="warm")
    send(svc, c1, a)
    now[0] += timedelta(days=3)
    send(svc, c2, b)  # 3-day gap is fine for warm
    c3 = svc.create_campaign(project_id="labs", name="Seminar", goal="Invite to seminar")
    c4 = svc.create_campaign(project_id="labs", name="Paper", goal="Share a paper")
    now[0] += timedelta(days=3)
    send(svc, c3, a)
    now[0] += timedelta(days=3)
    send(svc, c4, a)  # 4 in 30 days
    c5 = svc.create_campaign(project_id="labs", name="More", goal="One more ask")
    now[0] += timedelta(days=3)
    m = svc.add_draft(c5.id, a.id, subject="x", body="y")
    d = svc.cadence(m.id)
    assert [r["code"] for r in d["reasons"]] == ["over_cap"] and d["rule"]["max_per_30_days"] == 4
    assert d["next_allowed_at"] == datetime(2026, 10, 1, tzinfo=timezone.utc).isoformat()


def test_live_conversation_in_other_campaign_blocks_new_cold_message():
    now = [datetime(2026, 9, 1, tzinfo=timezone.utc)]
    svc, _, a, b, c1, c2 = setup(now)
    sent = send(svc, c1, a)
    svc.record_reply(sent.id, thread_id="t", snippet="Happy to talk")
    now[0] += timedelta(days=10)
    m = svc.add_draft(c2.id, b.id, subject="New ask", body="Hello")
    d = svc.cadence(m.id)
    assert {r["code"] for r in d["reasons"]} == {"live_conversation"} and d["next_allowed_at"] is None
    now[0] += timedelta(days=15)
    assert svc.cadence(m.id)["allowed"] is True


def test_opt_out_and_bounce_are_hard_stops():
    now = [datetime(2026, 9, 1, tzinfo=timezone.utc)]
    svc, _, a, b, c1, c2 = setup(now, opted_out=True)
    m = svc.add_draft(c1.id, a.id, subject="Hi", body="Hello")
    assert svc.cadence(m.id)["reasons"][0]["code"] == "opted_out"

    now2 = [datetime(2026, 9, 1, tzinfo=timezone.utc)]
    svc, _, a, b, c1, c2 = setup(now2)
    sent = send(svc, c1, a)
    svc.record_delivery_failure(sent.id, reason="550 no such user", bounced=True)
    now2[0] += timedelta(days=40)
    m = svc.add_draft(c2.id, b.id, subject="Hi", body="Hello")
    d = svc.cadence(m.id)
    assert {r["code"] for r in d["reasons"]} == {"bounced"} and d["next_allowed_at"] is None


def test_due_follow_ups_skip_people_contacted_elsewhere_recently():
    now = [datetime(2026, 9, 1, tzinfo=timezone.utc)]
    svc, _, a, b, c1, c2 = setup(now)
    first = send(svc, c1, a)
    now[0] += timedelta(days=8)
    send(svc, c2, b)  # other campaign, same person, gap respected
    now[0] += timedelta(days=1)  # c1's 5-day window long passed, but Rao heard from us yesterday
    assert svc.due_follow_ups() == []
    now[0] += timedelta(days=6)  # gap met, but cold cap is 2 per 30 days and both are used
    assert svc.due_follow_ups() == []
    now[0] = datetime(2026, 10, 2, tzinfo=timezone.utc)  # first send ages out of the window
    assert first.id in [m.id for m in svc.due_follow_ups()]  # submitting two at once is then caught as duplicate


def test_owner_policy_changes_rules_and_is_versioned(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.modules.m05_outreach_manager.cadence import CadencePolicyError, CadencePolicyStore

    e = create_engine(f"sqlite:///{tmp_path/'p.db'}"); Base.metadata.create_all(e)
    store = CadencePolicyStore("t1", session_factory=sessionmaker(bind=e))
    assert store.current()["version"] == 0 and store.current()["rules"]["cold"]["min_gap_days"] == 7
    with pytest.raises(CadencePolicyError):
        store.set(rules={"cold": {"min_gap_days": 3, "max_per_30_days": 2}}, live_thread_days=21, actor="u", reason="x")
    with pytest.raises(CadencePolicyError):
        store.set(rules={"cold": {"min_gap_days": 999, "max_per_30_days": 2}, "warm": {"min_gap_days": 3, "max_per_30_days": 4},
                         "close": {"min_gap_days": 1, "max_per_30_days": 8}}, live_thread_days=21, actor="u", reason="x")
    new = {"cold": {"min_gap_days": 2, "max_per_30_days": 3}, "warm": {"min_gap_days": 3, "max_per_30_days": 4},
           "close": {"min_gap_days": 1, "max_per_30_days": 8}}
    assert store.set(rules=new, live_thread_days=10, actor="udita", reason="academic outreach season")["version"] == 1
    assert CadencePolicyStore("t2", session_factory=sessionmaker(bind=e)).current()["version"] == 0

    now = [datetime(2026, 9, 1, tzinfo=timezone.utc)]
    contacts, campaigns, approvals = InMemoryContactRepository(), InMemoryCampaignRepository(), Approvals()
    svc = CampaignService(campaigns, contacts, approvals, clock=lambda: now[0], cadence_policy=store.current)
    people = Service(contacts, approvals, scholar=None)
    a = people.create_contact(ContactCreate(project_id="labs", name="Dr. Rao", email="rao@example.edu"))
    b = people.create_contact(ContactCreate(project_id="grants", name="Dr. Rao", email="rao@example.edu"))
    c1 = svc.create_campaign(project_id="labs", name="Lab search", goal="Find a summer lab")
    c2 = svc.create_campaign(project_id="grants", name="Grant mentor", goal="Ask about a mentor")
    send(svc, c1, a)
    now[0] += timedelta(days=2)
    m = svc.add_draft(c2.id, b.id, subject="Grant", body="Hello")
    d = svc.cadence(m.id)
    assert d["allowed"] is True and d["policy_version"] == 1 and d["rule"]["min_gap_days"] == 2
    t = svc.contact_timeline(b.id)
    assert t["person"] == "email:rao@example.edu" and t["policy_version"] == 1
    assert [r["campaign"] for r in t["messages"]] == ["Lab search", "Grant mentor"]
    assert t["contact_records"] == sorted([a.id, b.id])
