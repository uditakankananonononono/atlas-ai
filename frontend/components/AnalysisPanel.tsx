"use client";
// Module 16 analysis console (feature rows 1010-1034): runs tenant-bound,
// seeded analysis jobs and renders outputs alongside assumptions and limits.
import {useEffect,useState} from "react";
import {analysisApi,AnalysisJob,AnalysisMethodInfo} from "./executive-dashboard/analysis-api";
export default function AnalysisPanel({base="/api/v1"}:{base?:string}){
  const api=analysisApi(base);
  const [methods,setMethods]=useState<AnalysisMethodInfo[]>([]);
  const [method,setMethod]=useState("descriptive");
  const [dataText,setDataText]=useState('{"values":[1,2,3,4,5]}');
  const [paramsText,setParamsText]=useState("{}");
  const [seed,setSeed]=useState(0);
  const [jobs,setJobs]=useState<AnalysisJob[]>([]);
  const [selected,setSelected]=useState<AnalysisJob|null>(null);
  const [error,setError]=useState<string|null>(null);
  const refresh=()=>{api.jobs().then(setJobs).catch(e=>setError(String(e)));};
  useEffect(()=>{api.methods().then(ms=>{setMethods(ms);if(ms.length&&!ms.some(m=>m.method===method))setMethod(ms[0].method);}).catch(e=>setError(String(e)));refresh();},[]);
  const runJob=async()=>{
    setError(null);
    let data:Record<string,unknown>,params:Record<string,unknown>;
    try{data=JSON.parse(dataText);params=JSON.parse(paramsText);}catch(e){setError("data/params must be valid JSON objects");return;}
    if(typeof data!=="object"||data===null||Array.isArray(data)||typeof params!=="object"||params===null||Array.isArray(params)){setError("data/params must be JSON objects");return;}
    try{const job=await api.run({method,data,params,seed});setSelected(job);refresh();}catch(e){setError(String(e));}
  };
  const info=methods.find(m=>m.method===method);
  return <section aria-label="Analysis jobs">
    <h2>Analysis jobs (rows 1010-1034)</h2>
    <p>Bounded reference analytics. Every run stores its inputs, seed, assumptions and method limits; stochastic methods are reproducible per seed. Not a replacement for scipy/statsmodels/Stan.</p>
    {error&&<p role="alert">{error}</p>}
    <label>Method <select value={method} onChange={e=>setMethod(e.target.value)}>
      {methods.map(m=><option key={m.method} value={m.method}>{m.feature_row} {m.method} - {m.summary}</option>)}
    </select></label>
    {info&&<p>Required inputs: {info.required_inputs.join(", ")||"none"}</p>}
    <div><label>Data (JSON)<br/><textarea rows={4} cols={60} value={dataText} onChange={e=>setDataText(e.target.value)}/></label></div>
    <div><label>Params (JSON)<br/><textarea rows={2} cols={60} value={paramsText} onChange={e=>setParamsText(e.target.value)}/></label></div>
    <label>Seed <input type="number" value={seed} onChange={e=>setSeed(Number(e.target.value)||0)}/></label>
    <button onClick={runJob}>Run analysis</button>
    {selected&&<article aria-label="Latest result">
      <h3>{selected.feature_row} {selected.method} - {selected.status}</h3>
      {selected.error&&<p role="alert">{selected.error}</p>}
      {selected.output&&<>
        <pre>{JSON.stringify(selected.output,null,2)}</pre>
        <h4>Assumptions</h4>
        <ul>{((selected.output.assumptions as string[])??[]).map((a,i)=><li key={i}>{a}</li>)}</ul>
        <h4>Method limits</h4>
        <ul>{((selected.output.method_limits as string[])??[]).map((a,i)=><li key={i}>{a}</li>)}</ul>
      </>}
    </article>}
    <h3>Recent jobs</h3>
    <table><thead><tr><th>Row</th><th>Method</th><th>Status</th><th>Created</th></tr></thead>
      <tbody>{jobs.map(j=><tr key={j.id} onClick={()=>setSelected(j)} style={{cursor:"pointer"}}>
        <td>{j.feature_row}</td><td>{j.method}</td><td>{j.status}</td><td>{new Date(j.created_at).toLocaleString()}</td>
      </tr>)}</tbody></table>
  </section>;
}
