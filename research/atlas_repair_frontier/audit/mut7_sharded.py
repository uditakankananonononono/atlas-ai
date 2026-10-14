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
seen={};surv=[];killed=0;run=0;dup=0
base=ast.unparse(tree)
work='/tmp/a/work_'+os.path.basename(root.rstrip('/'))+'_'+os.environ['SHARD'];
for desc,m in muts:
    try:code=build(m)
    except Exception as e:continue
    if code==base or code in seen:dup+=1;continue
    seen[code]=1
    if (len(seen)-1) % 8 != int(os.environ['SHARD']):continue
    if os.path.exists(work):shutil.rmtree(work)
    shutil.copytree(root,work,ignore=shutil.ignore_patterns('.git'))
    open(os.path.join(work,modrel),'w').write(code)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.path.join(work,'backend'))
    try:
        r=subprocess.run([sys.executable,'-m','pytest','-q','-x','-p','no:cacheprovider']+__import__('shlex').split(os.environ.get('PYTEST_EXTRA',''))+[os.environ.get('TESTS','tests')],cwd=work,env=env,capture_output=True,timeout=20)
        ok=r.returncode==0
    except subprocess.TimeoutExpired:ok=False
    run+=1
    if ok:surv.append(desc)
    else:killed+=1
print(json.dumps({'run':run,'killed':killed,'dups_skipped':dup,'survivors':surv},indent=1))
