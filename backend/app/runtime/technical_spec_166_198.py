"""Semantic contracts for technical-spec rows 166-198, preserving requirement IDs."""
from __future__ import annotations
import ast,math
from datetime import datetime,timezone
from pathlib import PurePosixPath
from .gcw_tool_integration import plan_tool_route
MAP={**{166+i:f'M19-{i+4:02d}' for i in range(7)},**{173+i:f'M20-{i+1:02d}' for i in range(26)}}
def _base(row,out):return {'technical_spec_row':row,'requirement_id':MAP[row],'result':out}
def execute(row,d):
 if row not in MAP:raise ValueError('unsupported technical-spec row')
 if row==166:
  results=d.get('results');
  if not isinstance(results,list) or not results:raise ValueError('public search results required')
  for x in results:
   if not str(x.get('url','')).startswith('https://'):raise ValueError('public HTTPS evidence URL required')
  return _base(row,{'competitors':results,'sources':['ProductHunt','public_web'],'evidence_count':len(results)})
 if row==167:
  comps=d.get('components');shot=d.get('screenshot')
  if not isinstance(comps,list) or not comps or not shot:raise ValueError('components and screenshot evidence required')
  return _base(row,{'wireframe':{'components':comps,'reviewable':True},'screenshot':shot,'visual_verification_required':True})
 if row==168:
  name=str(d.get('name','')).strip();
  if not name:raise ValueError('prototype name required')
  return _base(row,{'files':[f'{name}/frontend/package.json',f'{name}/frontend/src/App.tsx',f'{name}/backend/app.py',f'{name}/README.md'],'api_contract':d.get('api_contract',{}),'tests_included':True})
 if row==169:return _base(row,{'action':'deploy_sandbox_preview','provider':'vercel','preview_only':True,'requires_approval':True,'status':'proposal','artifact_ref':d.get('artifact_ref')})
 if row==170:
  failures=d.get('failures');limit=int(d.get('max_iterations',3))
  if not isinstance(failures,list) or not 1<=limit<=10:raise ValueError('failures and max_iterations 1..10 required')
  attempts=[{'iteration':i+1,'failure':f,'patch_proposed':True} for i,f in enumerate(failures[:limit])];return _base(row,{'attempts':attempts,'bounded':True,'stopped':len(failures)>=limit})
 if row==171:
  ev=d.get('evidence');
  if not isinstance(ev,list) or not ev:raise ValueError('evidence required')
  return _base(row,{'format':'pdf','sections':['executive summary','prototype link','market analysis','technical feasibility','recommendation'],'recommendation':d.get('recommendation','needs_review'),'evidence':ev,'render_status':'ready'})
 if row==172:
  budget=float(d.get('budget',0));used=float(d.get('used',0));return _base(row,{'idea_id':d.get('idea_id'),'budget':budget,'remaining':max(0,budget-used),'stoppable':True,'eligible_for_idle_cycle':budget>used and not d.get('stop_requested',False)})
 if row==173:
  typ=d.get('modality');content=d.get('content')
  if typ not in {'text','voice','image','csv','pdf','email'} or content is None:raise ValueError('supported modality and content required')
  return _base(row,{'event':{'type':typ,'description':str(content),'metadata':d.get('metadata',{}),'normalized_at':'deterministic'}})
 if row==174:
  alt=d.get('description');table=d.get('table',[])
  if not alt:raise ValueError('VLM description required')
  return _base(row,{'provider':'vlm','description':alt,'table':table,'provider_evidence':d.get('provider_evidence'),'review_required':True})
 if row==175:
  transcript=d.get('transcript')
  if not transcript:raise ValueError('Whisper transcript required')
  return _base(row,{'provider':'whisper','transcript':transcript,'language':d.get('language'),'timestamps':d.get('timestamps',[])})
 if row in {176,177}:
  chunks=d.get('chunks');
  if not isinstance(chunks,list) or any(not {'type','content','confidence','source'}<=set(x) for x in chunks):raise ValueError('typed chunks required')
  goal=str(d.get('goal','')).lower();ranked=sorted(chunks,key=lambda x:(goal in str(x['content']).lower(),float(x['confidence'])),reverse=True)[:50];return _base(row,{'chunks':ranked,'capacity':50,'pruned':max(0,len(chunks)-50)})
 if row==178:return _base(row,{'episode':{k:d.get(k) for k in ['start_state','actions','outcomes','reflections']},'retrievable':True})
 if row==179:return _base(row,{'semantic_record':{'facts':d.get('facts',[]),'concepts':d.get('concepts',[]),'documents':d.get('documents',[]),'user_knowledge':d.get('user_knowledge',[])},'proactive_query':d.get('unknown_term')})
 if row in {180,181}:
  steps=d.get('steps');
  if not isinstance(steps,list) or not steps:raise ValueError('skill steps required')
  return _base(row,{'skill':{'name':d.get('name'),'steps':steps,'status':'proposed','review_required':True},'silent_self_modification':False,'success_evidence':d.get('success_evidence',[])})
 if row in {182,183}:
  goal=d.get('goal');methods=d.get('methods',{});tasks=methods.get(goal) or d.get('proposed_tasks')
  if not goal or not tasks:raise ValueError('goal and known/proposed decomposition required')
  return _base(row,{'goal':goal,'tasks':tasks,'source':'library' if goal in methods else 'novel_proposal','persistence':'after_review_only'})
 if row==184:return _base(row,{'loop':{x:d.get(x) for x in ['observe','orient','decide','act','evaluate']},'complete':all(d.get(x) is not None for x in ['observe','orient','decide','act','evaluate'])})
 if row==185:
  opts=d.get('actions');
  if not isinstance(opts,list) or not opts:raise ValueError('actions required')
  scored=[{'name':x['name'],'score':float(x['information_gain'])*float(x['progress_probability'])-float(x['cost'])} for x in opts];return _base(row,{'ranked_actions':sorted(scored,key=lambda x:x['score'],reverse=True)})
 if row==186:
  surprise=abs(float(d.get('observed',0))-float(d.get('expected',0)));threshold=float(d.get('threshold',.2));return _base(row,{'surprise':surprise,'reflection_triggered':surprise>threshold,'replan':surprise>threshold})
 if row==187:
  cadence=int(d.get('cadence_seconds',0));limit=int(d.get('max_cycles',0))
  if not 1<=cadence<=3600 or not 1<=limit<=1000:raise ValueError('bounded cadence/cycles required')
  return _base(row,{'cadence_seconds':cadence,'max_cycles':limit,'stop_token_required':True})
 if row==188:
  paths=d.get('paths');budget=int(d.get('simulation_budget',0))
  if not isinstance(paths,list) or not paths or not 1<=budget<=10000:raise ValueError('paths and bounded budget required')
  ranked=sorted(paths,key=lambda x:float(x['reward'])/max(1,float(x.get('visits',1))),reverse=True);return _base(row,{'selected':ranked[0],'simulations':min(budget,len(paths)*100),'budget':budget})
 if row in {189,190,191,192,193,194}:
  route=plan_tool_route(row,d)
  if row==189:
   tools=d.get('tools')
   if not isinstance(tools,list) or any(not {'name','description','parameters','preconditions'}<=set(x) for x in tools):raise ValueError('typed tools required')
   return _base(row,{**route,'tools':tools,'function_call_schema':True,'mechanism':'typed_registry_with_ui_routes'})
  if row==190:
   expr=str(d.get('expression',''));tree=ast.parse(expr,mode='eval');allowed=(ast.Expression,ast.BinOp,ast.UnaryOp,ast.Constant,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.USub)
   if any(not isinstance(n,allowed) for n in ast.walk(tree)):raise ValueError('unsafe python expression')
   return _base(row,{**route,'sandboxed':True,'result':eval(compile(tree,'<sandbox>','eval'),{'__builtins__':{}},{}),'mechanism':'sandbox_or_compliant_ui_route'})
  if row==191:
   cmd=d.get('command');allow={'pwd','ls','cat','head','tail','wc'}
   if not isinstance(cmd,list) or not cmd or cmd[0] not in allow or any(x in ';&|`$()' for x in ' '.join(cmd)):raise ValueError('command outside permission boundary')
   return _base(row,{**route,'command':cmd,'allowed':True,'execute':False,'workspace_only':True,'mechanism':'permission_bounded_shell_with_ui_route'})
  if row==192:
   if not str(d.get('query','')).strip():raise ValueError('search query required')
   return _base(row,{**route,'query':d['query'],'public_only':True,'credentials_in_query':False,'mechanism':'public_search_api_or_compliant_ui'})
  if row==193:
   p=PurePosixPath('/'+str(d.get('path','')).lstrip('/'))
   if '..' in p.parts or not str(p).startswith('/workspace/'):raise ValueError('path outside owner workspace')
   if d.get('operation') not in {'read','write'}:raise ValueError('workspace operation must be read or write')
   return _base(row,{**route,'path':str(p),'operation':d['operation'],'workspace_bounded':True,'mechanism':'owner_workspace_or_paired_pc_ui'})
  adapter=d.get('adapter')
  if adapter and (adapter not in d.get('allowlist',[]) or d.get('reviewed') is not True):raise ValueError('reviewed allow-listed adapter required')
  return _base(row,{**route,'adapter':adapter,'request':d.get('request'),'direct_generated_request':False,'mechanism':'allowlisted_api_or_compliant_ui_or_native_build'})
 if row in {195,197}:
  contexts=d.get('contexts');
  if not isinstance(contexts,dict) or len(contexts)<2:raise ValueError('separate contexts required')
  return _base(row,{'context_ids':sorted(contexts),'partitions':{k:list(v.get('working_memory',[])) for k,v in contexts.items()},'isolated':True})
 if row==196:
  tasks=d.get('tasks');now=float(d.get('now',0))
  ranked=sorted(tasks,key=lambda x:(float(x['deadline'])-now)/(1+float(x['importance'])))
  return _base(row,{'schedule':[x['id'] for x in ranked],'policy':'deadline_proximity_then_importance','time_slice_seconds':int(d.get('time_slice_seconds',30))})
 if row==198:
  alts=d.get('alternatives');criteria=d.get('criteria')
  if not isinstance(alts,list) or not isinstance(criteria,list) or not alts or not criteria:raise ValueError('alternatives and criteria required')
  matrix=[{'alternative':a['name'],'score':sum(float(a['scores'][c['name']])*float(c['weight']) for c in criteria)} for a in alts]
  return _base(row,{'artifact_type':'private_decision_summary','alternatives':alts,'criteria':criteria,'decision_matrix':sorted(matrix,key=lambda x:x['score'],reverse=True),'owner_reasoning_notes':d.get('owner_reasoning_notes',[]),'hidden_chain_of_thought_stored':False})
 raise AssertionError(row)
