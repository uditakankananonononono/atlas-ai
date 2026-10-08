import {describe,expect,it} from "vitest";
import {WriteSequencer} from "./write-ordering";
const gate=()=>{let open!:()=>void;const p=new Promise<void>(r=>{open=r;});return {p,open};};
describe("WriteSequencer",()=>{
  it("runs same-key writes in order, never overlapping",async()=>{
    const s=new WriteSequencer<string>({k:1});const log:string[]=[];const g=gate();
    const a=s.enqueue("k",1,async()=>{log.push("a+");await g.p;log.push("a-");return {version:2,value:"a"};});
    const b=s.enqueue("k",2,async()=>{log.push("b+");return {version:3,value:"b"};});
    await Promise.resolve();expect(log).toEqual(["a+"]);
    g.open();const[ra,rb]=await Promise.all([a.result,b.result]);
    expect(log).toEqual(["a+","a-","b+"]);expect(ra.status).toBe("committed");expect(rb.version).toBe(3);
  });
  it("second write on the same base is not sent",async()=>{
    const s=new WriteSequencer<string>({k:5});let sent=0;
    const a=s.enqueue("k",5,async()=>{sent++;return {version:6,value:"a"};});
    const b=s.enqueue("k",5,async()=>{sent++;return {version:6,value:"b"};});
    expect((await a.result).status).toBe("committed");
    const rb=await b.result;expect(rb.status).toBe("stale_base");expect(rb.version).toBe(6);expect(sent).toBe(1);
  });
  it("cancel of a queued write sends nothing",async()=>{
    const s=new WriteSequencer<string>({k:1});const g=gate();let sentB=0;
    const a=s.enqueue("k",1,async()=>{await g.p;return {version:2,value:"a"};});
    const b=s.enqueue("k",2,async()=>{sentB++;return {version:3,value:"b"};});
    expect(s.cancel(b.id)).toBe("cancelled");g.open();await a.result;
    expect((await b.result).status).toBe("cancelled");expect(sentB).toBe(0);
  });
  it("cancel of an issued write is reported as unknown outcome and blocks the key until reconciled",async()=>{
    const s=new WriteSequencer<string>({k:1});
    const a=s.enqueue("k",1,(sig)=>new Promise((_,rej)=>{sig.addEventListener("abort",()=>rej(new Error("aborted")));}));
    await Promise.resolve();
    expect(s.cancel(a.id)).toBe("abort_requested");
    expect((await a.result).status).toBe("abort_requested_outcome_unknown");
    expect(s.needsReconcile("k")).toBe(true);
    let sent=0;
    const b=s.enqueue("k",1,async()=>{sent++;return {version:2,value:"b"};});
    expect((await b.result).status).toBe("blocked_needs_reconcile");expect(sent).toBe(0);
    s.reconcile("k",2); // server shows the aborted write had been applied
    const c=s.enqueue("k",1,async()=>{sent++;return {version:3,value:"c"};});
    expect((await c.result).status).toBe("stale_base");
    const d=s.enqueue("k",2,async()=>{sent++;return {version:3,value:"d"};});
    expect((await d.result).status).toBe("committed");expect(sent).toBe(1);
  });
  it("a cancelled write whose request still finished is reported committed, not cancelled",async()=>{
    const s=new WriteSequencer<string>({k:1});const g=gate();
    const a=s.enqueue("k",1,async()=>{await g.p;return {version:2,value:"a"};});
    await Promise.resolve();s.cancel(a.id);g.open();
    const r=await a.result;expect(r.status).toBe("committed");expect(s.knownVersion("k")).toBe(2);
  });
  it("failure does not advance the version; different keys are independent",async()=>{
    const s=new WriteSequencer<string>({k:1,j:1});
    const a=s.enqueue("k",1,async()=>{throw new Error("500");});
    const j=s.enqueue("j",1,async()=>({version:2,value:"j"}));
    expect((await a.result)).toMatchObject({status:"failed",error:"500"});expect(s.knownVersion("k")).toBe(1);
    expect((await j.result).status).toBe("committed");
  });
});
