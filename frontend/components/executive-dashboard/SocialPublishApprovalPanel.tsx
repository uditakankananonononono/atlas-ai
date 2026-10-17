import React from "react";
import type {ApprovalCenterRequest} from "./api";
import {parsePublishSnapshot} from "./social-publish-snapshot";
// Review card for one M06 social post waiting in the M00 approval center.
// Shows the exact platform, account ID, content and publish time recorded in the request's publish snapshot,
// and only enables Approve when that snapshot is complete and agrees with the request. Nothing is inferred or
// filled in: an unknown or legacy destination is stated as unknown and cannot be approved from here.
// Deny is always available. Approving records the M00 decision; M06 publishes in its own gated step.
// unknown: a decision call failed and the request's real status could not be re-read, so it may already be decided.
export type SocialPublishApprovalState={request:ApprovalCenterRequest;error:string|null;unknown?:boolean};
const when=(iso:string)=>{const d=new Date(iso);return Number.isFinite(d.getTime())?`${d.toLocaleString()} (${d.toISOString()})`:iso};
export default function SocialPublishApprovalPanel({state,onDecide,onClose,busy,onRecheck}:{state:SocialPublishApprovalState|null;onDecide:(decision:"approved"|"denied")=>void;onClose:()=>void;busy:boolean;onRecheck?:()=>void}){
  if(!state)return null;
  const r=state.request;const parsed=parsePublishSnapshot(r.payload as Record<string,unknown>);const unknown=state.unknown===true;const pending=r.status==="pending"&&!unknown;
  return <aside role="dialog" aria-label="Social publish approval" className="fixed inset-y-0 right-0 z-20 w-full max-w-md overflow-y-auto break-words border-l border-slate-700 bg-slate-950 p-5">
    <div className="flex items-start justify-between gap-2"><div><p className="text-xs uppercase text-cyan-400">approval center · social post</p><h3 className="text-lg font-semibold">Review exact destination</h3></div><button onClick={onClose} className="shrink-0 rounded bg-slate-800 px-2 py-1 text-sm">Close</button></div>
    {state.error&&<p role="alert" className="mt-3 rounded bg-red-950 p-2 text-sm text-red-300">{state.error}</p>}
    {parsed.ok?<>
      <dl className="mt-3 space-y-1 text-sm">
        <div><dt className="inline text-slate-400">Platform </dt><dd className="inline">{parsed.snapshot.platform}</dd></div>
        <div><dt className="inline text-slate-400">Account ID </dt><dd className="inline break-all font-mono" data-testid="account-id">{parsed.snapshot.accountId}</dd></div>
        <div><dt className="inline text-slate-400">Publishes </dt><dd className="inline">{when(parsed.snapshot.publishAt)}</dd></div>
        <div><dt className="inline text-slate-400">Sponsored </dt><dd className="inline">{parsed.snapshot.sponsored?"yes":"no"}</dd></div>
        {parsed.snapshot.format&&<div><dt className="inline text-slate-400">Format </dt><dd className="inline">{parsed.snapshot.format}</dd></div>}
        {parsed.snapshot.link&&<div><dt className="inline text-slate-400">Link </dt><dd className="inline break-all">{parsed.snapshot.link}</dd></div>}
        <div><dt className="inline text-slate-400">Status </dt><dd className="inline uppercase">{unknown?"unknown (last seen "+r.status+")":r.status}</dd></div>
        <div><dt className="inline text-slate-400">Filed </dt><dd className="inline">{when(r.created_at)}</dd></div>
      </dl>
      <h4 className="mt-3 text-sm font-semibold">Content</h4>
      <pre aria-label="Post content" className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-900 p-2 text-xs text-slate-300">{parsed.snapshot.text}</pre>
      {parsed.snapshot.threadChunks.length>0&&<section aria-label="Thread parts" className="mt-2"><h4 className="text-sm font-semibold">Thread parts ({parsed.snapshot.threadChunks.length})</h4><ol className="mt-1 list-inside list-decimal space-y-1 text-xs text-slate-300">{parsed.snapshot.threadChunks.map((c,i)=><li key={i} className="whitespace-pre-wrap break-words rounded bg-slate-900 p-2">{c}</li>)}</ol></section>}
      <section aria-label="Media" className="mt-2"><h4 className="text-sm font-semibold">Media ({parsed.snapshot.mediaUrls.length})</h4>{parsed.snapshot.mediaUrls.length===0?<p className="mt-1 text-xs text-slate-500">No media attached.</p>:<ul className="mt-1 space-y-1 text-xs text-slate-300">{parsed.snapshot.mediaUrls.map((u,i)=><li key={i} className="break-all rounded bg-slate-900 p-2">{u}{parsed.snapshot.altTexts[i]?<span className="block text-slate-500">Alt: {parsed.snapshot.altTexts[i]}</span>:null}</li>)}</ul>}</section>
    </>:<div role="alert" className="mt-3 rounded border border-amber-500 bg-amber-950 p-3 text-sm text-amber-200">
      <p className="font-semibold">Destination not verified. Approve is disabled.</p>
      <ul className="mt-1 list-inside list-disc text-xs">{parsed.problems.map((p,i)=><li key={i}>{p}</li>)}</ul>
      <p className="mt-2 text-xs text-amber-300">Deny it and re-file the post so its exact account is recorded.</p></div>}
    {pending?<div className="mt-4"><p className="text-xs text-slate-400">{parsed.ok?"Approving records your decision for exactly this account, content and time. The post goes out only in M06's separate publish step.":"You can still deny this request."}</p>
      <div className="mt-2 flex gap-2"><button disabled={busy||!parsed.ok} onClick={()=>onDecide("approved")} className="rounded bg-emerald-500 px-3 py-1 text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">Approve</button><button disabled={busy} onClick={()=>onDecide("denied")} className="rounded bg-slate-700 px-3 py-1">Deny</button></div></div>
      :unknown?null:<p className="mt-4 text-sm text-slate-400">No decision needed.</p>}
    {unknown&&<div role="alert" className="mt-4 rounded border border-amber-500 bg-amber-950 p-3 text-sm text-amber-200"><p className="font-semibold">Status unknown. Decision controls are off.</p><p className="mt-1 text-xs">The decision call failed and the request's current status could not be read back, so it may already be decided. Check the status before doing anything else.</p>
      <button disabled={busy||!onRecheck} onClick={onRecheck} className="mt-2 rounded bg-amber-500 px-3 py-1 text-slate-950 disabled:opacity-40">Check status</button></div>}
  </aside>;
}
