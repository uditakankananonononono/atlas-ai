"use client";
import {useEffect,useState} from "react";
import {authFetch} from "../../lib/supabase";

const P="/api/v1/competition-manager/profile-corpus";
const TYPES=[
 {id:"writings",label:"Writings"},
 {id:"essays",label:"Essays"},
 {id:"activity_descriptions",label:"Activities"},
] as const;
type DocType=typeof TYPES[number]["id"];
type Status={documents:number;by_type:Record<string,number>;missing_types:string[];ready_for_drafting:boolean;complete:boolean;note?:string};

export default function OwnDocumentIntake({onDone}:{onDone:()=>void}){
 const [type,setType]=useState<DocType>("essays");
 const [title,setTitle]=useState("");
 const [text,setText]=useState("");
 const [status,setStatus]=useState<Status|null>(null);
 const [ids,setIds]=useState<number[]>([]);
 const [msg,setMsg]=useState<{kind:"ok"|"err";text:string}|null>(null);
 const [busy,setBusy]=useState(false);
 useEffect(()=>{authFetch(`${P}/onboarding/status`).then(r=>r.ok?r.json():null).then(s=>{if(s){setStatus(s);setIds((s.documents_list||[]).map((d:{id:number})=>d.id))}}).catch(()=>{})},[]);
 const detail=async(r:Response)=>{try{return (await r.json()).detail as string}catch{return `Request failed (${r.status})`}};
 async function add(){
  setBusy(true);setMsg(null);
  try{
   const r=await authFetch(`${P}/onboarding/documents`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({doc_type:type,title,text})});
   if(!r.ok){setMsg({kind:"err",text:typeof (await detail(r))==="string"?await detail(r):"Could not save this document."});return}
   const j=await r.json();setStatus(j.status);setIds(x=>[...x,j.document.id]);setTitle("");setText("");setMsg({kind:"ok",text:`Saved "${j.document.title}" as ${type.replace("_"," ")}. Stored locally; nothing was sent anywhere.`});
  }catch{setMsg({kind:"err",text:"Atlas backend is not reachable."})}finally{setBusy(false)}
 }
 async function finish(){
  setBusy(true);setMsg(null);
  const covered=TYPES.map(t=>t.id).filter(t=>(status?.by_type?.[t]||0)>0);
  try{
   const r=await authFetch(`${P}/onboarding/complete`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({document_types:covered,source_ids:ids})});
   if(!r.ok){setMsg({kind:"err",text:await detail(r)});return}
   onDone();
  }catch{setMsg({kind:"err",text:"Atlas backend is not reachable."})}finally{setBusy(false)}
 }
 async function skip(){await authFetch(`${P}/onboarding/skip`,{method:"POST"}).catch(()=>{});onDone()}
 const total=status?.documents||0;
 return <section aria-labelledby="own-docs-title" className="rounded-xl border border-cyan-700 bg-slate-900 p-6">
  <p className="text-sm uppercase tracking-wide text-cyan-400">Your source documents</p>
  <h2 id="own-docs-title" className="mt-1 text-2xl font-semibold">Add your writings, essays and activities</h2>
  <p className="mt-2 text-slate-300">Atlas reuses these when preparing competition answers for your review. Paste text you wrote yourself. It is stored locally and nothing is submitted. You can skip this and add documents later.</p>
  <div className="mt-4 flex gap-2" role="tablist" aria-label="Document type">{TYPES.map(t=><button key={t.id} role="tab" aria-selected={type===t.id} onClick={()=>setType(t.id)} className={`rounded px-3 py-1 text-sm ${type===t.id?"bg-cyan-600 text-white":"bg-slate-800 text-slate-300"}`}>{t.label}{status?.by_type?.[t.id]?` (${status.by_type[t.id]})`:""}</button>)}</div>
  <label className="mt-4 block text-sm">Title<input value={title} onChange={e=>setTitle(e.target.value)} maxLength={200} className="mt-1 w-full rounded bg-slate-800 p-2" placeholder="e.g. Harbor project essay"/></label>
  <label className="mt-3 block text-sm">Text<textarea value={text} onChange={e=>setText(e.target.value)} rows={8} className="mt-1 w-full rounded bg-slate-800 p-2" placeholder="Paste your own writing here (at least 20 characters)"/></label>
  <div className="mt-3 flex items-center gap-3"><button disabled={busy||!title.trim()||text.trim().length<20} onClick={add} className="rounded bg-cyan-600 px-4 py-2 disabled:opacity-40">Save document</button><span className="text-sm text-slate-400">{total} saved{status&&status.missing_types.length?` · not yet added: ${status.missing_types.map(x=>x.replace("_"," ")).join(", ")}`:""}</span></div>
  {msg&&<p role={msg.kind==="err"?"alert":"status"} className={`mt-3 text-sm ${msg.kind==="err"?"text-red-300":"text-emerald-300"}`}>{msg.text}</p>}
  {status?.note&&<p className="mt-3 text-xs text-slate-400">{status.note}</p>}
  <div className="mt-5 flex items-center justify-between"><button onClick={skip} className="text-sm text-slate-400 underline">Skip for now (drafting stays unavailable)</button><button disabled={busy||total===0} onClick={finish} className="rounded bg-emerald-600 px-4 py-2 disabled:opacity-40">Done</button></div>
 </section>;
}
