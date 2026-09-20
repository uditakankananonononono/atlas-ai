"use client";
import {useEffect,useMemo,useState} from "react";
import {Background,Controls,Handle,MiniMap,Position,ReactFlow,type Edge as FlowEdge,type Node as FlowNode} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
type GraphNode={id:string;node_type:string;title:string;body?:string;metadata:Record<string,unknown>};
type GraphEdge={id:string;source_id:string;target_id:string;relationship:string;confidence:number};
function Card({data}:{data:any}){return <div className="min-w-44 rounded-xl border border-slate-600 bg-slate-900 p-3 text-white"><Handle type="target" position={Position.Left}/><span className="text-[10px] uppercase text-cyan-300">{data.node_type}</span><strong className="block text-sm">{data.title}</strong><Handle type="source" position={Position.Right}/></div>}
const nodeTypes={card:Card};
export default function KnowledgeWorkspace({seedId,apiBase="/api/v1"}:{seedId:string;apiBase?:string}){
 const [nodes,setNodes]=useState<GraphNode[]>([]),[edges,setEdges]=useState<GraphEdge[]>([]),[types,setTypes]=useState<Set<string>>(new Set()),[selected,setSelected]=useState<GraphNode|null>(null),[error,setError]=useState("");
 useEffect(()=>{fetch(`${apiBase}/knowledge-workspace/nodes/${seedId}/neighborhood?depth=2`).then(r=>{if(!r.ok)throw Error("Could not load graph");return r.json()}).then(d=>{setNodes(d.nodes);setEdges(d.edges);setTypes(new Set(d.nodes.map((n:GraphNode)=>n.node_type)))}).catch(e=>setError(e.message))},[seedId,apiBase]);
 const shown=useMemo(()=>nodes.filter(n=>types.has(n.node_type)),[nodes,types]),visible=new Set(shown.map(n=>n.id));
 const flowNodes:FlowNode[]=shown.map((n,i)=>({id:n.id,type:"card",data:n,position:{x:(i%4)*240,y:Math.floor(i/4)*140}}));
 const flowEdges:FlowEdge[]=edges.filter(e=>visible.has(e.source_id)&&visible.has(e.target_id)).map(e=>({id:e.id,source:e.source_id,target:e.target_id,label:e.relationship,animated:e.confidence<1,style:{stroke:"#22d3ee"}}));
 function toggle(t:string){setTypes(old=>{const n=new Set(old);n.has(t)?n.delete(t):n.add(t);return n})}
 return <section className="rounded-2xl border border-slate-700 bg-slate-950 p-5 text-white" aria-label="Knowledge graph"><header className="flex items-center justify-between"><div><p className="text-xs text-cyan-400">MODULE 9</p><h2 className="text-xl font-semibold">Knowledge Workspace</h2></div><p className="text-xs text-slate-400">{shown.length} nodes · {flowEdges.length} links</p></header>
 {error&&<p role="alert" className="mt-4 text-red-300">{error}</p>}<div className="mt-4 flex flex-wrap gap-2">{[...new Set(nodes.map(n=>n.node_type))].map(t=><button key={t} aria-pressed={types.has(t)} onClick={()=>toggle(t)} className={`rounded-full px-3 py-1 text-xs ${types.has(t)?"bg-cyan-500 text-slate-950":"bg-slate-800"}`}>{t}</button>)}</div>
 <div className="mt-4 h-[560px] overflow-hidden rounded-xl border border-slate-800"><ReactFlow nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes} fitView onNodeDoubleClick={(_,n)=>setSelected(n.data as GraphNode)}><Background/><MiniMap/><Controls/></ReactFlow></div>
 {selected&&<aside className="mt-4 rounded-xl bg-slate-900 p-4"><div className="flex justify-between"><h3 className="font-semibold">{selected.title}</h3><button onClick={()=>setSelected(null)}>Close</button></div><p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{selected.body||"No notes"}</p><p className="mt-3 text-xs text-slate-500">Edits use the versioned node API so stale tabs cannot overwrite newer work.</p></aside>}</section>
}
