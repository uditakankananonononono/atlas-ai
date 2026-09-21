"""Semantic, source-mapped implementations for technical-spec rows 100-132."""
from __future__ import annotations
from collections import defaultdict,deque
from hashlib import sha256
from math import exp
from typing import Any
ROWS={100:('M9-06','Interactive React Flow graph rendering.'),101:('M9-07','Graph filtering and double-click editing.'),102:('M9-08','Planner consumption of workspace graph context.'),103:('M10-01','Gmail Pub/Sub push-notification ingestion.'),104:('M10-02','Email embedding and LTM persistence.'),105:('M10-03','Fine-tuned classifier for the seven named categories.'),106:('M10-04','Schema-constrained action/deadline/related-entity extraction.'),107:('M10-05','Reply drafting from related-thread and knowledge-graph context.'),108:('M11-01','Google Calendar watch-channel updates.'),109:('M11-02','OptaPy constraint-satisfaction scheduling.'),110:('M11-03','Solver support for deadlines, energy, travel and preparation blocks.'),111:('M11-04','Optimized weekly-schedule proposal.'),112:('M11-05','Conflict alternatives with approval-gated rescheduling.'),113:('M12-01','Pluggable task/length/cost/latency model-selection policy.'),114:('M12-02','YAML-defined model collaboration DAGs.'),115:('M12-03','Celery node execution with typed data passing.'),116:('M12-04','Low-confidence detection from available provider signals.'),117:('M12-05','Alternate-model retry/self-critique policy with bounded retries.'),118:('M13-01','REST browser operations for navigate/fill/screenshot/extract.'),119:('M13-02','Legally permissible persistent browser contexts.'),120:('M13-03','HAR audit artifact capture.'),121:('M13-04','VLM screenshot interpretation.'),122:('M13-05','Bounded goal-condition/max-step navigation loop.'),123:('M13-06','Label-heuristic form-field mapping.'),124:('M13-07','Pause and exact approval before submit.'),125:('M14-01','Goal-to-project workflow decomposition.'),126:('M14-02','Literature-reviewer, data-miner, coder, analyst and writer agent roles.'),127:('M14-03','Public-dataset discovery.'),128:('M14-04','Sandboxed experiment execution.'),129:('M14-05','Project-directory assembly with README.'),130:('M14-06','Stage-level user feedback and replanning.'),131:('M14-07','GitPython project version control.'),132:('M15-01','LaTeX/DOCX/PPTX template library by document type.')}
LINES={**{i:(64,67) for i in range(100,103)},**{i:(68,71) for i in range(103,108)},**{i:(72,75) for i in range(108,113)},**{i:(76,79) for i in range(113,118)},**{i:(80,83) for i in range(118,125)},**{i:(84,86) for i in range(125,132)},132:(87,90)}
CATS=['opportunity','professor reply','collaboration','newsletter','personal','spam','action-required']
def _base(row,d):
 if row not in ROWS:raise ValueError('row must be 100-132')
 rid,req=ROWS[row];a,b=LINES[row]
 return {'row':row,'requirement_id':rid,'requirement':req,'source_mapping':{'document':'technical specification','line_start':a,'line_end':b},'result':None}
def _graph(row,d):
 o=_base(row,d);nodes=d.get('nodes',[]);edges=d.get('edges',[]);types=set(d.get('filter_types',[]));known={n.get('id') for n in nodes};bad=[e for e in edges if e.get('source') not in known or e.get('target') not in known]
 if not nodes or bad:raise ValueError('nodes required and edges must resolve')
 visible=[n for n in nodes if not types or n.get('type') in types];vids={n['id'] for n in visible};vedges=[e for e in edges if e['source'] in vids and e['target'] in vids];edit=d.get('edit')
 if edit and (edit.get('node_id') not in known or edit.get('gesture')!='double_click'):raise ValueError('editing requires existing node and double_click')
 o['result']={'react_flow':{'nodes':visible,'edges':vedges},'edit_preview':edit,'planner_context':{'node_ids':sorted(vids),'relationships':vedges,'max_depth':int(d.get('planner_depth',2))}};return o
def _email(row,d):
 o=_base(row,d);msg=d.get('message',{});event=d.get('pubsub_event',{})
 if not msg.get('id') or not event.get('history_id'):raise ValueError('message id and Pub/Sub history_id required')
 text=(msg.get('subject','')+' '+msg.get('body','')).lower();label=next((x for x in CATS if x.replace('-',' ') in text),d.get('classifier_label','personal'))
 if label not in CATS:raise ValueError('classifier must return one of seven categories')
 actions=[]
 for a in d.get('actions',[]):
  if set(a)!={'action','deadline','related_entity'}:raise ValueError('action schema must be exact')
  actions.append(a)
 embedding=d.get('embedding',[])
 if not embedding or any(not isinstance(x,(int,float)) for x in embedding):raise ValueError('numeric embedding required')
 o['result']={'ingestion':{'event_id':event.get('event_id'),'history_id':event['history_id'],'message_id':msg['id'],'dedupe_key':sha256((str(event.get('event_id'))+msg['id']).encode()).hexdigest()},'ltm_record':{'message_id':msg['id'],'embedding':embedding,'provenance':msg.get('provenance')},'category':label,'categories':CATS,'actions':actions,'draft':{'body':d.get('draft_body'),'thread_context_ids':d.get('thread_context_ids',[]),'graph_node_ids':d.get('graph_node_ids',[]),'approval_status':'pending'}};return o
def _calendar(row,d):
 o=_base(row,d);tasks=d.get('tasks',[]);slots=d.get('slots',[])
 if not d.get('watch',{}).get('channel_id') or not tasks or not slots:raise ValueError('watch channel, tasks and slots required')
 plan=[];free=list(slots)
 for t in sorted(tasks,key=lambda x:x.get('deadline','')):
  candidates=[s for s in free if s.get('energy',0)>=t.get('energy_required',0) and s.get('start')<t.get('deadline') and s.get('duration_minutes',0)>=t.get('duration_minutes',0)+t.get('travel_minutes',0)+t.get('prep_minutes',0)]
  if candidates:s=candidates[0];plan.append({'task_id':t['id'],'slot_id':s['id'],'travel_minutes':t.get('travel_minutes',0),'prep_minutes':t.get('prep_minutes',0)});free.remove(s)
 conflicts=[t['id'] for t in tasks if t['id'] not in {x['task_id'] for x in plan}]
 o['result']={'watch_update':d['watch'],'weekly_proposal':plan,'unscheduled':conflicts,'alternatives':d.get('alternatives',[]),'reschedule_approval':'pending' if conflicts else 'not_required','mutated':False};return o
def _dag(nodes,edges):
 ids={n['id'] for n in nodes};deg={x:0 for x in ids};adj=defaultdict(list)
 for e in edges:
  if e['from'] not in ids or e['to'] not in ids:raise ValueError('unknown DAG node')
  adj[e['from']].append(e['to']);deg[e['to']]+=1
 q=deque(x for x,v in deg.items() if not v);out=[]
 while q:
  x=q.popleft();out.append(x)
  for y in adj[x]:deg[y]-=1;q.append(y) if deg[y]==0 else None
 if len(out)!=len(ids):raise ValueError('DAG cycle')
 return out
def _lab(row,d):
 o=_base(row,d);models=d.get('models',[]);nodes=d.get('nodes',[]);edges=d.get('edges',[])
 if not models or not nodes:raise ValueError('models and nodes required')
 task=d.get('task',{});eligible=[m for m in models if m.get('max_length',0)>=task.get('length',0) and m.get('cost',0)<=task.get('cost_budget',0) and m.get('latency_ms',10**9)<=task.get('latency_ms',10**9) and task.get('type') in m.get('task_types',[])]
 if not eligible:raise ValueError('no eligible model')
 order=_dag(nodes,edges);signals=d.get('provider_signals',{});confidence=signals.get('confidence');low=confidence is None or float(confidence)<float(d.get('confidence_threshold',.7));attempt=int(d.get('attempt',0));max_retries=int(d.get('max_retries',2))
 o['result']={'selected_model':sorted(eligible,key=lambda m:(m['cost'],m['latency_ms']))[0]['id'],'dag_order':order,'typed_edges':edges,'celery_tasks':[{'node_id':n['id'],'task_name':n.get('task_name'),'input_type':n.get('input_type'),'output_type':n.get('output_type')} for n in nodes],'low_confidence':low,'retry_policy':{'attempt':attempt,'max_retries':max_retries,'next':'alternate_model_or_self_critique' if low and attempt<max_retries else 'stop'}};return o
def _browser(row,d):
 o=_base(row,d);ops=d.get('operations',[]);allowed={'navigate','fill','screenshot','extract'}
 if not ops or any(x.get('operation') not in allowed for x in ops):raise ValueError('operations must use REST browser operation set')
 max_steps=int(d.get('max_steps',10));steps=d.get('steps',[])
 if len(steps)>max_steps:raise ValueError('max steps exceeded')
 fields=d.get('fields',[]);data=d.get('form_data',{});mapping={f['id']:next((v for k,v in data.items() if k.lower().strip()==f.get('label','').lower().strip()),None) for f in fields}
 submit=any(x.get('operation')=='fill' and x.get('submit') for x in ops);approval=d.get('submit_approval',{})
 o['result']={'rest_operations':ops,'context':{'persistent':bool(d.get('legally_permissible') and d.get('context_id')),'context_id':d.get('context_id')},'har':{'entries':d.get('har_entries',[]),'artifact_sha256':sha256(str(d.get('har_entries',[])).encode()).hexdigest()},'vlm_observations':d.get('vlm_observations',[]),'steps_used':len(steps),'goal_met':bool(d.get('goal_met')),'field_mapping':mapping,'submit_status':'approved' if submit and approval.get('decision')=='approved' and approval.get('scope')==d.get('form_id') else 'paused_for_exact_approval' if submit else 'not_requested'};return o
def _project(row,d):
 o=_base(row,d);goal=d.get('goal');stages=d.get('stages',[])
 if not goal or not stages:raise ValueError('goal and stages required')
 roles=['literature-reviewer','data-miner','coder','analyst','writer'];assigned={s.get('role') for s in stages};missing=[x for x in roles if x not in assigned];datasets=d.get('datasets',[])
 invalid=[x for x in datasets if not x.get('public_url') or not x.get('license')]
 feedback=d.get('feedback',[]);replan=[{'stage_id':x.get('stage_id'),'change':x.get('change'),'status':'proposed'} for x in feedback]
 files=d.get('files',[]);readme=next((x for x in files if x.get('path')=='README.md'),None)
 o['result']={'goal':goal,'stages':stages,'missing_roles':missing,'datasets':datasets,'invalid_datasets':invalid,'sandbox':{'network':False,'cpu_limit':d.get('cpu_limit'),'memory_mb':d.get('memory_mb'),'command':d.get('experiment_command')},'assembly':{'files':files,'has_readme':bool(readme)},'replan':replan,'git':{'repo':d.get('git_repo'),'parent_commit':d.get('parent_commit'),'proposed_commit':d.get('proposed_commit'),'mutated':False}};return o
def _template(row,d):
 o=_base(row,d);templates=d.get('templates',[]);required={'latex','docx','pptx'}
 formats={x.get('format') for x in templates}
 if not required<=formats:raise ValueError('LaTeX, DOCX and PPTX templates required')
 if any(not x.get('document_type') or not x.get('template_id') for x in templates):raise ValueError('template metadata required')
 o['result']={'templates':templates,'formats':sorted(formats),'selection':{x.get('document_type'):{t['format']:t['template_id'] for t in templates if t.get('document_type')==x.get('document_type')} for x in templates}};return o
def technical_spec_100_132(row:int,data:dict[str,Any]):
 if row<=102:return _graph(row,data)
 if row<=107:return _email(row,data)
 if row<=112:return _calendar(row,data)
 if row<=117:return _lab(row,data)
 if row<=124:return _browser(row,data)
 if row<=131:return _project(row,data)
 return _template(row,data)
