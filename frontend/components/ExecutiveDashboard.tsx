"use client";
import React,{FormEvent,useCallback,useEffect,useMemo,useState} from "react";
import OperationsChart from "./OperationsChart";
import {Card,CardContent,CardHeader} from "./ui/card";
import {Approval,Blocker,DashboardView,Digest,DrilldownResult,KPI,ModuleStatus,Snapshot,WidgetConfig,dashboardApi} from "./executive-dashboard/api";
type Api=ReturnType<typeof dashboardApi>;
const severityStyle:Record<string,string>={critical:"border-red-500 text-red-300",warning:"border-amber-500 text-amber-300",info:"border-slate-600 text-slate-300"};
const agentStyle:Record<string,string>={running:"text-emerald-400",idle:"text-slate-400",stalled:"text-amber-400",offline:"text-red-400"};
function Trend({kpi}:{kpi:KPI}){
  if(kpi.previous_value===null)return <span className="text-xs text-slate-500">no trend yet</span>;
  const delta=kpi.value-kpi.previous_value;
  return <span className={`text-xs ${delta>0?"text-emerald-400":delta<0?"text-red-400":"text-slate-400"}`}>{delta>0?"+":""}{delta} vs prior {kpi.window_hours}h</span>;
}
function DrilldownPanel({data,onClose}:{data:DrilldownResult|null;onClose:()=>void}){
  if(!data)return null;
  return <aside className="fixed inset-y-0 right-0 z-10 w-full max-w-md overflow-y-auto border-l border-slate-700 bg-slate-950 p-5">
    <div className="flex items-start justify-between"><div><p className="text-xs uppercase text-cyan-400">{data.subject.kind}</p><h3 className="text-lg font-semibold">{data.subject.summary||data.subject.id}</h3></div><button onClick={onClose} className="rounded bg-slate-800 px-2 py-1 text-sm">Close</button></div>
    {Object.keys(data.detail).length>0&&<pre className="mt-3 max-h-56 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-300">{JSON.stringify(data.detail,null,2)}</pre>}
    {data.approvals.length>0&&<><h4 className="mt-4 text-sm font-semibold">Approvals ({data.approvals.length})</h4><ul className="mt-1 space-y-1 text-sm text-slate-300">{data.approvals.map(a=><li key={a.id} className="rounded bg-slate-900 p-2">{a.title} <span className="text-xs uppercase text-slate-500">{a.state}</span></li>)}</ul></>}
    <h4 className="mt-4 text-sm font-semibold">Events ({data.events.length})</h4>
    <ul className="mt-1 space-y-1 text-sm text-slate-300">{data.events.map(e=><li key={e.id} className="rounded bg-slate-900 p-2"><span className="text-cyan-300">#{e.sequence}</span> {e.topic} <span className="text-xs text-slate-500">{new Date(e.occurred_at).toLocaleString()}</span></li>)}</ul>
    {data.events.length===0&&data.approvals.length===0&&<p className="mt-2 text-sm text-slate-500">No backing rows recorded yet.</p>}
  </aside>;
}
export default function ExecutiveDashboard({apiBase="/api/v1"}:{apiBase?:string}){
  const api=useMemo<Api>(()=>dashboardApi(apiBase),[apiBase]);
  const [view,setView]=useState<DashboardView|null>(null);
  const [kpis,setKpis]=useState<KPI[]>([]);const [modules,setModules]=useState<ModuleStatus[]>([]);const [blockers,setBlockers]=useState<Blocker[]>([]);
  const [approvals,setApprovals]=useState<Approval[]>([]);const [digest,setDigest]=useState<Digest|null>(null);const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [drilldown,setDrilldown]=useState<DrilldownResult|null>(null);
  const [selected,setSelected]=useState<Set<string>>(new Set());const [skippedNote,setSkippedNote]=useState<string|null>(null);
  const [command,setCommand]=useState("");const [preview,setPreview]=useState<{id:string;intent:string;read_only:boolean;confidence:number}|null>(null);
  const [live,setLive]=useState(false);const [error,setError]=useState<string|null>(null);const [editView,setEditView]=useState(false);
  const refresh=useCallback(async()=>{
    try{
      const [v,k,m,b,a,d,s]=await Promise.all([api.getView(),api.kpis(),api.modules(),api.blockers(),api.approvals(),api.digest(),api.snapshot()]);
      setView(v);setKpis(k);setModules(m);setBlockers(b);setApprovals(a);setDigest(d);setSnapshot(s);setError(null);
    }catch(e){setError(e instanceof Error?e.message:"dashboard refresh failed")}
  },[api]);
  useEffect(()=>{refresh();setLive(true);const timer=window.setInterval(refresh,30000);return()=>window.clearInterval(timer)},[refresh]);
  async function submitCommand(e:FormEvent){e.preventDefault();if(!command.trim())return;setPreview(await api.preview(command))}
  async function runCommand(){if(!preview)return;await api.execute(preview.id);setPreview(null);setCommand("");refresh()}
  async function decideOne(id:string,approve:boolean){await api.decide(id,approve);refresh()}
  async function decideBulk(approve:boolean){
    const result=await api.bulkDecide([...selected],approve);
    setSkippedNote(result.skipped.length?`${result.decided.length} decided; skipped: ${result.skipped.map(s=>`${s.id} (${s.reason})`).join(", ")}`:null);
    setSelected(new Set());refresh();
  }
  function toggleSelect(id:string){setSelected(prev=>{const next=new Set(prev);if(next.has(id))next.delete(id);else next.add(id);return next})}
  async function moveWidget(id:string,direction:-1|1){
    if(!view)return;const widgets=[...view.widgets];const i=widgets.findIndex(w=>w.id===id);const j=i+direction;
    if(i<0||j<0||j>=widgets.length)return;[widgets[i],widgets[j]]=[widgets[j],widgets[i]];
    widgets.forEach((w,idx)=>w.position=idx);setView(await api.saveView(widgets));
  }
  async function toggleWidget(id:string){if(!view)return;setView(await api.saveView(view.widgets.map(w=>w.id===id?{...w,visible:!w.visible}:w)))}
  const alerts=(snapshot?.data?.alerts??[]).slice(-8).reverse();
  const sections:Record<string,()=>React.JSX.Element|null>={
    kpi_card:()=><section key="kpis"><h2 className="text-lg font-semibold">KPIs</h2><div className="mt-2 grid gap-3 md:grid-cols-3 xl:grid-cols-4">{kpis.map(k=><button key={k.id} onClick={()=>api.kpiEvidence(k.id).then(setDrilldown)} className="rounded-xl bg-slate-900 p-4 text-left hover:bg-slate-800" title={k.definition}><p className="text-xs text-slate-400">{k.label}</p><strong className="text-2xl">{k.value}<span className="ml-1 text-xs font-normal text-slate-500">{k.unit!=="count"?k.unit:""}</span></strong><br/><Trend kpi={k}/>{k.evidence_total>0&&<span className="ml-2 text-xs text-cyan-400">{k.evidence_total} rows</span>}</button>)}</div></section>,
    module_status:()=><section key="modules"><h2 className="text-lg font-semibold">Modules</h2><div className="mt-2 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{modules.map(m=><button key={m.module_id} onClick={()=>api.drilldown("module",String(m.module_id)).then(setDrilldown)} className="rounded-xl bg-slate-900 p-3 text-left hover:bg-slate-800"><div className="flex justify-between"><strong className="text-sm">{m.module_id}. {m.name}</strong><span className={m.implemented?"text-xs text-emerald-400":"text-xs text-slate-500"}>{m.implemented?"implemented":"planned"}</span></div><p className="mt-1 text-xs text-slate-400">agent <span className={m.agent?agentStyle[m.agent.state]:"text-slate-500"}>{m.agent?m.agent.state:"none"}</span> · {m.pending_approvals} approvals · {m.events_24h} events/24h · {m.open_blockers} blockers</p></button>)}</div></section>,
    blockers:()=>blockers.length?<section key="blockers"><h2 className="text-lg font-semibold">Blockers ({blockers.length})</h2><ul className="mt-2 space-y-2">{blockers.map(b=><li key={b.id} className={`rounded-xl border-l-4 bg-slate-900 p-3 ${severityStyle[b.severity]}`}><p className="text-sm">{b.summary}</p><p className="mt-1 text-xs text-slate-400">{b.recommended_action}</p></li>)}</ul></section>:null,
    alerts:()=>alerts.length?<section key="alerts"><h2 className="text-lg font-semibold">Alerts</h2><ul className="mt-2 space-y-1">{alerts.map(a=><li key={a.event_id} className="rounded bg-slate-900 p-2 text-sm"><span className={`mr-2 text-xs uppercase ${a.severity==="critical"?"text-red-400":"text-amber-300"}`}>{a.severity}</span>{a.message}<span className="ml-2 text-xs text-slate-500">{new Date(a.occurred_at).toLocaleString()}</span></li>)}</ul></section>:null,
    digest:()=>digest?<section key="digest" className="rounded-xl bg-slate-900 p-4"><h2 className="text-lg font-semibold">Digest</h2>{digest.sections.map(sec=><div key={sec.title} className="mt-3"><h3 className="text-sm font-semibold text-cyan-300">{sec.title}</h3><ul className="mt-1 list-inside list-disc text-sm text-slate-300">{sec.lines.slice(0,8).map((l,i)=><li key={i}>{l}</li>)}</ul></div>)}</section>:null,
    approvals:()=><section key="approvals"><div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Approval queue ({approvals.length})</h2>{selected.size>0&&<div className="flex gap-2 text-sm"><button onClick={()=>decideBulk(true)} className="rounded bg-emerald-500 px-3 py-1 text-slate-950">Approve {selected.size}</button><button onClick={()=>decideBulk(false)} className="rounded bg-slate-700 px-3 py-1">Reject {selected.size}</button></div>}</div>
      {skippedNote&&<p className="mt-1 text-xs text-amber-300">{skippedNote}</p>}
      <div className="mt-2 space-y-2">{approvals.map(a=><article key={a.id} className="rounded-xl bg-slate-900 p-4"><div className="flex items-start gap-3"><input type="checkbox" checked={selected.has(a.id)} onChange={()=>toggleSelect(a.id)} className="mt-1" aria-label={`select ${a.title}`}/><div className="flex-1"><div className="flex justify-between"><strong>{a.title}</strong><span className="text-xs uppercase text-amber-300">{a.risk}</span></div><p className="mt-1 text-sm text-slate-300">{a.summary}</p><p className="mt-1 text-xs text-slate-500">module {a.module_id}{a.expires_at?` · expires ${new Date(a.expires_at).toLocaleString()}`:""}</p><div className="mt-3 flex gap-2"><button onClick={()=>decideOne(a.id,true)} className="rounded bg-emerald-500 px-3 py-1 text-slate-950">Approve</button><button onClick={()=>decideOne(a.id,false)} className="rounded bg-slate-700 px-3 py-1">Reject</button></div></div></div></article>)}{approvals.length===0&&<p className="text-sm text-slate-500">Queue is clear.</p>}</div></section>,
    timeline:()=>snapshot?.data?.timeline?.length?<section key="timeline"><h2 className="text-lg font-semibold">Timeline</h2><ul className="mt-2 space-y-1 text-sm">{snapshot.data.timeline.map((t,i)=><li key={String(t.id??i)} className="flex justify-between rounded bg-slate-900 p-2"><span>{String(t.title??t.id)}{Boolean(t.critical)&&<span className="ml-2 text-xs text-cyan-400">critical</span>}{Boolean(t.at_risk)&&<span className="ml-2 text-xs text-red-400">at risk</span>}</span><span className="text-xs text-slate-500">{Math.round(Number(t.progress??0)*100)}%</span></li>)}</ul></section>:null,
  };
  const widgets=(view?.widgets??[]).filter(w=>w.visible).sort((a,b)=>a.position-b.position);
  return <main className="space-y-5 bg-slate-950 p-6 text-white">
    <header className="flex items-center justify-between"><div><p className="text-xs text-cyan-400">MODULE 16</p><h1 className="text-2xl font-semibold">Executive Dashboard</h1></div><div className="flex items-center gap-3 text-sm"><button onClick={()=>setEditView(v=>!v)} className="rounded bg-slate-800 px-3 py-1">{editView?"Done":"Layout"}</button><span className={live?"text-emerald-400":"text-amber-400"}>{live?"Live":"Reconnecting"}</span></div></header>
    {error&&<p className="rounded bg-red-950 p-2 text-sm text-red-300">{error}</p>}
    {kpis.length>0&&<Card><CardHeader>Live KPI trend</CardHeader><CardContent><OperationsChart data={kpis.slice(0,12).map(k=>({time:k.label,value:k.value}))}/></CardContent></Card>}
    {editView&&view&&<section className="rounded-xl border border-slate-700 bg-slate-900 p-3 text-sm"><h2 className="font-semibold">Layout</h2><ul className="mt-2 space-y-1">{[...view.widgets].sort((a,b)=>a.position-b.position).map(w=><li key={w.id} className="flex items-center gap-2"><button onClick={()=>moveWidget(w.id,-1)} className="rounded bg-slate-800 px-2">Up</button><button onClick={()=>moveWidget(w.id,1)} className="rounded bg-slate-800 px-2">Down</button><label className="flex items-center gap-1"><input type="checkbox" checked={w.visible} onChange={()=>toggleWidget(w.id)}/>{w.kind}{w.kpi_id?`: ${w.kpi_id}`:""}</label></li>)}</ul></section>}
    <form onSubmit={submitCommand} className="rounded-xl border border-slate-700 bg-slate-900 p-4"><label className="text-sm" htmlFor="atlas-command">Ask Atlas or prepare an action</label><div className="mt-2 flex gap-2"><input id="atlas-command" value={command} onChange={e=>setCommand(e.target.value)} className="flex-1 rounded bg-slate-800 p-3" placeholder="Show blockers"/><button className="rounded bg-cyan-500 px-4 text-slate-950">Preview</button></div>{preview&&<div className="mt-3 rounded bg-slate-800 p-3"><p>{preview.intent} · {Math.round(preview.confidence*100)}% confidence</p><p className="text-sm text-slate-300">{preview.read_only?"Read-only":"Requires approval before any action"}</p><button type="button" onClick={runCommand} className="mt-2 rounded border border-cyan-400 px-3 py-1">{preview.read_only?"Run":"Send to approvals"}</button></div>}</form>
    {widgets.map(w=>{const render=sections[w.kind];return render?<div key={w.id}>{render()}</div>:null})}
    <DrilldownPanel data={drilldown} onClose={()=>setDrilldown(null)}/>
  </main>;
}
