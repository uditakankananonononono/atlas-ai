from pathlib import Path
import subprocess,os
r=Path('/home/sandbox/atlas-peer-review/peer');out=Path('/home/sandbox/atlas-ai/audits/rebuild-20261007/m13-order-reproduction')
for i in range(10):
 p=out/f'browser-repeat-{i}.log'
 with p.open('w') as log:
  run=subprocess.run(['/home/sandbox/atlas-peer-review/venv/bin/python','-m','pytest','tests/modules/test_m13_source_reconciliation_browser.py','-v','--tb=long','-p','no:cacheprovider','-p','no:randomly'],cwd=r,env={**os.environ,'PYTHONPATH':'backend'},stdout=log,stderr=subprocess.STDOUT,timeout=15)
 print(i,run.returncode,p.read_text().splitlines()[-1],flush=True)
 if run.returncode:break
