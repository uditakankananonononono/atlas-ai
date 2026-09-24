import {authFetch} from "../../lib/supabase";
// Typed client for the Module 16 executive dashboard API.
export type ApprovalState="pending"|"approved"|"rejected"|"expired";
export type Approval={id:string;module_id:number;action_type:string;title:string;summary:string;risk:string;evidence:Record<string,unknown>;proposed_payload:Record<string,unknown>;state:ApprovalState;created_at:string;expires_at:string|null;reviewed_at:string|null};
export type Event={id:string;sequence:number;topic:string;aggregate_type:string;aggregate_id:string;payload:Record<string,unknown>;occurred_at:string};
export type EvidenceRef={kind:string;id:string;summary:string;sequence:number|null};
export type KPI={id:string;label:string;unit:string;value:number;previous_value:number|null;window_hours:number;definition:string;evidence:EvidenceRef[];evidence_total:number};
export type AgentStatus={module_id:number;agent_id:string;state:"running"|"idle"|"stalled"|"offline";current_task:string|null;detail:Record<string,unknown>;last_heartbeat:string};
export type ModuleStatus={module_id:number;slug:string;name:string;implemented:boolean;agent:AgentStatus|null;pending_approvals:number;events_24h:number;open_blockers:number};
export type Blocker={id:string;kind:string;severity:"critical"|"warning"|"info";summary:string;module_id:number|null;evidence:EvidenceRef[];recommended_action:string;detected_at:string};
export type DrilldownResult={subject:EvidenceRef;detail:Record<string,unknown>;events:Event[];approvals:Approval[]};
export type Digest={generated_at:string;pending_approvals:number;open_blockers:number;sections:{title:string;lines:string[]}[]};
export type Snapshot={version:number;last_sequence:number;generated_at:string;data:{metrics?:Record<string,number>;timeline?:Array<Record<string,unknown>>;alerts?:AlertEntry[];freshness?:Record<string,string>}};
export type AlertEntry={event_id:string;sequence:number;occurred_at:string;severity:string;message:string;module_id:number|null};
export type WidgetConfig={id:string;kind:"kpi_card"|"module_status"|"blockers"|"timeline"|"approvals"|"alerts"|"digest"|"rerun_schedules";kpi_id:string|null;visible:boolean;position:number};
export type RerunProposalRow={schedule_id:string;original_approval_id:string;rerun_approval_id:string;state:string;filed_at:string;age_hours:number;overdue:boolean;verdict:string|null;approval_path:string};
export type RerunScheduleCard={available:boolean;reason:string|null;as_of:string;schedules_total:number;schedules_active:number;schedules_due_now:number;proposals_total:number;by_state:Record<string,number>;awaiting_approval:number;approved_not_executed:number;overdue_total:number;verdicts:Record<string,number>;overdue:RerunProposalRow[];recent:RerunProposalRow[]};
export type ApprovalCenterRequest={id:string;module_id:number;action_type:string;payload:Record<string,unknown>;user_id:string;status:"pending"|"approved"|"denied"|"expired"|"consumed"|string;created_at:string;expires_at:string|null;decided_at:string|null;approved_by:string|null};
export type ApprovalCenterEvent={event:string;actor:string|null;at:string};
export type DashboardView={widgets:WidgetConfig[];updated_at:string};
export type CommandPreview={id:string;utterance:string;intent:string;parameters:Record<string,unknown>;plan:Array<Record<string,unknown>>;read_only:boolean;confidence:number;expires_at:string;created_at:string};
export type BulkDecisionResult={decided:Approval[];skipped:{id:string;reason:string}[]};
async function req<T>(base:string,path:string,init?:RequestInit):Promise<T>{
  const r=await authFetch(`${base}${path}`,init);
  if(!r.ok)throw new Error(`${init?.method??"GET"} ${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}
const json=(body:unknown):RequestInit=>({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
export const dashboardApi=(base:string="/api/v1")=>{
  const p=`/executive-dashboard`;
  return {
    overview:()=>req<{generated_at:string;modules:ModuleStatus[];kpis:KPI[];blockers:Blocker[];pending_approvals:number;critical_path:string[]}>(base,`${p}/overview`),
    snapshot:()=>req<Snapshot>(base,`${p}/snapshot`),
    kpis:()=>req<KPI[]>(base,`${p}/kpis`),
    kpiEvidence:(id:string)=>req<DrilldownResult>(base,`${p}/kpis/${encodeURIComponent(id)}/evidence`),
    modules:()=>req<ModuleStatus[]>(base,`${p}/modules`),
    blockers:()=>req<Blocker[]>(base,`${p}/blockers`),
    digest:()=>req<Digest>(base,`${p}/digest`),
    approvals:()=>req<Approval[]>(base,`${p}/approvals`),
    decide:(id:string,approve:boolean,note?:string)=>req<Approval>(base,`${p}/approvals/${encodeURIComponent(id)}/decision`,json({approve,note:note??null})),
    bulkDecide:(ids:string[],approve:boolean,note?:string)=>req<BulkDecisionResult>(base,`${p}/approvals/bulk-decision`,json({approval_ids:ids,approve,note:note??null})),
    sweep:()=>req<Approval[]>(base,`${p}/approvals/sweep`,{method:"POST"}),
    drilldown:(kind:string,id:string)=>req<DrilldownResult>(base,`${p}/drilldown/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`),
    preview:(utterance:string)=>req<CommandPreview>(base,`${p}/commands/preview`,json({utterance})),
    execute:(previewId:string)=>req<{status:string;result?:unknown;approval_id?:string}>(base,`${p}/commands/${encodeURIComponent(previewId)}/execute`,{method:"POST"}),
    project:()=>req<{projected_events:number;last_sequence:number;recorded_points:number;alerts_fired:number;at:string}>(base,`${p}/project`,{method:"POST"}),
    rerunSchedules:()=>req<RerunScheduleCard>(base,`${p}/rerun-schedules`),
    // M00 approval center: re-run proposals wait here, not in the M16 queue. approval_path comes from the card row.
    approvalRequest:(path:string)=>req<ApprovalCenterRequest>(base,path),
    approvalAudit:(path:string)=>req<ApprovalCenterEvent[]>(base,`${path}/audit`),
    decideApprovalRequest:(path:string,decision:"approved"|"denied")=>req<ApprovalCenterRequest>(base,`${path}/decision`,json({decision,decided_by:"executive-dashboard"})),
    getView:()=>req<DashboardView>(base,`${p}/view`),
    saveView:(widgets:WidgetConfig[])=>req<DashboardView>(base,`${p}/view`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({widgets})}),
    liveUrl:`${base}${p}/live`,
  };
};
