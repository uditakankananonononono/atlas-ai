"""Approval-ID canonical-link pins (M7/M8/M11 repair).

Module 0's approval path assigns its OWN canonical id on submit and ignores the
provisional uuid4 the caller generated. Modules must retain and reference the
RETURNED id (the M10/M14/M15 pattern); storing/responding with the provisional
id mislinks every default approval reference. These pins use remapping stores
that mimic Module 0 (returned id != provisional id).
"""
from datetime import date, datetime, timedelta

import pytest

from app.core.models import ApprovalRequest
from app.modules.m07_brand_collaboration.schemas import BrandDiscoveryIn, MediaKitIn
from app.modules.m07_brand_collaboration.service import Service as BrandService
from app.modules.m08_startup_growth.schemas import LandingPageIn
from app.modules.m08_startup_growth.service import Service as GrowthService
from app.modules.m11_calendar_intelligence.schemas import (
    SchedulingPrefsSchema, SchedulingTaskCreate, WindowSchema)

from test_m11_calendar_intelligence import FakeApprovalGate, make_service, dt, MONDAY, UTC


def _remap(item: ApprovalRequest, tag: str) -> ApprovalRequest:
    return ApprovalRequest(id=f"canonical-{tag}-{item.id[:8]}", module_id=item.module_id,
                           action_type=item.action_type, payload=item.payload,
                           status=item.status)


class RemappingApprovals:
    """Module-0-style sink: issues its own id, keeps the item under that id."""

    def __init__(self, tag):
        self.tag = tag
        self.items = {}

    def put(self, item, *, user_id=None):
        stored = _remap(item, self.tag)
        self.items[stored.id] = (stored, user_id)
        return stored


class RemappingGate(FakeApprovalGate):
    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        stored = _remap(item, "m11")
        self.items[stored.id] = stored
        return stored


class _BrandRepo:
    def __init__(s): s.tenant_id = "tenant-test"; s.b = {}; s.a = {}; s.e = []
    def add_brand(s, **d): s.b[d['id']] = type('R', (), d)
    def brand(s, i): return s.b.get(i)
    def add_artifact(s, **d): s.a[d['id']] = type('R', (), d)
    def artifact(s, i): return s.a.get(i)
    def add_event(s, **d): s.e.append(type('R', (), d))
    def events(s, i): return [x for x in s.e if x.brand_id == i]


class _GrowthRepo:
    def __init__(s): s.tenant_id = "tenant-test"; s.x = {}
    def save(s, **d): s.x[d['id']] = type('R', (), d)
    def get(s, i): return s.x.get(i)


def test_m07_propose_send_references_canonical_id():
    approvals = RemappingApprovals("m07")
    svc = BrandService(_BrandRepo(), approvals)
    brand = svc.discover(BrandDiscoveryIn(name='Acme', mission='science',
                                          public_url='https://acme.test'), 'science')
    kit = svc.media_kit(MediaKitIn(brand_id=brand.id, creator_name='Ada',
                                   creator_mission='science', metrics={'reach': 100}))
    proposal = svc.propose_send(kit.id, 'brand@example.test')
    # the proposal must reference the store-issued id, not the provisional one
    assert proposal.approval_id.startswith("canonical-m07-")
    stored, user_id = approvals.items[proposal.approval_id]
    assert stored.action_type == proposal.action_type and user_id == "tenant-test"


def test_m08_propose_references_canonical_id():
    approvals = RemappingApprovals("m08")
    svc = GrowthService(_GrowthRepo(), approvals)
    site = svc.landing_page(LandingPageIn(project_id='p', product_name='Atlas',
                                          hero='Ship safely', features=['Approvals']))
    proposal = svc.propose(site.id, 'deploy_startup_site')
    assert proposal.approval_id.startswith("canonical-m08-")
    stored, user_id = approvals.items[proposal.approval_id]
    assert stored.action_type == 'deploy_startup_site' and user_id == "tenant-test"


def test_m11_propose_plan_references_canonical_id(tmp_path, monkeypatch):
    service, repo, _ = make_service(tmp_path)
    gate = RemappingGate()
    service.approval_gate = gate
    task = service.create_task(SchedulingTaskCreate(
        title="Write essay", duration_minutes=60, deadline=dt(MONDAY + timedelta(days=2), 17)))
    plan = service.plan_week(MONDAY)
    proposal = service.propose_plan(plan.id)
    assert proposal.approval_id.startswith("canonical-m11-")
    # the store holds it under the canonical id and the plan row links that same id
    assert gate.items[proposal.approval_id].payload["plan_id"] == plan.id
    assert repo.get_plan(plan.id).approval_id == proposal.approval_id
    # full round trip: approve under the canonical id, apply succeeds
    with pytest.raises(Exception):
        service.apply_plan(proposal.approval_id)
    gate.approve(proposal.approval_id)
    applied = service.apply_plan(proposal.approval_id)
    assert applied.status == "applied"
    assert repo.get_task(task.id).status == "scheduled"


def test_m11_request_reschedule_references_canonical_id(tmp_path):
    service, repo, _ = make_service(tmp_path)
    gate = RemappingGate()
    service.approval_gate = gate
    service.save_prefs(SchedulingPrefsSchema(
        working_hours={0: [WindowSchema(start="09:00", end="10:00")]},  # Monday only, 1h
        energy_curve={h: 3 for h in range(24)}))
    today = datetime.now(UTC).date()
    days_ahead = (0 - today.weekday()) % 7 or 7
    monday = today + timedelta(days=days_ahead)
    service.create_task(SchedulingTaskCreate(
        title="Existing high priority", duration_minutes=60,
        deadline=dt(monday, 17), priority=5))
    conflict_task = SchedulingTaskCreate(
        title="New deadline", duration_minutes=60, deadline=dt(monday, 12), priority=3)
    report, proposal = service.request_reschedule(conflict_task)
    assert report is not None and proposal is not None
    assert proposal.approval_id.startswith("canonical-m11-")
    assert gate.items[proposal.approval_id].action_type == "apply_reschedule"
    gate.approve(proposal.approval_id)
    applied = service.apply_reschedule(proposal.approval_id)
    assert applied.title == "New deadline" and applied.status == "scheduled"


# -- None-returning store fallback pins (auditor-4 survivors) -------------------
# Module 0's canonical path never returns None, but the M10-style
# `put(...) or provisional` compatibility guard must hold at every site for
# stores that return None: the module falls back to the provisional request
# and stays internally consistent instead of crashing on None.id.


class NoneReturningApprovals:
    def __init__(self):
        self.items = {}

    def put(self, item, *, user_id=None):
        self.items[item.id] = (item, user_id)
        return None


class NoneReturningGate(FakeApprovalGate):
    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        self.items[item.id] = item
        return None


def test_m07_propose_send_none_returning_store_falls_back():
    approvals = NoneReturningApprovals()
    svc = BrandService(_BrandRepo(), approvals)
    brand = svc.discover(BrandDiscoveryIn(name='Acme', mission='science',
                                          public_url='https://acme.test'), 'science')
    kit = svc.media_kit(MediaKitIn(brand_id=brand.id, creator_name='Ada',
                                   creator_mission='science', metrics={'reach': 100}))
    proposal = svc.propose_send(kit.id, 'brand@example.test')
    stored, user_id = approvals.items[proposal.approval_id]
    assert stored.id == proposal.approval_id and user_id == "tenant-test"


def test_m08_propose_none_returning_store_falls_back():
    approvals = NoneReturningApprovals()
    svc = GrowthService(_GrowthRepo(), approvals)
    site = svc.landing_page(LandingPageIn(project_id='p', product_name='Atlas',
                                          hero='Ship safely', features=['Approvals']))
    proposal = svc.propose(site.id, 'deploy_startup_site')
    stored, user_id = approvals.items[proposal.approval_id]
    assert stored.id == proposal.approval_id and user_id == "tenant-test"


def test_m11_propose_plan_none_returning_gate_falls_back(tmp_path):
    service, repo, _ = make_service(tmp_path)
    gate = NoneReturningGate()
    service.approval_gate = gate
    task = service.create_task(SchedulingTaskCreate(
        title="Write essay", duration_minutes=60, deadline=dt(MONDAY + timedelta(days=2), 17)))
    plan = service.plan_week(MONDAY)
    proposal = service.propose_plan(plan.id)
    assert gate.items[proposal.approval_id].payload["plan_id"] == plan.id
    assert repo.get_plan(plan.id).approval_id == proposal.approval_id
    gate.approve(proposal.approval_id)
    assert service.apply_plan(proposal.approval_id).status == "applied"
    assert repo.get_task(task.id).status == "scheduled"


def test_m11_request_reschedule_none_returning_gate_falls_back(tmp_path):
    service, repo, _ = make_service(tmp_path)
    gate = NoneReturningGate()
    service.approval_gate = gate
    service.save_prefs(SchedulingPrefsSchema(
        working_hours={0: [WindowSchema(start="09:00", end="10:00")]},
        energy_curve={h: 3 for h in range(24)}))
    today = datetime.now(UTC).date()
    days_ahead = (0 - today.weekday()) % 7 or 7
    monday = today + timedelta(days=days_ahead)
    service.create_task(SchedulingTaskCreate(
        title="Existing high priority", duration_minutes=60,
        deadline=dt(monday, 17), priority=5))
    report, proposal = service.request_reschedule(SchedulingTaskCreate(
        title="New deadline", duration_minutes=60, deadline=dt(monday, 12), priority=3))
    assert report is not None and proposal is not None
    assert gate.items[proposal.approval_id].action_type == "apply_reschedule"
    gate.approve(proposal.approval_id)
    assert service.apply_reschedule(proposal.approval_id).status == "scheduled"
