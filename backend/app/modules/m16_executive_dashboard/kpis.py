"""KPI computation for the executive dashboard.

Every KPI is computed from rows this module has actually stored (events,
approvals, agent heartbeats, timeline snapshot) and carries references to
the underlying rows, so each card on the dashboard can be drilled into its
evidence. Counts are never synthesized: with no matching rows a KPI is an
honest zero with empty evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from .schemas import AgentState,AgentStatus,Approval,Event,EvidenceRef,KPI,TimelineItem
from .timeline import overdue_items
EVIDENCE_SAMPLE_LIMIT=25
RESERVED_KPI_IDS=frozenset({"approvals_pending","approval_decisions","avg_approval_turnaround_hours","agents_stalled","timeline_items_at_risk"})
@dataclass(frozen=True)
class KPIDefinition:
    id:str;label:str;unit:str;definition:str;topics:frozenset[str]|None=None  # None matches every event
EVENT_KPIS:tuple[KPIDefinition,...]=(
    KPIDefinition("opportunities_discovered","Opportunities discovered","count","Events with topic opportunity.discovered inside the window.",frozenset({"opportunity.discovered"})),
    KPIDefinition("applications_submitted","Applications submitted","count","Events with topic application.submitted inside the window.",frozenset({"application.submitted"})),
    KPIDefinition("grants_won","Grants won","count","Events with topic grant.won inside the window.",frozenset({"grant.won"})),
    KPIDefinition("tasks_completed","Tasks completed","count","Events with topic task.completed inside the window.",frozenset({"task.completed"})),
    KPIDefinition("events_total","Dashboard events","count","All dashboard events inside the window.",None),
)
def event_ref(e:Event)->EvidenceRef:
    return EvidenceRef(kind="event",id=e.id,summary=f"{e.topic} on {e.aggregate_type}/{e.aggregate_id}",sequence=e.sequence)
def approval_ref(a:Approval)->EvidenceRef:
    return EvidenceRef(kind="approval",id=a.id,summary=f"{a.title} ({a.state.value})")
def agent_ref(a:AgentStatus)->EvidenceRef:
    return EvidenceRef(kind="agent",id=a.agent_id,summary=f"module {a.module_id} agent {a.state.value}")
def timeline_ref(i:TimelineItem)->EvidenceRef:
    return EvidenceRef(kind="timeline_item",id=i.id,summary=i.title)
def _sample(refs:list[EvidenceRef])->tuple[list[EvidenceRef],int]:
    return refs[:EVIDENCE_SAMPLE_LIMIT],len(refs)
def _event_kpi(defn:KPIDefinition,window:list[Event],previous:list[Event],window_hours:int)->KPI:
    match=[e for e in window if defn.topics is None or e.topic in defn.topics]
    prev=[e for e in previous if defn.topics is None or e.topic in defn.topics]
    refs,total=_sample([event_ref(e) for e in match])
    return KPI(id=defn.id,label=defn.label,unit=defn.unit,value=len(match),previous_value=float(len(prev)),window_hours=window_hours,definition=defn.definition,evidence=refs,evidence_total=total)
def compute_kpis(window_events:list[Event],previous_events:list[Event],pending_approvals:list[Approval],reviewed_approvals:list[Approval],agents:list[AgentStatus],timeline:list[TimelineItem],now:datetime,window_hours:int=24)->list[KPI]:
    out=[_event_kpi(d,window_events,previous_events,window_hours) for d in EVENT_KPIS]
    refs,total=_sample([approval_ref(a) for a in pending_approvals])
    out.append(KPI(id="approvals_pending",label="Approvals pending",value=len(pending_approvals),window_hours=window_hours,definition="Approval requests still awaiting a decision right now (gauge, no trend).",evidence=refs,evidence_total=total))
    refs,total=_sample([approval_ref(a) for a in reviewed_approvals])
    out.append(KPI(id="approval_decisions",label="Approval decisions",value=len(reviewed_approvals),window_hours=window_hours,definition="Approvals decided (approved or rejected) inside the window.",evidence=refs,evidence_total=total))
    durations=[(a.reviewed_at-a.created_at).total_seconds()/3600 for a in reviewed_approvals if a.reviewed_at and a.reviewed_at>=a.created_at]
    refs,total=_sample([approval_ref(a) for a in reviewed_approvals if a.reviewed_at and a.reviewed_at>=a.created_at])
    out.append(KPI(id="avg_approval_turnaround_hours",label="Avg approval turnaround",unit="hours",value=round(sum(durations)/len(durations),2) if durations else 0.0,window_hours=window_hours,definition="Mean hours from approval request to decision, over approvals decided inside the window.",evidence=refs,evidence_total=total))
    stuck=[a for a in agents if a.state in (AgentState.STALLED,AgentState.OFFLINE)]
    refs,total=_sample([agent_ref(a) for a in stuck])
    out.append(KPI(id="agents_stalled",label="Agents stalled/offline",value=len(stuck),window_hours=window_hours,definition="Agents whose heartbeat is stale (stalled) or missing past the offline threshold.",evidence=refs,evidence_total=total))
    risky=overdue_items(timeline,now)
    refs,total=_sample([timeline_ref(i) for i in risky])
    out.append(KPI(id="timeline_items_at_risk",label="Timeline items at risk",value=len(risky),window_hours=window_hours,definition="Timeline items past their end date with progress below 100%.",evidence=refs,evidence_total=total))
    return out
def custom_event_kpi(defn,window:list[Event],previous:list[Event],default_window_hours:int)->KPI:
    """Compute one tenant-defined event KPI (topics list, optional window override)."""
    topics=frozenset(defn.topics);hours=defn.window_hours or default_window_hours
    internal=KPIDefinition(defn.id,defn.label,defn.unit,f"Events with topic in {sorted(topics)} inside the window.",topics)
    return _event_kpi(internal,window,previous,hours)
def kpi_event_evidence(kpi_id:str,window:list[Event],previous:list[Event],window_hours:int)->tuple[list[Event],list[Event]]|None:
    """The exact events behind an event-backed KPI, for drilldown. None if the KPI is not event-backed."""
    for d in EVENT_KPIS:
        if d.id==kpi_id:
            match=lambda e:d.topics is None or e.topic in d.topics
            return [e for e in window if match(e)],[e for e in previous if match(e)]
    return None
