"""Broad AST mutation audit, reporting survivors without completeness claims.
Usage: python scripts/t_units_ast_battery.py START END OUTPUT
"""
import ast,copy,json,os,subprocess,sys,unittest,io,importlib
from pathlib import Path
root=Path(__file__).resolve().parents[1];p=root/'backend/app/modules/m20_general_cognitive_worker/training_data_units.py';source=p.read_text();tree=ast.parse(source)
mutants=[]
for index,node in enumerate(ast.walk(tree)):
    changes=[]
    if isinstance(node,ast.Constant):
        v=node.value
        if isinstance(v,bool):changes=[('bool flip',ast.Constant(not v))]
        elif isinstance(v,int):changes=[('integer +1',ast.Constant(v+1))]
        elif isinstance(v,str) and v:changes=[('string +X',ast.Constant(v+'X'))]
    elif isinstance(node,ast.Compare) and len(node.ops)==1:
        swaps={ast.Gt:ast.GtE,ast.GtE:ast.Gt,ast.Lt:ast.LtE,ast.LtE:ast.Lt,ast.Eq:ast.NotEq,ast.NotEq:ast.Eq,ast.In:ast.NotIn,ast.NotIn:ast.In,ast.Is:ast.IsNot,ast.IsNot:ast.Is}
        if type(node.ops[0]) in swaps:
            new=copy.deepcopy(node);new.ops=[swaps[type(node.ops[0])]()];changes=[('comparison',new)]
    elif isinstance(node,ast.BoolOp):
        new=copy.deepcopy(node);new.op=ast.And() if isinstance(node.op,ast.Or) else ast.Or();changes=[('boolean operator',new)]
    elif isinstance(node,ast.If):
        new=copy.deepcopy(node);new.test=ast.UnaryOp(ast.Not(),new.test);changes=[('negate if',new)]
    elif isinstance(node,ast.Raise):changes=[('raise to pass',ast.Pass())]
    elif isinstance(node,ast.Continue):changes=[('continue to pass',ast.Pass())]
    elif isinstance(node,ast.Return):changes=[('return None',ast.Return(ast.Constant(None)))]
    elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call):changes=[('delete call',ast.Pass())]
    for label,replacement in changes:
        mutants.append((index,getattr(node,'lineno',0),label,replacement))
start=int(sys.argv[1]);end=int(sys.argv[2]);out=sys.argv[3];results=[]
try:
    for number,(index,line,label,replacement) in list(enumerate(mutants))[start:end]:
        mutated=copy.deepcopy(tree);target=list(ast.walk(mutated))[index]
        class Replace(ast.NodeTransformer):
            def visit(self,n):
                if n is target:return copy.deepcopy(replacement)
                return super().visit(n)
        mutated=Replace().visit(mutated);ast.fix_missing_locations(mutated)
        p.write_text(ast.unparse(mutated)+'\n')
        for key in list(sys.modules):
            if key.startswith(('test_training_units','test_extra_guards','test_routes','test_audit_repair','training_data_units','tunit_routes_fixture')):sys.modules.pop(key,None)
        importlib.invalidate_caches()
        stream=io.StringIO()
        suite=unittest.defaultTestLoader.discover(str(root/'tests/t_units'))
        result=unittest.TextTestRunner(stream=stream).run(suite)
        class Run:pass
        run=Run();run.returncode=0 if result.wasSuccessful() else 1
        results.append({'number':number,'line':line,'mutation':label,'killed':run.returncode!=0,'exit':run.returncode,'source':source.splitlines()[line-1][:180] if line else ''})
        Path(out).write_text(json.dumps({'total_generated':len(mutants),'results':results,'survivors':[r for r in results if not r['killed']]},indent=2)+'\n')
finally:p.write_text(source)
Path(out).write_text(json.dumps({'total_generated':len(mutants),'start':start,'end':end,'results':results,'killed':sum(r['killed'] for r in results),'survivors':[r for r in results if not r['killed']]},indent=2)+'\n')
print('generated',len(mutants),'tested',len(results),'killed',sum(r['killed'] for r in results),'survivors',sum(not r['killed'] for r in results))
