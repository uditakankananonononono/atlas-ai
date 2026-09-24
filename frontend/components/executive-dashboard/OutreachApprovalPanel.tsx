import React from "react";
import type {ApprovalCenterRequest,CadenceDecision,ContactTimeline} from "./api";
// Review card for one M05 outreach send waiting in the M00 approval center.
// Shows every earlier message Atlas drafted or sent to this person (across campaigns and duplicate contact
// records) plus the cadence decision, so the reviewer decides with the full history in view.
// Read-only apart from Approve/Deny, which record the M00 decision; M05 mirrors it and sending stays a separate step.
export type OutreachApprovalState={request:ApprovalCenterRequest;timeline:ContactTimeline|null;timelineError:string|null;liveCadence:CadenceDecision|null;error:string|null};
export const OUTREACH_MODULE_ID=5;
const str=(v:unknown)=>typeof v==="string"?v:"";
const when=(iso:string|null|undefined)=>iso?new Date(iso).toLocaleString():"";
function Cadence({label,decision}:{label:string;decision:CadenceDecision|null|undefined}){
  if(!decision)return null;
  return <div className="mt-2 rounded bg-slate-900 p-2 text-sm"><p><span className="text-slate-400">{label} </span><span className={decision.allowed?"text-emerald-400":"text-red-400"}>{decision.allowed?"allowed":"blocked"}</span>{decision.policy_version!==undefined&&<span className="text-xs text-slate-500"> · policy v{decision.policy_version}</span>}</p>
    {decision.reasons?.length>0&&<ul className="mt-1 list-inside list-disc text-xs text-slate-300">{decision.reasons.map((r,i)=><li key={i}>{r.code}{r.detail?`: ${r.detail}`:""}</li>)}</ul>}
    {!decision.allowed&&decision.next_allowed_at&&<p className="mt-1 text-xs text-slate-400">Next allowed {when(decision.next_allowed_at)}</p>}</div>;
}
export default function OutreachApprovalPanel({state,onDecide,onClose,busy}:{state:OutreachApprovalState|null;onDecide:(decision:"approved"|"denied")=>void;onClose:()=>void;busy:boolean}){
  if(!state)return null;
  const r=state.request;const p=r.payload as Record<string,unknown>;const messageId=str(p.message_id);
  const history=state.timeline?.messages??[];const prior=history.filter(m=>m.message_id!==messageId);
  return <aside role="dialog" aria-label="Outreach approval" className="fixed inset-y-0 right-0 z-20 w-full max-w-md overflow-y-auto border-l border-slate-700 bg-slate-950 p-5">
    <div className="flex items-start justify-between"><div><p className="text-xs uppercase text-cyan-400">approval center · outreach</p><h3 className="text-lg font-semibold">{str(p.subject)||r.action_type}</h3></div><button onClick={onClose} className="rounded bg-slate-800 px-2 py-1 text-sm">Close</button></div>
    {state.error&&<p className="mt-3 rounded bg-red-950 p-2 text-sm text-red-300">{state.error}</p>}
    <dl className="mt-3 space-y-1 text-sm"><div><dt className="inline text-slate-400">To </dt><dd className="inline">{str(p.recipient)}</dd></div>
      <div><dt className="inline text-slate-400">Action </dt><dd className="inline">{r.action_type}</dd></div>
      <div><dt className="inline text-slate-400">Status </dt><dd className="inline uppercase">{r.status}</dd></div>
      <div><dt className="inline text-slate-400">Filed </dt><dd className="inline">{when(r.created_at)}</dd></div></dl>
    {str(p.body)&&<pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-900 p-2 text-xs text-slate-300">{str(p.body)}</pre>}
    <Cadence label="Cadence when filed:" decision={p.cadence as CadenceDecision|undefined}/>
    <Cadence label="Cadence now:" decision={state.liveCadence}/>
    <section aria-label="Contact timeline" className="mt-4"><h4 className="text-sm font-semibold">Earlier messages to this person ({state.timeline?prior.length:"…"})</h4>
      {state.timelineError&&<p className="mt-1 rounded bg-amber-950 p-2 text-xs text-amber-200">Could not load this person's history: {state.timelineError}. Check M05 before approving.</p>}
      {!state.timeline&&!state.timelineError&&<p className="mt-1 text-sm text-slate-500">Loading history...</p>}
      {state.timeline&&<>
        <p className="mt-1 text-xs text-slate-500">{state.timeline.person} · {state.timeline.relationship} (min gap {state.timeline.rule.min_gap_days}d, max {state.timeline.rule.max_per_30_days}/30d){state.timeline.contact_records.length>1?` · ${state.timeline.contact_records.length} contact records`:""}</p>
        {prior.length===0?<p className="mt-1 text-sm text-slate-400">No earlier messages. This would be the first contact.</p>
          :<ol className="mt-1 space-y-1 text-sm">{prior.map(m=><li key={m.message_id} className="rounded bg-slate-900 p-2"><div className="flex justify-between gap-2"><span>{m.subject}</span><span className="text-xs uppercase text-slate-400">{m.status}</span></div><p className="text-xs text-slate-500">{m.campaign??m.campaign_id} · {m.kind}{m.sequence>0?` #${m.sequence}`:""} · {m.sent_at?`sent ${when(m.sent_at)}`:`updated ${when(m.updated_at)}`}</p></li>)}</ol>}
      </>}
    </section>
    {r.status==="pending"?<div className="mt-4"><p className="text-xs text-slate-400">Approving records your decision. The email goes out only when it is sent from M05.</p><div className="mt-2 flex gap-2"><button disabled={busy} onClick={()=>onDecide("approved")} className="rounded bg-emerald-500 px-3 py-1 text-slate-950">Approve</button><button disabled={busy} onClick={()=>onDecide("denied")} className="rounded bg-slate-700 px-3 py-1">Deny</button></div></div>
      :<p className="mt-4 text-sm text-slate-400">No decision needed.</p>}
  </aside>;
}
