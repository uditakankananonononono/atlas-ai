"""M16 module status freshness: multi-agent selection and future-dated heartbeats (authored, not run: pydantic absent in author env)."""
from datetime import datetime,timedelta,timezone
from app.modules.m16_executive_dashboard.schemas import AgentState,AgentStatus
from app.modules.m16_executive_dashboard.status import (STALE_AFTER,OFFLINE_AFTER,ModuleInfo,effective_state,module_statuses)

NOW=datetime(2026,10,15,12,0,tzinfo=timezone.utc)

def ag(agent_id,age,state=AgentState.RUNNING,module_id=1):
    return AgentStatus(module_id=module_id,agent_id=agent_id,state=state,last_heartbeat=NOW-age)

class Cat:
    def list_modules(self):return [ModuleInfo(1,"m","M",True),ModuleInfo(2,"n","N",True)]

def test_existing_thresholds_unchanged():
    assert effective_state(ag("a",timedelta(0)),NOW)==AgentState.RUNNING
    assert effective_state(ag("a",STALE_AFTER),NOW)==AgentState.STALLED
    assert effective_state(ag("a",OFFLINE_AFTER),NOW)==AgentState.OFFLINE
    assert effective_state(ag("a",STALE_AFTER,AgentState.IDLE),NOW)==AgentState.IDLE

def _agent_of(statuses,mid):return next(s for s in statuses if s.module_id==mid).agent

def test_live_agent_not_masked_by_dead_one_in_either_order():
    live=ag("live",timedelta(minutes=1));dead=ag("dead",timedelta(hours=5))
    for order in ([live,dead],[dead,live]):
        a=_agent_of(module_statuses(Cat(),order,[],[],NOW),1)
        assert (a.agent_id,a.state)==("live",AgentState.RUNNING)

def test_tie_on_heartbeat_is_deterministic():
    x=ag("a",timedelta(minutes=1));y=ag("b",timedelta(minutes=1))
    for order in ([x,y],[y,x]):
        assert _agent_of(module_statuses(Cat(),order,[],[],NOW),1).agent_id=="b"

def test_module_without_agent_and_other_module_unaffected():
    st=module_statuses(Cat(),[ag("a",timedelta(minutes=1),module_id=2)],[],[],NOW)
    assert _agent_of(st,1) is None and _agent_of(st,2).agent_id=="a"
