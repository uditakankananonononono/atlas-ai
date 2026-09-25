"use client";
import {useState} from "react";
import {authFetch} from "../lib/supabase";

const tools=[
 ["deadline_triage","Deadline triage",{today:"2026-09-25",deadlines:[{id:"essay",due:"2026-10-01"}]}],
 ["workload_calendar","Weekly workload",{weeks:4,total_hours:20,max_hours_per_week:12}],
 ["requirement_gap","Requirement gaps",{required:["transcript","essay"],completed:["essay"]}],
 ["school_list_balance","School-list labels",{schools:[{name:"Example",student_assessed_category:"target"}]}],
 ["program_language_fit","Language of instruction",{languages:["English"],programs:[{id:"p",instruction_language:"English"}]}],
 ["tuition_scenario","Cost scenario",{tuition:20000,living:10000,confirmed_aid:5000,years:4,currency:"USD"}],
 ["scholarship_eligibility","Scholarship criteria",{student_facts:{country:"IN"},scholarships:[{id:"s",requirements:{country:"IN"},source:"https://example.edu"}]}],
 ["document_inventory","Document inventory",{requirements:[{kind:"transcript"}],documents:[]}],
 ["recommender_timeline","Recommender timeline",{due:"2026-10-20",lead_days:21}],
 ["essay_prompt_matrix","Prompt-evidence map",{prompts:[{id:"p",text:"Describe your research project"}],evidence:[{id:"e",description:"Research project",student_confirmed:true}]}],
 ["essay_overlap","Student-draft overlap",{drafts:[{id:"one",student_text:"My experience in research"},{id:"two",student_text:"My experience in service"}]}],
 ["word_limit","Essay word count",{student_text:"My student-written draft",limit:650}],
 ["activity_evidence","Activity evidence",{activities:[{id:"a",description:"Science fair",source:"student record",student_confirmed:true}]}],
 ["interview_question_bank","Interview practice questions",{activities:[{id:"a",title:"robotics",student_confirmed:true}]}],
 ["application_status","Application status rollup",{applications:[{id:"a",status:"in_progress"}]}],
 ["decision_comparison","Compare confirmed offers",{offers:[{id:"a",annual_cost:30000,confirmed_aid:12000}]}],
 ["visa_checklist","Visa source review",{requirements:[{id:"r",official_url:"https://example.gov"}]}],
 ["source_freshness","Source freshness",{today:"2026-09-25",max_age_days:90,sources:[{id:"s",checked_on:"2026-09-01"}]}],
 ["source_domain_check","Source URL inspection",{sources:[{id:"s",url:"https://example.edu",official:true}]}],
 ["privacy_minimization","Sensitive field check",{records:[{id:"r",ssn:"remove before sharing"}]}],
] as const;
export default function StudyAbroadPlanning(){
 const [selected,setSelected]=useState(0),[payload,setPayload]=useState<string>(JSON.stringify(tools[0][2],null,2)),[result,setResult]=useState(""),[busy,setBusy]=useState(false);
 async function run(){setBusy(true);setResult("");try{const data=JSON.parse(payload);const response=await authFetch(`/api/v1/study-abroad/planning/${tools[selected][0]}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({data}),cache:"no-store"});setResult(`${response.status}\n${JSON.stringify(await response.json(),null,2)}`)}catch(e){setResult(`Unable to run: ${String(e)}`)}finally{setBusy(false)}}
 return <section className="my-5 rounded-xl border border-slate-700 bg-slate-900 p-5" aria-label="Study abroad planning tools"><h3 className="text-xl font-semibold">Application planning tools</h3><p className="mt-2 text-sm text-slate-300">20 tools for student-supplied facts. Replace the sample JSON with your own data. These are planning checks, not admission predictions or submissions.</p><label className="mt-3 block text-sm">Tool<select className="mt-1 w-full rounded border border-slate-600 bg-slate-950 p-2" value={selected} onChange={e=>{const n=Number(e.target.value);setSelected(n);setPayload(JSON.stringify(tools[n][2],null,2));setResult("")}}>{tools.map(([id,label],i)=><option key={id} value={i}>{label}</option>)}</select></label><label className="mt-3 block text-sm">Student-supplied data (JSON)<textarea className="mt-1 w-full rounded border border-slate-600 bg-slate-950 p-2 font-mono text-xs" rows={7} spellCheck={false} value={payload} onChange={e=>setPayload(e.target.value)}/></label><button className="mt-3 rounded bg-cyan-400 px-3 py-2 text-slate-950 disabled:opacity-40" disabled={busy} onClick={run}>{busy?"Checking...":"Run planning check"}</button><pre aria-live="polite" className="mt-3 overflow-auto whitespace-pre-wrap rounded bg-black/40 p-3 text-xs">{result}</pre></section>
}
