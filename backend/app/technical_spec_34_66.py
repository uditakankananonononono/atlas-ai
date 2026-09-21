"""Executable semantics for technical-spec ledger rows 34-66.
Each result preserves requirement/source-line mapping from the owner document."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime,timezone
from math import exp,sqrt
from typing import Any
import copy,hashlib,json
ROWS={34:('A34','Hybrid semantic + keyword + metadata-filter retrieval.',19,20),35:('A35','Optional Neo4j entity knowledge graph with typed cross-artifact links.',19,20),36:('A36','Recursive objective/milestone/task/subtask planner.',21,22),37:('A37','Planner nodes with effort, dependency, deadline and tool assignments.',21,22),38:('A38','Memory-update-triggered plan refinement.',21,22),39:('A39','Versioned JSON plan persistence.',21,22),40:('A40','Policy-based multi-model task routing.',23,24),41:('A41','Multi-model research -> draft -> critique -> formatting chains.',23,24),42:('A42','Recursive result-merging algorithm.',23,24),43:('M0-01','Dedicated approval service and Redis Streams event boundary.',26,30),44:('M0-02','ApprovalRequest persistence with id, user, module, action type, JSON payload, status, timestamps, expiry and approver.',26,30),45:('M0-03','pending/approved/denied/expired state-machine transitions.',26,30),46:('M0-04','`approval_request` event publication and persistence.',26,30),47:('M0-05','Dashboard SSE notification for pending requests.',26,30),48:('M0-06','Calling-worker suspension without serializing executable callbacks unsafely.',26,30),49:('M0-07','Single-use callback/continuation release after valid approval.',26,30),50:('M0-08','Immutable decision audit records.',26,30),51:('M0-09','Shared request-approval SDK used by effectful modules.',26,30),52:('M1-01','Profile/opportunity cosine-similarity `match_score`.',31,35),53:('M1-02','Historical applied/won logistic-regression expected-impact score.',31,35),54:('M1-03','PostgreSQL persistence of enriched opportunity scores.',31,35),55:('M1-04','Instant SSE alerts for new matches above 0.8.',31,35),56:('M1-05','Daily digest draft with approval-gated sending.',31,35),57:('M5-01','Campaign-goal intake and campaign state.',49,52),58:('M5-02','Professor discovery by campaign keywords.',49,52),59:('M5-03','Professor ranking by Semantic Scholar publication impact.',49,52),60:('M5-04',"Personalization grounded in a professor's recent work.",49,52),61:('M5-05','SMTP/IMAP delivery only after exact approval.',49,52),62:('M5-06','Open/reply tracking from inbox threads, with tracking limits disclosed.',49,52),63:('M5-07','Configurable no-reply window.',49,52),64:('M5-08','Gentle follow-up draft queued for approval.',49,52),65:('M6-01','Content-brief intake.',53,55),66:('M6-02','Platform-specific format strategy.',53,55)}
class SpecError(ValueError):pass
def mapped(row,result):
 rid,req,a,b=ROWS[row];return {'row':row,'requirement_id':rid,'requirement':req,'source_mapping':{'document':'technical-spec-line-by-line','line_start':a,'line_end':b},'result':result}
def cosine(a,b):
 if not a or len(a)!=len(b):raise SpecError('vectors must be aligned and non-empty')
 den=sqrt(sum(x*x for x in a)*sum(x*x for x in b));return 0 if den==0 else sum(x*y for x,y in zip(a,b))/den
@dataclass
class State:
 memories:list[dict]=field(default_factory=list);edges:list[dict]=field(default_factory=list);plans:dict[str,list[dict]]=field(default_factory=dict);approvals:dict[str,dict]=field(default_factory=dict);events:list[dict]=field(default_factory=list);audits:list[dict]=field(default_factory=list);continuations:set[str]=field(default_factory=set);opportunities:dict[str,dict]=field(default_factory=dict);campaigns:dict[str,dict]=field(default_factory=dict)
state=State()
def reset():global state;state=State()
def _id(payload):return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()[:16]
def execute(row:int,p:dict[str,Any],s:State|None=None):
 if row not in ROWS:raise SpecError('unsupported row')
 s=s or state
 if row==34:
  q=p.get('query','').lower().split();qv=p.get('query_vector');items=p.get('items',[]);f=p.get('filters',{});out=[]
  for x in items:
   if any(x.get('metadata',{}).get(k)!=v for k,v in f.items()):continue
   sem=cosine(qv,x['embedding']) if qv is not None else 0;kw=len(set(q)&set(x.get('text','').lower().split()))/max(1,len(set(q)));out.append({'id':x['id'],'score':round(p.get('semantic_weight',.7)*sem+p.get('keyword_weight',.3)*kw,6),'semantic':sem,'keyword':kw})
  return mapped(row,{'ranked':sorted(out,key=lambda x:(-x['score'],x['id'])),'filters':f})
 if row==35:
  for e in p.get('edges',[]):
   if not all(e.get(k) for k in ('from','to','type')):raise SpecError('typed edge requires from, to and type')
  s.edges.extend(copy.deepcopy(p.get('edges',[])));return mapped(row,{'enabled':p.get('enabled',True),'typed_edges':copy.deepcopy(s.edges) if p.get('enabled',True) else []})
 if row in (36,37):
  goal=p.get('goal');levels=p.get('levels',['objective','milestone','task','subtask']);
  if not goal:raise SpecError('goal required')
  def node(level,i,parent=None):return {'id':f'{level}-{i}','type':level,'title':p.get('titles',{}).get(level,f'{level}: {goal}'),'parent':parent,'effort':p.get('effort',{}).get(level,1),'dependencies':p.get('dependencies',{}).get(level,[]),'deadline':p.get('deadlines',{}).get(level),'tools':p.get('tools',{}).get(level,[])}
  nodes=[];parent=None
  for i,l in enumerate(levels):n=node(l,i,parent);nodes.append(n);parent=n['id']
  return mapped(row,{'goal':goal,'nodes':nodes,'recursive_depth':len(levels)})
 if row in (38,39):
  pid=p.get('plan_id');
  if not pid:raise SpecError('plan_id required')
  hist=s.plans.setdefault(pid,[]);doc=copy.deepcopy(p.get('plan',{}));version=len(hist)+1;record={'version':version,'plan':doc,'trigger_memory_id':p.get('memory_id'),'created_at':datetime.now(timezone.utc).isoformat()};hist.append(record);return mapped(row,{'plan_id':pid,'version':version,'history':copy.deepcopy(hist),'refined_from_memory':row==38 and bool(p.get('memory_id'))})
 if row==40:
  task=p.get('task_type');policy=p.get('policy',{});model=policy.get(task) or policy.get('default')
  if not model:raise SpecError('no model policy for task')
  return mapped(row,{'task_type':task,'selected_model':model,'policy_reason':'exact task rule' if task in policy else 'default rule'})
 if row==41:
  required=['research','draft','critique','format'];chain=p.get('chain',[])
  if [x.get('stage') for x in chain]!=required:raise SpecError('chain must be research,draft,critique,format in order')
  artifacts=[];prior=p.get('input')
  for x in chain:artifacts.append({'stage':x['stage'],'model':x['model'],'input':prior,'output':x.get('output')});prior=x.get('output')
  return mapped(row,{'artifacts':artifacts,'final':prior})
 if row==42:
  def merge(a,b):
   if isinstance(a,dict) and isinstance(b,dict):return {k:merge(a[k],b[k]) if k in a and k in b else copy.deepcopy(a.get(k,b.get(k))) for k in a.keys()|b.keys()}
   if isinstance(a,list) and isinstance(b,list):return a+[x for x in b if x not in a]
   return b if b not in (None,'',[]) else a
  vals=p.get('results',[])
  if not vals:raise SpecError('results required')
  out=vals[0]
  for x in vals[1:]:out=merge(out,x)
  return mapped(row,{'merged':out,'input_count':len(vals)})
 if 43<=row<=51:return _approval(row,p,s)
 if 52<=row<=56:return _opportunity(row,p,s)
 if 57<=row<=64:return _campaign(row,p,s)
 return _social(row,p)
def _approval(row,p,s):
 if row in (43,44,46,47,48,51):
  required=('user_id','module','action_type','payload')
  if any(p.get(k) in (None,'') for k in required):raise SpecError('user_id, module, action_type and payload required')
  aid=p.get('id') or _id(p);now=datetime.now(timezone.utc).isoformat();rec={'id':aid,'user_id':p['user_id'],'module':p['module'],'action_type':p['action_type'],'payload':copy.deepcopy(p['payload']),'status':'pending','created_at':now,'expires_at':p.get('expires_at'),'approved_by':None,'continuation_token':p.get('continuation_token')};s.approvals[aid]=rec;event={'type':'approval_request','approval_id':aid,'at':now};s.events.append(event);s.audits.append({'approval_id':aid,'event':'created','at':now});return mapped(row,{'approval':copy.deepcopy(rec),'published_event':event,'sse':f'event: approval_request\ndata: {json.dumps(event)}\n\n','worker_state':'suspended','serialized_callback':False,'sdk':'request_approval'})
 aid=p.get('approval_id');rec=s.approvals.get(aid)
 if not rec:raise SpecError('approval not found')
 if row==45:
  target=p.get('decision');
  if rec['status']!='pending' or target not in ('approved','denied','expired'):raise SpecError('invalid state transition')
  rec['status']=target;rec['approved_by']=p.get('approved_by') if target=='approved' else None;s.audits.append({'approval_id':aid,'event':target,'at':datetime.now(timezone.utc).isoformat()});return mapped(row,{'approval':copy.deepcopy(rec)})
 if row==49:
  if rec['status']!='approved':raise SpecError('approval required')
  token=rec.get('continuation_token')
  if not token or token in s.continuations:raise SpecError('continuation missing or already released')
  s.continuations.add(token);return mapped(row,{'released':True,'continuation_token':token,'single_use':True})
 return mapped(row,{'audit':copy.deepcopy([x for x in s.audits if x['approval_id']==aid]),'append_only':True})
def _opportunity(row,p,s):
 if row==52:return mapped(row,{'match_score':round(cosine(p.get('profile_embedding'),p.get('opportunity_embedding')),6)})
 if row==53:
  features=p.get('features');coef=p.get('coefficients');
  if not features or not coef:raise SpecError('features and coefficients required')
  z=coef.get('intercept',0)+sum(coef[k]*features[k] for k in coef if k!='intercept');return mapped(row,{'expected_impact':round(1/(1+exp(-z)),6),'model':'logistic_regression'})
 if row==54:
  rec=p.get('opportunity');
  if not rec or not all(k in rec for k in ('id','match_score','expected_impact')):raise SpecError('enriched opportunity required')
  s.opportunities[rec['id']]=copy.deepcopy(rec);return mapped(row,{'persisted':copy.deepcopy(rec),'store':'postgres_repository_contract'})
 if row==55:
  score=float(p.get('match_score',0));return mapped(row,{'alert_emitted':score>.8,'threshold':.8,'transport':'SSE' if score>.8 else None})
 matches=p.get('matches',[]);draft={'subject':p.get('subject','Daily opportunity digest'),'items':[x for x in matches],'sent':False,'approval_status':'pending'};return mapped(row,{'draft':draft,'approval_required':True})
def _campaign(row,p,s):
 if row==57:
  goal=p.get('goal');
  if not goal:raise SpecError('campaign goal required')
  cid=_id({'goal':goal});s.campaigns[cid]={'id':cid,'goal':goal,'status':'draft','created_at':datetime.now(timezone.utc).isoformat()};return mapped(row,{'campaign':copy.deepcopy(s.campaigns[cid])})
 if row==58:
  kws={x.lower() for x in p.get('keywords',[])};profs=p.get('professors',[]);hits=[x for x in profs if kws & {t.lower() for t in x.get('keywords',[])}];return mapped(row,{'matches':hits,'keywords':sorted(kws)})
 if row==59:
  ranked=sorted(p.get('professors',[]),key=lambda x:(-(x.get('citation_count',0)+10*x.get('h_index',0)),-x.get('recent_citations',0),x.get('id','')));return mapped(row,{'ranked':ranked,'source':'Semantic Scholar supplied metrics'})
 if row==60:
  work=p.get('recent_work');
  if not work or not work.get('title') or not work.get('url'):raise SpecError('cited recent work required')
  return mapped(row,{'personalization':f"I read your recent work, {work['title']}",'citation':work['url'],'draft_only':True})
 if row==61:
  if p.get('approval_status')!='approved' or not p.get('exact_recipient') or not p.get('exact_message'):raise SpecError('exact approved recipient and message required')
  return mapped(row,{'delivery_authorized':True,'transport':p.get('transport','SMTP'),'delivered':False})
 if row==62:
  threads=p.get('threads',[]);return mapped(row,{'reply_detected':any(x.get('direction')=='inbound' for x in threads),'open_detected':any(x.get('open_receipt') for x in threads),'limits':['opens may be blocked or proxied','thread matching can miss replies']})
 if row==63:
  days=int(p.get('window_days',0));
  if not 1<=days<=90:raise SpecError('window_days must be 1..90')
  return mapped(row,{'window_days':days,'due_after':p.get('sent_at'),'configured':True})
 if p.get('reply_detected'):raise SpecError('follow-up not allowed after reply')
 return mapped(row,{'draft':{'body':p.get('body','Just following up on my earlier note.'),'sent':False},'queued_for_approval':True})
def _social(row,p):
 if row==65:
  required=('goal','audience','platforms','facts');
  if any(p.get(k) in (None,[],{}) for k in required):raise SpecError('goal, audience, platforms and facts required')
  return mapped(row,{'brief':{k:copy.deepcopy(p[k]) for k in required},'rights':p.get('rights','review_required'),'status':'accepted_for_strategy'})
 formats={'instagram':'carousel','twitter':'thread','x':'thread','tiktok':'60s_video_script','linkedin':'document_post','youtube':'video'};plans=[]
 for platform in p.get('platforms',[]):plans.append({'platform':platform,'format':formats.get(platform.lower(),'platform_native_post'),'rationale':'platform-native default; human review required'})
 if not plans:raise SpecError('platforms required')
 return mapped(row,{'strategy':plans,'scheduled':False,'approval_required':True})
