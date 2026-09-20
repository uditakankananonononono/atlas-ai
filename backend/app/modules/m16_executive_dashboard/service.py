from __future__ import annotations
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from .blockers import detect_blockers
from .kpis import EVENT_KPIS,RESERVED_KPI_IDS,compute_kpis,custom_event_kpi,event_ref,kpi_event_evidence
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
        return {"projected_events":projected,"last_sequence":self.repository.snapshot().last_sequence,"recorded_points":len(kpis) if recorder else 0,"at":now.isoformat()}
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
