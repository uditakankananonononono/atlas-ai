"""Executable architecture contracts for technical-spec A01-A33.

Adapters are dependency-injected so tests and local development never require cloud
services. All records retain their exact source-line mapping from the owner spec.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from hmac import compare_digest,new as hmac_new
from collections import defaultdict,deque
import base64,json,re,secrets
from typing import Any,Callable
class ArchitectureError(ValueError):pass
ROWS={1:('A01','Next.js 14 App Router frontend.',5),2:('A02','React 18 frontend.',5),3:('A03','Tailwind CSS frontend styling.',5),4:('A04','shadcn/ui component system.',5),5:('A05','React Flow graph visualizations.',5),6:('A06','Recharts dashboards.',5),7:('A07','Python 3.12 + FastAPI + Pydantic v2 backend contract.',6),8:('A08','Celery with Redis broker and result backend.',6),9:('A09','PostgreSQL 16 managed through Supabase-compatible deployment.',7),10:('A10','pgvector dense-embedding storage.',7),11:('A11','ChromaDB dedicated long-term-memory vector store.',7),12:('A12','Redis Streams inter-service event bus.',8),13:('A13','Optional RabbitMQ complex-routing backend.',8),14:('A14','LangChain abstraction plus custom prompt chains.',9),15:('A15','Dynamic routing across OpenAI, Anthropic, Gemini, DeepSeek and local Ollama models named in the spec.',9),16:('A16','Playwright browser service managed by Browserless or a controlled Chrome farm.',10),17:('A17','Selenium fallback for legacy sites.',10),18:('A18','PyMuPDF document processing.',11),19:('A19','Tesseract OCR processing.',11),20:('A20','Unstructured.io layout-aware parsing.',11),21:('A21','OAuth 2.0 / OpenID Connect for Google and GitHub.',12),22:('A22','JWT session lifecycle.',12),23:('A23','HashiCorp Vault credential storage.',12),24:('A24','Append-only PostgreSQL audit log.',12),25:('A25','APScheduler lightweight in-process scheduling.',13),26:('A26','Cloud Run stateless-service deployment target.',14),27:('A27','GKE long-running-agent deployment target.',14),28:('A28','Cloud Storage asset backend.',14),29:('A29','Cloud SQL managed-Postgres target.',14),30:('A30','Central authenticated, rate-limited FastAPI API Gateway.',15),31:('A31','Long-running dispatch from gateway to Celery workers.',15),32:('A32','SSE streaming from backend to Next.js frontend.',15),33:('A33','Universal LTM ingestion of generated and ingested artifacts.',19)}
def mapping():return [{'row':i,'requirement_id':x[0],'requirement':x[1],'source_line_start':x[2],'source_line_end':20 if i==33 else x[2]} for i,x in ROWS.items()]
class FrontendContract:
 def manifest(self):return {'framework':{'name':'Next.js','minimum_major':14,'router':'app','server_components':True},'view':{'name':'React','minimum_major':18},'styling':{'engine':'Tailwind CSS','content_scan':['app/**/*','components/**/*']},'components':{'system':'shadcn/ui','ownership':'copied source, locally editable','accessibility':'Radix semantics'},'graphs':{'library':'React Flow','node_ids_required':True,'edge_endpoints_validated':True},'charts':{'library':'Recharts','responsive_container':True,'accessible_labels_required':True}}
 def validate_graph(self,nodes,edges):
  ids=[x.get('id') for x in nodes]
  if None in ids or len(ids)!=len(set(ids)):raise ArchitectureError('graph node IDs must be unique')
  bad=[e for e in edges if e.get('source') not in ids or e.get('target') not in ids]
  if bad:raise ArchitectureError('edge endpoint missing')
  return {'nodes':nodes,'edges':edges,'fit_view':True}
 def chart(self,series):
  if not series or any('name' not in x or 'value' not in x for x in series):raise ArchitectureError('chart series needs name and value')
  return {'responsive':True,'aria_label':'Dashboard metric chart','series':series}
class BackendContract:
 def manifest(self):return {'python':'>=3.12','framework':'FastAPI','validation':'Pydantic v2','task_queue':'Celery','broker':'redis://','result_backend':'redis://','database':'PostgreSQL 16','managed_targets':['Supabase','Cloud SQL'],'extensions':['pgvector'],'vector_store':'ChromaDB'}
 def task(self,name,payload):
  if not name or not isinstance(payload,dict):raise ArchitectureError('task name and object payload required')
  return {'task':name,'payload':payload,'serializer':'json','acks_late':True,'result_backend':'redis'}
 def embedding(self,tenant,content,vector):
  if not tenant or not content or not vector or not all(isinstance(x,(int,float)) for x in vector):raise ArchitectureError('tenant, content and numeric vector required')
  return {'id':sha256((tenant+'|'+content).encode()).hexdigest()[:24],'tenant_id':tenant,'content':content,'embedding':list(map(float,vector)),'postgres_extension':'vector','vector_store_collection':f'ltm-{tenant}'}
class EventBus:
 def __init__(self):self.streams=defaultdict(list)
 def publish(self,stream,event):
  if not stream or not isinstance(event,dict):raise ArchitectureError('stream and object event required')
  eid=f'{len(self.streams[stream])+1}-0';item={'id':eid,'event':event};self.streams[stream].append(item);return item
 def read(self,stream,after='0-0'):return [x for x in self.streams[stream] if int(x['id'].split('-')[0])>int(after.split('-')[0])]
 def binding(self,pattern,queue):return {'backend':'RabbitMQ','exchange_type':'topic','routing_pattern':pattern,'queue':queue,'optional':True}
class ModelOrchestrator:
 MODELS={'openai':['gpt-4o','gpt-4-turbo'],'anthropic':['claude-3.5-sonnet'],'gemini':['gemini-1.5-pro'],'deepseek':['deepseek-v2'],'ollama':['llama-3.1-70b','deepseek-coder-v2','mixtral-8x22b']}
 def chain(self,steps,inputs):
  state=dict(inputs);trace=[]
  for s in steps:
   missing=[k for k in s.get('requires',[]) if k not in state]
   if missing:raise ArchitectureError(f"missing chain inputs: {missing}")
   rendered=s['template'].format(**state);state[s['output']]=rendered;trace.append({'name':s['name'],'output':s['output']})
  return {'outputs':state,'trace':trace,'abstraction':'LangChain-compatible Runnable sequence'}
 def route(self,requirements):
  provider='ollama' if requirements.get('local_only') else 'deepseek' if requirements.get('code') else 'anthropic' if requirements.get('long_context') else 'gemini' if requirements.get('multimodal') else 'openai'
  model=self.MODELS[provider][0];return {'provider':provider,'model':model,'reason':next((k for k,v in requirements.items() if v),'default quality route'),'allowed_catalog':self.MODELS}
class BrowserDocumentContract:
 def browser(self,legacy=False,authorized_session=False):
  return {'engine':'Selenium' if legacy else 'Playwright','endpoint':'legacy-grid' if legacy else 'browserless-or-controlled-chrome','authorized_session':authorized_session,'stealth_evasion':False,'robots_terms_required':True,'credential_mass_scraping':False}
 def document(self,mime,scanned=False,layout=False):
  if mime=='application/pdf' and scanned:return {'pipeline':['PyMuPDF page render','Tesseract OCR','layout reconciliation'],'human_review_low_confidence':True}
  if mime=='application/pdf':return {'pipeline':['PyMuPDF text and metadata'],'human_review_low_confidence':False}
  if layout:return {'pipeline':['Unstructured.io layout-aware partition'],'preserve_blocks_tables_titles':True}
  raise ArchitectureError('unsupported document path')
class SecurityContract:
 PROVIDERS={'google':{'issuer':'https://accounts.google.com','pkce':True},'github':{'issuer':'https://github.com/login/oauth','pkce':True}}
 def oauth(self,provider,redirect_uri,state,nonce):
  if provider not in self.PROVIDERS or not redirect_uri.startswith('https://') or not state or not nonce:raise ArchitectureError('valid provider, HTTPS redirect, state and nonce required')
  return {**self.PROVIDERS[provider],'provider':provider,'redirect_uri':redirect_uri,'state':state,'nonce':nonce,'scopes':['openid','email','profile']}
 def session(self,subject,secret,ttl=3600,now=None):
  if not subject or len(secret)<16:raise ArchitectureError('subject and >=16 byte secret required')
  now=int(now or datetime.now(timezone.utc).timestamp());body={'sub':subject,'iat':now,'exp':now+ttl,'jti':secrets.token_hex(8)};raw=base64.urlsafe_b64encode(json.dumps(body,separators=(',',':')).encode()).decode().rstrip('=');sig=hmac_new(secret.encode(),raw.encode(),'sha256').hexdigest();return {'token':raw+'.'+sig,'claims':body,'rotation':'refresh token rotates and old jti is revoked'}
 def verify(self,token,secret,now):
  try:raw,sig=token.split('.');expected=hmac_new(secret.encode(),raw.encode(),'sha256').hexdigest();claims=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
  except Exception as exc:raise ArchitectureError('malformed session') from exc
  if not compare_digest(sig,expected) or claims['exp']<=now:raise ArchitectureError('invalid or expired session')
  return claims
 def vault_reference(self,path,key):
  if not path.startswith('secret/') or not key:raise ArchitectureError('vault path and key required')
  return {'backend':'HashiCorp Vault','reference':f'vault://{path}#{key}','secret_material_returned':False,'encryption_in_transit':True,'audit_access':True}
class AppendOnlyAudit:
 def __init__(self):self._events=[]
 def append(self,actor,action,resource,metadata=None):
  previous=self._events[-1]['hash'] if self._events else 'GENESIS';body={'sequence':len(self._events)+1,'actor':actor,'action':action,'resource':resource,'metadata':metadata or {},'previous_hash':previous};body['hash']=sha256(json.dumps(body,sort_keys=True).encode()).hexdigest();self._events.append(body);return dict(body)
 def events(self):return [dict(x) for x in self._events]
 def verify(self):
  prev='GENESIS'
  for item in self._events:
   body={k:v for k,v in item.items() if k!='hash'}
   if body['previous_hash']!=prev or sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()!=item['hash']:return False
   prev=item['hash']
  return True
class SchedulerDeployment:
 def schedule(self,job_id,run_at,payload):
  if run_at.tzinfo is None:raise ArchitectureError('run_at must be timezone-aware')
  return {'scheduler':'APScheduler','job_id':job_id,'trigger':'date','run_at':run_at.isoformat(),'payload':payload,'misfire_grace_seconds':60}
 def target(self,kind):
  targets={'cloud_run':{'workload':'stateless service','autoscaling':'request based','container_required':True},'gke':{'workload':'long-running agent','controller':'Deployment','health_probes':True},'cloud_storage':{'workload':'assets','signed_urls':True,'uniform_access':True,'versioning':True},'cloud_sql':{'workload':'PostgreSQL 16','private_ip':True,'automated_backups':True,'connection_pooling':True}}
  if kind not in targets:raise ArchitectureError('unknown deployment target')
  return {'target':kind,**targets[kind]}
class Gateway:
 def __init__(self,limit=3):self.limit=limit;self.calls=defaultdict(deque);self.jobs=[]
 def authorize(self,principal,now):
  if not principal:raise ArchitectureError('authentication required')
  q=self.calls[principal]
  while q and q[0]<=now-60:q.popleft()
  if len(q)>=self.limit:raise ArchitectureError('rate limit exceeded')
  q.append(now);return {'principal':principal,'route_authorized':True,'remaining':self.limit-len(q)}
 def dispatch(self,principal,task,payload,now=0):
  auth=self.authorize(principal,now);job={'id':sha256(f'{principal}|{task}|{len(self.jobs)}'.encode()).hexdigest()[:20],'task':task,'payload':payload,'queue':'celery','state':'queued'};self.jobs.append(job);return {**job,'gateway':auth}
 def sse(self,event,data,event_id):return f'id: {event_id}\nevent: {event}\ndata: {json.dumps(data,separators=(",",":"))}\n\n'
class UniversalLTM:
 def __init__(self,embed:Callable[[str],list[float]]):self.embed=embed;self.items=[]
 def ingest(self,tenant,artifact):
  required={'content','artifact_type','source_uri'}
  if not tenant or not required<=artifact.keys() or not str(artifact['content']).strip():raise ArchitectureError('tenant and content/type/source required')
  content=str(artifact['content']);vector=self.embed(content)
  if not vector:raise ArchitectureError('embedding provider returned empty vector')
  item={'id':sha256((tenant+'|'+artifact['source_uri']+'|'+content).encode()).hexdigest()[:24],'tenant_id':tenant,'content':content,'artifact_type':artifact['artifact_type'],'source_uri':artifact['source_uri'],'metadata':artifact.get('metadata',{}),'embedding':vector,'dense_index':'ChromaDB','metadata_store':'PostgreSQL','keyword_index':True,'generated_or_ingested':artifact.get('origin','ingested')};self.items.append(item);return item
 def search(self,tenant,query,filters=None):
  terms=set(re.findall(r'\w+',query.lower()));hits=[]
  for x in self.items:
   if x['tenant_id']!=tenant or any(x['metadata'].get(k)!=v for k,v in (filters or {}).items()):continue
   score=len(terms&set(re.findall(r'\w+',x['content'].lower())))
   if score: hits.append({'id':x['id'],'score':score,'artifact_type':x['artifact_type']})
  return sorted(hits,key=lambda x:(-x['score'],x['id']))
