"use client";
import {ResponsiveContainer,BarChart,Bar,XAxis,YAxis,Tooltip,CartesianGrid} from "recharts";
type Metric={label:string;value:number;unit:string};
export default function OperationsChart({data}:{data:Metric[]}){
 const units=[...new Set(data.map(d=>d.unit))];
 return <div aria-label="Current KPI values by unit" className="space-y-5">{units.map(unit=><section key={unit} aria-label={`Current KPIs (${unit})`}><p className="mb-2 text-sm text-slate-300">Unit: {unit}</p><div className="h-64 w-full"><ResponsiveContainer><BarChart data={data.filter(d=>d.unit===unit)}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="label" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={{backgroundColor:"#0f172a",color:"#e2e8f0"}}/><Bar dataKey="value" fill="#22d3ee" isAnimationActive={false}/></BarChart></ResponsiveContainer></div></section>)}</div>;
}
