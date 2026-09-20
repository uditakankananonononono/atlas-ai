"use client";
import {useCallback,useEffect,useMemo,useState} from "react";
import {BurndownReport,Experiment,PrioritizedItem,SignificanceReport,Sprint,VelocityReport,WorkItem,planningApi} from "./executive-dashboard/planning-api";
const COLUMNS=["backlog","ready","in_progress","review","done"] as const;
export default function PlanningBoard({apiBase="/api/v1"}:{apiBase?:string}){
  const api=useMemo(()=>planningApi(apiBase),[apiBase]);
  const [items,setItems]=useState<WorkItem[]>([]);const [ranked,setRanked]=useState<PrioritizedItem[]>([]);const [method,setMethod]=useState("rice");
  const [sprints,setSprints]=useState<Sprint[]>([]);const [burndown,setBurndown]=useState<BurndownReport|null>(null);const [velocity,setVelocity]=useState<VelocityReport|null>(null);
  const [experiments,setExperiments]=useState<Experiment[]>([]);const [sig,setSig]=useState<Record<string,SignificanceReport>>({});
  const [wipError,setWipError]=useState<string|null>(null);const [title,setTitle]=useState("");
  const refresh=useCallback(async()=>{
    const [it,sp,v,ex]=await Promise.all([api.items(),api.sprints(),api.velocity(),api.experiments()]);
    setItems(it);setSprints(sp);setVelocity(v);setExperiments(ex);setRanked(await api.prioritization(method));
  },[api,method]);
  useEffect(()=>{refresh().catch(()=>{})},[refresh]);
  async function add(){if(!title.trim())return;await api.createItem({title});setTitle("");refresh()}
  async function move(id:string,column:string){setWipError(null);try{await api.move(id,column);refresh()}catch(e){setWipError(e instanceof Error?e.message:"move failed")}}
  async function showBurndown(id:string){setBurndown(await api.burndown(id))}
  async function showSig(id:string){const r=await api.significance(id);setSig(prev=>({...prev,[id]:r}))}
  const scoreById=useMemo(()=>Object.fromEntries(ranked.map(r=>[r.item.id,r])),[ranked]);
  const maxCommitted=burndown?Math.max(...burndown.series.map(p=>p.total_committed),1):1;
  return <main className="space-y-6 bg-slate-950 p-6 text-white">
    <header className="flex items-center justify-between"><div><p className="text-xs text-cyan-400">MODULE 16 · PLANNING</p><h1 className="text-2xl font-semibold">Planning & Experiments</h1></div><label className="text-sm">Priority: <select value={method} onChange={e=>setMethod(e.target.value)} className="rounded bg-slate-800 p-1"><option value="rice">RICE</option><option value="ice">ICE</option><option value="wsjf">WSJF</option></select></label></header>
    <section><h2 className="text-lg font-semibold">Kanban</h2>
      <div className="mt-2 flex gap-2"><input value={title} onChange={e=>setTitle(e.target.value)} placeholder="New backlog item" className="flex-1 rounded bg-slate-800 p-2 text-sm"/><button onClick={add} className="rounded bg-cyan-500 px-3 text-sm text-slate-950">Add</button></div>
      {wipError&&<p className="mt-1 text-xs text-amber-300">{wipError}</p>}
      <div className="mt-3 grid gap-2 md:grid-cols-5">{COLUMNS.map(col=><div key={col} className="rounded-xl bg-slate-900 p-2"><h3 className="text-xs uppercase text-slate-400">{col.replace("_"," ")} ({items.filter(i=>i.status===col).length})</h3><div className="mt-2 space-y-2">{items.filter(i=>i.status===col).map(i=>{const r=scoreById[i.id];return <article key={i.id} className="rounded bg-slate-800 p-2 text-sm"><p>{i.title}</p><p className="text-xs text-slate-400">{i.estimate!=null?`${i.estimate} pts`:"no estimate"}{r?.score!=null&&<span className="ml-2 text-cyan-300">{method.toUpperCase()} {r.score.toFixed(1)}</span>}{r&&r.score===null&&r.missing_inputs.length>0&&<span className="ml-2 text-amber-300">missing: {r.missing_inputs.join(", ")}</span>}</p><div className="mt-1 flex gap-1">{COLUMNS.filter(c=>c!==col).map(c=><button key={c} onClick={()=>move(i.id,c)} className="rounded bg-slate-700 px-1 text-[10px]">{c.replace("_"," ")}</button>)}</div></article>})}</div></div>)}</div></section>
    <section className="grid gap-4 md:grid-cols-2">
      <div className="rounded-xl bg-slate-900 p-4"><h2 className="text-lg font-semibold">Sprints & burndown</h2>
        <ul className="mt-2 space-y-1 text-sm">{sprints.map(sp=><li key={sp.id} className="flex items-center justify-between rounded bg-slate-800 p-2"><span>{sp.name} <span className="text-xs uppercase text-slate-400">{sp.status}</span></span><button onClick={()=>showBurndown(sp.id)} className="rounded bg-slate-700 px-2 py-1 text-xs">Burndown</button></li>)}</ul>
        {burndown&&<div className="mt-3"><div className="flex items-end gap-1">{burndown.series.map(p=><div key={p.day} className="flex-1" title={`${p.day.slice(0,10)}: actual ${p.actual_remaining}, ideal ${p.ideal_remaining}`}><div className="bg-cyan-500" style={{height:`${(p.actual_remaining/maxCommitted)*80+2}px`}}/><div className="bg-slate-600" style={{height:`${(p.ideal_remaining/maxCommitted)*40+1}px`}}/></div>)}</div><p className="mt-1 text-xs text-slate-500">bars: actual remaining (tall) vs ideal (short)</p><ul className="mt-1 text-xs text-slate-400">{burndown.assumptions.map((a,i)=><li key={i}>- {a}</li>)}</ul></div>}
      </div>
      <div className="rounded-xl bg-slate-900 p-4"><h2 className="text-lg font-semibold">Velocity</h2>
        {velocity&&<><p className="mt-1 text-sm">average completed: <strong>{velocity.average_completed??"no closed sprints"}</strong></p><ul className="mt-2 space-y-1 text-sm text-slate-300">{velocity.sprints.map(s=><li key={s.sprint_id} className="flex justify-between rounded bg-slate-800 p-2"><span>{s.sprint_name}</span><span>{s.completed_points}/{s.committed_points} pts</span></li>)}</ul></>}
      </div>
    </section>
    <section className="rounded-xl bg-slate-900 p-4"><h2 className="text-lg font-semibold">Experiments</h2>
      <div className="mt-2 space-y-2">{experiments.map(e=><article key={e.id} className="rounded bg-slate-800 p-3 text-sm"><div className="flex justify-between"><strong>{e.name}</strong><span className="text-xs uppercase text-slate-400">{e.kind} · {e.status}</span></div><p className="text-xs text-slate-400">metric: {e.metric}{e.hypothesis?` · ${e.hypothesis}`:""}</p>
        <ul className="mt-2 grid gap-1 md:grid-cols-2">{e.variants.map(v=><li key={v.key} className="rounded bg-slate-900 p-2 text-xs">{v.key}: {v.successes}/{v.trials}{v.trials?` (${(100*v.successes/v.trials).toFixed(1)}%)`:""} {Object.keys(v.factors).length>0&&<span className="text-slate-500">{Object.entries(v.factors).map(([k,x])=>`${k}=${x}`).join(" ")}</span>}</li>)}</ul>
        <button onClick={()=>showSig(e.id)} className="mt-2 rounded bg-slate-700 px-2 py-1 text-xs">Significance</button>
        {sig[e.id]&&<div className="mt-2 rounded bg-slate-900 p-2 text-xs"><p className={sig[e.id].significant?"text-emerald-400":"text-slate-300"}>{sig[e.id].test}: p={sig[e.id].p_value===null?"n/a":sig[e.id].p_value!.toExponential(2)} - {sig[e.id].significant?`significant at alpha ${sig[e.id].alpha}`:"not significant"}</p>{sig[e.id].uplift!==null&&<p>uplift {sig[e.id].uplift!.toFixed(4)}{sig[e.id].confidence_interval?` CI [${sig[e.id].confidence_interval![0].toFixed(4)}, ${sig[e.id].confidence_interval![1].toFixed(4)}]`:""}</p>}<ul className="mt-1 text-slate-500">{sig[e.id].assumptions.map((a,i)=><li key={i}>- {a}</li>)}</ul></div>}
      </article>)}{experiments.length===0&&<p className="text-sm text-slate-500">No experiments yet.</p>}</div></section>
  </main>;
}
