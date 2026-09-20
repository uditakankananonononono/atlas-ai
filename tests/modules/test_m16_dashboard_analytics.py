from datetime import datetime,timedelta,timezone
import pytest
from app.modules.m16_executive_dashboard.kpis import EVIDENCE_SAMPLE_LIMIT
from app.modules.m16_executive_dashboard.schemas import *
from app.modules.m16_executive_dashboard.service import Service
from app.modules.m16_executive_dashboard.status import ModuleInfo,event_module_id
NOW=datetime(2026,9,20,12,0,tzinfo=timezone.utc)
def event(i,topic,when,payload=None,agg_type="task",agg_id=None):
    return Event(id=f"e{i}",sequence=i,topic=topic,aggregate_type=agg_type,aggregate_id=agg_id or f"a{i}",payload=payload or {},occurred_at=when)
def approval(i,module_id=3,state=ApprovalState.PENDING,created=None,expires=None,reviewed=None):
    return Approval(id=f"ap{i}",module_id=module_id,action_type="send",title=f"Approval {i}",summary="s",state=state,created_at=created or NOW-timedelta(hours=2),expires_at=expires,reviewed_at=reviewed)
class FakeRepo:
    def __init__(self,events=(),approvals=(),agents=(),timeline=()):
        self._events=list(events);self._approvals=list(approvals);self._agents=list(agents);self.commands={};self.timeline=list(timeline)
    def snapshot(self):return Snapshot(version=1,last_sequence=len(self._events),generated_at=NOW,data={"timeline":[i.model_dump(mode="json") for i in self.timeline]})
    def events_after(self,cursor):return [e for e in self._events if e.sequence>cursor]
    def events_between(self,start,end):return [e for e in self._events if start<=e.occurred_at<=end]
    def pending_approvals(self):return [a for a in self._approvals if a.state==ApprovalState.PENDING]
    def approvals_reviewed_since(self,since):return [a for a in self._approvals if a.reviewed_at and a.reviewed_at>=since]
    def approval_by_id(self,i):return next((a for a in self._approvals if a.id==i),None)
    def event_by_id(self,i):return next((e for e in self._events if e.id==i),None)
    def list_agents(self):return list(self._agents)
    def heartbeat(self,data,at):
        a=AgentStatus(**data.model_dump(),last_heartbeat=at);self._agents=[x for x in self._agents if x.agent_id!=a.agent_id]+[a];return a
    def save_approval(self,a):self._approvals.append(a);return a
    def decide(self,*a):return None
    def save_command(self,c):self.commands[c.id]=[None,c];return c
    def get_command(self,i):
        row=type("Row",(),{"executed_at":None})();return row,self.commands[i][1]
    def mark_command(self,i,at):pass
class FakeCatalog:
    def __init__(self,mods):self.mods=mods
    def list_modules(self):return self.mods
CAT=FakeCatalog([ModuleInfo(1,"opportunity-discovery","Opportunity Discovery",True),ModuleInfo(3,"grant-writer","Grant Writer",True),ModuleInfo(18,"side-hustle","Side Hustle",False)])
def svc(**kw):return Service(FakeRepo(**kw),catalog=CAT)
def test_event_kpis_count_with_evidence():
    events=[event(i,"application.submitted",NOW-timedelta(hours=i)) for i in range(1,4)]+[event(9,"grant.won",NOW-timedelta(hours=1))]
    kpis={k.id:k for k in svc(events=events).kpis(NOW)}
    assert kpis["applications_submitted"].value==3 and kpis["grants_won"].value==1 and kpis["events_total"].value==4
    assert {r.id for r in kpis["applications_submitted"].evidence}=={"e1","e2","e3"}
    assert kpis["applications_submitted"].evidence_total==3
def test_kpi_honest_zero_and_evidence_cap():
    events=[event(i,"task.completed",NOW-timedelta(minutes=i)) for i in range(1,EVIDENCE_SAMPLE_LIMIT+6)]
    kpis={k.id:k for k in svc(events=events).kpis(NOW)}
    assert kpis["opportunities_discovered"].value==0 and kpis["opportunities_discovered"].evidence==[]
    assert kpis["tasks_completed"].value==EVIDENCE_SAMPLE_LIMIT+5
    assert len(kpis["tasks_completed"].evidence)==EVIDENCE_SAMPLE_LIMIT and kpis["tasks_completed"].evidence_total==EVIDENCE_SAMPLE_LIMIT+5
def test_kpi_previous_window_trend():
    events=[event(1,"application.submitted",NOW-timedelta(hours=2)),event(2,"application.submitted",NOW-timedelta(hours=30)),event(3,"application.submitted",NOW-timedelta(hours=40))]
    k={x.id:x for x in svc(events=events).kpis(NOW)}["applications_submitted"]
    assert k.value==1 and k.previous_value==2
def test_approval_gauges_and_turnaround():
    approvals=[approval(1),approval(2),approval(3,state=ApprovalState.APPROVED,reviewed=NOW-timedelta(hours=1)),approval(4,state=ApprovalState.REJECTED,created=NOW-timedelta(hours=10),reviewed=NOW-timedelta(hours=6))]
    kpis={k.id:k for k in svc(approvals=approvals).kpis(NOW)}
    assert kpis["approvals_pending"].value==2 and kpis["approval_decisions"].value==2
    assert kpis["avg_approval_turnaround_hours"].value==2.5
    assert {r.id for r in kpis["approval_decisions"].evidence}=={"ap3","ap4"}
def test_agent_states_and_stalled_kpi():
    agents=[AgentStatus(module_id=1,agent_id="w1",state=AgentState.RUNNING,last_heartbeat=NOW-timedelta(minutes=2)),AgentStatus(module_id=3,agent_id="w2",state=AgentState.RUNNING,last_heartbeat=NOW-timedelta(minutes=30)),AgentStatus(module_id=18,agent_id="w3",state=AgentState.RUNNING,last_heartbeat=NOW-timedelta(hours=3))]
    s=svc(agents=agents)
    statuses={m.module_id:m for m in s.module_statuses(NOW)}
    assert statuses[1].agent.state==AgentState.RUNNING and statuses[3].agent.state==AgentState.STALLED and statuses[18].agent.state==AgentState.OFFLINE
    k={x.id:x for x in s.kpis(NOW)}["agents_stalled"]
    assert k.value==2 and {r.id for r in k.evidence}=={"w2","w3"}
def test_module_statuses_aggregate_approvals_and_events():
    events=[event(1,"application.submitted",NOW,payload={"module_id":3}),event(2,"task.completed",NOW,agg_type="module:1"),event(3,"task.completed",NOW)]
    approvals=[approval(1,module_id=3),approval(2,module_id=3),approval(3,module_id=1)]
    statuses={m.module_id:m for m in svc(events=events,approvals=approvals).module_statuses(NOW)}
    assert statuses[3].pending_approvals==2 and statuses[3].events_24h==1
    assert statuses[1].pending_approvals==1 and statuses[1].events_24h==1
    assert statuses[18].implemented is False and statuses[3].implemented is True
def test_event_module_attribution():
    assert event_module_id(event(1,"t",NOW,payload={"module_id":7}))==7
    assert event_module_id(event(2,"t",NOW,agg_type="module:9"))==9
    assert event_module_id(event(3,"t",NOW,payload={"module_id":True})) is None
    assert event_module_id(event(4,"t",NOW)) is None
def test_blockers_expired_expiring_and_not_implemented():
    approvals=[approval(1,expires=NOW-timedelta(minutes=5)),approval(2,expires=NOW+timedelta(minutes=30)),approval(3,expires=NOW+timedelta(hours=5))]
    blocks={b.kind:b for b in svc(approvals=approvals).blockers(NOW)}
    assert blocks["approval_expired_pending"].severity==BlockerSeverity.CRITICAL and blocks["approval_expired_pending"].module_id==3
    assert blocks["approval_expiring_soon"].severity==BlockerSeverity.WARNING
    assert blocks["module_not_implemented"].module_id==18 and blocks["module_not_implemented"].severity==BlockerSeverity.INFO
    assert blocks["approval_expired_pending"].evidence[0].id=="ap1"
def test_blockers_timeline_cycle_and_overdue_critical():
    t=[TimelineItem(id="a",title="A",start=NOW-timedelta(hours=5),end=NOW+timedelta(hours=1),dependencies=["b"]),TimelineItem(id="b",title="B",start=NOW-timedelta(hours=4),end=NOW+timedelta(hours=2),dependencies=["a"])]
    assert any(b.kind=="timeline_dependency_cycle" for b in svc(timeline=t).blockers(NOW))
    ok=[TimelineItem(id="a",title="A",start=NOW-timedelta(hours=5),end=NOW-timedelta(hours=1),progress=.4),TimelineItem(id="b",title="B",start=NOW-timedelta(hours=1),end=NOW+timedelta(hours=3),dependencies=["a"])]
    kinds={b.kind for b in svc(timeline=ok).blockers(NOW)}
    assert "critical_path_item_overdue" in kinds and "timeline_dependency_cycle" not in kinds
def test_overview_counts_blockers_per_module():
    approvals=[approval(1,module_id=3,expires=NOW-timedelta(minutes=5))]
    overview=svc(approvals=approvals).overview(NOW)
    m3=next(m for m in overview.modules if m.module_id==3)
    assert m3.open_blockers==1 and overview.pending_approvals==0
    assert overview.kpis and overview.generated_at==NOW
def test_kpi_evidence_drilldown():
    events=[event(1,"grant.won",NOW-timedelta(hours=1)),event(2,"task.completed",NOW-timedelta(hours=1))]
    s=svc(events=events,approvals=[approval(1)])
    result=s.kpi_evidence("grants_won",NOW)
    assert [e.id for e in result.events]==["e1"] and result.detail["count"]==1
    pending=s.kpi_evidence("approvals_pending",NOW)
    assert [a.id for a in pending.approvals]==["ap1"]
    with pytest.raises(LookupError):s.kpi_evidence("not_a_kpi",NOW)
def test_drilldown_event_approval_module_timeline():
    events=[event(1,"grant.won",NOW-timedelta(hours=1),agg_id="ap1"),event(2,"task.completed",NOW-timedelta(hours=1),agg_id="x")]
    approvals=[approval(1)]
    timeline=[TimelineItem(id="a",title="A",start=NOW,end=NOW+timedelta(hours=2)),TimelineItem(id="b",title="B",start=NOW,end=NOW+timedelta(hours=3),dependencies=["a"])]
    s=svc(events=events,approvals=approvals,timeline=timeline)
    assert s.drilldown("event","e1",NOW).subject.kind=="event"
    detail=s.drilldown("approval","ap1",NOW)
    assert detail.subject.id=="ap1" and [e.id for e in detail.events]==["e1"]
    module=s.drilldown("module","3",NOW)
    assert module.detail["module_id"]==3 and [a.id for a in module.approvals]==["ap1"]
    item=s.drilldown("timeline_item","a",NOW)
    assert item.detail["dependents"]==["b"] and item.detail["on_critical_path"] is True
    with pytest.raises(LookupError):s.drilldown("event","missing",NOW)
    with pytest.raises(LookupError):s.drilldown("module","99",NOW)
def test_heartbeat_roundtrip():
    s=svc()
    status=s.heartbeat(AgentHeartbeat(module_id=1,agent_id="w1",state=AgentState.RUNNING,current_task="scan"))
    assert status.last_heartbeat is not None
    s.heartbeat(AgentHeartbeat(module_id=1,agent_id="w1",state=AgentState.IDLE))
    agents=s._agents();assert len(agents)==1 and agents[0].state==AgentState.IDLE
def test_command_intents_execute_read_only():
    s=svc(approvals=[approval(1,expires=NOW-timedelta(minutes=5))])
    preview=s.preview("show blockers")
    assert preview.intent=="show_blockers" and preview.read_only and preview.confidence>.55
    result=s.execute(preview.id)
    assert result["status"]=="completed" and result["result"]["blockers"][0]["kind"]=="approval_expired_pending"
    kpis=s.execute(s.preview("what are the kpis").id)
    assert kpis["status"]=="completed" and any(k["id"]=="approvals_pending" for k in kpis["result"]["kpis"])
    write=s.execute(s.preview("email this to the professor").id)
    assert write["status"]=="approval_required"
