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
