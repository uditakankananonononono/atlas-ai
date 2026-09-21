"use client";
import {ResponsiveContainer,LineChart,Line,XAxis,YAxis,Tooltip,CartesianGrid} from "recharts";
export default function OperationsChart({data}:{data:Array<{time:string;value:number}>}){return <div aria-label="Operations metric chart" className="h-64 w-full"><ResponsiveContainer><LineChart data={data}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="time"/><YAxis/><Tooltip/><Line type="monotone" dataKey="value" stroke="#22d3ee" dot={false}/></LineChart></ResponsiveContainer></div>}
