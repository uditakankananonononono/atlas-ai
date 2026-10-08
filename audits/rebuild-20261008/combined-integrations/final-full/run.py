import json,subprocess,time,pathlib,os,re
root=pathlib.Path('/tmp/atlas-m05-m19-integration/final-full'); manifest=root/'manifest.json'
if not manifest.exists():
 files=sorted(str(p) for p in pathlib.Path('tests').rglob('test_*.py'))
 manifest.write_text(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'file_count':len(files),'batches':[files[i:i+10] for i in range(0,len(files),10)]},indent=2))
m=json.load(open(manifest));started=time.monotonic()
for i,files in enumerate(m['batches']):
 receipt=root/f'batch{i}.json'
 if receipt.exists():continue
 tick=time.monotonic();log=root/f'batch{i}.log'
 init_env={**os.environ,'PYTHONPATH':'/tmp/atlas-pg-oct8:backend:.','ATLAS_DATABASE_URL':f'sqlite:///{root}/batch{i}.sqlite','ATLAS_AUTO_CREATE_SCHEMA':'1'}
 subprocess.run(['/home/sandbox/atlas-ai/.venv/bin/python','-c','from app.modules import registry; from app.core.database import Base,engine; Base.metadata.create_all(engine)'],env=init_env,check=True,stdout=subprocess.DEVNULL)
 os.environ.pop('ATLAS_AUTO_CREATE_SCHEMA',None)
 with log.open('w') as out:
  try:r=subprocess.run(['/home/sandbox/atlas-ai/.venv/bin/python','-m','pytest','-q',*files,'--tb=short'],stdout=out,stderr=subprocess.STDOUT,timeout=110,env={**os.environ,'PYTHONPATH':'/tmp/atlas-pg-oct8:backend:.','ATLAS_DATABASE_URL':f'sqlite:///{root}/batch{i}.sqlite'});code=r.returncode
  except subprocess.TimeoutExpired:code=124
 text=log.read_text();last=text.splitlines()[-1] if text.splitlines() else '';counts={k:int(v) for v,k in re.findall(r'(\d+) (passed|failed|skipped|errors?)\b',last)}
 receipt.write_text(json.dumps({'batch':i,'files':len(files),'exit':code,'seconds':time.monotonic()-tick,'counts':counts}))
 print(i,code,last,flush=True)
 if code or time.monotonic()-started>5:break
receipts=[json.loads(p.read_text()) for p in root.glob('batch*.json')]
s={'head':m['head'],'file_count':m['file_count'],'done':len(receipts),'batches':len(m['batches']),'counts':{k:sum(x['counts'].get(k,0) for x in receipts) for k in ('passed','failed','skipped','error','errors')},'nonzero':[x['batch'] for x in receipts if x['exit']]}
(root/'summary.json').write_text(json.dumps(s,indent=2));print(json.dumps(s))
