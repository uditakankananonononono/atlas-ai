"""Hand-selected mutations with per-mutant survivor analysis."""
import pathlib,json,tempfile,subprocess
MUTANTS={
 'policy-removal':("    guard('read')","    pass"),
 'clinical-flag':('if clinical or diagnostic or (imitation and condition):','if diagnostic or (imitation and condition):'),
 'diagnosis-refusal':('if clinical or diagnostic or (imitation and condition):','if clinical or (imitation and condition):'),
 'imitation-refusal':('if clinical or diagnostic or (imitation and condition):','if clinical or diagnostic:'),
 'schema-keys':("set(request) - {'idea','lenses','clinical_claim'}",'False'),
 'idea-length':('len(idea)>2000','len(idea)>2001'),
 'empty-idea':('not idea.strip()','False'),
 'clinical-type':('if type(clinical) is not bool:','if False:'),
 'lens-lower':('not 1<=len(keys)<=len(DEFINITIONS)','not 0<=len(keys)<=len(DEFINITIONS)'),
 'lens-upper':('not 1<=len(keys)<=len(DEFINITIONS)','not 1<=len(keys)<=len(DEFINITIONS)-1'),
 'lens-dedupe':('or len(set(keys))!=len(keys)',''),
 'asof':("if not isinstance(as_of,str) or date.fromisoformat(as_of).isoformat()!=as_of:",'if False:'),
 'angle-count':('count=len(angles)','count=len(angles)+1'),
 'disclaimer':('disclaimer=DISCLAIMER','disclaimer="Thinking only"'),
 'idea-interpolation':('q.format(idea=idea.strip())','q.format(idea="unrelated")'),
 'question-count':('prompts[:3]','prompts[:2]'),
 'lens-selected':('prompts=DEFINITIONS[key]','prompts=DEFINITIONS["pattern-first"]'),
 'next-step':('next_step=prompts[3]','next_step=""'),
}

def main():
 root=pathlib.Path(__file__).parent
 code=root.parents[1]/'backend/app/modules/m20_general_cognitive_worker/c31_s15'
 source=(code/'lenses.py').read_text()
 results=[]
 for name,(old,new) in MUTANTS.items():
  assert old in source,name
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);(d/'lenses.py').write_text(source.replace(old,new));(d/'test_lenses.py').write_text('\n'.join(line for line in (root/'test_lenses.py').read_text().splitlines() if not line.startswith('sys.path.insert')));(d/'route_adapter.py').write_bytes((code/'route_adapter.py').read_bytes())
   p=subprocess.run(['python3','-m','unittest','test_lenses'],cwd=d,capture_output=True,text=True)
   behavioral=p.returncode!=0 and 'SyntaxError' not in p.stderr and 'ImportError' not in p.stderr
   results.append(dict(mutant=name,killed=behavioral,analysis='behavioral test failure' if behavioral else 'SURVIVOR: test gap or equivalent, inspect before landing'))
 for name,old,new in (
  ('route-tenant',"if not isinstance(tenant_id,str) or not tenant_id.strip():","if False:"),
  ('route-get-policy',"            self.guard('read')","            pass"),
  ('route-unknown',"raise Refused('FLEET_REFUSED_ROUTE')","return {}")):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp)
   (d/'lenses.py').write_text(source)
   (d/'route_adapter.py').write_text((code/'route_adapter.py').read_text().replace(old,new))
   (d/'test_lenses.py').write_text('\n'.join(line for line in (root/'test_lenses.py').read_text().splitlines() if not line.startswith('sys.path.insert')))
   p=subprocess.run(['python3','-m','unittest','test_lenses'],cwd=d,capture_output=True,text=True)
   behavioral=p.returncode!=0 and 'SyntaxError' not in p.stderr and 'ImportError' not in p.stderr
   results.append(dict(mutant=name,killed=behavioral,analysis='behavioral test failure' if behavioral else 'SURVIVOR: inspect'))
 print(json.dumps(dict(total=len(results),killed=sum(r['killed'] for r in results),survivors=[r for r in results if not r['killed']],results=results),indent=2))
 return all(r['killed'] for r in results)
if __name__=='__main__':raise SystemExit(0 if main() else 1)
