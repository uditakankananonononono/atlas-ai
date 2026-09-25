"use client";
import {useEffect,useState} from "react";
import {authFetch} from "../lib/supabase";

type Case={id:string;publisher:string;title:string;url:string;example_school:string|null;evidence_type:string;reading_mode:string;scope_note:string};
export default function AdmittedCaseReader(){
 const [cases,setCases]=useState<Case[]>([]),[query,setQuery]=useState(""),[loading,setLoading]=useState(true),[error,setError]=useState("");
 useEffect(()=>{let mounted=true;authFetch("/api/v1/study-abroad/admitted-cases",{cache:"no-store"}).then(async response=>{if(!response.ok)throw new Error(`Case index unavailable (${response.status})`);return response.json()}).then(data=>{if(mounted)setCases(data.cases??[])}).catch(e=>{if(mounted)setError(String(e))}).finally(()=>{if(mounted)setLoading(false)});return()=>{mounted=false}},[]);
 const filtered=cases.filter(c=>`${c.publisher} ${c.title} ${c.example_school??""}`.toLowerCase().includes(query.toLowerCase()));
 return <section className="my-5 rounded-xl border border-slate-700 bg-slate-900 p-5" aria-label="Admitted student essay reader">
  <h3 className="text-xl font-semibold">Admitted student reading shelf</h3><p className="mt-2 text-sm text-slate-300">Browse 20 public sources. "Read at publisher" opens the original page in a new tab, where you can read the essay. Atlas does not copy, store, or rehost it. Some pages are case stories or anthologies rather than a single full essay; access and availability can change.</p>
  <label className="mt-4 block text-sm">Find a school or publisher<input value={query} onChange={e=>setQuery(e.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-950 p-2" placeholder="MIT, Cornell, Hamilton..."/></label>
  {loading&&<p role="status">Loading sources...</p>}{error&&<p role="alert">{error}</p>}
  <ul className="mt-4 grid gap-3">{filtered.map(c=><li key={c.id} className="rounded border border-slate-700 p-3"><div className="text-xs text-cyan-300">{c.publisher} | {c.example_school??"Several schools"} | Publisher page</div><strong className="block">{c.title}</strong><span className="text-xs text-slate-400">{c.evidence_type.replaceAll("_"," ")}. Admission claim is publisher/student-reported, not independently verified.</span><div><a href={c.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block rounded bg-cyan-400 px-3 py-1 text-sm font-semibold text-slate-950" aria-label={`Read ${c.title} at ${c.publisher} (opens publisher site in a new tab)`}>Read at publisher ↗</a></div></li>)}</ul>
  {!loading&&!error&&filtered.length===0&&<p>No matching sources.</p>}
 </section>
}
