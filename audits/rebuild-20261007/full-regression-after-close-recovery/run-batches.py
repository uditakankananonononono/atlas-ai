import json,subprocess,time,pathlib
root=pathlib.Path('audits/rebuild-20261007/full-regression-after-close-recovery');m=json.load(open(root/'manifest.json'));start=time.monotonic()
for i,files in enumerate(m['batches']):
 log=root/f'batch{i}.log';receipt=root/f'batch{i}.json'
 if receipt.exists():continue
 with log.open('w') as output:
  tick=time.monotonic()
  try:r=subprocess.run(['.venv/bin/python','-m','pytest',*files,'-q'],stdout=output,stderr=subprocess.STDOUT,timeout=90);code=r.returncode
  except subprocess.TimeoutExpired:code=124
 json.dump({'batch':i,'file_count':len(files),'exit':code,'seconds':time.monotonic()-tick},receipt.open('w'))
 print(i,code,log.read_text().splitlines()[-1],flush=True)
 if code or time.monotonic()-start>60:break
