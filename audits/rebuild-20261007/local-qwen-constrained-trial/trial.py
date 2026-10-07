import subprocess,time,json,os,urllib.request,sys,socket,threading,hashlib
from pathlib import Path
root=Path('/home/sandbox/atlas-local-trial');out=Path('audits/rebuild-20261007/local-qwen-constrained-trial');port=18950
assert hashlib.sha256((root/'qwen.gguf').read_bytes()).hexdigest()=='74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db'
assert subprocess.check_output(['git','-C',str(root/'runner'),'rev-parse','HEAD'],text=True).strip()=='8345f333951c661d166b00e6f9362e553768f292'
s=socket.socket();s.bind(('127.0.0.1',port));s.close()
log=open(out/'server.log','w');proc=subprocess.Popen([str(root/'runner/build/bin/llama-server'),'-m',str(root/'qwen.gguf'),'--host','127.0.0.1','--port',str(port),'-t','2','-tb','2','-c','1024','-np','1','-n','128','--no-webui'],stdout=log,stderr=log)
started=time.monotonic();peak=0;stop=threading.Event()
def monitor():
 global peak
 while not stop.wait(.1):
  try:
   rss=int(next(l for l in Path(f'/proc/{proc.pid}/status').read_text().splitlines() if l.startswith('VmRSS:')).split()[1]);peak=max(peak,rss)
   if rss>1100000 or time.monotonic()-started>100:proc.terminate();return
  except (OSError,StopIteration):return
thread=threading.Thread(target=monitor);thread.start()
step_schema={'type':'object','properties':{'id':{'type':'string'},'title':{'type':'string'},'tool':{'type':'null'},'arguments':{'type':'object','properties':{},'additionalProperties':False},'depends_on':{'type':'array','items':{'type':'string'}},'risk':{'type':'string','enum':['read']}},'required':['id','title','tool','arguments','depends_on','risk'],'additionalProperties':False}
samples=[('planner','Return exactly two steps. First id s1 title Count blocks, no dependencies. Second id s2 title Report count, depends on s1. Both tool null, arguments {}, risk read. No actual tool execution.',{'type':'array','items':step_schema,'minItems':2,'maxItems':2}),('reason','Compute 17+25. Return JSON object with result as the decimal answer string only.',{'type':'object','properties':{'result':{'type':'string'}},'required':['result'],'additionalProperties':False}),('reflect','Synthetic failed count had empty input. Return cause as exactly empty_input, fix as exactly request_nonempty_input, retry false. Do not claim to have fixed it.',{'type':'object','properties':{'cause':{'type':'string'},'fix':{'type':'string'},'retry':{'type':'boolean'}},'required':['cause','fix','retry'],'additionalProperties':False})]
report={'scope':'small_model_plumbing_verification_only','weights_revision':'9217f5db79a29953eb74d5343926648285ec7e67','weights_sha256':'74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db','runner_commit':'8345f333951c661d166b00e6f9362e553768f292','transport':'trial_only_native_schema_generation_injected_into_actual_adapter','requests':[]}
try:
 for _ in range(100):
  if proc.poll() is not None:raise RuntimeError('server stopped')
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=.5) as r:
    if r.status==200:break
  except Exception:time.sleep(.2)
 else:raise RuntimeError('startup timeout')
 report['startup_seconds']=time.monotonic()-started
 sys.path.insert(0,str(Path('backend').resolve()))
 from app.modules.m20_general_cognitive_worker import model_adapters as ma
 from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner
 from jsonschema import validate
 for purpose,prompt,schema in samples:
  item={'purpose':purpose,'prompt':prompt,'schema':schema};tick=time.monotonic()
  async def local_generate(original_prompt,*args,**kwargs):
   item['adapter_original_prompt']=original_prompt
   request={'model':'qwen-trial','messages':[{'role':'user','content':prompt}], 'temperature':0,'seed':73,'max_tokens':128,'response_format':{'type':'json_schema','json_schema':{'name':purpose,'schema':schema}}}
   with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',data=json.dumps(request).encode(),headers={'Content-Type':'application/json'}),timeout=30) as response:data=json.load(response)
   item['native_response']=data
   text=data['choices'][0]['message']['content'];item['raw_text']=text
   try:validate(json.loads(text),schema);item['schema_valid']=True
   except Exception as exc:item['schema_valid']=False;item['schema_error']=str(exc)
   return 'trial_native_schema','qwen-trial',text
  ma.model_catalog.generate_free_first=local_generate
  try:
   if purpose=='planner':
    parsed=ma.FreeFirstPlannerModel({},model_name='').decompose(prompt)
    HTNPlanner()._validate(parsed)
    passed=len(parsed)==2 and [(x['id'],x['title'],x.get('tool'),x['arguments'],x['depends_on'],x['risk']) for x in parsed]==[('s1','Count blocks',None,{},[],'read'),('s2','Report count',None,{},['s1'],'read')]
   else:
    parsed=ma.FreeFirstExecutiveModel(model_name='').complete(purpose,{'synthetic_prompt':prompt})
    passed=parsed.get('result')=='42' if purpose=='reason' else parsed.get('cause')=='empty_input' and parsed.get('fix')=='request_nonempty_input' and parsed.get('retry') is False
   item.update(adapter_output=parsed,adapter_accepted=parsed.get('available') is not False if isinstance(parsed,dict) else True,exact_task_pass=passed)
  except Exception as exc:item.update(adapter_accepted=False,exact_task_pass=False,error=type(exc).__name__+': '+str(exc))
  item['seconds']=time.monotonic()-tick;report['requests'].append(item)
finally:
 stop.set();proc.terminate()
 try:proc.wait(timeout=5)
 except subprocess.TimeoutExpired:proc.kill();proc.wait()
 thread.join();log.close();report.update(peak_rss_kib=peak,total_seconds=time.monotonic()-started,exit_code=proc.returncode)
 (out/'result.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!='requests'},indent=2))
 for item in report['requests']:print(json.dumps({k:v for k,v in item.items() if k not in ('schema','native_response','adapter_original_prompt')},indent=2))
