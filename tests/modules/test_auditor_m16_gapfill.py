"""Auditor gap-fill for the M16 delta: pins the three behaviors the supplied six leave unpinned."""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch
import os
from app.modules.m16_executive_dashboard import routes
from app.modules.m16_executive_dashboard.schemas import AgentState, AgentStatus
from app.modules.m16_executive_dashboard.status import ModuleInfo, module_statuses


def test_events_default_cursor_is_zero():
    seen = []
    class Svc:
        def events_after(self, cursor, limit=500): seen.append(cursor); return []
    routes.events(service=Svc())  # no cursor argument: must default to 0, replaying from the start
    assert seen == [0]


def test_422_detail_text():
    with pytest.raises(HTTPException) as ei:
        routes.events(2**63, object())
    assert ei.value.status_code == 422
    assert ei.value.detail == "cursor out of range"


NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)

class Cat:
    def list_modules(self): return [ModuleInfo(1, 'm', 'M', True)]


def test_duplicate_agent_key_keeps_first_occurrence():
    # same module, same agent_id, same heartbeat, different state: shipped behavior
    # keeps the FIRST list entry (strict > never replaces on an exact key tie)
    a = AgentStatus(module_id=1, agent_id='dup', state=AgentState.RUNNING, last_heartbeat=NOW)
    b = AgentStatus(module_id=1, agent_id='dup', state=AgentState.IDLE, last_heartbeat=NOW)
    for order in ([a, b], [b, a]):
        agent = next(s for s in module_statuses(Cat(), order, [], [], NOW) if s.module_id == 1).agent
        assert agent.state is order[0].state
