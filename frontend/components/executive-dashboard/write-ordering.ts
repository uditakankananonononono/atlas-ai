// Ordered, base-versioned writes for the executive dashboard.
// Rules (each one is exercised in write-ordering.test.tsx):
//  1. Writes for one key run one at a time, in the order they were enqueued.
//  2. A write carries the server version it was made against ("base"). If a
//     newer version is already known for the key, the write is NOT sent and
//     ends as "stale_base". Two writes made on the same base therefore cannot
//     both go out: the second one ends as "stale_base" once the first commits.
//  3. Cancelling a queued write removes it ("cancelled", nothing was sent).
//  4. Cancelling a write that was already issued only aborts the client side
//     request. The server may still have applied it, so the result is
//     "abort_requested_outcome_unknown" and the key is blocked until
//     reconcile() is given a version read back from the server.
export type WriteStatus="committed"|"stale_base"|"cancelled"|"abort_requested_outcome_unknown"|"failed"|"blocked_needs_reconcile";
export type WriteResult<T>={id:string;key:string;base:number;status:WriteStatus;version?:number;value?:T;error?:string};
type Job<T>={id:string;key:string;base:number;run:(signal:AbortSignal)=>Promise<{version:number;value:T}>;ctrl:AbortController;issued:boolean;cancelled:boolean;settle:(r:WriteResult<T>)=>void};
export class WriteSequencer<T=unknown>{
  private known=new Map<string,number>();
  private queues=new Map<string,Job<T>[]>();
  private running=new Set<string>();
  private blocked=new Set<string>();
  private byId=new Map<string,Job<T>>();
  private n=0;
  constructor(initial:Record<string,number>={}){for(const[k,v]of Object.entries(initial))this.known.set(k,v);}
  knownVersion(key:string):number|undefined{return this.known.get(key);}
  needsReconcile(key:string):boolean{return this.blocked.has(key);}
  enqueue(key:string,base:number,run:(signal:AbortSignal)=>Promise<{version:number;value:T}>):{id:string;result:Promise<WriteResult<T>>}{
    const id=`w${++this.n}`;
    let settle!:(r:WriteResult<T>)=>void;
    const result=new Promise<WriteResult<T>>(res=>{settle=res;});
    const job:Job<T>={id,key,base,run,ctrl:new AbortController(),issued:false,cancelled:false,settle};
    this.byId.set(id,job);
    if(!this.queues.has(key))this.queues.set(key,[]);
    this.queues.get(key)!.push(job);
    void this.pump(key);
    return {id,result};
  }
  cancel(id:string):"cancelled"|"abort_requested"|"unknown_id"|"already_finished"{
    const job=this.byId.get(id);
    if(!job)return "unknown_id";
    if(job.cancelled)return "already_finished";
    job.cancelled=true;
    if(!job.issued){
      const q=this.queues.get(job.key)!;
      q.splice(q.indexOf(job),1);
      this.byId.delete(id);
      job.settle({id,key:job.key,base:job.base,status:"cancelled"});
      return "cancelled";
    }
    job.ctrl.abort();
    return "abort_requested";
  }
  // Give the key a version read back from the server and unblock it.
  reconcile(key:string,serverVersion:number):void{
    const cur=this.known.get(key);
    if(cur===undefined||serverVersion>cur)this.known.set(key,serverVersion);
    else this.known.set(key,Math.max(cur,serverVersion));
    this.blocked.delete(key);
    void this.pump(key);
  }
  private async pump(key:string):Promise<void>{
    if(this.running.has(key))return;
    this.running.add(key);
    try{
      const q=this.queues.get(key)??[];
      while(q.length){
        const job=q[0];
        if(this.blocked.has(key)){
          q.shift();this.byId.delete(job.id);
          job.settle({id:job.id,key,base:job.base,status:"blocked_needs_reconcile"});
          continue;
        }
        const known=this.known.get(key);
        if(known!==undefined&&job.base<known){
          q.shift();this.byId.delete(job.id);
          job.settle({id:job.id,key,base:job.base,status:"stale_base",version:known});
          continue;
        }
        job.issued=true;
        let r:WriteResult<T>;
        try{
          const out=await job.run(job.ctrl.signal);
          if(job.cancelled){
            // The request finished anyway: the server applied it. Record the truth.
            this.known.set(key,Math.max(this.known.get(key)??0,out.version));
            r={id:job.id,key,base:job.base,status:"committed",version:out.version,value:out.value};
          }else{
            this.known.set(key,Math.max(this.known.get(key)??0,out.version));
            r={id:job.id,key,base:job.base,status:"committed",version:out.version,value:out.value};
          }
        }catch(e){
          if(job.cancelled){this.blocked.add(key);r={id:job.id,key,base:job.base,status:"abort_requested_outcome_unknown"};}
          else r={id:job.id,key,base:job.base,status:"failed",error:e instanceof Error?e.message:String(e)};
        }
        q.shift();this.byId.delete(job.id);
        job.settle(r);
      }
    }finally{this.running.delete(key);}
  }
}
