import React from "react";
import type {RerunScheduleCard as Card} from "./api";
// Read-only M04 scheduled re-run card. Approvals are decided in the approval queue; nothing here files or runs.
const stateLabel:Record<string,string>={pending:"awaiting approval",approved_not_executed:"approved, not run",executed:"run",denied:"denied",expired:"expired"};
export default function RerunScheduleCard({card}:{card:Card|null}){
  if(!card)return null;
  if(!card.available)return <section aria-label="Scheduled re-runs" className="rounded-xl bg-slate-900 p-4"><h2 className="text-lg font-semibold">Scheduled re-runs</h2><p className="mt-1 text-sm text-slate-500">{card.reason??"Unavailable"}</p></section>;
  const verdicts=Object.entries(card.verdicts);
  return <section aria-label="Scheduled re-runs" className="rounded-xl bg-slate-900 p-4">
    <div className="flex items-baseline justify-between"><h2 className="text-lg font-semibold">Scheduled re-runs</h2><span className="text-xs text-slate-500">as of {new Date(card.as_of).toLocaleString()}</span></div>
    <dl className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
      <div><dt className="text-xs text-slate-400">Active schedules</dt><dd className="text-xl font-semibold">{card.schedules_active}<span className="text-sm text-slate-500"> / {card.schedules_total}</span></dd></div>
      <div><dt className="text-xs text-slate-400">Due now</dt><dd className="text-xl font-semibold">{card.schedules_due_now}</dd></div>
      <div><dt className="text-xs text-slate-400">Awaiting approval</dt><dd className="text-xl font-semibold">{card.awaiting_approval}</dd></div>
      <div><dt className="text-xs text-slate-400">Overdue</dt><dd className={`text-xl font-semibold ${card.overdue_total>0?"text-amber-300":""}`}>{card.overdue_total}</dd></div>
    </dl>
    <p className="mt-2 text-xs text-slate-400">Approved, not run: {card.approved_not_executed} · Proposals: {card.proposals_total}{verdicts.length>0&&<> · Verdicts: {verdicts.map(([v,n])=>`${n} ${v}`).join(", ")}</>}</p>
    {card.overdue.length>0&&<><h3 className="mt-3 text-sm font-semibold text-amber-300">Overdue proposals</h3><ul className="mt-1 space-y-1 text-sm">{card.overdue.map(r=><li key={r.rerun_approval_id} className="flex justify-between rounded bg-slate-950 p-2"><span>Re-run of {r.original_approval_id}</span><span className="text-xs text-slate-400">{stateLabel[r.state]??r.state} · {r.age_hours}h</span></li>)}</ul></>}
    {card.schedules_total===0&&<p className="mt-2 text-sm text-slate-500">No re-run schedules yet.</p>}
  </section>;
}
