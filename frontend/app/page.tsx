"use client";
import {useEffect,useState} from "react";
import ExecutiveDashboard from "../components/ExecutiveDashboard";
import KnowledgeWorkspace from "../components/KnowledgeWorkspace";
import PlanningBoard from "../components/PlanningBoard";
import AnalysisPanel from "../components/AnalysisPanel";
type Module={id:number;name:string;status:string};
type View="dashboard"|"planning"|"analysis"|"knowledge"|"modules";
export default function Home(){
 const [modules,setModules]=useState<Module[]>([]),[view,setView]=useState<View>("dashboard"),[seed,setSeed]=useState("");
 useEffect(()=>{fetch("/api/v1/modules").then(x=>x.ok?x.json():Promise.reject(x)).then(setModules).catch(()=>setModules([]))},[]);
 return <main className="min-h-screen bg-slate-950 p-6 text-white"><header className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-cyan-400">ATLAS AI</p><h1 className="text-3xl font-semibold">Human-controlled operations</h1></div><nav className="flex flex-wrap gap-2">{(["dashboard","planning","analysis","knowledge","modules"] as View[]).map(x=><button key={x} aria-pressed={view===x} onClick={()=>setView(x)} className={`rounded border px-3 py-2 capitalize ${view===x?"border-cyan-400 bg-slate-800":"border-slate-700"}`}>{x}</button>)}</nav></header><section className="mt-8">
 {view==="dashboard"&&<ExecutiveDashboard/>}
 {view==="planning"&&<PlanningBoard/>}
 {view==="analysis"&&<AnalysisPanel/>}
 {view==="knowledge"&&<><label className="mb-3 block text-sm">Knowledge node ID <input value={seed} onChange={e=>setSeed(e.target.value)} className="ml-2 rounded bg-slate-800 p-2" placeholder="Select or paste an ID"/></label>{seed?<KnowledgeWorkspace seedId={seed}/>:<p className="rounded bg-slate-900 p-4 text-slate-400">Enter a node ID to open its cited neighborhood.</p>}</>}
 {view==="modules"&&<div className="grid gap-3 md:grid-cols-4">{modules.map(m=><article key={m.id} className="rounded-xl border border-slate-700 bg-slate-900 p-4"><b>{m.id}. {m.name}</b><p className="text-sm text-emerald-400">{m.status}</p></article>)}</div>}
 </section></main>
}
