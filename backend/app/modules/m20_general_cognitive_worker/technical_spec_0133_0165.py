"""Semantic workbench for technical-spec ledger rows 133-165.
Each result retains requirement id and original source-line mapping.
"""
from __future__ import annotations
import difflib,hashlib,math,re
META={
133:('M15-02',87,90,'structured_content'),134:('M15-03',87,90,'figure_embedding'),135:('M15-04',87,90,'sandboxed_plot'),136:('M15-05',87,90,'document_versions'),137:('M16-01',91,93,'live_feed'),138:('M16-02',91,93,'priority_timeline'),139:('M16-03',91,93,'approval_queue'),140:('M16-04',91,93,'agent_status'),141:('M16-05',91,93,'kpi_cards'),142:('M16-06',91,93,'command_bar'),143:('M17-01',94,97,'advice_sources'),144:('M17-02',94,97,'whisper_transcription'),145:('M17-03',94,97,'advice_clustering'),146:('M17-04',94,97,'actionable_tips'),147:('M17-05',94,97,'identity_vector'),148:('M17-06',94,97,'structure_retrieval'),149:('M17-07',94,97,'essay_concepts'),150:('M17-08',94,97,'voice_consistency'),151:('M17-09',94,97,'multi_model_critique'),152:('M17-10',94,97,'suggestion_diff'),153:('M17-11',94,97,'literary_devices'),154:('M18-01',98,101,'legal_blueprints'),155:('M18-02',98,101,'blueprint_extraction'),156:('M18-03',98,101,'scam_classifier'),157:('M18-04',98,101,'blueprint_schema'),158:('M18-05',98,101,'contextual_guide'),159:('M18-06',98,101,'swot'),160:('M18-07',98,101,'trend_saturation'),161:('M18-08',98,101,'viability_score'),162:('M18-09',98,101,'feasibility_report'),163:('M19-01',102,108,'idea_intake'),164:('M19-02',102,108,'lean_canvas'),165:('M19-03',102,108,'market_research')}
BY={v[3]:k for k,v in META.items()}
def _need(x,msg):
 if not x:raise ValueError(msg)
def _tokens(x):return re.findall(r"[a-z0-9']+",str(x).lower())
def run(method,data):
 _need(method in BY,'unsupported method');row=BY[method];rid,start,end,_=META[row];out={};limits=['Reference implementation on supplied evidence; external effects require their owning module and approval policy.']
 if row==133:
  sections=data.get('sections');_need(isinstance(sections,list) and sections,'sections required');out={'document':{'sections':[{'heading':s['heading'],'paragraphs':s.get('paragraphs',[]),'bullets':s.get('bullets',[]),'figure_captions':s.get('figure_captions',[])} for s in sections]},'schema_valid':all(s.get('heading') for s in sections)}
 elif row==134:
  figs=data.get('figures');_need(isinstance(figs,list) and figs,'figures required');allowed={'plotly','matplotlib'};_need(all(x.get('engine') in allowed and x.get('artifact_uri') for x in figs),'valid figure engine/artifact required');out={'embedded':[{'engine':x['engine'],'artifact_uri':x['artifact_uri'],'caption':x.get('caption',''),'alt_text':x.get('alt_text','')} for x in figs],'count':len(figs)}
 elif row==135:
  spec=data.get('plot_spec');_need(isinstance(spec,dict),'plot_spec required');allowed={'line','bar','scatter','histogram'};_need(spec.get('kind') in allowed,'unsupported plot kind');_need(set(spec)<= {'kind','x','y','title','labels'},'unsafe plot field');out={'sandbox_plan':{'network':False,'filesystem':'output-only','cpu_seconds':5,'memory_mb':256},'validated_spec':spec,'generated_code':f"plot(kind={spec['kind']!r}, x=data['x'], y=data.get('y'))"};limits+=['No arbitrary caller code is executed.']
 elif row==136:
  old=str(data.get('previous',''));new=str(data.get('current',''));version=int(data.get('version',1));_need(version>=1,'positive version required');out={'version':version,'content_hash':hashlib.sha256(new.encode()).hexdigest(),'diff':list(difflib.unified_diff(old.splitlines(),new.splitlines(),lineterm='')),'parent_version':version-1 if version>1 else None}
 elif row==137:
  events=data.get('events');_need(isinstance(events,list),'events required');allowed={'task_progress','opportunity','approval'};out={'feed':[x for x in events if x.get('type') in allowed],'cursor':max([x.get('sequence',0) for x in events],default=0),'rejected_types':[x.get('type') for x in events if x.get('type') not in allowed]}
 elif row==138:
  tasks=data.get('tasks');_need(isinstance(tasks,list),'tasks required');out={'bars':sorted([{'id':x['id'],'start':x['start'],'end':x['end'],'dependencies':x.get('dependencies',[]),'priority':x.get('priority',0)} for x in tasks],key=lambda x:(-x['priority'],x['start']))}
 elif row==139:
  approvals=data.get('approvals');_need(isinstance(approvals,list),'approvals required');out={'pending':[x for x in approvals if x.get('status')=='pending'],'decided':[x for x in approvals if x.get('status') in {'approved','rejected'}]}
 elif row==140:
  agents=data.get('agents');_need(isinstance(agents,list),'agents required');out={'agents':[{'id':x['id'],'state':x.get('state','unknown'),'last_heartbeat':x.get('last_heartbeat'),'stale':bool(x.get('stale'))} for x in agents],'running':sum(x.get('state')=='running' for x in agents)}
 elif row==141:
  cards=data.get('cards');_need(isinstance(cards,list),'cards required');_need(all(x.get('evidence_ids') for x in cards),'every KPI needs evidence');out={'cards':[{'metric':x['metric'],'value':x['value'],'evidence_ids':x['evidence_ids'],'window':x.get('window')} for x in cards]}
 elif row==142:
  cmd=str(data.get('command','')).strip();_need(cmd,'command required');mutating=any(w in cmd.lower() for w in ['apply','send','submit','delete','buy']);out={'command':cmd,'planner_intent':re.sub(r'\s+',' ',cmd.lower()),'plan_preview_required':True,'approval_required':mutating,'execution_allowed':False}
 elif row==143:
  src=data.get('sources');_need(isinstance(src,list),'sources required');out={'allowed':[x for x in src if x.get('official_or_licensed') and x.get('url') and not x.get('login_scrape')],'blocked':[x for x in src if not x.get('official_or_licensed') or x.get('login_scrape')],'provenance_fields':['url','publisher','captured_at','license']}
 elif row==144:
  media=data.get('media');_need(isinstance(media,list),'media required');_need(all(x.get('permission') and x.get('uri') for x in media),'permission and uri required');out={'jobs':[{'uri':x['uri'],'model':'whisper','language':x.get('language','auto'),'status':'queued'} for x in media]}
 elif row==145:
  advice=data.get('advice');_need(isinstance(advice,list),'advice required');clusters={}
  for x in advice:clusters.setdefault(x.get('topic','other'),[]).append(x['id'])
  out={'clusters':[{'topic':k,'advice_ids':v} for k,v in sorted(clusters.items())]}
 elif row==146:
  advice=data.get('advice');_need(isinstance(advice,list),'advice required');out={'tips':[{'action':x['tip'],'citation':x['source_url'],'advice_id':x['id']} for x in advice if x.get('tip') and x.get('source_url')],'uncited_rejected':sum(bool(x.get('tip')) and not x.get('source_url') for x in advice)}
 elif row==147:
  facts=data.get('user_facts');_need(isinstance(facts,list) and facts,'user_facts required');out={'dimensions':{k:[x['fact'] for x in facts if x.get('dimension')==k] for k in sorted({x.get('dimension') for x in facts})},'owner_editable':True,'inferred_facts':[]}
 elif row==148:
  q=set(data.get('identity_tags',[]));corpus=data.get('structures');_need(isinstance(corpus,list),'structures required');out={'matches':sorted([{'id':x['id'],'score':len(q&set(x.get('tags',[])))/max(1,len(q)),'citation':x.get('source_url')} for x in corpus],key=lambda x:x['score'],reverse=True)}
 elif row==149:
  evidence=data.get('evidence');_need(isinstance(evidence,list) and evidence,'evidence required');count=max(5,min(10,int(data.get('count',5))));concepts=[]
  for i in range(count):
   e=evidence[i%len(evidence)];concepts.append({'title':f"Concept {i+1}: {e['theme']}",'metaphor':e.get('metaphor','thread'),'outline':['scene','change','reflection'],'sample_opening':f"Coaching sample based on: {e.get('fact','student fact')}",'final_essay':False})
  out={'concepts':concepts,'count':count};limits+=['Samples are coaching prompts, not final ghostwritten essays.']
 elif row==150:
  samples=' '.join(data.get('user_samples',[]));draft=str(data.get('draft',''));_need(samples and draft,'samples and draft required');a=set(_tokens(samples));b=set(_tokens(draft));out={'vocabulary_overlap':len(a&b)/max(1,len(b)),'flagged_new_terms':sorted(b-a),'impersonation_allowed':False,'final_essay_generated':False}
 elif row==151:
  reviews=data.get('reviews');_need(isinstance(reviews,list) and len(reviews)>=3,'three model reviews required');out={'dimensions':{x['dimension']:x.get('issues',[]) for x in reviews},'models':len(reviews),'human_decision_required':True}
 elif row==152:
  old=str(data.get('original',''));new=str(data.get('suggested',''));out={'diff':list(difflib.unified_diff(old.splitlines(),new.splitlines(),fromfile='student',tofile='suggestion',lineterm='')),'original_preserved':old}
 elif row==153:
  draft=str(data.get('draft',''));library={'scene':'Open at a concrete moment','motif':'Repeat a meaningful image','callback':'Echo the opening near the end','contrast':'Place before and after side by side'};out={'library':library,'placements':[{'device':k,'suggestion':v,'position':'review-needed'} for k,v in library.items() if k not in draft.lower()]}
 elif row==154:
  src=data.get('sources');_need(isinstance(src,list),'sources required');out={'collectable':[x for x in src if x.get('public') and x.get('url') and not x.get('login_required')],'blocked':[x for x in src if not x.get('public') or x.get('login_required')]}
 elif row==155:
  text=str(data.get('text',''));_need(text,'text required');steps=[x.strip() for x in re.split(r'\n|\d+[.)]',text) if x.strip()];tools=[x for x in data.get('known_tools',[]) if x.lower() in text.lower()];money=[x for x in ['subscription','affiliate','service','product','ads'] if x in text.lower()];out={'steps':steps,'tools':tools,'monetization':money}
 elif row==156:
  claims=' '.join(map(str,data.get('claims',[]))).lower();signals={'guaranteed_income':('guaranteed' in claims),'upfront_fee':bool(data.get('upfront_fee')),'urgency':('act now' in claims),'verifiable_identity':bool(data.get('verifiable_identity'))};risk=sum([signals['guaranteed_income'],signals['upfront_fee'],signals['urgency'],not signals['verifiable_identity']])/4;out={'risk_score':risk,'signals':signals,'blocked':risk>=.5}
 elif row==157:
  required=['steps','tools','complexity','time_to_first_dollar','automation_level','source_urls'];missing=[x for x in required if x not in data];_need(not missing,f'missing fields: {missing}');out={'blueprint':{k:data[k] for k in required},'schema_valid':True}
 elif row==158:
  bp=data.get('blueprint');ctx=data.get('user_context');_need(isinstance(bp,dict) and isinstance(ctx,dict),'blueprint/context required');out={'guide':[{'order':i+1,'step':s,'adaptation':f"Use {ctx.get('weekly_hours','available')} hours/week"} for i,s in enumerate(bp.get('steps',[]))],'constraints':ctx.get('constraints',[])}
 elif row==159:
  out={'strengths':data.get('strengths',[]),'weaknesses':data.get('weaknesses',[]),'opportunities':data.get('opportunities',[]),'threats':data.get('threats',[]),'complete':all(isinstance(data.get(k),list) and data[k] for k in ['strengths','weaknesses','opportunities','threats'])}
 elif row==160:
  points=data.get('trend_points');_need(isinstance(points,list) and len(points)>=2,'trend_points required');first=float(points[0]);last=float(points[-1]);out={'trend_change':last-first,'saturation_signal':sum(points)/len(points)/100,'direction':'rising' if last>first else 'falling' if last<first else 'flat'}
 elif row==161:
  saturation=float(data['saturation']);barrier=float(data['barrier']);demand=float(data['demand']);_need(all(0<=x<=1 for x in [saturation,barrier,demand]),'scores 0..1 required');score=.5*demand+.25*(1-saturation)+.25*(1-barrier);out={'viability_score':score,'barrier_to_entry':barrier,'recommendation':'go' if score>=.65 else 'investigate' if score>=.4 else 'no-go'}
 elif row==162:
  required=['blueprint','swot','saturation','viability'];missing=[k for k in required if k not in data];_need(not missing,f'missing report sections: {missing}');out={'report':{k:data[k] for k in required},'evidence_urls':data.get('evidence_urls',[]),'complete':True}
 elif row==163:
  text=str(data.get('text','')).strip();transcript=str(data.get('voice_transcript','')).strip();_need(bool(text)^bool(transcript),'provide exactly one of text or voice_transcript');out={'idea':text or transcript,'modality':'text' if text else 'voice','transcribed':bool(transcript),'status':'captured'}
 elif row==164:
  idea=str(data.get('idea','')).strip();_need(idea,'idea required');out={'lean_canvas':{'problem':data.get('problem'),'customer_segments':data.get('customers',[]),'unique_value_proposition':idea,'solution':data.get('solution'),'channels':data.get('channels',[]),'revenue_streams':data.get('revenue',[]),'cost_structure':data.get('costs',[]),'key_metrics':data.get('metrics',[]),'unfair_advantage':data.get('advantage')},'unknown_fields':[k for k,v in data.items() if v is None]}
 elif row==165:
  queries=data.get('queries');_need(isinstance(queries,list) and queries,'queries required');out={'jobs':[{'query':q,'sources':['google_public','producthunt_public'],'status':'queued','login_scraping':False} for q in queries],'concurrent_limit':min(len(queries),int(data.get('concurrent_limit',4))),'evidence_required':True}
 out['method_limits']=limits
 return {'row':row,'requirement_id':rid,'source_line_start':start,'source_line_end':end,'method':method,'inputs':data,'output':out}
