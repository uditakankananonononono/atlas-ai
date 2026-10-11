from pathlib import Path
import subprocess,json,sys
R=Path(__file__).resolve().parents[2];P=R/'backend/app/modules/c36/blueprint.py'
cmd=[sys.executable,'-m','pytest','tests/modules/test_c36_blueprint_s51.py','tests/modules/test_c36_blueprint_s51_delta.py','-q']
s=P.read_text();assert subprocess.run(cmd,cwd=R,capture_output=True).returncode==0
mutants=[
('count_first','    _preflight(request)\n',''),
('raw_caps_before_scan','        _caps(raw_niches)','        pass'),
('nodes','if nodes>10000 or depth>32:','if nodes>10001 or depth>32:'),
('depth','if nodes>10000 or depth>32:','if nodes>10000 or depth>33:'),
('cycle','if id(node) in active:','if False:'),
('cf_text','{"Cc", "Cf", "Zl", "Zp"}','{"Cc", "Zl", "Zp"}'),
('key_cap','if len(key)>200:','if len(key)>201:'),
('currency_cap','len(currency)>3','len(currency)>4'),
('asof_cap','len(raw_as_of)>10','len(raw_as_of)>11'),
('exact_request','if type(request) is not dict:','if not isinstance(request,dict):'),
('exact_numeric','if type(v) not in (int, float):','if not isinstance(v,(int,float)):'),
('regulated','if not built:','if False:'),
('prices','"price_points": n["price_points"]','"price_points": []'),
('graph_edges','if a in nodes and b in nodes','if a in nodes'),
('null_kpis','"target": None','"target": 10'),
('sort','key=lambda n: n["id"]','key=lambda n: n["id"], reverse=True'),
('date_fullmatch','not _DATE.fullmatch(as_of)','not _DATE.match(as_of)'),
('currency_fullmatch','not _CUR.fullmatch(currency)','not _CUR.match(currency)'),
]
results=[]
for name,old,new in mutants:
 assert old in s,name
 try:
  P.write_text(s.replace(old,new,1))
  for p in P.parent.glob('__pycache__/blueprint*.pyc'):p.unlink()
  try:
   x=subprocess.run(cmd,cwd=R,capture_output=True,text=True,timeout=12);output=x.stdout+x.stderr
   result={'name':name,'outcome':'SURVIVED'if x.returncode==0 else 'assertion/error','exit_code':x.returncode}
  except subprocess.TimeoutExpired:
   output='Timed out at 12s';result={'name':name,'outcome':'timeout','exit_code':124}
  (R/'audits/s51-delta'/('mutant-'+name+'.log')).write_text('\n'.join(l.rstrip()for l in output.splitlines())+'\n')
  results.append(result)
 finally:
  P.write_text(s)
  for p in P.parent.glob('__pycache__/blueprint*.pyc'):p.unlink()
print(json.dumps({'mutants':len(results),'killed':sum(r['exit_code']!=0 for r in results),'results':results},indent=2))
