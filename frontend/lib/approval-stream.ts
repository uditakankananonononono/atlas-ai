import {authFetch} from './supabase';
export type StreamState='connecting'|'connected'|'reconnecting'|'disconnected'|'auth-required';
const allowed=new Set(['approval_request','approval_decision','approval_expired']);
export class ApprovalFrameParser{
 private buffer='';
 private decoder=new TextDecoder();
 constructor(private onSignal:()=>void,private cap=65536){}
 push(chunk:Uint8Array){
  this.buffer+=this.decoder.decode(chunk,{stream:true});
  // Count UTF8 bytes, not JS characters. Cap before retaining unbounded frames.
  if(new TextEncoder().encode(this.buffer).length>this.cap)throw new Error('Approval stream frame exceeds limit');
  this.buffer=this.buffer.replace(/\r\n/g,'\n');
  let end:number;
  while((end=this.buffer.indexOf('\n\n'))>=0){
   const frame=this.buffer.slice(0,end);this.buffer=this.buffer.slice(end+2);
   const data=frame.split('\n').filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trimStart()).join('\n');
   if(!data)continue;
   let event:unknown;try{event=JSON.parse(data)}catch{continue}
   if(event&&typeof event==='object'){
    const value=event as Record<string,unknown>;
    if(Object.keys(value).sort().join(',')==='approval_id,type'&&typeof value.type==='string'&&allowed.has(value.type)&&typeof value.approval_id==='string'&&value.approval_id.length>0&&value.approval_id.length<=120)this.onSignal();
   }
  }
 }
}
export function startApprovalStream(url:string,onSignal:()=>void,onState:(state:StreamState)=>void,
 options:{fetcher?:typeof authFetch;delays?:number[]}={}){
 const controller=new AbortController();const fetcher=options.fetcher??authFetch;const delays=options.delays??[1000,2000,4000];
 let reader:ReadableStreamDefaultReader<Uint8Array>|undefined;let timer:ReturnType<typeof setTimeout>|undefined;
 const pause=(ms:number)=>new Promise<void>(resolve=>{
  timer=setTimeout(resolve,ms);
  controller.signal.addEventListener('abort',()=>{if(timer)clearTimeout(timer);resolve()},{once:true});
 });
 void (async()=>{
  for(let attempt=0;attempt<=delays.length&&!controller.signal.aborted;attempt++){
   onState(attempt?'reconnecting':'connecting');
   try{
    const response=await fetcher(url,{signal:controller.signal,headers:{Accept:'text/event-stream'}});
    if(controller.signal.aborted)return;
    if(response.status===401||response.status===403){onState('auth-required');return}
    if(!response.ok||!response.body||!response.headers.get('content-type')?.includes('text/event-stream'))throw new Error('Approval stream unavailable');
    onState('connected');onSignal();
    const parser=new ApprovalFrameParser(()=>{if(!controller.signal.aborted)onSignal()});
    reader=response.body.getReader();
    while(!controller.signal.aborted){const {done,value}=await reader.read();if(done)break;if(value)parser.push(value)}
   }catch{if(controller.signal.aborted)return}
   finally{await reader?.cancel().catch(()=>{});reader=undefined}
   if(attempt<delays.length&&!controller.signal.aborted){onState('reconnecting');await pause(delays[attempt])}
  }
  if(!controller.signal.aborted)onState('disconnected');
 })();
 return ()=>{controller.abort();if(timer)clearTimeout(timer);void reader?.cancel().catch(()=>{})};
}
