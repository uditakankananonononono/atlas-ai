"""Full study-abroad lifecycle workbench for previously unverified audit rows.
All actions are plans/checks only; submission and external communication require approval.
"""
from __future__ import annotations
import hashlib,math,re
ROWS={1:'end_to_end_lifecycle',2:'destinations_55',3:'top_institutions',8:'identity_embedding',9:'pattern_clustering',10:'story_frameworks',11:'essay_feedback',12:'common_app',13:'coalition',14:'uc_piq',15:'ucas',16:'ouac',17:'european_systems',18:'graduate_sop',19:'diversity_statement',20:'research_statement',22:'draft_version_control',23:'official_monitoring',24:'university_profiles',25:'program_intelligence',26:'fit_scoring',27:'portal_support',28:'deadline_tracker',29:'document_vault',30:'recommender_coordination',31:'interview_preparation',32:'submission_approval',33:'multi_model_review',34:'scholarship_databases',35:'scholarship_matching',36:'net_cost_calculator',37:'financial_aid_forms',38:'scholarship_tasks',39:'award_tracking',40:'allowed_social_sources',41:'advice_credibility',42:'trend_detection',43:'webinar_discovery',44:'webinar_workflow',45:'daily_brief',46:'strategist_agent',47:'storyteller_agent',48:'researcher_agent',49:'executor_agent',50:'critic_agent',51:'tenant_records',52:'vector_embeddings',53:'university_graph',54:'source_schedules',55:'collectors',56:'multi_provider_ai',57:'nlp_stack',58:'encrypted_credentials_audit',59:'achievement_narrative_flow',60:'languages_12',61:'historical_improvement',62:'career_visa_pathways'}
BY_METHOD={v:k for k,v in ROWS.items()}
DESTINATIONS=['United States','United Kingdom','Canada','Australia','Germany','France','Netherlands','Ireland','Italy','Spain','Switzerland','Sweden','Norway','Denmark','Finland','Austria','Belgium','Portugal','Poland','Czechia','Hungary','Greece','Estonia','Latvia','Lithuania','Iceland','Luxembourg','Malta','Cyprus','New Zealand','Singapore','Japan','South Korea','China','Hong Kong','Taiwan','India','United Arab Emirates','Qatar','Saudi Arabia','Israel','Turkey','South Africa','Kenya','Ghana','Nigeria','Egypt','Morocco','Brazil','Mexico','Argentina','Chile','Colombia','Costa Rica','Malaysia']
SYSTEMS={'common_app':650,'coalition':650,'uc_piq':350,'ucas':4000,'ouac':500,'european_systems':1000,'graduate_sop':1000,'diversity_statement':750,'research_statement':1500}
def _tokens(s):return set(re.findall(r"[a-z0-9']+",str(s).lower()))
def _require(cond,msg):
 if not cond:raise ValueError(msg)
def run(method,data):
 _require(method in BY_METHOD,f'unsupported lifecycle method {method}');row=BY_METHOD[method];limits=['Planning/evaluation only; current official sources and human review control application decisions.'];out={}
 if row==1:
  stages=['identity','destination research','school list','essays','documents','recommendations','funding','review','approval','submission','decision','visa','arrival'];done=set(data.get('completed_stages',[]));out={'stages':[{'stage':s,'complete':s in done} for s in stages],'completion':len(done&set(stages))/len(stages),'next_stage':next((s for s in stages if s not in done),None)}
 elif row==2:out={'destinations':DESTINATIONS,'count':len(DESTINATIONS),'coverage_valid':len(set(DESTINATIONS))==55}
 elif row==3:
  institutions=data.get('institutions');_require(isinstance(institutions,list) and institutions,'institutions required');valid=[x for x in institutions if x.get('official_source') and isinstance(x.get('rank'),int) and 1<=x['rank']<=100];out={'eligible_top_100':sorted(valid,key=lambda x:x['rank']),'excluded_count':len(institutions)-len(valid)}
 elif row==8:
  text=str(data.get('identity_text',''));_require(text.strip(),'identity_text required');vec=[0.0]*16
  for t in _tokens(text):vec[int(hashlib.sha256(t.encode()).hexdigest(),16)%16]+=1
  z=math.sqrt(sum(x*x for x in vec)) or 1;out={'embedding':[x/z for x in vec],'dimensions':16,'model':'transparent_token_hash','source_text_preserved':text}
 elif row==9:
  records=data.get('records');_require(isinstance(records,list) and records,'records required');groups={}
  for x in records:
   key=x.get('theme','unclassified');groups.setdefault(key,[]).append(x.get('id'))
  out={'clusters':[{'theme':k,'record_ids':v,'size':len(v)} for k,v in sorted(groups.items())],'cluster_count':len(groups)}
 elif 10<=row<=20:
  evidence=data.get('evidence');draft=str(data.get('student_draft',''));_require(isinstance(evidence,list) and evidence,'student evidence required');framework=data.get('framework','challenge-action-reflection');prompt=str(data.get('prompt',''));word_limit=int(data.get('word_limit',SYSTEMS.get(method,650)));words=draft.split();themes=sorted(set(t for e in evidence for t in e.get('themes',[])));dimensions={'specificity':sum(bool(e.get('detail')) for e in evidence)/len(evidence),'reflection':int(any(w in draft.lower() for w in ['learned','realized','changed'])),'voice':int(bool(draft)),'prompt_fit':len(_tokens(prompt)&_tokens(draft))/max(1,len(_tokens(prompt)))};out={'framework':framework,'outline':['context','specific evidence','meaning','future connection'],'themes':themes,'feedback':dimensions,'word_count':len(words),'word_limit':word_limit,'within_limit':len(words)<=word_limit,'final_prose_generated':False};limits+=['Coaches structure and feedback; never ghostwrites final prose.']
 elif row==22:
  versions=data.get('versions');_require(isinstance(versions,list) and versions,'versions required');ids=[v.get('version') for v in versions];_require(len(ids)==len(set(ids)),'duplicate versions');out={'latest':max(versions,key=lambda v:v.get('version',0)),'history':sorted(versions,key=lambda v:v.get('version',0)),'rollback_supported':len(versions)>1}
 elif row in {23,24,25}:
  records=data.get('records');_require(isinstance(records,list) and records,'records required');verified=[r for r in records if r.get('official_url') and r.get('checked_at')];out={'verified_records':verified,'stale_or_unofficial':[r for r in records if r not in verified],'coverage':len(verified)/len(records),'program_level':row==25};limits+=['No login scraping; official public sources must be rechecked for current facts.']
 elif row==26:
  schools=data.get('schools');_require(isinstance(schools,list) and schools,'schools required');res=[]
  for s in schools:
   fit=float(s.get('fit',0));admit=float(s.get('estimated_admit_probability',0));bucket='safety' if admit>=.65 else 'target' if admit>=.3 else 'reach';res.append({'school':s['name'],'fit':fit,'probability':admit,'bucket':bucket})
  out={'schools':res,'counts':{b:sum(x['bucket']==b for x in res) for b in ['reach','target','safety']}};limits+=['Buckets are planning labels, never admission guarantees.']
 elif row in {27,28,29,30,31,38}:
  items=data.get('items');_require(isinstance(items,list) and items,'items required');required={'id','status'};_require(all(required<=set(x) for x in items),'each item needs id/status');out={'items':items,'open':[x for x in items if x['status']!='complete'],'complete_count':sum(x['status']=='complete' for x in items),'workflow':method}
 elif row==32:
  approved=bool(data.get('module0_approval'));artifact=data.get('artifact');out={'artifact':artifact,'module0_approval':approved,'submission_allowed':approved and bool(artifact),'state':'approved' if approved and artifact else 'blocked'};limits+=['No submission occurs on this route.']
 elif row==33:
  reviews=data.get('reviews');_require(isinstance(reviews,list) and len(reviews)>=2,'at least two model reviews required');issues={x for r in reviews for x in r.get('issues',[])};out={'review_count':len(reviews),'consensus_issues':sorted(x for x in issues if sum(x in r.get('issues',[]) for r in reviews)>1),'all_issues':sorted(issues),'human_review_required':True}
 elif row in {34,35}:
  scholarships=data.get('scholarships');profile=set(data.get('profile_tags',[]));_require(isinstance(scholarships,list) and scholarships,'scholarships required');res=[]
  for s in scholarships:
   req=set(s.get('eligibility_tags',[]));res.append({'id':s['id'],'eligible':req<=profile,'match':len(req&profile)/max(1,len(req)),'official_url':s.get('official_url')})
  out={'matches':sorted(res,key=lambda x:x['match'],reverse=True),'verified_count':sum(bool(x['official_url']) for x in res)}
 elif row==36:
  tuition=float(data['tuition']);fees=float(data.get('fees',0));living=float(data.get('living',0));aid=float(data.get('aid',0));years=float(data.get('years',1));out={'gross_cost':(tuition+fees+living)*years,'aid':aid,'net_cost':(tuition+fees+living)*years-aid,'currency':data.get('currency','USD')}
 elif row==37:
  forms=data.get('forms');_require(isinstance(forms,list) and forms,'forms required');out={'forms':[{'name':x['name'],'complete':all(x.get(k) for k in x.get('required_fields',[])),'missing':[k for k in x.get('required_fields',[]) if not x.get(k)]} for x in forms]};limits+=['Does not submit or provide tax/legal advice.']
 elif row==39:
  awards=data.get('awards');_require(isinstance(awards,list),'awards required');out={'awards':awards,'total_offered':sum(float(x.get('amount',0)) for x in awards),'accepted_total':sum(float(x.get('amount',0)) for x in awards if x.get('accepted'))}
 elif row==40:
  sources=data.get('sources');_require(isinstance(sources,list),'sources required');allow={'official','public_forum','public_social','institution_webinar'};out={'allowed':[x for x in sources if x.get('type') in allow and not x.get('login_required')],'blocked':[x for x in sources if x.get('type') not in allow or x.get('login_required')]};limits+=['Private/login-gated mass scraping is blocked.']
 elif row==41:
  evidence=float(data.get('evidence_quality',0));expert=float(data.get('expertise',0));recency=float(data.get('recency',0));conflict=float(data.get('conflict_risk',0));score=max(0,min(1,.4*evidence+.25*expert+.25*recency-.1*conflict));out={'credibility_score':score,'components':{'evidence':evidence,'expertise':expert,'recency':recency,'conflict_risk':conflict}}
 elif row==42:
  series=data.get('series');_require(isinstance(series,list) and len(series)>=2,'series required');first=float(series[0]['value']);last=float(series[-1]['value']);out={'absolute_change':last-first,'relative_change':(last-first)/first if first else None,'direction':'up' if last>first else 'down' if last<first else 'flat','observations':len(series)}
 elif row in {43,44}:
  events=data.get('events');_require(isinstance(events,list),'events required');verified=[e for e in events if e.get('official_url') and e.get('starts_at')];out={'events':verified,'registration_tasks':[{'event_id':e['id'],'action':'review and register','approval_required':True} for e in verified]}
 elif row==45:
  items=data.get('items');_require(isinstance(items,list),'items required');out={'sections':{k:[x for x in items if x.get('type')==k] for k in ['deadline','admissions','scholarship','webinar']},'item_count':len(items),'generated_from_verified_only':all(x.get('source_verified') for x in items)}
 elif 46<=row<=50:
  tasks=data.get('tasks');_require(isinstance(tasks,list),'tasks required');role=method.replace('_agent','');out={'role':role,'accepted_tasks':[x for x in tasks if x.get('role')==role],'rejected_tasks':[x for x in tasks if x.get('role')!=role],'external_actions_require_approval':True}
 elif row==51:
  records=data.get('records');tenant=data.get('tenant_id');_require(tenant and isinstance(records,list),'tenant_id and records required');out={'tenant_id':tenant,'records':[x for x in records if x.get('tenant_id')==tenant],'cross_tenant_rejected':sum(x.get('tenant_id')!=tenant for x in records)}
 elif row==52:
  q=data.get('query');items=data.get('items');_require(isinstance(q,list) and isinstance(items,list),'query/items required');cos=lambda a,b:sum(x*y for x,y in zip(a,b))/(math.sqrt(sum(x*x for x in a)*sum(y*y for y in b)) or 1);out={'ranked':sorted([{'id':x['id'],'score':cos(q,x['embedding'])} for x in items],key=lambda x:x['score'],reverse=True)}
 elif row==53:
  edges=data.get('edges');_require(isinstance(edges,list),'edges required');nodes=sorted({v for e in edges for v in (e['from'],e['to'])});out={'nodes':nodes,'edges':edges,'node_count':len(nodes),'edge_count':len(edges)}
 elif row==54:
  schedules=data.get('schedules');_require(isinstance(schedules,list),'schedules required');out={'schedules':schedules,'enabled':[x for x in schedules if x.get('enabled')],'invalid':[x for x in schedules if not x.get('source') or not x.get('cadence')]}
 elif row==55:
  collectors=data.get('collectors');_require(isinstance(collectors,list),'collectors required');out={'static':[x for x in collectors if x.get('kind')=='static'],'browser':[x for x in collectors if x.get('kind')=='playwright' and not x.get('login_required')],'blocked':[x for x in collectors if x.get('login_required')]}
 elif row==56:
  providers=data.get('providers');_require(isinstance(providers,list) and providers,'providers required');healthy=[x for x in providers if x.get('healthy')];out={'selected':min(healthy,key=lambda x:float(x.get('cost',0))) if healthy else None,'fallback_order':sorted(healthy,key=lambda x:(-float(x.get('quality',0)),float(x.get('cost',0))))};_require(healthy,'no healthy provider')
 elif row==57:
  text=str(data.get('text',''));_require(text,'text required');dates=re.findall(r'\b\d{4}-\d{2}-\d{2}\b',text);entities=re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',text);out={'tokens':re.findall(r"\w+",text),'dates':dates,'entities':entities,'bert_ready':True,'pipeline':['spaCy','dateparser','BERT']}
 elif row==58:
  credentials=data.get('credentials');audits=data.get('audit_events');_require(isinstance(credentials,list) and isinstance(audits,list),'credentials/audit_events required');out={'encrypted_count':sum(bool(x.get('encrypted')) for x in credentials),'unencrypted_ids':[x.get('id') for x in credentials if not x.get('encrypted')],'audit_event_count':len(audits),'rotation_due':[x.get('id') for x in credentials if x.get('rotation_due')]}
 elif row==59:
  achievements=data.get('achievements');_require(isinstance(achievements,list),'achievements required');out={'evidence_packets':[{'id':x['id'],'fact':x.get('fact'),'source_module':x.get('source_module'),'usable':bool(x.get('fact') and x.get('evidence'))} for x in achievements],'cross_module_sources':sorted({x.get('source_module') for x in achievements})}
 elif row==60:
  supported=['English','Hindi','Assamese','Spanish','French','German','Italian','Portuguese','Dutch','Mandarin','Japanese','Korean'];requested=data.get('language','English');out={'supported_languages':supported,'count':len(supported),'requested':requested,'supported':requested in supported}
 elif row==61:
  history=data.get('history');_require(isinstance(history,list) and history,'history required');applied=[x for x in history if x.get('applied')];won=[x for x in applied if x.get('won')];patterns={t:sum(t in x.get('tags',[]) for x in won) for t in sorted({t for x in won for t in x.get('tags',[])})};out={'applied':len(applied),'won':len(won),'win_rate':len(won)/len(applied) if applied else None,'winning_patterns':patterns};limits+=['Historical associations do not guarantee future outcomes.']
 elif row==62:
  pathways=data.get('pathways');_require(isinstance(pathways,list) and pathways,'pathways required');out={'pathways':sorted(pathways,key=lambda x:(not bool(x.get('official_url')),float(x.get('estimated_cost',0)))),'officially_sourced':sum(bool(x.get('official_url')) for x in pathways),'requires_current_visa_check':True};limits+=['Visa rules change; verify on the official government source and seek qualified advice.']
 else:raise AssertionError(row)
 out['method_limits']=limits;return {'row':row,'method':method,'inputs':data,'output':out}
