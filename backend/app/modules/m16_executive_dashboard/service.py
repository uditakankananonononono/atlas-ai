from __future__ import annotations
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from .alerts import alert_message,cooldown_bucket,evaluate
from .blockers import detect_blockers
from .kpis import EVENT_KPIS,RESERVED_KPI_IDS,compute_kpis,custom_event_kpi,event_ref,kpi_event_evidence
from . import analysis,finance_core as finance,climate_environment_1610_1659 as climate_environment,ai_systems_1910_1959 as ai_systems,planning
from .projector import fold
from .schemas import *
from .status import RepoCatalog,effective_state,event_module_id,module_statuses
from .timeline import critical_path
def _utcnow():return datetime.now(timezone.utc)
class Service:
    def __init__(self,repository,catalog=None,parser=None,executor=None,window_hours:int=24):
        self.repository=repository;self.catalog=catalog or RepoCatalog();self.parser=parser or self._parse;self.executor=executor or self._execute_read;self.window_hours=window_hours
    # --- snapshot, events, approvals (existing contract) ---
    def snapshot(self):
        self._project_if_needed()
        return self.repository.snapshot()
    def _project_if_needed(self):
        updater=getattr(self.repository,"update_snapshot",None)
        if not updater:return 0
        snap=self.repository.snapshot();pending=self.repository.events_after(snap.last_sequence)
        if not pending:return 0
        data,last=fold(snap.data,pending);updater(data,last);return len(pending)
    def project(self,now=None):
        """Fold pending events into the snapshot and record a KPI history point. Returns a summary."""
        now=now or _utcnow();projected=self._project_if_needed()
        kpis=self.kpis(now)
        recorder=getattr(self.repository,"record_kpi_points",None)
        if recorder:recorder([(k.id,k.window_hours,k.value) for k in kpis],now)
        fired=self._evaluate_alert_rules(kpis,now)
        return {"projected_events":projected,"last_sequence":self.repository.snapshot().last_sequence,"recorded_points":len(kpis) if recorder else 0,"alerts_fired":fired,"at":now.isoformat()}
    def _evaluate_alert_rules(self,kpis,now):
        fired=0
        for rule,kpi in evaluate(self.list_alert_rules(),kpis):
            self.repository.append_event(Event(id=f"alert:{rule.id}:{cooldown_bucket(rule,now)}",sequence=0,topic="alert",aggregate_type="alert_rule",aggregate_id=rule.id,payload={"severity":rule.severity.value,"message":alert_message(rule,kpi),"kpi_id":kpi.id,"value":kpi.value,"threshold":rule.threshold},occurred_at=now));fired+=1
        if fired:self._project_if_needed()
        return fired
    def events_after(self,cursor):return self.repository.events_after(cursor)
    def pending_approvals(self):
        now=_utcnow();return [a for a in self.repository.pending_approvals() if not a.expires_at or a.expires_at>now]
    def _all_pending(self):return list(self.repository.pending_approvals())
    def decide(self,aid,data):
        pending=next((a for a in self._all_pending() if a.id==aid),None)
        if not pending:raise LookupError(aid)
        if pending.expires_at and pending.expires_at<_utcnow():raise RuntimeError("approval expired")
        return self.repository.decide(aid,ApprovalState.APPROVED if data.approve else ApprovalState.REJECTED,data.note,_utcnow())
    # --- command bar (existing contract, real read-only executor) ---
    def preview(self,utterance):
        parsed=self.parser(utterance);now=_utcnow();return self.repository.save_command(CommandPreview(id=str(uuid4()),utterance=utterance,expires_at=now+timedelta(minutes=10),created_at=now,**parsed))
    def execute(self,cid):
        row,p=self.repository.get_command(cid)
        if not p:raise LookupError(cid)
        now=_utcnow()
        if row.executed_at:raise RuntimeError("command already executed")
        if p.expires_at<now:raise RuntimeError("command preview expired")
        if not p.read_only:
            a=Approval(id=str(uuid4()),module_id=16,action_type=p.intent,title=f"Command: {p.intent}",summary=p.utterance,risk="medium",evidence={"command_preview_id":p.id,"plan":p.plan},proposed_payload=p.parameters,created_at=now,expires_at=now+timedelta(hours=24));self.repository.save_approval(a);return {"status":"approval_required","approval_id":a.id}
        result=self.executor(p.intent,p.parameters);self.repository.mark_command(cid,now);return {"status":"completed","result":result}
    def _execute_read(self,intent,params):
        now=_utcnow()
        if intent=="show_kpis":return {"kpis":[k.model_dump(mode="json") for k in self.kpis(now)]}
        if intent=="show_blockers":return {"blockers":[b.model_dump(mode="json") for b in self.blockers(now)]}
        if intent=="show_status":return {"modules":[m.model_dump(mode="json") for m in self.module_statuses(now)]}
        if intent=="show_timeline":
            timeline=self._timeline()
            return {"timeline":[i.model_dump(mode="json") for i in timeline],"critical_path":self._critical_path(timeline)}
        return {"items":self._search_snapshot(str(params.get("query",""))),"intent":intent,"parameters":params}
    def _search_snapshot(self,query):
        data=self.snapshot().data;q=query.casefold();hits=[]
        def walk(node,path):
            if len(hits)>=50:return
            if isinstance(node,dict):
                for k,v in node.items():walk(v,f"{path}.{k}" if path else str(k))
            elif isinstance(node,list):
                for i,v in enumerate(node):walk(v,f"{path}[{i}]")
            elif q in str(node).casefold():hits.append({"path":path,"value":node})
        walk(data,"")
        return hits
    @staticmethod
    def _parse(text):
        lowered=text.casefold();mutations=("send ","email ","schedule ","create ","update ","delete ","approve ","publish ","submit ")
        read_only=not any(x in lowered for x in mutations)
        if not read_only:
            return {"intent":"proposed_action","parameters":{"query":text},"plan":[{"action":"prepare_for_approval","input":text}],"read_only":False,"confidence":.55}
        keywords=(("blocker","show_blockers"),("blocked","show_blockers"),("stuck","show_blockers"),("kpi","show_kpis"),("metric","show_kpis"),("status","show_status"),("health","show_status"),("timeline","show_timeline"),("gantt","show_timeline"),("critical path","show_timeline"))
        intent,confidence="search_dashboard",.55
        for word,target in keywords:
            if word in lowered:intent,confidence=target,.7;break
        return {"intent":intent,"parameters":{"query":text},"plan":[{"action":"read_dashboard","input":text}],"read_only":True,"confidence":confidence}
    # --- repository access with graceful degradation for lean repositories ---
    def _agents(self):
        getter=getattr(self.repository,"list_agents",None);return list(getter()) if getter else []
    def _events_between(self,start,end):
        getter=getattr(self.repository,"events_between",None);return list(getter(start,end)) if getter else []
    def _reviewed_since(self,since):
        getter=getattr(self.repository,"approvals_reviewed_since",None);return list(getter(since)) if getter else []
    def _timeline(self):
        raw=self.snapshot().data.get("timeline",[]);items=[]
        for entry in raw:
            try:items.append(entry if isinstance(entry,TimelineItem) else TimelineItem(**entry))
            except Exception:continue
        return items
    def _critical_path(self,items):
        try:return critical_path(items)
        except ValueError:return []
    def _modules(self):return self.catalog.list_modules()
    # --- cross-module status, KPIs, blockers, drilldowns ---
    def module_statuses(self,now=None):
        now=now or _utcnow();since=now-timedelta(hours=24)
        return module_statuses(self.catalog,self._agents(),self._all_pending(),self._events_between(since,now),now)
    def kpis(self,now=None):
        now=now or _utcnow();since=now-timedelta(hours=self.window_hours);prev=since-timedelta(hours=self.window_hours)
        out=compute_kpis(self._events_between(since,now),self._events_between(prev,since),self.pending_approvals(),self._reviewed_since(since),[a.model_copy(update={"state":effective_state(a,now)}) for a in self._agents()],self._timeline(),now,self.window_hours)
        history=getattr(self.repository,"kpi_value_at_or_before",None)
        if history:
            for k in out:
                if k.previous_value is None:
                    prior=history(k.id,k.window_hours,since)
                    if prior is not None:k.previous_value=float(prior)
        for d in self.list_kpi_definitions():
            hours=d.window_hours or self.window_hours;dstart=now-timedelta(hours=hours);dprev=dstart-timedelta(hours=hours)
            out.append(custom_event_kpi(d,self._events_between(dstart,now),self._events_between(dprev,dstart),self.window_hours))
        return out
    def blockers(self,now=None):
        now=now or _utcnow()
        return detect_blockers(self._all_pending(),self._agents(),self._timeline(),self._modules(),now)
    def overview(self,now=None):
        now=now or _utcnow();timeline=self._timeline()
        statuses=self.module_statuses(now);blocks=self.blockers(now)
        for s in statuses:s.open_blockers=sum(1 for b in blocks if b.module_id==s.module_id)
        return DashboardOverview(generated_at=now,modules=statuses,kpis=self.kpis(now),blockers=blocks,pending_approvals=len(self.pending_approvals()),critical_path=self._critical_path(timeline))
    def kpi_evidence(self,kpi_id,now=None):
        now=now or _utcnow();since=now-timedelta(hours=self.window_hours);prev=since-timedelta(hours=self.window_hours)
        event_windows=kpi_event_evidence(kpi_id,self._events_between(since,now),self._events_between(prev,since),self.window_hours)
        if event_windows is not None:
            current,previous=event_windows
            return DrilldownResult(subject=EvidenceRef(kind="kpi",id=kpi_id,summary=f"KPI {kpi_id}"),detail={"window_start":since.isoformat(),"window_end":now.isoformat(),"count":len(current),"previous_count":len(previous)},events=current)
        gauges={"approvals_pending":self.pending_approvals(),"approval_decisions":self._reviewed_since(since),"avg_approval_turnaround_hours":self._reviewed_since(since)}
        if kpi_id in gauges:
            approvals=gauges[kpi_id]
            return DrilldownResult(subject=EvidenceRef(kind="kpi",id=kpi_id,summary=f"KPI {kpi_id}"),detail={"window_start":since.isoformat(),"window_end":now.isoformat(),"count":len(approvals)},approvals=approvals)
        if kpi_id=="agents_stalled":
            stuck=[a for a in self._agents() if effective_state(a,now) in (AgentState.STALLED,AgentState.OFFLINE)]
            return DrilldownResult(subject=EvidenceRef(kind="kpi",id=kpi_id,summary="KPI agents_stalled"),detail={"count":len(stuck),"agents":[a.model_dump(mode="json") for a in stuck]})
        if kpi_id=="timeline_items_at_risk":
            from .timeline import overdue_items
            risky=overdue_items(self._timeline(),now)
            return DrilldownResult(subject=EvidenceRef(kind="kpi",id=kpi_id,summary="KPI timeline_items_at_risk"),detail={"count":len(risky),"items":[i.model_dump(mode="json") for i in risky]})
        raise LookupError(kpi_id)
    def drilldown(self,kind,ref_id,now=None):
        now=now or _utcnow()
        if kind=="event":
            getter=getattr(self.repository,"event_by_id",None);e=getter(ref_id) if getter else None
            if not e:raise LookupError(ref_id)
            related=self._events_between(e.occurred_at-timedelta(minutes=5),e.occurred_at+timedelta(minutes=5))
            return DrilldownResult(subject=event_ref(e),detail=e.model_dump(mode="json"),events=[x for x in related if x.id!=e.id])
        if kind=="approval":
            getter=getattr(self.repository,"approval_by_id",None);a=getter(ref_id) if getter else None
            if not a:raise LookupError(ref_id)
            events=[e for e in self._events_between(a.created_at-timedelta(days=30),now) if e.aggregate_id==a.id][:100]
            return DrilldownResult(subject=EvidenceRef(kind="approval",id=a.id,summary=a.title),detail=a.model_dump(mode="json"),events=events,approvals=[a])
        if kind=="module":
            try:mid=int(ref_id)
            except ValueError:raise LookupError(ref_id)
            status=next((s for s in self.module_statuses(now) if s.module_id==mid),None)
            if not status:raise LookupError(ref_id)
            approvals=[a for a in self._all_pending() if a.module_id==mid]
            events=[e for e in self._events_between(now-timedelta(hours=24),now) if event_module_id(e)==mid][:100]
            return DrilldownResult(subject=EvidenceRef(kind="module",id=str(mid),summary=status.name),detail=status.model_dump(mode="json"),events=events,approvals=approvals)
        if kind=="timeline_item":
            item=next((i for i in self._timeline() if i.id==ref_id),None)
            if not item:raise LookupError(ref_id)
            timeline=self._timeline();dependents=[i for i in timeline if ref_id in i.dependencies]
            detail=item.model_dump(mode="json");detail["dependents"]=[i.id for i in dependents]
            try:detail["on_critical_path"]=ref_id in critical_path(timeline)
            except ValueError:detail["on_critical_path"]=False
            return DrilldownResult(subject=EvidenceRef(kind="timeline_item",id=item.id,summary=item.title),detail=detail)
        raise LookupError(f"{kind}/{ref_id}")
    # --- event intake ---
    def intake(self,data:EventIn):
        now=_utcnow()
        e=Event(id=data.id or str(uuid4()),sequence=0,topic=data.topic,aggregate_type=data.aggregate_type,aggregate_id=data.aggregate_id,payload=data.payload,occurred_at=data.occurred_at or now)
        return self.repository.append_event(e)
    def intake_batch(self,items):
        return [self.intake(i) for i in items]
    # --- tenant-defined KPIs ---
    def save_kpi_definition(self,data:KpiDefinitionIn):
        saver=getattr(self.repository,"save_kpi_definition",None)
        if not saver:raise RuntimeError("repository does not support kpi definitions")
        reserved=RESERVED_KPI_IDS|{d.id for d in EVENT_KPIS}
        if data.id in reserved:raise ValueError(f"kpi id {data.id} is reserved")
        return saver(data,_utcnow())
    def list_kpi_definitions(self):
        getter=getattr(self.repository,"list_kpi_definitions",None);return list(getter()) if getter else []
    def delete_kpi_definition(self,kpi_id):
        deleter=getattr(self.repository,"delete_kpi_definition",None)
        if not deleter or not deleter(kpi_id):raise LookupError(kpi_id)
    # --- KPI alert rules ---
    def save_alert_rule(self,data:AlertRuleIn):
        saver=getattr(self.repository,"save_alert_rule",None)
        if not saver:raise RuntimeError("repository does not support alert rules")
        return saver(data,_utcnow())
    def list_alert_rules(self):
        getter=getattr(self.repository,"list_alert_rules",None);return list(getter()) if getter else []
    def delete_alert_rule(self,rule_id):
        deleter=getattr(self.repository,"delete_alert_rule",None)
        if not deleter or not deleter(rule_id):raise LookupError(rule_id)
    # --- bulk approval decisions ---
    def decide_many(self,data:BulkApprovalDecision):
        decided=[];skipped=[]
        for aid in data.approval_ids:
            try:
                result=self.decide(aid,ApprovalDecision(approve=data.approve,note=data.note))
                if result:decided.append(result)
                else:skipped.append({"id":aid,"reason":"not pending"})
            except LookupError:skipped.append({"id":aid,"reason":"not pending"})
            except RuntimeError as e:skipped.append({"id":aid,"reason":str(e)})
        return BulkDecisionResult(decided=decided,skipped=skipped)
    # --- tenant dashboard view ---
    DEFAULT_WIDGETS=({"id":"kpis","kind":WidgetKind.KPI_CARD,"position":0},{"id":"blockers","kind":WidgetKind.BLOCKERS,"position":1},{"id":"modules","kind":WidgetKind.MODULE_STATUS,"position":2},{"id":"timeline","kind":WidgetKind.TIMELINE,"position":3},{"id":"approvals","kind":WidgetKind.APPROVALS,"position":4})
    def get_view(self,now=None):
        getter=getattr(self.repository,"get_view",None)
        layout,at=(getter() if getter else (None,None))
        if layout is None:return DashboardView(widgets=[WidgetConfig(**w) for w in self.DEFAULT_WIDGETS],updated_at=now or _utcnow())
        return DashboardView(widgets=[WidgetConfig(**w) for w in layout["widgets"]],updated_at=at)
    def save_view(self,data:DashboardViewIn):
        saver=getattr(self.repository,"save_view",None)
        if not saver:raise RuntimeError("repository does not support view preferences")
        known={k.id for k in self.kpis()}
        ids=set()
        for w in data.widgets:
            if w.id in ids:raise ValueError(f"duplicate widget id {w.id}")
            ids.add(w.id)
            if w.kind==WidgetKind.KPI_CARD and w.kpi_id is not None and w.kpi_id not in known:raise ValueError(f"unknown kpi_id {w.kpi_id}")
        ordered=sorted(data.widgets,key=lambda w:w.position)
        for i,w in enumerate(ordered):w.position=i
        now=_utcnow();saver({"widgets":[w.model_dump(mode="json") for w in ordered]},now)
        return DashboardView(widgets=ordered,updated_at=now)
    # --- approval expiry sweep ---
    def sweep_expired(self,now=None):
        """Flip pending approvals past their expiry to EXPIRED. Returns the expired approvals."""
        now=now or _utcnow()
        sweeper=getattr(self.repository,"expire_approvals_before",None)
        if not sweeper:raise RuntimeError("repository does not support expiry sweeps")
        return sweeper(now)
    # --- evidence export ---
    def export_events_csv(self,since_hours:int=24,topic:str|None=None,after_sequence:int=0,now=None):
        now=now or _utcnow();since=now-timedelta(hours=max(1,min(since_hours,24*30)))
        rows=[e for e in self._events_between(since,now) if e.sequence>after_sequence]
        if topic:rows=[e for e in rows if e.topic==topic]
        import csv,io
        buf=io.StringIO();w=csv.writer(buf)
        w.writerow(["id","sequence","topic","aggregate_type","aggregate_id","module_id","occurred_at"])
        for e in rows[:5000]:w.writerow([e.id,e.sequence,e.topic,e.aggregate_type,e.aggregate_id,event_module_id(e) or "",e.occurred_at.isoformat()])
        return buf.getvalue()
    def export_kpis_csv(self,now=None):
        now=now or _utcnow()
        import csv,io
        buf=io.StringIO();w=csv.writer(buf)
        w.writerow(["id","label","value","unit","previous_value","window_hours","evidence_total"])
        for k in self.kpis(now):w.writerow([k.id,k.label,k.value,k.unit,"" if k.previous_value is None else k.previous_value,k.window_hours,k.evidence_total])
        return buf.getvalue()
    # --- planning & measurement (feature rows 388-399) ---
    def create_work_item(self,data:WorkItemIn):
        existing=self.repository.list_work_items()
        rank=max((i.rank for i in existing),default=0)+1
        now=_utcnow()
        return self.repository.save_work_item(WorkItemOut(id=str(uuid4()),rank=rank,created_at=now,updated_at=now,**data.model_dump()))
    def patch_work_item(self,item_id,patch:WorkItemPatch):
        item=self.repository.get_work_item(item_id)
        if not item:raise LookupError(item_id)
        data=item.model_dump()
        for k,v in patch.model_dump(exclude_unset=True).items():
            if v is not None:data[k]=v
        if data["status"] not in planning.KANBAN_COLUMNS:raise ValueError(f"unknown status {data['status']}")
        if data["status"]=="done" and item.status!="done":data["completed_at"]=_utcnow()
        if data["status"]!="done":data["completed_at"]=None
        data["updated_at"]=_utcnow()
        return self.repository.save_work_item(WorkItemOut(**data))
    def delete_work_item(self,item_id):
        if not self.repository.delete_work_item(item_id):raise LookupError(item_id)
    def list_work_items(self,sprint_id=None,roadmap_id=None,status=None):
        return self.repository.list_work_items(sprint_id,roadmap_id,status)
    def prioritization(self,method:str):
        items=[i for i in self.repository.list_work_items() if i.status!="done"]
        return planning.prioritize(items,method)
    def create_sprint(self,data:SprintIn):
        if data.end<=data.start:raise ValueError("sprint end must be after start")
        return self.repository.save_sprint(SprintOut(id=str(uuid4()),**data.model_dump()))
    def list_sprints(self):return self.repository.list_sprints()
    def start_sprint(self,sprint_id):
        sp=self.repository.get_sprint(sprint_id)
        if not sp:raise LookupError(sprint_id)
        if sp.status!="planned":raise ValueError(f"sprint is {sp.status}, only planned sprints can start")
        for other in self.repository.list_sprints():
            if other.status=="active":raise ValueError(f"sprint {other.name} is already active")
        sp.status="active";return self.repository.save_sprint(sp)
    def close_sprint(self,sprint_id):
        sp=self.repository.get_sprint(sprint_id)
        if not sp:raise LookupError(sprint_id)
        if sp.status!="active":raise ValueError(f"sprint is {sp.status}, only active sprints can close")
        sp.status="closed";sp.closed_at=_utcnow();return self.repository.save_sprint(sp)
    def burndown(self,sprint_id,now=None):
        sp=self.repository.get_sprint(sprint_id)
        if not sp:raise LookupError(sprint_id)
        items=self.repository.list_work_items(sprint_id=sprint_id)
        series,assumptions=planning.burndown(sp,items,now or _utcnow())
        return BurndownReport(sprint_id=sprint_id,series=series,assumptions=assumptions)
    def velocity_report(self):
        sprints=self.repository.list_sprints()
        by_sprint={sp.id:self.repository.list_work_items(sprint_id=sp.id) for sp in sprints}
        points,avg=planning.velocity(sprints,by_sprint)
        return VelocityReport(sprints=points,average_completed=avg,inputs={"sprint_ids":[p.sprint_id for p in points],"note":"Average over closed sprints only; completed means items in done with estimates."})
    def board(self):
        items=self.repository.list_work_items()
        columns={c:[i for i in items if i.status==c] for c in planning.KANBAN_COLUMNS}
        return KanbanBoard(columns=columns,wip_limits=planning.DEFAULT_WIP_LIMITS)
    def move_item(self,item_id,column):
        item=self.repository.get_work_item(item_id)
        if not item:raise LookupError(item_id)
        planning.move_item(item,column,self.repository.list_work_items())
        return self.patch_work_item(item_id,WorkItemPatch(status=column))
    def create_roadmap(self,data:RoadmapIn):
        if data.horizon_end<=data.horizon_start:raise ValueError("horizon end must be after start")
        return self.repository.save_roadmap(RoadmapOut(id=str(uuid4()),created_at=_utcnow(),**data.model_dump()))
    def list_roadmaps(self):return self.repository.list_roadmaps()
    def roadmap_view(self,roadmap_id):
        rm=self.repository.get_roadmap(roadmap_id)
        if not rm:raise LookupError(roadmap_id)
        return RoadmapView(roadmap=rm,lanes=planning.roadmap_view(self.repository.list_work_items(roadmap_id=roadmap_id)))
    def create_ceremony(self,data:CeremonyIn):
        if not self.repository.get_sprint(data.sprint_id):raise LookupError(data.sprint_id)
        return self.repository.save_ceremony(CeremonyOut(id=str(uuid4()),created_at=_utcnow(),**data.model_dump()))
    def list_ceremonies(self,sprint_id=None):return self.repository.list_ceremonies(sprint_id)
    def create_retrospective(self,data:RetrospectiveIn):
        if not self.repository.get_sprint(data.sprint_id):raise LookupError(data.sprint_id)
        items=[{**a,"status":a.get("status","open")} for a in data.action_items]
        return self.repository.save_retrospective(RetrospectiveOut(id=str(uuid4()),created_at=_utcnow(),**{**data.model_dump(),"action_items":items}))
    def list_retrospectives(self):return self.repository.list_retrospectives()
    def retro_rollup(self):return planning.retro_rollup(self.repository.list_retrospectives())
    def create_experiment(self,data:ExperimentIn):
        errors=planning.validate_experiment(data.kind,[v.model_dump() for v in data.variants])
        if errors:raise ValueError("; ".join(errors))
        now=_utcnow()
        return self.repository.save_experiment(ExperimentOut(id=str(uuid4()),variants=[VariantOut(**v.model_dump()) for v in data.variants],created_at=now,updated_at=now,**data.model_dump(exclude={"variants"})))
    def list_experiments(self):return self.repository.list_experiments()
    def get_experiment(self,experiment_id):
        e=self.repository.get_experiment(experiment_id)
        if not e:raise LookupError(experiment_id)
        return e
    def record_measurement(self,experiment_id,data:MeasurementIn):
        e=self.get_experiment(experiment_id)
        if e.status!="running":raise ValueError(f"experiment is {e.status}; measurements require a running experiment")
        for v in e.variants:
            if v.key==data.variant_key:
                v.trials=data.trials;v.successes=data.successes;e.updated_at=_utcnow()
                return self.repository.save_experiment(e)
        raise LookupError(data.variant_key)
    def set_experiment_status(self,experiment_id,status):
        allowed={"draft":{"running"},"running":{"paused","concluded"},"paused":{"running","concluded"},"concluded":set()}
        e=self.get_experiment(experiment_id)
        if status not in allowed.get(e.status,set()):raise ValueError(f"cannot move experiment from {e.status} to {status}")
        e.status=status;e.updated_at=_utcnow();return self.repository.save_experiment(e)
    def experiment_significance(self,experiment_id,alpha:float=0.05):
        return planning.experiment_significance(self.get_experiment(experiment_id),alpha)
    # --- agent heartbeats ---
    def digest(self,now=None):
        """Deterministic executive digest: text sections computed from live KPIs, blockers and statuses."""
        now=now or _utcnow();kpis=self.kpis(now);blocks=self.blockers(now);statuses=self.module_statuses(now)
        kpi_lines=[]
        for k in kpis:
            trend=""
            if k.previous_value is not None:
                delta=k.value-k.previous_value;trend=f" ({'+' if delta>=0 else ''}{delta:g} vs prior {k.window_hours}h)"
            kpi_lines.append(f"{k.label}: {k.value:g} {k.unit}{trend}")
        blocker_lines=[f"[{b.severity.value}] {b.summary} Action: {b.recommended_action}" for b in blocks[:20]]
        agent_lines=[f"module {s.module_id} ({s.slug}): {'implemented' if s.implemented else 'not implemented'}, agent {(s.agent.state.value if s.agent else 'none')}, {s.pending_approvals} pending approvals, {s.events_24h} events/24h, {s.open_blockers} blockers" for s in statuses]
        return Digest(generated_at=now,pending_approvals=len(self.pending_approvals()),open_blockers=len(blocks),sections=[DigestSection(title="KPIs",lines=kpi_lines),DigestSection(title="Blockers",lines=blocker_lines or ["none"]),DigestSection(title="Modules",lines=agent_lines)])
    def heartbeat(self,data:AgentHeartbeat):
        saver=getattr(self.repository,"heartbeat",None)
        if not saver:raise RuntimeError("repository does not support agent heartbeats")
        return saver(data,_utcnow())
# --- tenant-bound analysis jobs (feature rows 1010-1034) ---
METHOD_SUMMARIES={"predictive":"Forecasts future outcomes","prescriptive":"Recommends actions","descriptive":"Summarizes past data","diagnostic":"Explains why things happened","eda":"Discovers patterns","confirmatory":"Tests hypotheses","inference":"Draws conclusions","hypothesis_test":"Tests claims","confidence_interval":"Quantifies uncertainty","bootstrap":"Resamples for inference","permutation_test":"Tests without assumptions","nonparametric":"Avoids distributional assumptions","robust":"Resists outliers","outlier_detection":"Finds anomalies","imputation":"Fills gaps","multiple_imputation":"Handles uncertainty","mle":"Finds best parameters","em":"Handles latent variables","mcmc":"Samples complex distributions","variational":"Fast approximate inference","gibbs":"Iterative sampling","metropolis_hastings":"MCMC algorithm","hmc":"Efficient MCMC","smc":"Particle filtering","particle_filter":"Track dynamic systems","kalman_filter":"Linear-Gaussian state estimation","extended_kalman_filter":"Locally linearized nonlinear state estimation","unscented_kalman_filter":"Sigma-point nonlinear state estimation","hidden_markov_model":"Latent discrete-state sequence inference","conditional_random_field":"Structured sequence labeling from log-potentials","graphical_model":"Dependency graph structural diagnostics","bayesian_network":"Exact conditional inference in a binary DAG","markov_random_field":"Exact inference over binary undirected log-potentials","factor_graph":"Exact inference over binary factor products","belief_propagation":"Sum-product messages on binary factor graphs","variational_message_passing":"Conjugate natural-parameter message passing","expectation_propagation":"Moment-matched Gaussian factor approximation","laplace_approximation":"Local Gaussian posterior approximation at the MAP","importance_sampling":"Weighted proposal sampling with ESS diagnostics","rejection_sampling":"Envelope-based exact target sampling","slice_sampling":"Stepping-out univariate slice sampling","nested_sampling":"Likelihood-constrained evidence integration","approximate_bayesian_computation":"Simulator-based likelihood-free rejection inference","synthetic_likelihood":"Gaussian likelihood over simulated summaries","indirect_inference":"Auxiliary-statistic simulation matching","method_of_moments":"Parameter fitting from sample moments","generalized_method_of_moments":"Moment-condition parameter estimation","instrumental_variables":"Linear IV causal-effect estimation","two_stage_least_squares":"Explicit first-stage and second-stage IV estimation","limited_information_maximum_likelihood":"k-class limited-information IV estimation","control_functions":"Residual-inclusion endogeneity control","regression_discontinuity":"Local discontinuity estimation at an assignment cutoff","difference_in_differences":"Two-group two-period trend differencing","synthetic_control":"Convex donor-counterfactual construction","matching_methods":"Standardized nearest-neighbor covariate matching","propensity_score_matching":"Nearest-neighbor propensity-score matching","coarsened_exact_matching":"Exact matching over coarsened covariate strata","genetic_matching":"Weighted multivariate covariate matching","entropy_balancing":"Maximum-entropy exact covariate balance","inverse_probability_weighting":"Propensity-weighted marginal effect estimation","doubly_robust_estimation":"Augmented inverse-propensity estimation","targeted_maximum_likelihood":"Targeted logistic fluctuation estimation","machine_learning_causal_inference":"Cross-fitted nonparametric effect learning","causal_forests":"Heterogeneous-effect tree estimation","double_machine_learning":"Cross-fitted partially-linear effect estimation","orthogonalized_estimation":"Neyman-orthogonal residual-on-residual estimation","cross_fitting":"Out-of-fold prediction validation","sample_splitting":"Deterministic independent train/holdout allocation","post_selection_inference":"Selection-aware interval widening","selective_inference":"Threshold-conditional truncated-Normal testing","simultaneous_inference":"Family-level simultaneous confidence intervals","false_discovery_rate_control":"BH/BY false-discovery control","family_wise_error_rate":"Bonferroni/Holm/Sidak family-wise control","bonferroni_correction":"Per-test Bonferroni FWER correction","holm_bonferroni":"Step-down Holm family-wise correction","benjamini_hochberg":"Step-up BH false-discovery control","storeys_method":"Adaptive q-values using estimated null proportion","local_fdr":"Posterior null probability per observed statistic","permutation_based_fdr":"Permutation-null threshold FDR estimation","knockoffs":"Knockoff-filter variable selection","stability_selection":"Subsample selection-probability filtering","bootstrap_aggregation":"Bootstrap aggregation of scalar estimators","random_forests":"Bootstrap random-feature regression ensemble","gradient_boosting":"Sequential residual regression boosting","xgboost":"Regularized boosted regression stumps","lightgbm":"Leafwise-style boosted regression reference","catboost":"Ordered-style boosted numeric regression reference","adaboost":"Adaptive reweighting of binary decision stumps","stacking":"Out-of-fold weighted meta-ensembling","blending":"Held-out weighted prediction blending","bagging":"Bootstrap sampling ensemble semantics","pasting":"Subsampling-without-replacement ensemble semantics","voting_classifiers":"Hard/soft equal-vote classification","weighted_voting":"Weighted soft-vote classification","bayesian_model_averaging":"Evidence-weighted predictive averaging","bayesian_model_selection":"Posterior-probability model selection","information_criteria":"AIC/AICc/BIC model comparison","cross_validation":"Fold-wise out-of-sample evaluation","leave_one_out":"Leave-one-out prediction evaluation","k_fold_cross_validation":"Explicit k-fold out-of-sample evaluation"}
METHOD_INPUTS={"predictive":["x","y","future_x"],"prescriptive":["options"],"descriptive":["values"],"diagnostic":["x","y"],"eda":["values"],"confirmatory":["values"],"inference":["values"],"hypothesis_test":["values"],"confidence_interval":["values"],"bootstrap":["values"],"permutation_test":["group_a","group_b"],"nonparametric":["group_a","group_b"],"robust":["values"],"outlier_detection":["values"],"imputation":["values"],"multiple_imputation":["values"],"mle":["values"],"em":["values"],"mcmc":["values"],"variational":["values"],"gibbs":["values"],"metropolis_hastings":["values"],"hmc":["values"],"smc":["observations"],"particle_filter":["observations"],"kalman_filter":["observations"],"extended_kalman_filter":["observations"],"unscented_kalman_filter":["observations"],"hidden_markov_model":["observations","states","start_probability","transition_probability","emission_probability"],"conditional_random_field":["tokens","labels","emission_scores"],"graphical_model":["nodes","edges"],"bayesian_network":["variables","parents","cpts","query"],"markov_random_field":["variables","edges","unary_log_potentials","pairwise_log_potentials"],"factor_graph":["variables","factors"],"belief_propagation":["variables","factors"],"variational_message_passing":["observations"],"expectation_propagation":["lower"],"laplace_approximation":["observations","trials","successes"],"importance_sampling":["distribution parameters"],"rejection_sampling":["distribution parameters"],"slice_sampling":["distribution parameters"],"nested_sampling":["observation"],"approximate_bayesian_computation":["observed_summary"],"synthetic_likelihood":["observed_summary","simulated_summaries"],"indirect_inference":["observed_auxiliary","parameter_grid","simulated_auxiliary"],"method_of_moments":["values"],"generalized_method_of_moments":["instrument","regressor","outcome"],"instrumental_variables":["instrument","regressor","outcome"],"two_stage_least_squares":["instrument","regressor","outcome"],"limited_information_maximum_likelihood":["instrument","regressor","outcome"],"control_functions":["instrument","regressor","outcome"],"regression_discontinuity":["running_variable","outcome"],"difference_in_differences":["treated","post","outcome"],"synthetic_control":["treated_pre","donor_pre","treated_post","donor_post"],"matching_methods":["treated","outcome","covariates"],"propensity_score_matching":["treated","outcome","covariates"],"coarsened_exact_matching":["treated","outcome","covariates"],"genetic_matching":["treated","outcome","covariates"],"entropy_balancing":["treated","outcome","covariate"],"inverse_probability_weighting":["treated","outcome","propensity_score"],"doubly_robust_estimation":["treated","outcome","propensity_score","outcome_model_treated","outcome_model_control"],"targeted_maximum_likelihood":["treated","outcome","propensity_score","initial_q1","initial_q0"],"machine_learning_causal_inference":["treated","outcome","features"],"causal_forests":["treated","outcome","feature"],"double_machine_learning":["treatment","outcome","feature"],"orthogonalized_estimation":["treatment","outcome","feature"],"cross_fitting":["ids","predictions","targets"],"sample_splitting":["ids"],"post_selection_inference":["estimates","standard_errors","selected_indices"],"selective_inference":["estimate","standard_error","selection_threshold"],"simultaneous_inference":["estimates","standard_errors"],"false_discovery_rate_control":["p_values"],"family_wise_error_rate":["p_values"],"bonferroni_correction":["p_values"],"holm_bonferroni":["p_values"],"benjamini_hochberg":["p_values"],"storeys_method":["p_values"],"local_fdr":["z_scores"],"permutation_based_fdr":["observed_statistics","permuted_statistics"],"knockoffs":["original_importance","knockoff_importance"],"stability_selection":["selections","feature_count"],"bootstrap_aggregation":["values"],"random_forests":["features","targets"],"gradient_boosting":["features","targets"],"xgboost":["features","targets"],"lightgbm":["features","targets"],"catboost":["features","targets"],"adaboost":["features","labels"],"stacking":["base_predictions","targets"],"blending":["base_predictions","targets"],"bagging":["features","targets"],"pasting":["features","targets"],"voting_classifiers":["predictions"],"weighted_voting":["predictions","weights"],"bayesian_model_averaging":["model_predictions","log_evidence"],"bayesian_model_selection":["model_names","log_evidence"],"information_criteria":["models","sample_size"],"cross_validation":["fold_predictions","fold_targets"],"leave_one_out":["predictions","targets"],"k_fold_cross_validation":["fold_ids","predictions","targets"]}
METHOD_SUMMARIES.update(finance.SUMMARIES)
METHOD_INPUTS.update(finance.INPUTS)
METHOD_SUMMARIES.update(climate_environment.SUMMARIES)
METHOD_INPUTS.update(climate_environment.INPUTS)
METHOD_SUMMARIES.update(ai_systems.SUMMARIES)
METHOD_INPUTS.update(ai_systems.INPUTS)
def _analysis_methods(self):
    return [AnalysisMethodInfo(method=m,feature_row=analysis.ROWS[m],summary=METHOD_SUMMARIES[m],required_inputs=METHOD_INPUTS[m],limits=[]) for m in analysis.ROWS]
def _run_analysis(self,data:AnalysisJobIn):
    if data.method not in analysis.ROWS:raise ValueError(f"unsupported analysis method {data.method}")
    started=_utcnow()
    try:
        result=analysis.run(data.method,data.data,data.params,data.seed)
        job=AnalysisJobOut(id=str(uuid4()),method=data.method,feature_row=analysis.ROWS[data.method],data=data.data,params=data.params,seed=data.seed,status="completed",output=result["output"],error=None,created_at=started,completed_at=_utcnow())
    except ValueError as e:
        job=AnalysisJobOut(id=str(uuid4()),method=data.method,feature_row=analysis.ROWS[data.method],data=data.data,params=data.params,seed=data.seed,status="failed",output=None,error=str(e),created_at=started,completed_at=_utcnow())
    return self.repository.save_analysis_job(job)
def _get_analysis_job(self,job_id):
    j=self.repository.get_analysis_job(job_id)
    if not j:raise LookupError(job_id)
    return j
def _list_analysis_jobs(self,method=None):return self.repository.list_analysis_jobs(method)
Service.analysis_methods=_analysis_methods;Service.run_analysis=_run_analysis;Service.get_analysis_job=_get_analysis_job;Service.list_analysis_jobs=_list_analysis_jobs
