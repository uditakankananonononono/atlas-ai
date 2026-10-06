import subprocess,time,json,os,urllib.request,sys,signal
from pathlib import Path
root=Path('/home/sandbox/atlas-local-trial');log=open(root/'server.log','w');port=18948
# Verify fresh port before launch, never interact with an existing server.
import socket
s=socket.socket();s.bind(('127.0.0.1',port));s.close()
proc=subprocess.Popen([str(root/'runner/build/bin/llama-server'),'-m',str(root/'qwen.gguf'),'--host','127.0.0.1','--port',str(port),'-t','2','-tb','2','-c','1024','-np','1','-n','128','--no-webui'],stdout=log,stderr=log)
peak=0;started=time.monotonic();report={'runner_commit':'8345f333951c661d166b00e6f9362e553768f292','weights_revision':'9217f5db79a29953eb74d5343926648285ec7e67','weights_sha256':'74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db','requests':[],'scope':'small_pretrained_model_local_behavior_only'}
import threading
stop=threading.Event()
def monitor():
 global peak
 while not stop.wait(.1):
  try:
   lines=Path(f'/proc/{proc.pid}/status').read_text().splitlines();rss=int(next(l for l in lines if l.startswith('VmRSS:')).split()[1]);peak=max(peak,rss)
   if rss>1100000 or time.monotonic()-started>100:proc.terminate();return
  except (OSError,StopIteration):return
thread=threading.Thread(target=monitor);thread.start()
try:
 for i in range(100):
  if proc.poll() is not None:raise RuntimeError('server stopped during startup')
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=.5) as r:
    if r.status==200:break
  except Exception:time.sleep(.2)
 else:raise RuntimeError('startup deadline')
 report['startup_seconds']=time.monotonic()-started
 os.environ['ATLAS_LOCAL_OPENAI_URL']=f'http://127.0.0.1:{port}/v1';os.environ['ATLAS_LOCAL_OPENAI_MODEL']='qwen-trial';os.environ['ATLAS_OLLAMA_URL']='http://127.0.0.1:1';os.environ.pop('HF_TOKEN',None);os.environ['ATLAS_ALLOW_PAID']='false'
 sys.path.insert(0,'/home/sandbox/atlas-ai/backend')
 from app.modules.m20_general_cognitive_worker.model_adapters import FreeFirstPlannerModel,FreeFirstExecutiveModel
 from app.modules.m20_general_cognitive_worker.schemas import Risk
 for name,fn in [('planner',lambda:FreeFirstPlannerModel({'read_fixture':Risk.READ},model_name='').decompose('Read the supplied fixture then summarize it in two steps.',context='Synthetic fixture has three colored blocks. No external tools available.')),('reason',lambda:FreeFirstExecutiveModel(model_name='').complete('reason',{'goal':'Summarize this synthetic fixture in one sentence','fixture':'Three blocks are red, green and blue.'})),('reflect',lambda:FreeFirstExecutiveModel(model_name='').complete('reflect',{'goal':'Count blocks in synthetic fixture','error':'Input fixture was empty.'}))]:
  tick=time.monotonic()
  try:output=fn();report['requests'].append({'name':name,'output':output,'seconds':time.monotonic()-tick})
  except Exception as e:report['requests'].append({'name':name,'error':type(e).__name__+': '+str(e),'seconds':time.monotonic()-tick})
except Exception as e:report['error']=type(e).__name__+': '+str(e)
finally:
 stop.set();proc.terminate()
 try:proc.wait(timeout=5)
 except subprocess.TimeoutExpired:proc.kill();proc.wait()
 thread.join();log.close();report['peak_rss_kib']=peak;report['total_seconds']=time.monotonic()-started;report['exit_code']=proc.returncode
 (root/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
