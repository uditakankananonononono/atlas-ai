import {describe,it,expect,vi} from 'vitest';
import {ApprovalFrameParser,startApprovalStream} from '../lib/approval-stream';
vi.mock('../lib/supabase',()=>({authFetch:vi.fn()}));
const encode=(x:string)=>new TextEncoder().encode(x);
describe('bounded authenticated approval stream',()=>{
 it('parses split UTF8/CRLF frames and only exact approved signals',()=>{
  const signal=vi.fn(),parser=new ApprovalFrameParser(signal);
  parser.push(encode(': heartbeat\r\n\r\ndata: {"type":"approval_'));parser.push(encode('request","approval_id":"a"}\r'));parser.push(encode('\n\r\n'));
  expect(signal).toHaveBeenCalledTimes(1);
  for(const value of [{type:'unknown',approval_id:'a'},{type:'approval_request',approval_id:'a',approval:{payload:'injected'}},{type:'approval_request',approval_id:'a',tenant_id:'foreign'}])parser.push(encode(`data: ${JSON.stringify(value)}\n\n`));
  expect(signal).toHaveBeenCalledTimes(1);
  expect(()=>new ApprovalFrameParser(signal,10).push(encode('data: oversized frame'))).toThrow();
 });
 it('drains a large chunk of small frames without exceeding the per-frame cap',()=>{
  const signal=vi.fn(),parser=new ApprovalFrameParser(signal,256);
  const frame='data: {"type":"approval_request","approval_id":"a"}\n\n';
  parser.push(encode(frame.repeat(2000)));
  expect(signal).toHaveBeenCalledTimes(2000);
  expect(()=>parser.push(encode('data: '+ 'x'.repeat(300)+'\n\n'))).toThrow();
 });
 it('has four total attempts even when every attempt connects briefly',async()=>{
  const states:string[]=[],signal=vi.fn();
  const fetcher=vi.fn(async(_url:RequestInfo|URL,_init?:RequestInit)=>new Response(new ReadableStream({start(c){c.enqueue(encode('data: {"type":"approval_decision","approval_id":"a"}\n\n'));c.close()}}),{headers:{'Content-Type':'text/event-stream'}}));
  const stop=startApprovalStream('/api/v1/approval-center/events',signal,s=>states.push(s),{fetcher,delays:[0,0,0]});
  await vi.waitFor(()=>expect(states.at(-1)).toBe('disconnected'));
  expect(fetcher).toHaveBeenCalledTimes(4);
  expect(signal).toHaveBeenCalledTimes(8); // connection refresh + one signal each
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/approval-center/events');
  stop();
 });
 it('auth failure stops immediately and abort cancels an active reader',async()=>{
  const states:string[]=[];const forbidden=vi.fn(async()=>new Response('',{status:401}));
  startApprovalStream('/stream',()=>{},s=>states.push(s),{fetcher:forbidden,delays:[0,0,0]});
  await vi.waitFor(()=>expect(states.at(-1)).toBe('auth-required'));expect(forbidden).toHaveBeenCalledTimes(1);
  const cancel=vi.fn(),signal=vi.fn();
  const live=vi.fn(async(_url:RequestInfo|URL,_init?:RequestInit)=>new Response(new ReadableStream({cancel}),{headers:{'Content-Type':'text/event-stream'}}));
  const stop=startApprovalStream('/stream',signal,()=>{},{fetcher:live});
  await vi.waitFor(()=>expect(signal).toHaveBeenCalled());stop();
  await vi.waitFor(()=>expect(cancel).toHaveBeenCalledTimes(1));expect(live).toHaveBeenCalledTimes(1);
 });
});

describe('approval stream inactivity recovery',()=>{
 it('cancels never-yielding bodies and exhausts exactly four attempts',async()=>{
  vi.useFakeTimers();
  const states:string[]=[],cancel=vi.fn(),signal=vi.fn();
  const fetcher=vi.fn(async()=>new Response(new ReadableStream({cancel}),{headers:{'Content-Type':'text/event-stream'}}));
  const stop=startApprovalStream('/stream',signal,s=>states.push(s),{fetcher,idleTimeoutMs:45,delays:[1,1,1]});
  try{
   await vi.advanceTimersByTimeAsync(0);expect(states.at(-1)).toBe('connected');
   await vi.advanceTimersByTimeAsync(184);
   expect(states.at(-1)).toBe('disconnected');expect(fetcher).toHaveBeenCalledTimes(4);
   expect(cancel).toHaveBeenCalledTimes(4);expect(signal).toHaveBeenCalledTimes(4);
   expect(vi.getTimerCount()).toBe(0);
  }finally{stop();vi.useRealTimers()}
 });
 it('heartbeat bytes reset inactivity without inventing approval signals',async()=>{
  vi.useFakeTimers();
  let stream:ReadableStreamDefaultController<Uint8Array>;
  const states:string[]=[],signal=vi.fn(),cancel=vi.fn();
  const fetcher=vi.fn(async()=>new Response(new ReadableStream<Uint8Array>({start(c){stream=c},cancel}),{headers:{'Content-Type':'text/event-stream'}}));
  const stop=startApprovalStream('/stream',signal,s=>states.push(s),{fetcher,idleTimeoutMs:45,delays:[]});
  try{
   await vi.advanceTimersByTimeAsync(0);
   for(let i=0;i<4;i++){
    await vi.advanceTimersByTimeAsync(30);stream!.enqueue(encode(': heartbeat\n\n'));await vi.advanceTimersByTimeAsync(0);
    expect(states.at(-1)).toBe('connected');
   }
   expect(signal).toHaveBeenCalledTimes(1);expect(fetcher).toHaveBeenCalledTimes(1);
   await vi.advanceTimersByTimeAsync(46);
   expect(states.at(-1)).toBe('disconnected');expect(cancel).toHaveBeenCalledTimes(1);
  }finally{stop();vi.useRealTimers()}
 });
 it('empty chunks do not prolong a silent connection',async()=>{
  vi.useFakeTimers();let stream:ReadableStreamDefaultController<Uint8Array>;
  const states:string[]=[];
  const fetcher=vi.fn(async()=>new Response(new ReadableStream<Uint8Array>({start(c){stream=c}}),{headers:{'Content-Type':'text/event-stream'}}));
  const stop=startApprovalStream('/stream',()=>{},s=>states.push(s),{fetcher,idleTimeoutMs:45,delays:[]});
  try{
   await vi.advanceTimersByTimeAsync(30);stream!.enqueue(new Uint8Array());await vi.advanceTimersByTimeAsync(16);
   expect(states.at(-1)).toBe('disconnected');
  }finally{stop();vi.useRealTimers()}
 });
 it('bounds stalled response headers even if a fixture ignores abort',async()=>{
  vi.useFakeTimers();const states:string[]=[];const signals:AbortSignal[]=[];
  const fetcher=vi.fn((_url:RequestInfo|URL,init?:RequestInit)=>{signals.push(init!.signal!);return new Promise<Response>(()=>{})});
  const stop=startApprovalStream('/stream',()=>{},s=>states.push(s),{fetcher,idleTimeoutMs:45,delays:[1,1,1]});
  try{
   await vi.advanceTimersByTimeAsync(184);
   expect(states.at(-1)).toBe('disconnected');expect(fetcher).toHaveBeenCalledTimes(4);
   expect(signals.every(s=>s.aborted)).toBe(true);expect(vi.getTimerCount()).toBe(0);
  }finally{stop();vi.useRealTimers()}
 });
 it('stop cancels activity timer and never retries or signals afterward',async()=>{
  vi.useFakeTimers();const states:string[]=[],signal=vi.fn(),cancel=vi.fn();
  const fetcher=vi.fn(async()=>new Response(new ReadableStream({cancel}),{headers:{'Content-Type':'text/event-stream'}}));
  const stop=startApprovalStream('/stream',signal,s=>states.push(s),{fetcher,idleTimeoutMs:45,delays:[1,1,1]});
  try{
   await vi.advanceTimersByTimeAsync(0);stop();const before=[...states];
   await vi.advanceTimersByTimeAsync(300);
   expect(states).toEqual(before);expect(signal).toHaveBeenCalledTimes(1);expect(fetcher).toHaveBeenCalledTimes(1);
   expect(cancel).toHaveBeenCalledTimes(1);expect(vi.getTimerCount()).toBe(0);
  }finally{stop();vi.useRealTimers()}
 });
 it('auth failure clears the timer and stops without retry',async()=>{
  vi.useFakeTimers();const states:string[]=[],signal=vi.fn();
  const fetcher=vi.fn(async()=>new Response('',{status:403}));
  const stop=startApprovalStream('/stream',signal,s=>states.push(s),{fetcher,idleTimeoutMs:45,delays:[1,1,1]});
  try{
   await vi.advanceTimersByTimeAsync(300);
   expect(states).toEqual(['connecting','auth-required']);expect(signal).not.toHaveBeenCalled();expect(fetcher).toHaveBeenCalledTimes(1);
   expect(vi.getTimerCount()).toBe(0);
  }finally{stop();vi.useRealTimers()}
 });
 it('a stuck cancellation hook cannot hold retry exhaustion hostage',async()=>{
  vi.useFakeTimers();const states:string[]=[];
  const fetcher=vi.fn(async()=>new Response(new ReadableStream({cancel(){return new Promise<void>(()=>{})}}),{headers:{'Content-Type':'text/event-stream'}}));
  const stop=startApprovalStream('/stream',()=>{},s=>states.push(s),{fetcher,idleTimeoutMs:45,delays:[1,1,1]});
  try{
   await vi.advanceTimersByTimeAsync(184);
   expect(states.at(-1)).toBe('disconnected');expect(fetcher).toHaveBeenCalledTimes(4);
  }finally{stop();vi.useRealTimers()}
 });
 it.each([0,-1,NaN,Infinity])('refuses invalid idle timeout %s',idleTimeoutMs=>{
  const fetcher=vi.fn();expect(()=>startApprovalStream('/stream',()=>{},()=>{},{fetcher,idleTimeoutMs})).toThrow();
  expect(fetcher).not.toHaveBeenCalled();
 });
});
