import subprocess,time,json,os,socket,threading,hashlib,urllib.request,sys
from pathlib import Path
root=Path('/home/sandbox/atlas-local-trial');out=Path('audits/rebuild-20261007/local-qwen-ideation-acceptance');port=18961
assert hashlib.sha256((root/'qwen.gguf').read_bytes()).hexdigest()=='74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db'
assert subprocess.check_output(['git','-C',str(root/'runner'),'rev-parse','HEAD'],text=True).strip()=='8345f333951c661d166b00e6f9362e553768f292'
s=socket.socket();s.bind(('127.0.0.1',port));s.close()
os.environ['ATLAS_LOCAL_OPENAI_URL']=f'http://127.0.0.1:{port}/v1';os.environ['ATLAS_LOCAL_OPENAI_MODEL']='qwen-trial';os.environ['ATLAS_OLLAMA_URL']='http://127.0.0.1:18962';os.environ['ATLAS_ALLOW_PAID']='false'
for key in ('HF_TOKEN','ATLAS_LOCAL_OPENAI_KEY','ATLAS_GCW_MODEL'):os.environ.pop(key,None)
log=open(out/'server.log','w');proc=subprocess.Popen([str(root/'runner/build/bin/llama-server'),'-m',str(root/'qwen.gguf'),'--host','127.0.0.1','--port',str(port),'-t','2','-tb','2','-c','1024','-np','1','-n','256','--no-webui'],stdout=log,stderr=log)
started=time.monotonic();peak=0;stop=threading.Event()
def monitor():
 global peak
 while not stop.wait(.1):
  try:
   rss=int(next(l for l in Path(f'/proc/{proc.pid}/status').read_text().splitlines() if l.startswith('VmRSS:')).split()[1]);peak=max(peak,rss)
   if rss>1100000 or time.monotonic()-started>100:proc.terminate();return
  except (OSError,StopIteration):return
thread=threading.Thread(target=monitor);thread.start()
report={'scope':'actual_local_ideation_acceptance_no_mock','source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'weights_sha256':'74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db','runner_commit':'8345f333951c661d166b00e6f9362e553768f292','requests':[]}
try:
 for _ in range(100):
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=.5) as r:
    if r.status==200:break
  except Exception:time.sleep(.2)
 else:raise RuntimeError('startup timeout')
 sys.path.insert(0,str(Path('backend').resolve()))
 from app.modules.m20_general_cognitive_worker.reflection import ModelIdeationEngine
 from app.modules.m20_general_cognitive_worker.model_adapters import FreeFirstExecutiveModel
 from app.core import providers
 original=providers.generate
 item={}
 async def record_actual(prompt,provider,model):
  item['prompt']=prompt
  chosen,text=await original(prompt,provider,model)
  item.update(provider=provider,model=chosen,raw_text=text)
  return chosen,text
 providers.generate=record_actual # Observability wrapper forwards real provider, no output substitution.
 for objective,constraints in [('Recruit students for a free library study club',['No money spent','Do not contact anyone during generation']),('Reduce missed homework deadlines',['No paid software'])]:
  item={'objective':objective,'constraints':constraints,'count':1};tick=time.monotonic()
  try:
   result=ModelIdeationEngine(FreeFirstExecutiveModel()).generate(objective,constraints=constraints,count=1)
   item.update(workflow_accepted=True,result=result)
  except Exception as exc:item.update(workflow_accepted=False,error=type(exc).__name__+': '+str(exc))
  item['seconds']=time.monotonic()-tick;report['requests'].append(item)
finally:
 stop.set();proc.terminate()
 try:proc.wait(timeout=5)
 except subprocess.TimeoutExpired:proc.kill();proc.wait()
 thread.join();log.close();report.update(peak_rss_kib=peak,total_seconds=time.monotonic()-started,exit_code=proc.returncode)
 (out/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
