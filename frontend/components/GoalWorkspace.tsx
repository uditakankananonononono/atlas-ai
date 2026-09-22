"use client";
import {FormEvent,useCallback,useEffect,useMemo,useState} from "react";
import {ApiError,ExecutionState,Goal,goalWorkspaceApi} from "./goal-workspace-api";

type DraftStep={title:string;action_type:string;citations:string[]};
const STATE_STYLE:Record<string,string>={planned:"text-slate-300",simulated:"text-cyan-300",externally_executed:"text-emerald-400",independently_verified:"text-emerald-300"};

export default function GoalWorkspace({apiBase="/api/v1/product-orchestrator"}:{apiBase?:string}){
  const api=useMemo(()=>goalWorkspaceApi(apiBase),[apiBase]);
  const [statement,setStatement]=useState("");const [sourceLines,setSourceLines]=useState("");
  const [goal,setGoal]=useState<Goal|null>(null);const [state,setState]=useState<ExecutionState|null>(null);
  const [steps,setSteps]=useState<DraftStep[]>([{title:"",action_type:"",citations:[]}]);
  const [error,setError]=useState<string|null>(null);const [busy,setBusy]=useState(false);
  const refresh=useCallback(async(id:string)=>{setGoal(await api.getGoal(id));setState(await api.executionState(id))},[api]);
  useEffect(()=>{if(goal)refresh(goal.id).catch(()=>{})},[]);// eslint-disable-line react-hooks/exhaustive-deps
  async function guard(fn:()=>Promise<void>){setBusy(true);setError(null);try{await fn()}catch(e){setError(e instanceof ApiError?e.detail:e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
  function createGoal(e:FormEvent){e.preventDefault();guard(async()=>{
    const sources=sourceLines.split("\n").map(l=>l.trim()).filter(Boolean).map(uri=>({uri}));
    const created=await api.createGoal(statement,sources);setGoal(created);setState(await api.executionState(created.id));
  })}
  function setStep(i:number,patch:Partial<DraftStep>){setSteps(prev=>prev.map((s,j)=>j===i?{...s,...patch}:s))}
  function toggleCitation(i:number,sourceId:string){const s=steps[i];setStep(i,{citations:s.citations.includes(sourceId)?s.citations.filter(c=>c!==sourceId):[...s.citations,sourceId]})}
  function submitPlan(e:FormEvent){e.preventDefault();if(!goal)return;guard(async()=>{await api.buildPlan(goal.id,steps);await refresh(goal.id)})}
  function requestApproval(){if(!goal)return;guard(async()=>{await api.requestApproval(goal.id);await refresh(goal.id)})}
  function execute(){if(!goal||!goal.approval_id)return;const goalId=goal.id,approvalId=goal.approval_id;guard(async()=>{await api.execute(goalId,approvalId);await refresh(goalId)})}
  const decision=state?.approval_decision??null;
  return <main className="space-y-5 bg-slate-950 p-6 text-white">
    <header><p className="text-xs text-cyan-400">MODULE 20 · GOAL-FIRST</p><h1 className="text-2xl font-semibold">Goal workspace</h1><p className="mt-1 text-sm text-slate-400">Goal and sources in, cited plan out, human approval before execution, honest readback after.</p></header>
    {error&&<p role="alert" className="rounded bg-red-950 p-3 text-sm text-red-300">{error}</p>}
    {!goal&&<form onSubmit={createGoal} className="rounded-xl bg-slate-900 p-4">
      <label className="block text-sm">Goal<input value={statement} onChange={e=>setStatement(e.target.value)} className="mt-1 w-full rounded bg-slate-800 p-2" placeholder="Launch the cited pilot"/></label>
      <label className="mt-3 block text-sm">Sources (one URI per line)<textarea value={sourceLines} onChange={e=>setSourceLines(e.target.value)} rows={3} className="mt-1 w-full rounded bg-slate-800 p-2 font-mono text-xs" placeholder={"https://example.test/spec\nhttps://example.test/metrics"}/></label>
      <button disabled={busy||statement.trim().length<3||!sourceLines.trim()} className="mt-3 rounded bg-cyan-500 px-4 py-2 text-sm text-slate-950 disabled:opacity-40">Register goal</button>
    </form>}
    {goal&&<><section className="rounded-xl bg-slate-900 p-4">
      <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">{goal.statement}</h2><span className="text-xs uppercase text-cyan-300">{goal.status}</span></div>
      <h3 className="mt-3 text-sm font-semibold">Sources</h3>
      <ul className="mt-1 space-y-1 text-sm text-slate-300">{goal.sources.map(s=><li key={s.id}><span className="font-mono text-xs text-cyan-200">{s.uri}</span>{s.note&&<span className="ml-2 text-slate-500">{s.note}</span>}</li>)}</ul>
    </section>
    {goal.steps.length===0&&goal.status==="registered"&&<form onSubmit={submitPlan} className="rounded-xl bg-slate-900 p-4">
      <h2 className="text-lg font-semibold">Cited plan</h2>
      <p className="mt-1 text-xs text-slate-400">Every step must cite at least one registered source.</p>
      {steps.map((s,i)=><div key={i} className="mt-3 rounded bg-slate-800 p-3">
        <div className="grid gap-2 md:grid-cols-2">
          <label className="text-sm">Step title<input value={s.title} onChange={e=>setStep(i,{title:e.target.value})} className="mt-1 w-full rounded bg-slate-950 p-2"/></label>
          <label className="text-sm">Action type<input value={s.action_type} onChange={e=>setStep(i,{action_type:e.target.value})} className="mt-1 w-full rounded bg-slate-950 p-2"/></label>
        </div>
        <fieldset className="mt-2 text-sm"><legend className="text-xs text-slate-400">Citations</legend>
          {goal.sources.map(src=><label key={src.id} className="mr-4 inline-flex items-center gap-1 text-xs"><input type="checkbox" checked={s.citations.includes(src.id)} onChange={()=>toggleCitation(i,src.id)}/>{src.uri}</label>)}
        </fieldset>
      </div>)}
      <div className="mt-3 flex gap-2">
        <button type="button" onClick={()=>setSteps(prev=>[...prev,{title:"",action_type:"",citations:[]}])} className="rounded bg-slate-700 px-3 py-1 text-sm">Add step</button>
        <button disabled={busy||steps.some(s=>!s.title.trim()||!s.action_type.trim()||s.citations.length===0)} className="rounded bg-cyan-500 px-4 py-1 text-sm text-slate-950 disabled:opacity-40">Submit cited plan</button>
      </div>
    </form>}
    {goal.steps.length>0&&<section className="rounded-xl bg-slate-900 p-4">
      <h2 className="text-lg font-semibold">Plan ({goal.steps.length} steps)</h2>
      <ul className="mt-2 space-y-2 text-sm">{goal.steps.map(s=><li key={s.id} className="rounded bg-slate-800 p-2"><strong>{s.title}</strong> <span className="text-xs text-slate-400">{s.action_type} · {s.risk}</span><p className="mt-1 text-xs text-cyan-200">cites {s.citations.length} source{s.citations.length===1?"":"s"}</p></li>)}</ul>
    </section>}
    <section className="rounded-xl bg-slate-900 p-4">
      <h2 className="text-lg font-semibold">Approval</h2>
      {!goal.approval_id&&goal.steps.length>0&&<button onClick={requestApproval} disabled={busy} className="mt-2 rounded bg-cyan-500 px-4 py-2 text-sm text-slate-950 disabled:opacity-40">Request approval</button>}
      {goal.approval_id&&<div className="mt-2 rounded bg-slate-800 p-3 text-sm">
        <p>approval <span className="font-mono text-xs">{goal.approval_id}</span></p>
        <p className="mt-1">decision: <span className={decision==="approved"?"text-emerald-400":"text-amber-300"}>{decision??"unknown"}</span></p>
        <p className="mt-1 text-xs text-slate-500">Decisions are made by a human in the executive dashboard approval queue.</p>
        <div className="mt-2 flex gap-2">
          <button onClick={()=>goal&&guard(async()=>refresh(goal.id))} disabled={busy} className="rounded bg-slate-700 px-3 py-1 text-sm">Refresh decision</button>
          <button onClick={execute} disabled={busy||decision!=="approved"||goal.status==="executed"} className="rounded bg-emerald-500 px-3 py-1 text-sm text-slate-950 disabled:opacity-40">Execute approved plan</button>
        </div>
      </div>}
    </section>
    {state&&<section className="rounded-xl bg-slate-900 p-4">
      <h2 className="text-lg font-semibold">Execution readback</h2>
      <p className="mt-1 text-xs text-slate-400">{state.ledger.boundary}</p>
      <div className="mt-2 flex flex-wrap gap-3 text-sm">{Object.entries(state.ledger.counts).map(([k,v])=><span key={k} className={STATE_STYLE[k]??""}>{k}: {v}</span>)}<span className="text-slate-400">verified {state.ledger.verified_fraction}</span></div>
      <ul className="mt-2 space-y-1 text-sm">{state.ledger.items.map(item=><li key={item.id} className="rounded bg-slate-800 p-2"><span className={STATE_STYLE[item.state]??""}>{item.state}</span> <strong className="ml-2">{item.claim}</strong>{item.evidence_ids.length>0&&<span className="ml-2 text-xs text-slate-500">evidence: {item.evidence_ids.join(", ")}</span>}{item.verifier&&<span className="ml-2 text-xs text-emerald-300">verified by {item.verifier}</span>}{state.errors[item.id]&&<span className="ml-2 text-xs text-red-300">{state.errors[item.id]}</span>}</li>)}</ul>
      {state.ledger.items.length===0&&<p className="mt-2 text-sm text-slate-500">No steps yet - submit a cited plan first.</p>}
    </section>}</>}
  </main>;
}
