import React from "react";
import type {ApprovalCenterEvent,ApprovalCenterRequest} from "./api";
// Detail for one scheduled re-run proposal, read from the M00 approval center.
// Approve/Deny record the human decision only; the re-run itself still has to be executed separately in M04.
export type RerunApprovalState={path:string;request:ApprovalCenterRequest|null;audit:ApprovalCenterEvent[];error:string|null};
export default function RerunApprovalPanel({state,onDecide,onClose,busy}:{state:RerunApprovalState|null;onDecide:(decision:"approved"|"denied")=>void;onClose:()=>void;busy:boolean}){
  if(!state)return null;
  const r=state.request;const reason=r?String((r.payload as Record<string,unknown>).reason??""):"";
  return <aside role="dialog" aria-label="Re-run approval" className="fixed inset-y-0 right-0 z-20 w-full max-w-md overflow-y-auto border-l border-slate-700 bg-slate-950 p-5">
    <div className="flex items-start justify-between"><div><p className="text-xs uppercase text-cyan-400">approval center</p><h3 className="text-lg font-semibold">Scheduled re-run</h3></div><button onClick={onClose} className="rounded bg-slate-800 px-2 py-1 text-sm">Close</button></div>
    {state.error&&<p className="mt-3 rounded bg-red-950 p-2 text-sm text-red-300">{state.error}</p>}
    {!r&&!state.error&&<p className="mt-3 text-sm text-slate-500">Loading approval...</p>}
    {r&&<>
      <dl className="mt-3 space-y-1 text-sm"><div><dt className="inline text-slate-400">Approval </dt><dd className="inline font-mono">{r.id}</dd></div>
        <div><dt className="inline text-slate-400">Status </dt><dd className="inline uppercase">{r.status}</dd></div>
        <div><dt className="inline text-slate-400">Filed </dt><dd className="inline">{new Date(r.created_at).toLocaleString()}</dd></div>
        {r.approved_by&&<div><dt className="inline text-slate-400">Decided by </dt><dd className="inline">{r.approved_by}</dd></div>}
        {reason&&<div><dt className="inline text-slate-400">Reason </dt><dd className="inline">{reason}</dd></div>}</dl>
      {r.status==="pending"?<div className="mt-4"><p className="text-xs text-slate-400">Approving only records your decision. The re-run runs when it is executed from M04.</p><div className="mt-2 flex gap-2"><button disabled={busy} onClick={()=>onDecide("approved")} className="rounded bg-emerald-500 px-3 py-1 text-slate-950">Approve</button><button disabled={busy} onClick={()=>onDecide("denied")} className="rounded bg-slate-700 px-3 py-1">Deny</button></div></div>
        :<p className="mt-4 text-sm text-slate-400">{r.status==="approved"?"Approved; waiting to be executed from M04.":"No decision needed."}</p>}
      <h4 className="mt-4 text-sm font-semibold">Audit ({state.audit.length})</h4>
      <ul className="mt-1 space-y-1 text-sm text-slate-300">{state.audit.map((e,i)=><li key={i} className="rounded bg-slate-900 p-2">{e.event}{e.actor&&<span className="text-slate-500"> by {e.actor}</span>} <span className="text-xs text-slate-500">{new Date(e.at).toLocaleString()}</span></li>)}</ul>
    </>}
  </aside>;
}
