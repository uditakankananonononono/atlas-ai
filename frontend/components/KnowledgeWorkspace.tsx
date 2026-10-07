"use client";
import {useEffect,useMemo,useRef,useState} from "react";
import {authFetch} from "../lib/supabase";
import {Background,Controls,Handle,MiniMap,Position,ReactFlow,applyNodeChanges,type Edge as FlowEdge,type Node as FlowNode,type NodeChange} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
type GraphNode={id:string;node_type:string;title:string;body?:string;metadata:Record<string,unknown>;version:number;source_uri?:string};
type GraphEdge={id:string;source_id:string;target_id:string;relationship:string;confidence:number};
function Card({data}:{data:any}){return <div className="min-w-44 rounded-xl border border-slate-600 bg-slate-900 p-3 text-white"><Handle type="target" position={Position.Left}/><span className="text-[10px] uppercase text-cyan-300">{data.node_type}</span><strong className="block text-sm">{data.title}</strong><Handle type="source" position={Position.Right}/></div>}
const nodeTypes={card:Card};
export default function KnowledgeWorkspace({seedId,apiBase="/api/v1"}:{seedId:string;apiBase?:string}){
 const [nodes,setNodes]=useState<GraphNode[]>([]),[edges,setEdges]=useState<GraphEdge[]>([]),[types,setTypes]=useState<Set<string>>(new Set()),[selected,setSelected]=useState<GraphNode|null>(null),[error,setError]=useState("");
 useEffect(()=>{let stale=false;setNodes([]);setEdges([]);setTypes(new Set());setSelected(null);setError("");authFetch(`${apiBase}/knowledge-workspace/nodes/${seedId}/neighborhood?depth=2`).then(r=>{if(!r.ok)throw Error("Could not load graph");return r.json()}).then(d=>{if(stale)return;setNodes(d.nodes);setEdges(d.edges);setTypes(new Set(d.nodes.map((n:GraphNode)=>n.node_type)))}).catch(e=>{if(!stale)setError(e.message)});return()=>{stale=true}},[seedId,apiBase]);
 const [draftTitle,setDraftTitle]=useState(""),[draftBody,setDraftBody]=useState(""),[saving,setSaving]=useState(false),[editError,setEditError]=useState("");
 const editEpoch=useRef(0);
 useEffect(()=>{editEpoch.current++;setDraftTitle(selected?.title||"");setDraftBody(selected?.body||"");setEditError("");setSaving(false)},[selected,seedId,apiBase]);
 async function saveEdit(){
  if(!selected||saving)return;
  const epoch=editEpoch.current,node=selected;setSaving(true);setEditError("");
  try{
   const r=await authFetch(`${apiBase}/knowledge-workspace/nodes/${encodeURIComponent(node.id)}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:draftTitle,body:draftBody,expected_version:node.version})});
   if(r.status===409)throw Error("This node changed. Reload the latest version before saving again. Your draft is still here.");
   if(!r.ok)throw Error("Could not save node. Your draft is still here.");
   const updated:GraphNode=await r.json();if(epoch!==editEpoch.current)return;
   setNodes(old=>old.map(n=>n.id===updated.id?updated:n));setSelected(updated);
  }catch(e){if(epoch===editEpoch.current)setEditError(e instanceof Error?e.message:"Could not save node")}
  finally{if(epoch===editEpoch.current)setSaving(false)}
 }
 async function reloadSelected(){
  if(!selected||saving)return;
  const epoch=editEpoch.current,id=selected.id;setSaving(true);setEditError("");
  try{
   const r=await authFetch(`${apiBase}/knowledge-workspace/nodes/${encodeURIComponent(id)}/neighborhood?depth=2`);
   if(!r.ok)throw Error("Could not reload node. Your draft is still here.");
   const d=await r.json(),latest=d.nodes.find((n:GraphNode)=>n.id===id);
   if(!latest)throw Error("Node is no longer available. Your draft is still here.");
   if(epoch!==editEpoch.current)return;setNodes(old=>old.map(n=>n.id===id?latest:n));setSelected(latest);
  }catch(e){if(epoch===editEpoch.current)setEditError(e instanceof Error?e.message:"Could not reload node")}
  finally{if(epoch===editEpoch.current)setSaving(false)}
 }
 const sourceHref=selected?.source_uri&&/^https?:\/\//i.test(selected.source_uri)?selected.source_uri:null;
 const shown=useMemo(()=>nodes.filter(n=>types.has(n.node_type)),[nodes,types]),visible=new Set(shown.map(n=>n.id));
 const boxRef=useRef<HTMLDivElement>(null),[wide,setWide]=useState(true);
 // Layout follows the canvas container width (not the window), so a narrow side panel gets the compact layout too.
 useEffect(()=>{const el=boxRef.current;if(!el)return;const f=()=>{const w=el.getBoundingClientRect().width;if(w>0)setWide(w>=560)};f();if(typeof ResizeObserver==="undefined")return;const ro=new ResizeObserver(f);ro.observe(el);return()=>ro.disconnect()},[]);
 const cols=wide?4:2;
 const baseNodes:FlowNode[]=useMemo(()=>shown.map((n,i)=>({id:n.id,type:"card",data:n,position:{x:(i%cols)*240,y:Math.floor(i/cols)*140}})),[shown,cols]);
 // Controlled nodes must feed React Flow's measured sizes back, otherwise the MiniMap has no node dimensions to draw.
 const [flowNodes,setFlowNodes]=useState<FlowNode[]>([]);
 const lastCols=useRef(cols),lastSeed=useRef(seedId);
 useEffect(()=>{const relayout=lastCols.current!==cols||lastSeed.current!==seedId;lastCols.current=cols;lastSeed.current=seedId;setFlowNodes(old=>baseNodes.map(n=>{const o=relayout?undefined:old.find(x=>x.id===n.id);return o?{...n,position:o.position,measured:o.measured,width:o.width,height:o.height}:n}))},[baseNodes,cols,seedId]);
 const onNodesChange=(changes:NodeChange[])=>setFlowNodes(old=>applyNodeChanges(changes,old));
 const flowEdges:FlowEdge[]=edges.filter(e=>visible.has(e.source_id)&&visible.has(e.target_id)).map(e=>({id:e.id,source:e.source_id,target:e.target_id,label:e.relationship,animated:e.confidence<1,style:{stroke:"#22d3ee"}}));
 function toggle(t:string){setTypes(old=>{const n=new Set(old);n.has(t)?n.delete(t):n.add(t);return n})}
 return <section className="rounded-2xl border border-slate-700 bg-slate-950 p-5 text-white" aria-label="Knowledge graph"><header className="flex items-center justify-between"><div><p className="text-xs text-cyan-400">MODULE 9</p><h2 className="text-xl font-semibold">Knowledge Workspace</h2></div><p className="text-xs text-slate-400">{shown.length} nodes · {flowEdges.length} links</p></header>
 {error&&<p role="alert" className="mt-4 text-red-300">{error}</p>}<div className="mt-4 flex flex-wrap gap-2">{[...new Set(nodes.map(n=>n.node_type))].map(t=><button key={t} aria-pressed={types.has(t)} onClick={()=>toggle(t)} className={`rounded-full px-3 py-1 text-xs ${types.has(t)?"bg-cyan-500 text-slate-950":"bg-slate-800"}`}>{t}</button>)}</div>
 <div ref={boxRef} className="mt-4 h-[560px] overflow-hidden rounded-xl border border-slate-800"><ReactFlow key={`${seedId}:${cols}:${shown.length}`} nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} minZoom={0.1} fitView fitViewOptions={{padding:wide?{top:"24px",left:"24px",right:"190px",bottom:"110px"}:{top:"16px",left:"16px",right:"16px",bottom:"130px"}}} onNodeDoubleClick={(_,n)=>setSelected(n.data as GraphNode)}><Background/><MiniMap pannable zoomable ariaLabel="Graph overview" nodeColor="#22d3ee" nodeStrokeColor="#0e7490" maskColor="rgba(2,6,23,0.7)" style={{width:wide?160:96,height:wide?100:64,background:"#0f172a",border:"1px solid #334155",borderRadius:8}}/><Controls showInteractive={false} className="[&_button]:!border-slate-700 [&_button]:!bg-slate-800 [&_button]:!text-slate-100 [&_svg]:!fill-slate-100"/></ReactFlow></div>
 {selected&&<aside aria-label="Node details" className="mt-4 rounded-xl bg-slate-900 p-4"><div className="flex justify-between"><h3 className="font-semibold">{selected.title}</h3><button onClick={()=>setSelected(null)}>Close</button></div>
 <p className="mt-2 text-xs text-slate-400">Version {selected.version}. Save checks this version at the database write.</p>
 {sourceHref&&<a className="mt-2 block break-all text-sm text-cyan-300 underline" href={sourceHref} target="_blank" rel="noopener noreferrer">Open source</a>}
 <label className="mt-3 block text-sm">Node title<input className="mt-1 block w-full rounded bg-slate-800 p-2" value={draftTitle} maxLength={500} onChange={e=>setDraftTitle(e.target.value)} disabled={saving}/></label>
 <label className="mt-3 block text-sm">Node notes<textarea className="mt-1 block min-h-28 w-full rounded bg-slate-800 p-2" value={draftBody} onChange={e=>setDraftBody(e.target.value)} disabled={saving}/></label>
 {editError&&<p role="alert" className="mt-3 text-sm text-red-300">{editError}</p>}
 <div className="mt-3 flex flex-wrap gap-3"><button className="rounded bg-cyan-500 px-3 py-2 text-sm text-slate-950 disabled:opacity-50" disabled={saving||!draftTitle.trim()||!selected.version} onClick={saveEdit}>{saving?"Working...":"Save changes"}</button><button className="rounded bg-slate-700 px-3 py-2 text-sm disabled:opacity-50" disabled={saving} onClick={reloadSelected}>Reload latest (discard draft)</button></div>
 </aside>}</section>
}
