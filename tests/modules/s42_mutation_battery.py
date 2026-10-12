"""Honest named-mutation outcomes; baseline must pass before flips."""
from pathlib import Path
import json
import subprocess
import sys
R=Path(__file__).resolve().parents[2];P=R/'backend/app/modules/c35/docs_ingest.py'
cmd=[sys.executable,'-m','pytest','tests/modules/test_c35_docs_ingest_s42.py','-q']
original=P.read_text()
mutations=[
('pin_check','if doc_url not in pinned_doc_urls:','if False:'),
('host_lower',"authority=host.lower()","authority=parts.netloc"),
('drop_fragment',"query,''))","query,parts.fragment))"),
('trailing_slash',"parts.path.rstrip('/')","parts.path"),
('utm_filter',"if not key.casefold().startswith('utm_')","if True"),
('utm_casefold',"key.casefold().startswith('utm_')","key.startswith('utm_')"),
('keep_blank_query',"keep_blank_values=True","keep_blank_values=False"),
('dedupe','if url in by_url:','if False:'),
('dup_counter','duplicates+=1','duplicates+=0'),
('source_provenance',"if doc_url not in by_url[url]['doc_urls']:",'if False:'),
('template_trigger',"if not TEMPLATE_RE.search(lines[i]):","if True:"),
('template_delimiter',"while i<len(lines) and lines[i].strip():","while i<len(lines):"),
('template_verbatim',"'text':block,","'text':block.strip(),"),
('placeholder_list',r"sorted(set(re.findall(r'\{(name|school|opportunity)\}',block)))","[]"),
('template_casefold',"TEMPLATE_RE=re.compile(r'fee waiver|waiver request',re.I)","TEMPLATE_RE=re.compile(r'fee waiver|waiver request')"),
('classification','if any(word in host for word in keywords):','if False:'),
('unknown_count',"sum(row['kind']=='unknown'for row in index)",'0'),
('label_whitespace',"'label':line,","'label':line.strip(),"),
('policy_allow_ws',"allow_ws=True","allow_ws=False"),
('text_cap',"'text',2_000_000","'text',2_000_001"),
('no_effect_fields',"or set(request)-{'as_of','docs'}",''),
]
base=subprocess.run(cmd,cwd=R,capture_output=True,text=True);assert base.returncode==0,base.stdout+base.stderr
results=[]
for name,old,new in mutations:
 assert old in original,name
 try:
  P.write_text(original.replace(old,new,1))
  for p in P.parent.glob('__pycache__/docs_ingest*.pyc'):p.unlink()
  done=subprocess.run(cmd,cwd=R,capture_output=True,text=True,timeout=12)
  output=done.stdout+done.stderr
  status='SURVIVED' if done.returncode==0 else ('assertion' if 'AssertionError' in output or 'DID NOT RAISE' in output else 'error')
  (R/'audits/s42'/('mutant-'+name+'.log')).write_text('\n'.join(l.rstrip()for l in output.splitlines())+'\n')
  results.append({'name':name,'outcome':status,'killed':done.returncode!=0,'exit_code':done.returncode,'disposition':'Test rejects behavioral change' if done.returncode else 'OPEN: needs test or equivalence justification'})
 finally:
  P.write_text(original)
  for p in P.parent.glob('__pycache__/docs_ingest*.pyc'):p.unlink()
print(json.dumps({'mutants':len(results),'killed':sum(r['killed']for r in results),'survived':sum(not r['killed']for r in results),'results':results},indent=2))
