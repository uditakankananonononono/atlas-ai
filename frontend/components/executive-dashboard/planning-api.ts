// Typed client for Module 16 planning & measurement endpoints (rows 388-399).
export type WorkItem={id:string;title:string;item_type:string;status:string;estimate:number|null;reach:number|null;impact:number|null;confidence:number|null;effort:number|null;value:number|null;sprint_id:string|null;roadmap_id:string|null;planned_start:string|null;planned_end:string|null;rank:number;created_at:string;updated_at:string;completed_at:string|null};
export type PrioritizedItem={item:WorkItem;method:string;score:number|null;inputs:Record<string,number|null>;formula:string;missing_inputs:string[]};
export type Sprint={id:string;name:string;goal:string;start:string;end:string;capacity_points:number|null;status:string;closed_at:string|null};
export type BurndownReport={sprint_id:string;series:{day:string;ideal_remaining:number;actual_remaining:number;total_committed:number}[];assumptions:string[]};
export type VelocityReport={sprints:{sprint_id:string;sprint_name:string;committed_points:number;completed_points:number}[];average_completed:number|null;inputs:Record<string,unknown>};
export type Experiment={id:string;name:string;hypothesis:string;metric:string;kind:string;variants:{key:string;name:string;allocation:number;factors:Record<string,string>;trials:number;successes:number}[];status:string;created_at:string;updated_at:string};
export type SignificanceReport={test:string;p_value:number|null;significant:boolean;alpha:number;uplift:number|null;confidence_interval:[number,number]|null;inputs:Record<string,unknown>;assumptions:string[]};
async function req<T>(base:string,path:string,init?:RequestInit):Promise<T>{
  const r=await fetch(`${base}${path}`,init);
  if(!r.ok)throw new Error(`${init?.method??"GET"} ${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}
const post=(body?:unknown):RequestInit=>({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body??{})});
export const planningApi=(base:string="/api/v1")=>{
  const p=`/executive-dashboard/planning`;
  return {
    items:(sprintId?:string)=>req<WorkItem[]>(base,`${p}/items${sprintId?`?sprint_id=${encodeURIComponent(sprintId)}`:""}`),
    createItem:(item:Partial<WorkItem>&{title:string})=>req<WorkItem>(base,`${p}/items`,post(item)),
    move:(id:string,column:string)=>req<WorkItem>(base,`${p}/items/${encodeURIComponent(id)}/move?column=${encodeURIComponent(column)}`,{method:"POST"}),
    prioritization:(method:string)=>req<PrioritizedItem[]>(base,`${p}/prioritization?method=${encodeURIComponent(method)}`),
    sprints:()=>req<Sprint[]>(base,`${p}/sprints`),
    burndown:(id:string)=>req<BurndownReport>(base,`${p}/sprints/${encodeURIComponent(id)}/burndown`),
    velocity:()=>req<VelocityReport>(base,`${p}/velocity`),
    experiments:()=>req<Experiment[]>(base,`${p}/experiments`),
    significance:(id:string)=>req<SignificanceReport>(base,`${p}/experiments/${encodeURIComponent(id)}/significance`),
  };
};
