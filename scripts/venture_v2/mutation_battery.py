"""Remove each explicit refusal and invert every guard comparison; test in-process.

Equivalent mutants and survivors are reported, never hidden. No product source writes.
"""
import ast
import importlib
import io
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'tests/venture_v2')]
from app.modules.m20_general_cognitive_worker.venture_v2 import engines, policy, transforms
mods=[policy,transforms,engines]
REFUSAL=policy.Refusal
original={m.__name__:Path(m.__file__).read_text() for m in mods}

def restore():
    for m in mods:
        exec(compile(original[m.__name__],m.__file__,'exec'),m.__dict__)
        m.Refusal=REFUSAL
    engines.guard=policy.guard; engines.number=policy.number; engines.text=policy.text; engines.citation=policy.citation
    engines.validate_url=policy.validate_url; engines.validate_behavior=transforms.validate_behavior; engines.transform=transforms.transform; engines.generate=transforms.generate
    transforms.number=policy.number; transforms.text=policy.text

def test_passes():
    suite=unittest.TestLoader().discover(str(ROOT/'tests/venture_v2'))
    r=unittest.TextTestRunner(stream=io.StringIO()).run(suite)
    return r.wasSuccessful()

class Mutator(ast.NodeTransformer):
    def __init__(self,line,kind):self.line=line;self.kind=kind;self.changed=False
    def visit_Raise(self,node):
        if node.lineno==self.line and self.kind=='remove_refusal':self.changed=True;return ast.copy_location(ast.Pass(),node)
        return node
    def visit_If(self,node):
        self.generic_visit(node)
        if node.lineno==self.line and self.kind=='invert_guard':node.test=ast.UnaryOp(op=ast.Not(),operand=node.test);self.changed=True
        return node

def main():
    restore()
    if not test_passes():raise SystemExit('baseline must pass')
    results=[]
    for m in mods:
        source=original[m.__name__]; tree=ast.parse(source)
        candidates=sorted({(n.lineno,'remove_refusal') for n in ast.walk(tree) if isinstance(n,ast.Raise) and isinstance(n.exc,ast.Call) and isinstance(n.exc.func,ast.Name) and n.exc.func.id=='Refusal'}|{(n.lineno,'invert_guard') for n in ast.walk(tree) if isinstance(n,ast.If)})
        for line,kind in candidates:
            restore();tree=ast.parse(source);mutator=Mutator(line,kind);tree=mutator.visit(tree);ast.fix_missing_locations(tree)
            try:
                exec(compile(tree,m.__file__,'exec'),m.__dict__)
                m.Refusal=REFUSAL
                engines.guard=policy.guard; engines.number=policy.number; engines.text=policy.text;engines.citation=policy.citation;engines.validate_url=policy.validate_url
                engines.validate_behavior=transforms.validate_behavior;engines.transform=transforms.transform;engines.generate=transforms.generate
                transforms.number=policy.number;transforms.text=policy.text
                killed=not test_passes(); outcome='killed' if killed else 'survived'
            except Exception as exc: outcome='invalid';reason=type(exc).__name__
            results.append({'module':m.__name__.split('.')[-1],'line':line,'mutation':kind,'outcome':outcome})
    restore();report={'baseline_passed':test_passes(),'mutants':len(results),'killed':sum(x['outcome']=='killed' for x in results),'survived':sum(x['outcome']=='survived' for x in results),'invalid':sum(x['outcome']=='invalid' for x in results),'results':results}
    output=ROOT/'audits/venture_v2/mutation-results.json';output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='results'})); print(json.dumps([x for x in results if x['outcome']!='killed'],indent=2))

if __name__=='__main__':main()
