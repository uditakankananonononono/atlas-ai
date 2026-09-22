import {authFetch} from "../lib/supabase";
// Typed client for the M20 goal-first product orchestration API.
export type GoalSource={id:string;uri:string;note:string};
export type PlanStep={id:string;title:string;action_type:string;risk:string;citations:string[];detail:string};
export type Goal={id:string;tenant_id:string;statement:string;status:string;created_at:string;sources:GoalSource[];steps:PlanStep[];approval_id:string|null};
export type LedgerItem={id:string;claim:string;state:string;evidence_ids:string[];verifier:string|null;source_module:string|null};
export type ExecutionState={goal_id:string;tenant_id:string;statement:string;status:string;approval_id:string|null;approval_decision:string|null;errors:Record<string,string>;ledger:{counts:Record<string,number>;highest_observed_state:string|null;items:LedgerItem[];verified_fraction:number;boundary:string}};
export class ApiError extends Error{constructor(public status:number,public detail:string){super(detail)}}
async function req<T>(path:string,init?:RequestInit):Promise<T>{
  const r=await authFetch(path,init);
  if(!r.ok){let detail=`${init?.method??"GET"} ${path} failed: ${r.status}`;try{const body=await r.json();if(body?.detail)detail=typeof body.detail==="string"?body.detail:JSON.stringify(body.detail)}catch{}throw new ApiError(r.status,detail)}
  return r.json() as Promise<T>;
}
const json=(body:unknown):RequestInit=>({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
export const goalWorkspaceApi=(base:string="/api/v1/product-orchestrator")=>({
  createGoal:(statement:string,sources:{uri:string;note?:string}[])=>req<Goal>(`${base}/goals`,json({statement,sources})),
  getGoal:(id:string)=>req<Goal>(`${base}/goals/${encodeURIComponent(id)}`),
  buildPlan:(id:string,steps:{title:string;action_type:string;citations:string[];risk?:string;detail?:string}[])=>req<Goal>(`${base}/goals/${encodeURIComponent(id)}/plan`,json({steps})),
  requestApproval:(id:string)=>req<{goal_id:string;approval_id:string}>(`${base}/goals/${encodeURIComponent(id)}/approval-requests`,{method:"POST"}),
  execute:(id:string,approvalId:string)=>req<{goal_id:string;status:string;failed_steps:number}>(`${base}/goals/${encodeURIComponent(id)}/executions`,json({approval_id:approvalId})),
  executionState:(id:string)=>req<ExecutionState>(`${base}/goals/${encodeURIComponent(id)}/execution-state`),
});
