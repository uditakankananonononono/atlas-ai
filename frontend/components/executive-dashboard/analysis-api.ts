// Typed client for Module 16 tenant-bound analysis jobs (feature rows 1010-1034).
export type AnalysisMethodInfo={method:string;feature_row:number;summary:string;required_inputs:string[];limits:string[]};
export type AnalysisJob={id:string;method:string;feature_row:number;data:Record<string,unknown>;params:Record<string,unknown>;seed:number;status:"completed"|"failed";output:Record<string,unknown>|null;error:string|null;created_at:string;completed_at:string|null};
async function req<T>(base:string,path:string,init?:RequestInit):Promise<T>{
  const r=await fetch(`${base}${path}`,init);
  if(!r.ok)throw new Error(`${init?.method??"GET"} ${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}
const post=(body:unknown):RequestInit=>({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
export const analysisApi=(base:string="/api/v1")=>{
  const p=`/executive-dashboard/analysis`;
  return {
    methods:()=>req<AnalysisMethodInfo[]>(base,`${p}/methods`),
    run:(job:{method:string;data:Record<string,unknown>;params?:Record<string,unknown>;seed?:number})=>req<AnalysisJob>(base,`${p}/jobs`,post({params:{},seed:0,...job})),
    jobs:(method?:string)=>req<AnalysisJob[]>(base,`${p}/jobs${method?`?method=${encodeURIComponent(method)}`:""}`),
    job:(id:string)=>req<AnalysisJob>(base,`${p}/jobs/${encodeURIComponent(id)}`),
  };
};
