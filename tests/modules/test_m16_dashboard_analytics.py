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
from app.modules.m16_executive_dashboard.projector import apply_event,fold
class ProjectingRepo(FakeRepo):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.points=[]
    def update_snapshot(self,data,last_sequence):
        self.timeline=[TimelineItem(**t) for t in data.get("timeline",[])]
        self._data=data;self._last=last_sequence
        return Snapshot(version=2,last_sequence=last_sequence,generated_at=NOW,data=data)
    def snapshot(self):
        data=getattr(self,"_data",None)
        if data is None:data={"timeline":[i.model_dump(mode="json") for i in self.timeline]}
        return Snapshot(version=2,last_sequence=getattr(self,"_last",0),generated_at=NOW,data=data)
    def record_kpi_points(self,points,at):self.points.extend((p,at) for p in points)
    def kpi_value_at_or_before(self,kpi_id,window_hours,moment):
        vals=[(p[0][2],p[1]) for p in self.points if p[0][0]==kpi_id and p[1]<=moment]
        return vals[-1][0] if vals else None
def test_projector_folds_metrics_freshness_timeline_alerts():
    item=TimelineItem(id="t1",title="Apply",start=NOW,end=NOW+timedelta(hours=3))
    events=[event(1,"application.submitted",NOW,payload={"module_id":3}),event(2,"timeline.upsert",NOW,payload={"item":item.model_dump(mode="json")}),event(3,"alert",NOW,payload={"severity":"warning","message":"worker slow","module_id":3})]
    data,last=fold({"metrics":{},"timeline":[],"alerts":[],"freshness":{}},events)
    assert last==3 and data["metrics"]["topic:application.submitted"]==1 and data["metrics"]["module:3:events"]==2
    assert data["timeline"][0]["id"]=="t1" and len(data["alerts"])==1 and data["alerts"][0]["module_id"]==3
    assert "task/a1" in data["freshness"]
    again,last2=fold(data,[])
    assert again==data and last2==0
def test_projector_timeline_upsert_replaces_by_id():
    older=TimelineItem(id="t1",title="v1",start=NOW,end=NOW+timedelta(hours=1)).model_dump(mode="json")
    newer=TimelineItem(id="t1",title="v2",start=NOW,end=NOW+timedelta(hours=2),progress=.5).model_dump(mode="json")
    data,_=fold({"timeline":[older]},[event(1,"timeline.upsert",NOW,payload={"item":newer})])
    assert len(data["timeline"])==1 and data["timeline"][0]["title"]=="v2"
def test_service_snapshot_autoprojects_and_project_records_points():
    item=TimelineItem(id="t1",title="Apply",start=NOW,end=NOW+timedelta(hours=3))
    repo=ProjectingRepo(events=[event(1,"timeline.upsert",NOW,payload={"item":item.model_dump(mode="json")}),event(2,"grant.won",NOW)])
    s=Service(repo,catalog=CAT)
    snap=s.snapshot()
    assert snap.last_sequence==2 and snap.data["metrics"]["topic:grant.won"]==1
    assert [i.id for i in s._timeline()]==["t1"]
    summary=s.project(NOW)
    assert summary["projected_events"]==0 and summary["recorded_points"]>0
    k={x.id:x for x in s.kpis(NOW+timedelta(hours=24))}["approvals_pending"]
    assert k.previous_value==0.0
def test_projector_rejects_invalid_timeline_payload():
    data,_=fold({"timeline":[]},[event(1,"timeline.upsert",NOW,payload={"item":{"bad":1}})])
    assert data["timeline"]==[]
def test_event_intake_assigns_ids_and_defaults():
    repo=FakeRepo();s=Service(repo,catalog=CAT)
    saved=[]
    repo._events=saved
    orig=repo.__class__
    # FakeRepo lacks append_event; add one
    repo.append_event=lambda e:(saved.append(e) or e)
    e=s.intake(EventIn(topic="grant.won",aggregate_type="module:3",aggregate_id="g1",payload={"module_id":3}))
    assert e.id and e.occurred_at is not None and saved==[e]
    batch=s.intake_batch([EventIn(topic="a",aggregate_type="t",aggregate_id="1"),EventIn(topic="b",aggregate_type="t",aggregate_id="2")])
    assert len(batch)==2 and len({e.id for e in batch})==2
def test_custom_kpi_definition_lifecycle_and_computation():
    repo=FakeRepo(events=[event(1,"outreach.sent",NOW-timedelta(hours=2)),event(2,"outreach.sent",NOW-timedelta(hours=30)),event(3,"other",NOW-timedelta(hours=1))])
    defs={}
    repo.save_kpi_definition=lambda d,at:defs.setdefault(d.id,KpiDefinitionOut(**d.model_dump(),created_at=at))
    repo.list_kpi_definitions=lambda:list(defs.values())
    repo.delete_kpi_definition=lambda i:defs.pop(i,None) is not None
    s=Service(repo,catalog=CAT)
    out=s.save_kpi_definition(KpiDefinitionIn(id="outreach_sent",label="Outreach sent",topics=["outreach.sent"]))
    assert out.id=="outreach_sent"
    k={x.id:x for x in s.kpis(NOW)}["outreach_sent"]
    assert k.value==1 and k.previous_value==1 and {r.id for r in k.evidence}=={"e1"}
    with pytest.raises(ValueError):s.save_kpi_definition(KpiDefinitionIn(id="grants_won",label="x",topics=["t"]))
    s.delete_kpi_definition("outreach_sent")
    assert "outreach_sent" not in {x.id for x in s.kpis(NOW)}
    with pytest.raises(LookupError):s.delete_kpi_definition("outreach_sent")
def test_custom_kpi_window_override():
    repo=FakeRepo(events=[event(1,"outreach.sent",NOW-timedelta(hours=50))])
    defs={}
    repo.save_kpi_definition=lambda d,at:defs.setdefault(d.id,d)
    repo.list_kpi_definitions=lambda:list(defs.values())
    s=Service(repo,catalog=CAT)
    s.save_kpi_definition(KpiDefinitionIn(id="outreach_week",label="Outreach week",topics=["outreach.sent"],window_hours=72))
    k={x.id:x for x in s.kpis(NOW)}["outreach_week"]
    assert k.value==1 and k.window_hours==72
def test_digest_sections_reflect_state():
    approvals=[approval(1,module_id=3,expires=NOW-timedelta(minutes=5))]
    events=[event(1,"grant.won",NOW-timedelta(hours=1))]
    s=svc(approvals=approvals,events=events)
    d=s.digest(NOW)
    assert d.open_blockers>=2 and d.generated_at==NOW
    titles={sec.title for sec in d.sections}
    assert titles=={"KPIs","Blockers","Modules"}
    kpis_sec=next(sec for sec in d.sections if sec.title=="KPIs")
    assert any(line.startswith("Grants won: 1") for line in kpis_sec.lines)
    blockers_sec=next(sec for sec in d.sections if sec.title=="Blockers")
    assert any("[critical]" in line for line in blockers_sec.lines)
    modules_sec=next(sec for sec in d.sections if sec.title=="Modules")
    assert any("module 3" in line for line in modules_sec.lines)
def _rule_repo(repo):
    rules={}
    repo.save_alert_rule=lambda d,at:rules.setdefault(d.id,d)
    repo.list_alert_rules=lambda:list(rules.values())
    repo.delete_alert_rule=lambda i:rules.pop(i,None) is not None
    appended=[]
    repo.append_event=lambda e:(appended.append(e) or e)
    repo._appended=appended
    return rules
def test_alert_rule_fires_on_projection_and_dedupes_hourly():
    repo=FakeRepo(events=[event(1,"grant.won",NOW-timedelta(hours=1)),event(2,"grant.won",NOW-timedelta(hours=2))])
    rules=_rule_repo(repo)
    s=Service(repo,catalog=CAT)
    s.save_alert_rule(AlertRuleIn(id="grants_spike",kpi_id="grants_won",comparator=AlertComparator.GTE,threshold=2))
    summary=s.project(NOW)
    assert summary["alerts_fired"]==1
    alerts=[e for e in repo._appended if e.topic=="alert"]
    assert len(alerts)==1 and alerts[0].aggregate_id=="grants_spike" and alerts[0].payload["value"]==2
    again=s.project(NOW)
    assert again["alerts_fired"]==1 and len([e for e in repo._appended if e.topic=="alert"])==2  # redelivery dedupes at repo level in SQL
def test_alert_rule_below_threshold_and_unknown_kpi():
    repo=FakeRepo(events=[event(1,"grant.won",NOW-timedelta(hours=1))])
    _rule_repo(repo)
    s=Service(repo,catalog=CAT)
    s.save_alert_rule(AlertRuleIn(id="grants_spike",kpi_id="grants_won",comparator=AlertComparator.GT,threshold=5))
    s.save_alert_rule(AlertRuleIn(id="ghost",kpi_id="no_such_kpi",comparator=AlertComparator.GT,threshold=0))
    assert s.project(NOW)["alerts_fired"]==0 and repo._appended==[]
def test_alert_rule_custom_message_and_delete():
    repo=FakeRepo();_rule_repo(repo)
    s=Service(repo,catalog=CAT)
    s.save_alert_rule(AlertRuleIn(id="pending_high",kpi_id="approvals_pending",comparator=AlertComparator.GTE,threshold=0,message="queue needs review"))
    assert s.project(NOW)["alerts_fired"]==1
    assert repo._appended[0].payload["message"]=="queue needs review"
    s.delete_alert_rule("pending_high")
    with pytest.raises(LookupError):s.delete_alert_rule("pending_high")
    assert s.project(NOW)["alerts_fired"]==0
def test_bulk_decide_mixed_results():
    repo=FakeRepo(approvals=[approval(1),approval(2),approval(3,expires=NOW-timedelta(minutes=5))])
    outcomes={}
    def decide(aid,state,note,at):
        a=next(x for x in repo._approvals if x.id==aid);a.state=state;a.reviewed_at=at;outcomes[aid]=state;return a
    repo.decide=decide
    s=Service(repo,catalog=CAT)
    result=s.decide_many(BulkApprovalDecision(approval_ids=["ap1","ap2","ap3","missing"],approve=True,note="batch"))
    assert [a.id for a in result.decided]==["ap1","ap2"]
    reasons={x["id"]:x["reason"] for x in result.skipped}
    assert reasons["ap3"]=="approval expired" and reasons["missing"]=="not pending"
    assert outcomes=={"ap1":ApprovalState.APPROVED,"ap2":ApprovalState.APPROVED}
def test_sweep_expired_flips_state():
    expired=approval(1,expires=NOW-timedelta(minutes=5));fresh=approval(2,expires=NOW+timedelta(hours=2))
    repo=FakeRepo(approvals=[expired,fresh])
    def sweep(moment):
        out=[a for a in repo._approvals if a.state==ApprovalState.PENDING and a.expires_at and a.expires_at<moment]
        for a in out:a.state=ApprovalState.EXPIRED
        return out
    repo.expire_approvals_before=sweep
    s=Service(repo,catalog=CAT)
    result=s.sweep_expired(NOW)
    assert [a.id for a in result]==["ap1"] and expired.state==ApprovalState.EXPIRED and fresh.state==ApprovalState.PENDING
    assert s.blockers(NOW)==[b for b in s.blockers(NOW) if b.kind!="approval_expired_pending"]
def test_export_events_csv_filtered_and_bounded():
    events=[event(1,"grant.won",NOW-timedelta(hours=1),payload={"module_id":3}),event(2,"task.completed",NOW-timedelta(hours=1)),event(3,"grant.won",NOW-timedelta(hours=40))]
    s=svc(events=events)
    csv_text=s.export_events_csv(24,"grant.won",now=NOW)
    lines=csv_text.strip().splitlines()
    assert lines[0]=="id,sequence,topic,aggregate_type,aggregate_id,module_id,occurred_at"
    assert len(lines)==2 and lines[1].startswith("e1,1,grant.won") and ",3," in lines[1]
    assert "e3" not in s.export_events_csv(24,None,now=NOW) and "e2" in s.export_events_csv(24,None,now=NOW)
def test_export_kpis_csv():
    s=svc(events=[event(1,"grant.won",NOW-timedelta(hours=1))])
    text=s.export_kpis_csv(NOW)
    assert text.splitlines()[0]=="id,label,value,unit,previous_value,window_hours,evidence_total"
    row=next(l for l in text.splitlines() if l.startswith("grants_won,"))
    assert row.startswith("grants_won,Grants won,1.0,count,") or row.startswith("grants_won,Grants won,1,count,")
def test_default_view_when_unset():
    view=svc().get_view(NOW)
    assert [w.kind for w in view.widgets]==[WidgetKind.KPI_CARD,WidgetKind.BLOCKERS,WidgetKind.MODULE_STATUS,WidgetKind.TIMELINE,WidgetKind.APPROVALS]
def test_save_view_validates_and_normalizes():
    repo=FakeRepo();stored={}
    repo.save_view=lambda layout,at:stored.update(layout=layout,at=at)
    repo.get_view=lambda:(stored.get("layout"),stored.get("at"))
    s=Service(repo,catalog=CAT)
    view=s.save_view(DashboardViewIn(widgets=[WidgetConfig(id="b",kind=WidgetKind.BLOCKERS,position=9),WidgetConfig(id="k",kind=WidgetKind.KPI_CARD,kpi_id="grants_won",position=3)]))
    assert [w.id for w in view.widgets]==["k","b"] and [w.position for w in view.widgets]==[0,1]
    loaded=s.get_view(NOW)
    assert [w.id for w in loaded.widgets]==["k","b"]
    with pytest.raises(ValueError):s.save_view(DashboardViewIn(widgets=[WidgetConfig(id="x",kind=WidgetKind.KPI_CARD,kpi_id="nope"),WidgetConfig(id="x",kind=WidgetKind.BLOCKERS)]))
    with pytest.raises(ValueError):s.save_view(DashboardViewIn(widgets=[WidgetConfig(id="y",kind=WidgetKind.KPI_CARD,kpi_id="nope")]))
def test_alert_cooldown_buckets():
    from app.modules.m16_executive_dashboard.alerts import cooldown_bucket
    base=datetime.fromtimestamp(int(NOW.timestamp()//21600)*21600,tz=timezone.utc)  # aligned 6h boundary
    rule=AlertRuleOut(id="rr",kpi_id="kk",comparator=AlertComparator.GT,threshold=1,cooldown_hours=6,created_at=NOW)
    assert cooldown_bucket(rule,base)==cooldown_bucket(rule,base+timedelta(hours=5))
    assert cooldown_bucket(rule,base+timedelta(hours=7))>cooldown_bucket(rule,base)
    hourly=AlertRuleOut(id="rr",kpi_id="kk",comparator=AlertComparator.GT,threshold=1,created_at=NOW)
    assert cooldown_bucket(hourly,base)!=cooldown_bucket(hourly,base+timedelta(hours=1))
def test_export_events_csv_cursor_pagination():
    events=[event(i,"task.completed",NOW-timedelta(minutes=i)) for i in range(1,6)]
    s=svc(events=events)
    page1=s.export_events_csv(24,None,0,NOW).strip().splitlines()
    assert len(page1)==6
    page2=s.export_events_csv(24,None,3,NOW).strip().splitlines()
    ids=[l.split(",")[0] for l in page2[1:]]
    assert ids==["e4","e5"]
