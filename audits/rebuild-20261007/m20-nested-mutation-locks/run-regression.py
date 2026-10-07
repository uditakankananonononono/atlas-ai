import json,re,subprocess,time,pathlib,sys
root=pathlib.Path('audits/rebuild-20261007/m20-nested-mutation-locks/full-regression');root.mkdir(exist_ok=True)
manifest=root/'manifest.json'
if not manifest.exists():
 files=sorted(str(p) for p in pathlib.Path('tests').rglob('test_*.py'))
 manifest.write_text(json.dumps({'files':files,'batches':[files[i:i+10] for i in range(0,len(files),10)]},indent=2))
m=json.loads(manifest.read_text());started=time.monotonic()
for i,files in enumerate(m['batches']):
 receipt=root/f'batch{i}.json';log=root/f'batch{i}.log'
 if receipt.exists():continue
 with log.open('w') as output:
  tick=time.monotonic()
  try:
   result=subprocess.run(['/home/sandbox/atlas-ai/.venv/bin/python','-m','pytest',*files,'-q','--tb=short'],stdout=output,stderr=subprocess.STDOUT,timeout=90)
   code=result.returncode
  except subprocess.TimeoutExpired:code=124
 text=log.read_text();counts={}
 for kind in ['passed','failed','skipped','error','errors']:
  hits=re.findall(r'(\d+) '+kind+r'\b',text.splitlines()[-1] if text.splitlines() else '')
  if hits:counts[kind]=int(hits[-1])
 receipt.write_text(json.dumps({'batch':i,'file_count':len(files),'exit':code,'seconds':time.monotonic()-tick,'counts':counts}))
 print(i,code,text.splitlines()[-1] if text.splitlines() else '',flush=True)
 if time.monotonic()-started>70:break
receipts=[json.loads(p.read_text()) for p in root.glob('batch*.json')]
summary={'file_count':len(m['files']),'batches_total':len(m['batches']),'batches_done':len(receipts),'counts':{k:sum(x['counts'].get(k,0) for x in receipts) for k in ('passed','failed','skipped','error','errors')},'nonzero_batches':[x['batch'] for x in receipts if x['exit']]}
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
