import ast,sys,os,subprocess,shutil,copy,json
root,modrel=sys.argv[1],sys.argv[2]
src=open(os.path.join(root,modrel)).read();tree=ast.parse(src)
SW={ast.Lt:[ast.LtE,ast.Gt],ast.LtE:[ast.Lt,ast.GtE],ast.Gt:[ast.GtE,ast.Lt],ast.GtE:[ast.Gt,ast.LtE],ast.Eq:[ast.NotEq],ast.NotEq:[ast.Eq],ast.Is:[ast.IsNot],ast.IsNot:[ast.Is],ast.In:[ast.NotIn],ast.NotIn:[ast.In]}
BIN={ast.Add:ast.Sub,ast.Sub:ast.Add,ast.Mult:ast.Add,ast.FloorDiv:ast.Mult,ast.Mod:ast.Mult}
muts=[]
nodes=list(ast.walk(tree))
def add(desc,fn):muts.append((desc,fn))
for idx,n in enumerate(nodes):
    ln=getattr(n,'lineno','?')
    if isinstance(n,ast.Compare):
        for k,op in enumerate(n.ops):
            for new in SW.get(type(op),[]):
                add(f'L{ln} cmp {type(op).__name__}->{new.__name__}',(idx,'cmp',k,new))
    elif isinstance(n,ast.Constant):
        v=n.value
        if isinstance(v,bool):add(f'L{ln} bool {v}',(idx,'const',not v))
        elif isinstance(v,int):
            for d in (1,-1):add(f'L{ln} int {v}->{v+d}',(idx,'const',v+d))
            if v!=0: add(f'L{ln} int {v}->0',(idx,'const',0))
        elif isinstance(v,str) and v:add(f'L{ln} str {v[:30]!r}',(idx,'const',v+'X'))
    elif isinstance(n,ast.BoolOp):
        add(f'L{ln} boolop',(idx,'boolop'))
    elif isinstance(n,ast.BinOp) and type(n.op) in BIN:
        add(f'L{ln} binop {type(n.op).__name__}',(idx,'binop'))
    elif isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.Not,ast.USub)):
        add(f'L{ln} unary drop {type(n.op).__name__}',(idx,'unary'))
    elif isinstance(n,(ast.If,ast.IfExp,ast.While)):
        add(f'L{ln} negate test',(idx,'negate'))
    elif isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('any','all','min','max','sorted','len','type','sum','tuple','list'):
        sw={'any':'all','all':'any','min':'max','max':'min','sorted':'list','sum':'len','len':'sum'}.get(n.func.id)
        if sw:add(f'L{ln} call {n.func.id}->{sw}',(idx,'call',sw))
    elif isinstance(n,(ast.Raise,ast.Expr,ast.Assign,ast.AugAssign,ast.Break,ast.Continue)) and not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant)):
        add(f'L{ln} del {type(n).__name__}',(idx,'del'))
    elif isinstance(n,ast.Return):
        add(f'L{ln} return None',(idx,'ret'))
def build(m):
    t=copy.deepcopy(tree);ns=list(ast.walk(t));n=ns[m[0]];k=m[1]
    if k=='cmp':n.ops[m[2]]=m[3]()
    elif k=='const':n.value=m[2]
    elif k=='boolop':n.op=ast.Or() if isinstance(n.op,ast.And) else ast.And()
    elif k=='binop':n.op=BIN[type(n.op)]()
    elif k=='unary':
        for p in ns:
            for f,v in ast.iter_fields(p):
                if v is n:setattr(p,f,n.operand)
                elif isinstance(v,list):
                    for i,x in enumerate(v):
                        if x is n:v[i]=n.operand
    elif k=='negate':n.test=ast.UnaryOp(ast.Not(),n.test)
    elif k=='call':n.func.id=m[2]
    elif k=='del':
        for p in ns:
            for f,v in ast.iter_fields(p):
                if isinstance(v,list):
                    for i,x in enumerate(v):
                        if x is n:
                            v[i]=ast.Pass() if len(v)>=1 else x
    elif k=='ret':n.value=ast.Constant(None)
    ast.fix_missing_locations(t);return ast.unparse(t)

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
started=time.monotonic()
seen=set();jobs=[];base=ast.unparse(tree);dups=0
for desc,m in muts:
    try:code=build(m)
    except Exception:continue
    if code==base or code in seen:dups+=1;continue
    seen.add(code);jobs.append((desc,code))
progress='/tmp/mutb-v2-progress.jsonl'
done={}
if os.path.exists(progress):
    for line in open(progress):
        row=json.loads(line);done[row['id']]=row

def evaluate(job):
    if time.monotonic()-started>35:return None
    idx,(desc,code)=job
    work='/tmp/a/bench_v2_'+str(idx)
    if os.path.exists(work):shutil.rmtree(work)
    shutil.copytree(root,work,ignore=shutil.ignore_patterns('.git','__pycache__'))
    open(os.path.join(work,modrel),'w').write(code)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.path.join(work,'backend'))
    code2="import sys;sys.path.insert(0,'research/atlas_repair_frontier');import run_benchmark as r;x=r.run()['results'];sys.exit(0 if (x['exact_total_utility'],x['scalarized_total_utility'],x['greedy_total_utility'],x['exact_strictly_beats_scalarized'],x['exact_strictly_beats_greedy'],x['full_replay_over_budget'],x['budget_violations'])==(288420,271475,285668,2200,909,4622,0) else 1)"
    try:
        r=subprocess.run([sys.executable,'-c',code2],cwd=work,env=env,capture_output=True,timeout=60)
        killed=r.returncode!=0;reason='nonzero' if killed else 'survived'
    except subprocess.TimeoutExpired:killed=True;reason='timeout60'
    return {'id':idx,'desc':desc,'killed':killed,'reason':reason}
with ThreadPoolExecutor(max_workers=8) as pool:
    fs=[pool.submit(evaluate,(i,job)) for i,job in enumerate(jobs) if i not in done]
    for f in as_completed(fs):
        row=f.result()
        if row is None:continue
        done[row['id']]=row
        with open(progress,'a') as out:out.write(json.dumps(row)+'\n');out.flush()
result={'run':len(done),'killed':sum(r['killed'] for r in done.values()),'dups_skipped':dups,'survivors':[r['desc'] for _,r in sorted(done.items()) if not r['killed']],'timeouts':sum(r['reason']=='timeout60' for r in done.values())}
print(json.dumps(result,indent=2))
