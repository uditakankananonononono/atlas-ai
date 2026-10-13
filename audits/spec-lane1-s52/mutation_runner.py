import ast, pathlib, subprocess, json, copy, hashlib
repo=pathlib.Path(__file__).resolve().parents[2];path=repo/'backend/app/modules/c36/gaps.py'; original=path.read_text();tree=ast.parse(original)
mutations=[]
for node in ast.walk(tree):
    if isinstance(node, ast.Compare) and len(node.ops)==1:
        swaps={ast.Gt:ast.GtE,ast.GtE:ast.Gt,ast.Eq:ast.NotEq,ast.NotEq:ast.Eq,ast.In:ast.NotIn,ast.NotIn:ast.In,ast.Is:ast.IsNot,ast.IsNot:ast.Is}
        if type(node.ops[0]) in swaps:
            n=copy.deepcopy(node); n.ops=[swaps[type(node.ops[0])]()]; mutations.append((node,n,'compare'))
    elif isinstance(node, ast.If):
        n=copy.deepcopy(node.test); n=ast.UnaryOp(op=ast.Not(),operand=n); mutations.append((node.test,n,'branch'))
    elif isinstance(node,ast.Constant) and type(node.value) is int and node.value>0:
        mutations.append((node,ast.Constant(node.value+1),'limit+1'))
# Replace by exact source offsets to retain other code; one mutant per process.
lines=original.splitlines(keepends=True); offsets=[0]
for line in lines:offsets.append(offsets[-1]+len(line))
results=[]
try:
 for i,(node,replacement,kind) in enumerate(mutations):
    a=offsets[node.lineno-1]+node.col_offset;b=offsets[node.end_lineno-1]+node.end_col_offset

    for cache in path.parent.glob('__pycache__/gaps.*.pyc'):cache.unlink()
    mutated=original[:a]+ast.unparse(replacement)+original[b:];path.write_text(mutated)
    p=subprocess.run([__import__('sys').executable,'-m','pytest','--noconftest','-q','tests/c36/test_s52_occupation_coverage.py'],cwd=repo,env={**__import__('os').environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=30)
    results.append({'id':i,'line':node.lineno,'kind':kind,'before':ast.get_source_segment(original,node),'after':ast.unparse(replacement),'killed':p.returncode!=0,'exit_code':p.returncode,'tail':p.stdout[-600:]})
finally:
 path.write_text(original)
 for cache in path.parent.glob('__pycache__/gaps.*.pyc'):cache.unlink()
pathlib.Path(__file__).with_name('s52-mutations.json').write_text(json.dumps({'source_sha256':hashlib.sha256(original.encode()).hexdigest(),'results':results},indent=2))
print('mutants',len(results),'killed',sum(r['killed'] for r in results),'survived',sum(not r['killed'] for r in results))
for r in results:
 if not r['killed']:print('SURVIVOR',r['id'],r['line'],r['before'],r['after'])
