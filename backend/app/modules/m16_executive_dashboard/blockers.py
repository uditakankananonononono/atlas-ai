"""Blocker detection.

Every blocker is derived from rows stored by this module (approvals, agent
heartbeats, timeline snapshot) or from the shared module catalog, and
carries the evidence rows behind it plus a concrete recommended action.
Nothing here guesses at other modules' internals.
"""
from __future__ import annotations
from datetime import datetime,timedelta
from .kpis import agent_ref,approval_ref,timeline_ref
from .schemas import AgentState,AgentStatus,Approval,Blocker,BlockerSeverity,TimelineItem
from .status import ModuleInfo,effective_state
from .timeline import find_cycle,mark_critical_and_risk
EXPIRING_WITHIN=timedelta(hours=1)
def detect_blockers(pending_approvals:list[Approval],agents:list[AgentStatus],timeline:list[TimelineItem],modules:list[ModuleInfo],now:datetime,expiring_within:timedelta=EXPIRING_WITHIN)->list[Blocker]:
    out=[]
    for a in pending_approvals:
        if a.expires_at and a.expires_at<now:
            out.append(Blocker(id=f"approval-expired:{a.id}",kind="approval_expired_pending",severity=BlockerSeverity.CRITICAL,summary=f"Approval '{a.title}' (module {a.module_id}) expired while still pending.",module_id=a.module_id,evidence=[approval_ref(a)],recommended_action="Mark the approval expired and re-issue it if the action is still wanted; the underlying worker stays blocked until then.",detected_at=now))
        elif a.expires_at and a.expires_at-now<=expiring_within:
            out.append(Blocker(id=f"approval-expiring:{a.id}",kind="approval_expiring_soon",severity=BlockerSeverity.WARNING,summary=f"Approval '{a.title}' (module {a.module_id}) expires at {a.expires_at.isoformat()}.",module_id=a.module_id,evidence=[approval_ref(a)],recommended_action="Review the approval before expiry; after expiry the gated action is cancelled.",detected_at=now))
    for agent in agents:
        state=effective_state(agent,now)
        if state==AgentState.OFFLINE:
            out.append(Blocker(id=f"agent-offline:{agent.agent_id}",kind="agent_offline",severity=BlockerSeverity.CRITICAL,summary=f"Agent '{agent.agent_id}' (module {agent.module_id}) has not heartbeated since {agent.last_heartbeat.isoformat()}.",module_id=agent.module_id,evidence=[agent_ref(agent)],recommended_action="Check the worker process and its queue; restart or reassign its current task.",detected_at=now))
        elif state==AgentState.STALLED:
            out.append(Blocker(id=f"agent-stalled:{agent.agent_id}",kind="agent_stalled",severity=BlockerSeverity.WARNING,summary=f"Agent '{agent.agent_id}' (module {agent.module_id}) is declared running but its heartbeat is stale.",module_id=agent.module_id,evidence=[agent_ref(agent)],recommended_action="Inspect the agent's current task; a stale heartbeat on a running agent usually means a hung step.",detected_at=now))
    cycle=find_cycle(timeline)
    if cycle:
        refs=[timeline_ref(i) for i in timeline if i.id in cycle]
        out.append(Blocker(id="timeline-cycle",kind="timeline_dependency_cycle",severity=BlockerSeverity.CRITICAL,summary=f"Timeline dependency cycle: {' -> '.join(cycle)}.",evidence=refs,recommended_action="Break the cycle by removing or retargeting one of these dependencies; the Gantt critical path cannot be computed until then.",detected_at=now))
    else:
        for item in mark_critical_and_risk(timeline,now):
            if item.critical and item.at_risk:
                out.append(Blocker(id=f"timeline-overdue:{item.id}",kind="critical_path_item_overdue",severity=BlockerSeverity.WARNING,summary=f"Critical-path item '{item.title}' ended {item.end.isoformat()} at {int(item.progress*100)}% progress.",module_id=item.module_id,evidence=[timeline_ref(item)],recommended_action="Re-plan the item or its dependents; every downstream critical item slips with it.",detected_at=now))
    for m in modules:
        if not m.implemented:
            out.append(Blocker(id=f"module-not-implemented:{m.id}",kind="module_not_implemented",severity=BlockerSeverity.INFO,summary=f"Module {m.id} ({m.name}) is in the catalog but not implemented.",module_id=m.id,evidence=[],recommended_action="Route work through the build pipeline or hide the module card until it ships.",detected_at=now))
    order={BlockerSeverity.CRITICAL:0,BlockerSeverity.WARNING:1,BlockerSeverity.INFO:2}
    return sorted(out,key=lambda b:order[b.severity])
