from pathlib import Path
import random,subprocess,os,json
root=Path('/home/sandbox/atlas-peer-review/peer');out=Path('/home/sandbox/atlas-ai/audits/rebuild-20261007/m13-order-reproduction');out.mkdir(exist_ok=True)
files=sorted(str(p.relative_to(root)) for pat in ('test_m11_*.py','test_m13_*.py') for p in (root/'tests/modules').glob(pat))
seed=int(os.environ['SEED']);random.Random(seed).shuffle(files)
(out/f'order-{seed}.json').write_text(json.dumps(files,indent=2))
with (out/f'order-{seed}.log').open('w') as stream:
 result=subprocess.run(['/home/sandbox/atlas-peer-review/venv/bin/python','-m','pytest',*files,'-v','--tb=short','-p','no:randomly','-p','no:cacheprovider'],cwd=root,env={**os.environ,'PYTHONPATH':'backend'},stdout=stream,stderr=subprocess.STDOUT,timeout=65)
print('seed',seed,'exit',result.returncode);print((out/f'order-{seed}.log').read_text().splitlines()[-1])
