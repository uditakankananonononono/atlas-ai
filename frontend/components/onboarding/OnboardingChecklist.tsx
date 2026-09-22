"use client";
import {useEffect,useState} from "react";

type Step={id:string;title:string;detail:string};
const STEPS:Step[]=[
 {id:"profile",title:"Confirm your profile",detail:"Add only facts and preferences you want Atlas to use."},
 {id:"sources",title:"Connect a source",detail:"Start with one account or document source. Connections remain optional."},
 {id:"approvals",title:"Review approval boundaries",detail:"Messages, publishing, submissions, deletion and spending require review."},
 {id:"goal",title:"Create a first goal",detail:"Choose a small goal and inspect the plan before any external action."},
];
const KEY="atlas:onboarding:v1";
export default function OnboardingChecklist({onFinish}:{onFinish:()=>void}){
 const [done,setDone]=useState<string[]>([]);
 useEffect(()=>{try{setDone(JSON.parse(localStorage.getItem(KEY)||"[]"))}catch{setDone([])}},[]);
 const toggle=(id:string)=>setDone(current=>{const next=current.includes(id)?current.filter(x=>x!==id):[...current,id];localStorage.setItem(KEY,JSON.stringify(next));return next});
 return <section aria-labelledby="onboarding-title" className="rounded-xl border border-cyan-700 bg-slate-900 p-6">
  <p className="text-sm uppercase tracking-wide text-cyan-400">First run</p><h2 id="onboarding-title" className="mt-1 text-2xl font-semibold">Set up a controlled workspace</h2>
  <p className="mt-2 text-slate-300">Nothing here sends, publishes, submits or spends. Complete the checklist in any order.</p>
  <ol className="mt-5 grid gap-3">{STEPS.map(step=><li key={step.id}><label className="flex cursor-pointer gap-3 rounded border border-slate-700 p-4"><input type="checkbox" checked={done.includes(step.id)} onChange={()=>toggle(step.id)} className="mt-1"/><span><b>{step.title}</b><span className="block text-sm text-slate-400">{step.detail}</span></span></label></li>)}</ol>
  <div className="mt-5 flex items-center justify-between"><span className="text-sm text-slate-400">{done.length}/{STEPS.length} complete</span><button disabled={done.length!==STEPS.length} onClick={()=>{localStorage.setItem("atlas:onboarding:complete","1");onFinish()}} className="rounded bg-cyan-500 px-4 py-2 font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">Open Atlas</button></div>
 </section>;
}
