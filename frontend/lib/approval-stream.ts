import {authFetch} from './supabase';
export type StreamState='connecting'|'connected'|'reconnecting'|'disconnected'|'auth-required';
const allowed=new Set(['approval_request','approval_decision','approval_expired']);
export class ApprovalFrameParser{
 private buffer='';
 private decoder=new TextDecoder();
 constructor(private onSignal:()=>void,private cap=65536){}
 push(chunk:Uint8Array){
  // Slice input so one transport chunk containing many valid frames never
  // becomes one giant retained buffer. Process frames between bounded slices.
  for(let offset=0;offset<chunk.length;offset+=4096){
   this.consume(this.decoder.decode(chunk.subarray(offset,offset+4096),{stream:true}));
  }
 }
 private consume(text:string){
  this.buffer+=text;
  this.buffer=this.buffer.replace(/\r\n/g,'\n');
  let end:number;
  while((end=this.buffer.indexOf('\n\n'))>=0){
   const frame=this.buffer.slice(0,end);this.buffer=this.buffer.slice(end+2);
   const data=frame.split('\n').filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trimStart()).join('\n');
   if(new TextEncoder().encode(frame).length>this.cap)throw new Error('Approval stream frame exceeds limit');
   if(!data)continue;
   let event:unknown;try{event=JSON.parse(data)}catch{continue}
   if(event&&typeof event==='object'){
    const value=event as Record<string,unknown>;
    if(Object.keys(value).sort().join(',')==='approval_id,type'&&typeof value.type==='string'&&allowed.has(value.type)&&typeof value.approval_id==='string'&&value.approval_id.length>0&&value.approval_id.length<=120)this.onSignal();
   }
  }
  if(new TextEncoder().encode(this.buffer).length>this.cap)throw new Error('Approval stream frame exceeds limit');
 }
}
export function startApprovalStream(url:string,onSignal:()=>void,onState:(state:StreamState)=>void,
 options:{fetcher?:typeof authFetch;delays?:number[];idleTimeoutMs?:number}={}){
 const idleTimeoutMs=options.idleTimeoutMs??45000; // Three server heartbeat intervals.
 if(!Number.isFinite(idleTimeoutMs)||idleTimeoutMs<=0)throw new Error('Approval stream timeout must be positive and finite');
 const controller=new AbortController();const fetcher=options.fetcher??authFetch;const delays=options.delays??[1000,2000,4000];
 let reader:ReadableStreamDefaultReader<Uint8Array>|undefined;let timer:ReturnType<typeof setTimeout>|undefined;
 const pause=(ms:number)=>new Promise<void>(resolve=>{
  const done=()=>{if(timer)clearTimeout(timer);controller.signal.removeEventListener('abort',done);resolve()};
  timer=setTimeout(done,ms);controller.signal.addEventListener('abort',done,{once:true});
 });
 void (async()=>{
  for(let attempt=0;attempt<=delays.length&&!controller.signal.aborted;attempt++){
   onState(attempt?'reconnecting':'connecting');
   const attemptController=new AbortController();
   let idleTimer:ReturnType<typeof setTimeout>|undefined;
   let rejectDeadline:(error:Error)=>void=()=>{};
   const deadline=new Promise<never>((_resolve,reject)=>{rejectDeadline=reject});
   const stopAttempt=()=>{rejectDeadline(new Error('Approval stream stopped'));attemptController.abort()};
   controller.signal.addEventListener('abort',stopAttempt,{once:true});
   const armDeadline=()=>{
    if(idleTimer)clearTimeout(idleTimer);
    idleTimer=setTimeout(()=>{
     rejectDeadline(new Error('Approval stream inactive'));attemptController.abort();
     void reader?.cancel().catch(()=>{});
    },idleTimeoutMs);
   };
   try{
    armDeadline(); // Includes waiting for response headers, not only the body.
    const response=await Promise.race([fetcher(url,{signal:attemptController.signal,headers:{Accept:'text/event-stream'}}),deadline]);
    if(controller.signal.aborted)return;
    if(response.status===401||response.status===403){onState('auth-required');return}
    if(!response.ok||!response.body||!response.headers.get('content-type')?.includes('text/event-stream'))throw new Error('Approval stream unavailable');
    onState('connected');onSignal();armDeadline();
    const parser=new ApprovalFrameParser(()=>{if(!controller.signal.aborted)onSignal()});
    reader=response.body.getReader();
    while(!controller.signal.aborted){
     const {done,value}=await Promise.race([reader.read(),deadline]);
     if(done)break;
     if(value?.byteLength){armDeadline();parser.push(value)}
    }
   }catch{if(controller.signal.aborted)return}
   finally{
    if(idleTimer)clearTimeout(idleTimer);
    controller.signal.removeEventListener('abort',stopAttempt);attemptController.abort();
    void reader?.cancel().catch(()=>{});reader=undefined;
   }
   if(attempt<delays.length&&!controller.signal.aborted){onState('reconnecting');await pause(delays[attempt])}
  }
  if(!controller.signal.aborted)onState('disconnected');
 })();
 return ()=>{controller.abort();if(timer)clearTimeout(timer);void reader?.cancel().catch(()=>{})};
}
