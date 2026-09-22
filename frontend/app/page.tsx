"use client";
import {useEffect,useState} from "react";
import {authFetch,supabase} from "../lib/supabase";
import type {Session} from "@supabase/supabase-js";
import ExecutiveDashboard from "../components/ExecutiveDashboard";
import KnowledgeWorkspace from "../components/KnowledgeWorkspace";
import PlanningBoard from "../components/PlanningBoard";
import AnalysisPanel from "../components/AnalysisPanel";
import ModuleWorkbench from "../components/ModuleWorkbench";
import OnboardingChecklist from "../components/onboarding/OnboardingChecklist";
type Module={id:number;name:string;status:string};
type View="dashboard"|"planning"|"analysis"|"knowledge"|"workbench"|"modules";
export default function Home(){
 const [modules,setModules]=useState<Module[]>([]),[view,setView]=useState<View>("dashboard"),[seed,setSeed]=useState("");
 const [session,setSession]=useState<Session|null>(null);
 const [onboarded,setOnboarded]=useState(true);
 useEffect(()=>{setOnboarded(localStorage.getItem("atlas:onboarding:complete")==="1")},[]);
 useEffect(()=>{supabase?.auth.getSession().then(({data})=>setSession(data.session));const {data:listener}=supabase?.auth.onAuthStateChange((_event,next)=>setSession(next))??{data:{subscription:{unsubscribe(){}}}};return()=>listener.subscription.unsubscribe()},[]);
 useEffect(()=>{if(!session)return;authFetch("/api/v1/modules").then(x=>x.ok?x.json():Promise.reject(x)).then(setModules).catch(()=>setModules([]))},[session]);
 const client=supabase;
 if(!client)return <main className="min-h-screen bg-slate-950 p-8 text-white"><h1 className="text-3xl">Atlas AI</h1><p className="mt-4 text-red-300">Authentication is not configured.</p></main>;
 if(!session)return <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white"><section className="rounded-xl border border-slate-700 bg-slate-900 p-8 text-center"><h1 className="text-3xl font-semibold">Atlas AI</h1><p className="mt-3 text-slate-300">Sign in to open your private workspace.</p><button className="mt-5 rounded bg-cyan-500 px-4 py-2 text-slate-950" onClick={()=>client.auth.signInWithOAuth({provider:"github",options:{redirectTo:window.location.origin}})}>Continue with GitHub</button></section></main>;
 return <main className="min-h-screen bg-slate-950 p-6 text-white"><header className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-cyan-400">ATLAS AI</p><h1 className="text-3xl font-semibold">Human-controlled operations</h1></div><nav className="flex flex-wrap gap-2">{(["dashboard","planning","analysis","knowledge","workbench","modules"] as View[]).map(x=><button key={x} aria-pressed={view===x} onClick={()=>setView(x)} className={`rounded border px-3 py-2 capitalize ${view===x?"border-cyan-400 bg-slate-800":"border-slate-700"}`}>{x}</button>)}</nav><button onClick={()=>client.auth.signOut()} className="rounded border border-slate-700 px-3 py-2">Sign out</button></header><section className="mt-8">
 if(!onboarded)return <main className="min-h-screen bg-slate-950 p-6 text-white"><div className="mx-auto mt-12 max-w-2xl"><OnboardingChecklist onFinish={()=>setOnboarded(true)}/></div></main>;
 return <main className="min-h-screen bg-slate-950 p-6 text-white"><header className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-cyan-400">ATLAS AI</p><h1 className="text-3xl font-semibold">Human-controlled operations</h1></div><nav className="flex flex-wrap gap-2">{(["dashboard","planning","analysis","knowledge","modules"] as View[]).map(x=><button key={x} aria-pressed={view===x} onClick={()=>setView(x)} className={`rounded border px-3 py-2 capitalize ${view===x?"border-cyan-400 bg-slate-800":"border-slate-700"}`}>{x}</button>)}</nav><button onClick={()=>client.auth.signOut()} className="rounded border border-slate-700 px-3 py-2">Sign out</button></header><section className="mt-8">
 {view==="dashboard"&&<ExecutiveDashboard/>}
 {view==="planning"&&<PlanningBoard/>}
 {view==="analysis"&&<AnalysisPanel/>}
 {view==="knowledge"&&<><label className="mb-3 block text-sm">Knowledge node ID <input value={seed} onChange={e=>setSeed(e.target.value)} className="ml-2 rounded bg-slate-800 p-2" placeholder="Select or paste an ID"/></label>{seed?<KnowledgeWorkspace seedId={seed}/>:<p className="rounded bg-slate-900 p-4 text-slate-400">Enter a node ID to open its cited neighborhood.</p>}</>}
 {view==="workbench"&&<ModuleWorkbench/>}
 {view==="modules"&&<div className="grid gap-3 md:grid-cols-4">{modules.map(m=><article key={m.id} className="rounded-xl border border-slate-700 bg-slate-900 p-4"><b>{m.id}. {m.name}</b><p className="text-sm text-emerald-400">{m.status}</p></article>)}</div>}
 </section></main>
}
