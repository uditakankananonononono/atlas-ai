"""Wider repair battery: constants, arithmetic/comparisons, guards/refusals.

All candidates reported; survivors are not called equivalent without review.
Supports deterministic shards to run independent in-process mutations in parallel.
"""
import ast,io,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'tests/venture_v2')]
from app.modules.m20_general_cognitive_worker.venture_v2 import engines,policy,transforms,store
MODS=[policy,transforms,engines,store];REFUSAL=policy.Refusal
ORIGINAL={m.__name__:Path(m.__file__).read_text() for m in MODS}

def bind():
    for m in MODS:m.Refusal=REFUSAL
    for name in ['guard','number','text','citation','validate_url']:setattr(engines,name,getattr(policy,name))
    for name in ['validate_behavior','transform','generate']:setattr(engines,name,getattr(transforms,name))
    transforms.number=policy.number;transforms.text=policy.text;store.text=policy.text
    for name in ['test_routes','test_pins','test_alternate_pins']:
        if name in sys.modules:sys.modules[name].ReportStore=store.ReportStore

def restore():
    for m in MODS:exec(compile(ORIGINAL[m.__name__],m.__file__,'exec'),m.__dict__)
    bind()

def tests():
    suite=unittest.TestLoader().discover(str(ROOT/'tests/venture_v2'));result=unittest.TextTestRunner(stream=io.StringIO()).run(suite)
    return result.wasSuccessful()

REPLACEMENTS={ast.Add:ast.Sub,ast.Sub:ast.Add,ast.Mult:ast.Add,ast.Div:ast.Mult,ast.Eq:ast.NotEq,ast.NotEq:ast.Eq,ast.Lt:ast.LtE,ast.LtE:ast.Lt,ast.Gt:ast.GtE,ast.GtE:ast.Gt,ast.In:ast.NotIn,ast.NotIn:ast.In,ast.Is:ast.IsNot,ast.IsNot:ast.Is}

def candidates(source):
    result=[]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Constant) and not (isinstance(node.value,str) and len(node.value)>300):
            if isinstance(node.value,(str,int,float,bool)) or node.value is None:result.append((node.lineno,node.col_offset,'constant'))
        if isinstance(node,ast.If):result.append((node.lineno,node.col_offset,'guard'))
        if isinstance(node,ast.Raise) and isinstance(node.exc,ast.Call) and isinstance(node.exc.func,ast.Name) and node.exc.func.id=='Refusal':result.append((node.lineno,node.col_offset,'refusal'))
        if isinstance(node,ast.BinOp) and type(node.op) in REPLACEMENTS:result.append((node.lineno,node.col_offset,'arithmetic'))
        if isinstance(node,ast.Compare):
            for i,op in enumerate(node.ops):
                if type(op) in REPLACEMENTS:result.append((node.lineno,node.col_offset,'comparison:'+str(i)))
    return sorted(result)

class Change(ast.NodeTransformer):
    def __init__(self,target):self.target=target
    def generic_visit(self,node):
        super().generic_visit(node)
        if (getattr(node,'lineno',-1),getattr(node,'col_offset',-1))!=self.target[:2]:return node
        kind=self.target[2]
        if kind=='constant' and isinstance(node,ast.Constant):
            v=node.value;node.value=not v if isinstance(v,bool) else (1 if v is None else (v+1 if isinstance(v,(int,float)) else v+'__mutant'))
        elif kind=='guard' and isinstance(node,ast.If):node.test=ast.UnaryOp(op=ast.Not(),operand=node.test)
        elif kind=='refusal' and isinstance(node,ast.Raise):return ast.copy_location(ast.Pass(),node)
        elif kind=='arithmetic' and isinstance(node,ast.BinOp):node.op=REPLACEMENTS[type(node.op)]()
        elif kind.startswith('comparison:') and isinstance(node,ast.Compare):i=int(kind.split(':')[1]);node.ops[i]=REPLACEMENTS[type(node.ops[i])]()
        return node

def main():
    shard=int(sys.argv[1]) if len(sys.argv)>1 else 0;shards=int(sys.argv[2]) if len(sys.argv)>2 else 1
    restore()
    if not tests():raise SystemExit('baseline not green')
    survivors=None
    if '--survivors' in sys.argv:
        previous=json.loads((ROOT/'audits/venture_v2/repair-mutation-results.json').read_text())
        survivors={(r['module'],r['line'],r['column'],r['kind']) for r in previous['results'] if r['outcome']=='survived'}
    rows=[];counter=0
    for m in MODS:
        for target in candidates(ORIGINAL[m.__name__]):
            counter+=1
            if (counter-1)%shards!=shard:continue
            if survivors is not None and (m.__name__.split('.')[-1],*target) not in survivors:continue
            restore();tree=Change(target).visit(ast.parse(ORIGINAL[m.__name__]));ast.fix_missing_locations(tree)
            try:
                exec(compile(tree,m.__file__,'exec'),m.__dict__);bind();outcome='survived' if tests() else 'killed'
            except Exception as exc:outcome='invalid';error=type(exc).__name__
            rows.append({'module':m.__name__.split('.')[-1],'line':target[0],'column':target[1],'kind':target[2],'outcome':outcome})
    restore();report={'shard':shard,'shards':shards,'total_candidates':counter,'baseline_passed':tests(),'mutants':len(rows),'killed':sum(r['outcome']=='killed' for r in rows),'survived':sum(r['outcome']=='survived' for r in rows),'invalid':sum(r['outcome']=='invalid' for r in rows),'results':rows}
    prefix='survivors' if survivors is not None else 'mutation'
    path=ROOT/f'audits/venture_v2/repair-{prefix}-shard-{shard}.json';path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='results'}))
if __name__=='__main__':main()
