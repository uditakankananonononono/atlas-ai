"""Deterministic AI-system evaluation engines for feature rows 1910-1959.

One keyed engine per ledger row: every row owns a distinct function with
row-specific inputs, metrics, assumptions and method limits. These engines
evaluate caller-supplied artifacts, scores, traces and policy facts. They do
not train opaque models, synthesize or alter media, call external services, or
execute agent actions; release/deployment outcomes are advisory gates that a
human approval step must enforce. Results retain inputs, evidence flags,
assumptions, and explicit limitations so every number is auditable.
"""
from __future__ import annotations
import math,re

def _f(x,n):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError(f'{n} must be a finite number')
 return float(x)
def _v(d,k,n=1):
 x=d.get(k)
 if not isinstance(x,list) or len(x)<n:raise ValueError(f'{k} needs at least {n} numeric values')
 return [_f(v,k) for v in x]
def _l(d,k,n=1):
 x=d.get(k)
 if not isinstance(x,list) or len(x)<n:raise ValueError(f'{k} needs at least {n} entries')
 return x
def _aligned(*xs):
 if len({len(x) for x in xs})!=1:raise ValueError('aligned arrays required')
def _tokens(s):return re.findall(r"[A-Za-z0-9']+",str(s).lower())
def _bool(d,k):
 v=d.get(k)
 if not isinstance(v,bool):raise ValueError(f'{k} must be a boolean')
 return v
def _syllables(w):
 w=re.sub(r'[^a-z]','',w.lower())
 if not w:return 0
 groups=re.findall(r'[aeiouy]+',w);c=len(groups)
 if w.endswith('e') and c>1:c-=1
 return max(1,c)

def _r1910(d,p):
 logp=_v(d,'token_log_probabilities');n=len(logp);loss=-sum(logp)/n;cwin=_f(d.get('context_window',n),'context_window')
 if cwin<=0:raise ValueError('context_window must be positive')
 return {'token_count':n,'negative_log_likelihood':loss,'perplexity':math.exp(min(loss,700)),'bits_per_token':loss/math.log(2),'context_utilization':min(1.0,n/cwin)},['Token log probabilities come from one tokenizer and one held-out evaluation corpus.'],['Perplexity is comparable only across identical tokenizers and corpora; it says nothing about factuality or downstream task quality.']
def _r1911(d,p):
 mods=_l(d,'modalities');scores=_v(d,'modality_scores');weights=_v(d,'weights');_aligned(mods,scores,weights);z=sum(weights)
 if z<=0:raise ValueError('positive weight total required')
 probs=[w/z for w in weights];ent=-sum(x*math.log(x) for x in probs if x>0)
 return {'modalities':mods,'fused_score':sum(s*w for s,w in zip(scores,weights))/z,'weakest_modality':mods[min(range(len(scores)),key=scores.__getitem__)],'modality_gap':max(scores)-min(scores),'distinct_modality_coverage':len(set(mods)),'fusion_weight_entropy':ent},['Each modality score is measured on the same examples before late fusion.'],['Weighted fusion hides per-modality failure modes; a high fused score can coexist with a failed modality.']
def _r1912(d,p):
 images=_l(d,'image_ids');captions=_l(d,'captions');sims=_v(d,'similarities');_aligned(images,captions,sims);th=_f(p.get('threshold',.5),'threshold');below=[images[i] for i,s in enumerate(sims) if s<th]
 return {'pair_count':len(images),'mean_alignment':sum(sims)/len(sims),'grounded_pairs':len(sims)-len(below),'grounding_rate':(len(sims)-len(below))/len(sims),'below_threshold_images':below},['Similarity scores come from one embedding space for both images and captions.'],['Embedding similarity is a proxy for grounding, not proof the model attends to the right image regions.']
def _r1913(d,p):
 prompt=set(_tokens(d.get('prompt','')));artifact=set(_tokens(d.get('artifact_description','')));q=_v(d,'quality_scores');w=_f(d.get('width',0),'width');h=_f(d.get('height',0),'height');rw=_f(d.get('requested_width',w),'requested_width');rh=_f(d.get('requested_height',h),'requested_height')
 if w<0 or h<0 or rw<=0 or rh<=0:raise ValueError('invalid dimensions')
 return {'prompt_adherence':len(prompt&artifact)/len(prompt) if prompt else 0,'mean_quality':sum(q)/len(q),'minimum_quality':min(q),'megapixels':round(w*h/1e6,4),'resolution_match':w>=rw and h>=rh,'aspect_ratio_error':abs((w/h)-(rw/rh)) if w and h else None,'provenance_present':bool(d.get('provenance')),'watermark_present':bool(d.get('watermark'))},[],['Metadata and text-overlap checks cannot establish perceptual quality, copyright status, or that the image is safe to publish.']
def _r1914(d,p):
 prompt=set(_tokens(d.get('prompt','')));artifact=set(_tokens(d.get('artifact_description','')));frames=_v(d,'frame_quality_scores',2);fps=_f(d.get('fps',24),'fps');dur=_f(d.get('duration_seconds',len(frames)/fps),'duration_seconds')
 if fps<=0 or dur<=0:raise ValueError('fps and duration_seconds must be positive')
 flick=sum(abs(frames[i]-frames[i-1]) for i in range(1,len(frames)))/(len(frames)-1);worst=min(range(len(frames)),key=frames.__getitem__)
 return {'prompt_adherence':len(prompt&artifact)/len(prompt) if prompt else 0,'mean_frame_quality':sum(frames)/len(frames),'temporal_flicker':flick,'worst_frame_index':worst,'expected_frame_count':int(round(dur*fps)),'scored_frame_coverage':len(frames)/max(1,int(round(dur*fps)))},['Sampled frame scores represent the whole clip.'],['Frame sampling misses short artifacts between samples; temporal scores do not prove narrative or physical coherence.']
def _r1915(d,p):
 verts=_f(d.get('vertex_count',0),'vertex_count');faces=_f(d.get('face_count',0),'face_count');nm=int(_f(d.get('non_manifold_edges',0),'non_manifold_edges'));bb=d.get('bounding_box')
 if verts<=0 or faces<=0:raise ValueError('positive vertex_count and face_count required')
 if not isinstance(bb,dict):raise ValueError('bounding_box required')
 dims=[_f(bb.get(k,0),f'bounding_box.{k}') for k in ('x','y','z')];maxf=int(_f(p.get('max_faces',100000),'max_faces'));wat=_bool(d,'watertight')
 return {'vertex_count':int(verts),'face_count':int(faces),'bounding_volume':dims[0]*dims[1]*dims[2],'face_to_vertex_ratio':faces/verts,'watertight':wat,'non_manifold_edges':nm,'manifold_ok':wat and nm==0,'within_triangle_budget':faces<=maxf},['Counts come from the exported mesh, not the generator\'s self-report.'],['Mesh statistics do not measure visual quality or printability; a manifold mesh can still be a bad artifact.']
def _r1916(d,p):
 sr=_f(d.get('sample_rate_hz',0),'sample_rate_hz');dur=_f(d.get('duration_seconds',0),'duration_seconds');peak=_f(d.get('peak_amplitude',0),'peak_amplitude');rms=_f(d.get('rms_amplitude',0),'rms_amplitude');clip=int(_f(d.get('clipping_samples',0),'clipping_samples'));total=int(_f(d.get('total_samples',0),'total_samples'))
 if sr<=0 or dur<=0 or total<=0:raise ValueError('sample_rate_hz, duration_seconds and total_samples must be positive')
 if not 0<=rms<=peak<=1:raise ValueError('amplitudes must satisfy 0<=rms<=peak<=1')
 minsr=_f(p.get('min_sample_rate',16000),'min_sample_rate')
 return {'sample_rate_hz':sr,'sample_rate_ok':sr>=minsr,'duration_seconds':dur,'crest_factor':peak/rms if rms>0 else None,'estimated_loudness_dbfs':20*math.log10(rms) if rms>0 else None,'clipping_rate':clip/total},['Amplitude statistics are computed on the final rendered waveform.'],['Signal statistics cannot judge semantic content, speaker identity, or musical quality.']
def _r1917(d,p):
 KRUMHANSL=[6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88]
 events=_l(d,'note_events');key=d.get('declared_key')
 if not isinstance(key,int) or isinstance(key,bool) or not 0<=key<=11:raise ValueError('declared_key must be a pitch class 0-11')
 tempos=_v(d,'tempo_bpm_samples');pcs=[0]*12;total_dur=0.0
 for e in events:
  pc=e.get('pitch_class');du=_f(e.get('duration',0),'duration')
  if not isinstance(pc,int) or isinstance(pc,bool) or not 0<=pc<=11 or du<=0:raise ValueError('each note_event needs pitch_class 0-11 and positive duration')
  pcs[pc]+=du;total_dur+=du
 hist=[x/total_dur for x in pcs];prof=KRUMHANSL[-key%12:]+KRUMHANSL[:-key%12] if key else KRUMHANSL
 mh=sum(hist)/12;mp=sum(prof)/12
 cov=sum((a-mh)*(b-mp) for a,b in zip(hist,prof));den=math.sqrt(sum((a-mh)**2 for a in hist)*sum((b-mp)**2 for b in prof))
 tmean=sum(tempos)/len(tempos);tvar=sum((t-tmean)**2 for t in tempos)/len(tempos)
 return {'note_count':len(events),'total_duration':total_dur,'key_correlation':cov/den if den else 0,'mean_tempo_bpm':tmean,'tempo_stability':1/(1+math.sqrt(tvar)),'pitch_class_histogram':hist},['Duration-weighted pitch classes approximate key; declared_key uses the Krumhansl major profile.'],['Key correlation is a coarse tonal heuristic, not a judgment of musical merit.']
def _r1918(d,p):
 consent=_bool(d,'consent_verified');prov=bool(d.get('provenance'));wm=_bool(d,'watermark');sim=_f(d.get('identity_similarity',0),'identity_similarity');svs=_f(d.get('speaker_verification_score',0),'speaker_verification_score');th=_f(p.get('similarity_threshold',.85),'similarity_threshold')
 flags=[x for x,v in [('missing_consent',consent),('missing_provenance',prov),('missing_watermark',wm)] if not v]
 return {'identity_similarity':sim,'speaker_verification_score':svs,'similarity_above_threshold':sim>=th,'consent_verified':consent,'provenance_present':prov,'watermark_present':wm,'release_allowed':consent and prov and wm,'risk_flags':flags},[],['No voice is synthesized here; identity similarity never substitutes for documented consent from the speaker.']
def _r1919(d,p):
 consent=_bool(d,'consent_verified');prov=bool(d.get('provenance'));wm=_bool(d,'watermark');art=_f(d.get('face_swap_artifact_score',0),'face_swap_artifact_score');temp=_f(d.get('temporal_inconsistency',0),'temporal_inconsistency');sim=_f(d.get('identity_similarity',0),'identity_similarity')
 risk=round(.5*art+.3*temp+.2*sim,6);flags=[x for x,v in [('missing_consent',consent),('missing_provenance',prov),('missing_watermark',wm),('high_artifact_score',art<=.5),('high_temporal_inconsistency',temp<=.5)] if not v]
 blocked=not(consent and prov and wm)
 return {'manipulation_risk_score':risk,'detector_signals':{'face_swap_artifact_score':art,'temporal_inconsistency':temp,'identity_similarity':sim},'consent_verified':consent,'provenance_present':prov,'watermark_present':wm,'release_blocked':blocked,'recommended_action':'block_release' if blocked else ('human_review' if risk>.4 else 'allow_with_label'),'risk_flags':flags},['Detector scores come from documented forensic tools with known error rates.'],['Detector scores are probabilistic hints; none proves manipulation, and this engine never creates manipulated media.']
def _r1920(d,p):
 def rgb(c):
  if isinstance(c,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',c):return tuple(int(c[i:i+2],16) for i in (1,3,5))
  raise ValueError('palette colors must be #rrggbb strings')
 pal=[rgb(c) for c in _l(d,'palette')];ref=[rgb(c) for c in _l(d,'reference_palette')];focal=d.get('composition_focal_point');canvas=d.get('canvas')
 if not isinstance(focal,dict) or not isinstance(canvas,dict):raise ValueError('composition_focal_point and canvas required')
 fx=_f(focal.get('x',0),'focal.x');fy=_f(focal.get('y',0),'focal.y');cw=_f(canvas.get('width',0),'canvas.width');ch=_f(canvas.get('height',0),'canvas.height')
 if cw<=0 or ch<=0:raise ValueError('canvas dimensions must be positive')
 dist=lambda a,b:math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
 pd=[min(dist(c,r) for r in ref) for c in pal];style=_v(d,'style_match_scores')
 tx,ty=cw/3,ch/3;thirds=[(tx,ty),(2*tx,ty),(tx,2*ty),(2*tx,2*ty)];fd=min(dist((fx,fy),t) for t in thirds);maxd=dist((0,0),(cw,ch))
 return {'palette_mean_distance':sum(pd)/len(pd),'palette_worst_distance':max(pd),'rule_of_thirds_score':1-fd/maxd,'mean_style_match':sum(style)/len(style),'provenance_present':bool(d.get('provenance'))},['Palette fidelity is measured in RGB space against the caller-declared reference palette.'],['Color and composition metrics do not measure artistic value or originality.']
def _r1921(d,p):
 text=str(d.get('text',''));sources=_l(d,'sources',0);claims=_l(d,'claims',0);words=_tokens(text);sents=max(1,len(re.findall(r'[.!?]+',text)));syl=sum(_syllables(w) for w in words)
 wps=len(words)/sents;spw=syl/len(words) if words else 0
 return {'word_count':len(words),'sentence_count':sents,'average_words_per_sentence':wps,'flesch_kincaid_grade':round(.39*wps+11.8*spw-15.59,2) if words else 0,'citation_coverage':min(1,len(sources)/len(claims)) if claims else 1,'uncited_claims':max(0,len(claims)-len(sources)),'duplicate_word_ratio':1-len(set(words))/len(words) if words else 0},['The claims list is the caller\'s own extraction of checkable statements.'],['Readability and citation counts do not verify that any claim is true.']
def _r1922(d,p):
 passed=_v(d,'tests_passed');total=_v(d,'tests_total');_aligned(passed,total)
 if any(t<0 or q<0 or q>t for q,t in zip(passed,total)):raise ValueError('invalid test counts')
 cov=_f(d.get('coverage_percent',0),'coverage_percent');mincov=_f(p.get('min_coverage',80),'min_coverage');sai=int(_f(d.get('static_analysis_issues',0),'static_analysis_issues'));clean=_bool(d,'dependency_scan_clean');tp,tt=sum(passed),sum(total)
 return {'suites':len(total),'tests_passed':tp,'tests_total':tt,'pass_rate':tp/tt if tt else None,'failing_suites':[i for i,(q,t) in enumerate(zip(passed,total)) if q<t],'coverage_percent':cov,'coverage_ok':cov>=mincov,'static_analysis_issues':sai,'dependency_scan_clean':clean,'quality_gate_passed':tp==tt>0 and cov>=mincov and sai==0 and clean},['Reported test counts come from a CI run on the exact submitted revision.'],['Green tests and coverage never prove the absence of defects.']
def _r1923(d,p):
 steps=_l(d,'steps');irr=[s for s in steps if s.get('irreversible')];appr=[s for s in irr if s.get('approved')];blocked=sum(bool(s.get('blocked')) for s in steps);overrides=int(_f(d.get('human_overrides',0),'human_overrides'))
 return {'step_count':len(steps),'irreversible_steps':len(irr),'approved_irreversible_steps':len(appr),'approval_coverage':len(appr)/len(irr) if irr else 1,'blocked_steps':blocked,'human_overrides':overrides,'goal_completed':bool(d.get('goal_completed')),'safe_to_execute':len(appr)==len(irr)},['Step metadata truthfully marks irreversible effects and their approval state.'],['Supervision metrics describe the recorded run; they cannot certify future runs are safe.']
def _r1924(d,p):
 steps=_l(d,'steps');assisted=sum(bool(s.get('human_assisted')) for s in steps);overrides=int(_f(d.get('human_overrides',0),'human_overrides'));esc=int(_f(d.get('escalation_events',0),'escalation_events'));viol=_l(d,'constraint_violations',0);maxo=int(_f(p.get('max_overrides',0),'max_overrides'))
 return {'step_count':len(steps),'autonomy_index':(len(steps)-assisted)/len(steps),'human_assisted_steps':assisted,'override_rate':overrides/len(steps),'escalation_rate':esc/len(steps),'constraint_violation_count':len(viol),'goal_completed':bool(d.get('goal_completed')),'autonomy_acceptable':not viol and overrides<=maxo},['Autonomy is scored from recorded run traces, not the agent\'s self-report.'],['An acceptable trace sample does not license unsupervised operation; irreversible actions still need approval gates.']
def _r1925(d,p):
 agents=_l(d,'agents');edges=_l(d,'delegations',0);known=set(agents);invalid=[e for e in edges if e.get('from') not in known or e.get('to') not in known]
 adj={}
 for e in edges:
  if e.get('from') in known:adj.setdefault(e['from'],[]).append(e.get('to'))
 depth=0;cycles=[]
 def dfs(u,path):
  nonlocal depth
  for v in adj.get(u,[]):
   if v in path:cycles.append(path[path.index(v):]+[v])
   elif len(path)<len(known):dfs(v,path+[v]);depth=max(depth,len(path)+1)
 for a in known:dfs(a,[a])
 return {'agent_count':len(known),'delegation_count':len(edges),'invalid_delegations':invalid,'connected_agents':sorted({v for e in edges for v in (e.get('from'),e.get('to')) if v in known}),'max_delegation_depth':depth,'delegation_cycles':cycles},['The delegation list is the complete declared edge set for the system under review.'],['Graph validity says nothing about whether delegating these tasks is appropriate or permitted.']
def _r1926(d,p):
 msgs=_l(d,'messages');required={'sender','recipient','type','correlation_id'};allowed=p.get('allowed_types') or ['request','reply','inform','error'];valid=[required<=set(m) for m in msgs]
 bycorr={}
 for m in msgs:bycorr.setdefault(m.get('correlation_id'),[]).append(m)
 orphans=[c for c,ms in bycorr.items() if any(m.get('type')=='request' for m in ms) and not any(m.get('type')=='reply' for m in ms)]
 return {'message_count':len(msgs),'schema_valid_rate':sum(valid)/len(valid),'protocol_violations':[i for i,m in enumerate(msgs) if m.get('type') not in allowed],'unmatched_replies':sum(m.get('type')=='reply' and not m.get('in_reply_to') for m in msgs),'orphan_request_correlations':orphans,'correlation_ids':len(bycorr)},['Message logs are complete for the reviewed window.'],['Protocol conformance does not verify message content is truthful or authorized.']
def _r1927(d,p):
 tasks=_l(d,'tasks');owners=[t.get('owner') for t in tasks];deps={t.get('id'):set(t.get('depends_on',[])) for t in tasks};known=set(deps)
 visiting,done,order=set(),set(),[]
 def dfs(u):
  if u in visiting:raise ValueError('dependency cycle detected')
  if u in done or u not in deps:return
  visiting.add(u)
  for x in deps[u]:dfs(x)
  visiting.discard(u);done.add(u);order.append(u)
 for t in deps:dfs(t)
 depth={}
 for u in order:depth[u]=max((depth.get(x,0) for x in deps[u]),default=0)+1
 return {'task_count':len(tasks),'unowned_tasks':sum(not x for x in owners),'unknown_dependencies':sorted({x for ds in deps.values() for x in ds if x not in known}),'ready_tasks':[i for i,ds in deps.items() if not ds],'has_cycle':False,'critical_path_length':max(depth.values(),default=0)},['Task identifiers are unique and depends_on lists are complete.'],['Schedule structure metrics ignore duration, cost and resource contention.']
def _r1928(d,p):
 offers=_l(d,'offers');utils=_v(d,'utilities');_aligned(offers,utils);res=_f(p.get('reservation_utility',0),'reservation_utility');feasible=[(i,u) for i,u in enumerate(utils) if u>=res];best=max(feasible,key=lambda z:z[1]) if feasible else None
 return {'agreement_possible':best is not None,'selected_offer':offers[best[0]] if best else None,'selected_utility':best[1] if best else None,'utility_gap_to_reservation':(best[1]-res) if best else None,'offers_below_reservation':len(utils)-len(feasible),'concession_count':sum(utils[i]<utils[i-1] for i in range(1,len(utils)))},['Utilities are truthful, comparable scores on one scale from the negotiating party this engine serves.'],['Selecting an offer is advisory; commitments bind only after the owner approves them.']
def _r1929(d,p):
 before=_v(d,'before_scores');after=_v(d,'after_scores');_aligned(before,after);gains=[b-a for a,b in zip(before,after)];mg=sum(gains)/len(gains)
 var=sum((g-mg)**2 for g in gains)/len(gains)
 return {'mean_gain':mg,'gain_std':math.sqrt(var),'improved_fraction':sum(x>0 for x in gains)/len(gains),'regressions':[i for i,x in enumerate(gains) if x<0],'effect_size':mg/math.sqrt(var) if var>0 else None},['Before and after scores are measured on the same held-out tasks.'],['Average improvement can hide severe regressions on individual tasks; inspect the regressions list.']
def _r1930(d,p):
 chosen=_v(d,'chosen_rewards');rejected=_v(d,'rejected_rewards');_aligned(chosen,rejected);m=[a-b for a,b in zip(chosen,rejected)];acc=sum(x>0 for x in m)/len(m)
 se=math.sqrt(acc*(1-acc)/len(m))
 return {'preference_accuracy':acc,'accuracy_ci95':[max(0,acc-1.96*se),min(1,acc+1.96*se)],'mean_reward_margin':sum(m)/len(m),'ties':sum(x==0 for x in m),'pair_count':len(m)},['Reward scores are held-out and aligned to human preference pairs.'],['Preference accuracy measures reward-model agreement with labelers, not goodness of the resulting policy.']
def _r1931(d,p):
 principles=_l(d,'principles');critiques=_l(d,'critiques',0);revisions=_l(d,'revisions',0);uncrit=[x for x in principles if not any(x in str(c) for c in critiques)]
 return {'principle_count':len(principles),'critique_count':len(critiques),'revision_count':len(revisions),'principle_critique_coverage':1-len(uncrit)/len(principles),'uncritiqued_principles':uncrit,'revision_followthrough':min(1,len(revisions)/len(critiques)) if critiques else None,'chain_complete':not uncrit and len(revisions)>=len(critiques)>0},['Critique entries name the principle they address.'],['A complete critique-revision chain on paper is not evidence the resulting behavior changed.']
def _r1932(d,p):
 intended=_v(d,'intended_scores');observed=_v(d,'observed_scores');_aligned(intended,observed);err=[abs(a-b) for a,b in zip(intended,observed)];tol=_f(p.get('tolerance',.1),'tolerance');worst=max(range(len(err)),key=err.__getitem__)
 return {'mean_objective_gap':sum(err)/len(err),'max_objective_gap':err[worst],'worst_case_index':worst,'within_tolerance_rate':sum(x<=tol for x in err)/len(err),'misaligned_cases':[i for i,x in enumerate(err) if x>tol]},['Observed scores faithfully proxy the deployed behavior on the evaluated distribution.'],['Behavioral gap metrics miss reward hacking that stays inside the measured proxy.']
def _r1933(d,p):
 sev=_v(d,'hazard_severity');lik=_v(d,'hazard_likelihood');det=_v(d,'detectability');_aligned(sev,lik,det);rpn=[s*l*x for s,l,x in zip(sev,lik,det)];th=_f(p.get('threshold',1),'threshold')
 return {'risk_priority_numbers':rpn,'total_risk':sum(rpn),'unacceptable_hazards':[i for i,x in enumerate(rpn) if x>th],'top_hazard_index':max(range(len(rpn)),key=rpn.__getitem__),'mean_detectability':sum(det)/len(det)},['Severity, likelihood and detectability scores use the caller\'s documented hazard rubric.'],['RPN ranking is a screening heuristic, not a quantified risk assessment; low RPN never means safe.']
def _r1934(d,p):
 principles=_l(d,'principles');ev=d.get('evidence')
 if not isinstance(ev,dict):raise ValueError('evidence mapping required')
 status=[{'principle':x,'evidenced':bool(ev.get(x))} for x in principles];covered=[s['principle'] for s in status if s['evidenced']]
 return {'principle_count':len(principles),'coverage':len(covered)/len(principles),'covered_principles':covered,'gaps':[s['principle'] for s in status if not s['evidenced']],'per_principle_status':status,'review_recommendation':'proceed_with_documented_gaps' if len(covered)==len(principles) else 'close_gaps_before_claiming_conformance'},['The evidence mapping points to real artifacts the reviewer can open.'],['Evidence coverage is not an ethical judgment; unlisted harms remain unexamined.']
def _r1935(d,p):
 imp=_v(d,'feature_importance');names=_l(d,'feature_names');_aligned(imp,names);total=sum(abs(x) for x in imp);rank=sorted(zip(names,imp),key=lambda z:abs(z[1]),reverse=True)
 full=_f(d.get('score_full',0),'score_full');notop=_f(d.get('score_without_top',full),'score_without_top')
 return {'ranked_features':[{'feature':n,'importance':v,'share':abs(v)/total if total else 0} for n,v in rank],'top_feature':rank[0][0],'sparsity':sum(x==0 for x in imp)/len(imp),'faithfulness_drop':full-notop,'faithful':(full-notop)>0 if total else None},['Importance values come from one stated explanation method.'],['Feature attribution describes this explanation method, not causality or the model\'s true internals.']
def _r1936(d,p):
 nfeat=int(_f(d.get('num_features_used',0),'num_features_used'));depth=int(_f(d.get('max_rule_depth',0),'max_rule_depth'));rules=int(_f(d.get('num_rules',0),'num_rules'));mono=_l(d,'monotonicity_checks',0);fid=_f(d.get('surrogate_fidelity',1),'surrogate_fidelity')
 if nfeat<=0 or depth<0 or rules<0:raise ValueError('invalid model shape counts')
 viol=sum(int(_f(m.get('violations',0),'violations')) for m in mono);maxr=int(_f(p.get('max_rules',10),'max_rules'))
 return {'num_features_used':nfeat,'max_rule_depth':depth,'num_rules':rules,'monotonicity_violations':viol,'monotonicity_ok':viol==0,'surrogate_fidelity':fid,'complexity_score':nfeat*(depth+1)+rules,'globally_interpretable':rules<=maxr and depth<=3 and viol==0},['Shape counts describe the deployed artifact, not a simplified stand-in.'],['An interpretable form does not guarantee a faithful or fair model; surrogate fidelity bounds what explanations of it can claim.']
def _r1937(d,p):
 groups=_l(d,'groups');sel=_l(d,'selected');pos=_l(d,'positive_labels');_aligned(groups,sel,pos);stats={}
 for g in sorted(set(groups),key=str):
  ids=[i for i,x in enumerate(groups) if x==g];sr=sum(bool(sel[i]) for i in ids)/len(ids);pids=[i for i in ids if pos[i]];tpr=sum(bool(sel[i]) for i in pids)/len(pids) if pids else None;stats[str(g)]={'n':len(ids),'selection_rate':sr,'true_positive_rate':tpr}
 rates=[x['selection_rate'] for x in stats.values()];tprs=[x['true_positive_rate'] for x in stats.values() if x['true_positive_rate'] is not None]
 return {'group_metrics':stats,'demographic_parity_difference':max(rates)-min(rates),'selection_rate_ratio':min(rates)/max(rates) if max(rates)>0 else None,'equal_opportunity_difference':(max(tprs)-min(tprs)) if len(tprs)>1 else None},['Group labels and labels are accurate and lawfully usable for this audit.'],['Two parity metrics cannot capture every fairness definition; some definitions are mutually incompatible.']
def _r1938(d,p):
 dims=_l(d,'dimensions');scores=_v(d,'scores');weights=_v(d,'weights');_aligned(dims,scores,weights);z=sum(weights)
 if z<=0:raise ValueError('positive weight total required')
 ws=sum(s*w for s,w in zip(scores,weights))/z;th=_f(p.get('threshold',.7),'threshold');order=sorted(zip(dims,scores),key=lambda z:z[1])
 return {'dimension_scores':dict(zip(dims,scores)),'weighted_score':ws,'weakest_dimension':order[0][0],'dimension_ranking':[x[0] for x in order],'all_thresholds_met':all(s>=th for s in scores),'maturity_level':'leading' if ws>=.9 else ('established' if ws>=th else 'developing')},['Dimension scores come from documented assessments on the stated review date.'],['A composite score smooths over the weakest dimension; never report the composite alone.']
def _r1939(d,p):
 cal=_v(d,'calibration_errors');rob=_v(d,'robustness_scores');eps=_f(d.get('privacy_budget_epsilon',0),'privacy_budget_epsilon');maxeps=_f(p.get('max_epsilon',1),'max_epsilon');minrob=_f(p.get('min_robustness',.8),'min_robustness');maxcal=_f(p.get('max_calibration_error',.05),'max_calibration_error')
 ece=sum(cal)/len(cal)
 return {'expected_calibration_error':ece,'min_robustness':min(rob),'privacy_budget_epsilon':eps,'calibration_ok':ece<=maxcal,'robustness_ok':min(rob)>=minrob,'privacy_ok':eps<=maxeps,'trust_certificate_ready':ece<=maxcal and min(rob)>=minrob and eps<=maxeps},['Calibration, robustness and privacy figures come from the stated evaluation harness and accounting method.'],['Passing three thresholds is a checklist result, not a guarantee of trustworthiness in deployment.']
def _r1940(d,p):
 roles=_l(d,'roles');pols=_l(d,'policies',0);cad=int(_f(d.get('review_cadence_days',0),'review_cadence_days'));inc=_bool(d,'incident_process_documented');maxcad=int(_f(p.get('max_review_cadence_days',365),'max_review_cadence_days'))
 unfilled=[r.get('name') for r in roles if not r.get('filled')];noresp=[r.get('name') for r in roles if not r.get('responsibilities')]
 return {'role_count':len(roles),'unfilled_roles':unfilled,'roles_without_responsibilities':noresp,'policy_count':len(pols),'review_cadence_days':cad,'cadence_ok':0<cad<=maxcad,'incident_process_documented':inc,'governance_score':(len(roles)-len(unfilled)-len(noresp))/len(roles) if roles else 0,'board_ready':not unfilled and not noresp and inc and 0<cad<=maxcad},['The role and policy lists are the complete current governance inventory.'],['Structural completeness does not measure whether governance is actually followed.']
def _r1941(d,p):
 jur=str(d.get('jurisdiction','')).strip()
 if not jur:raise ValueError('jurisdiction required')
 reqs=_l(d,'requirements');ev=d.get('evidence')
 if not isinstance(ev,dict):raise ValueError('evidence mapping required')
 met=[r for r in reqs if bool(ev.get(r))]
 return {'jurisdiction':jur,'obligations':len(reqs),'met':len(met),'compliance_rate':len(met)/len(reqs),'met_obligations':met,'gaps':[r for r in reqs if r not in met],'decision':'ready_for_counsel_review' if len(met)==len(reqs) else 'evidence_incomplete'},['The obligation list comes from counsel-reviewed sources for the stated jurisdiction.'],['This checklist is not legal advice and is not a regulator determination.']
def _r1942(d,p):
 stmts=_l(d,'policy_statements');controls=d.get('controls')
 if not isinstance(controls,dict):raise ValueError('controls mapping required')
 viol=_l(d,'violations',0);bysev={}
 for v in viol:
  sev=str(v.get('severity','unknown'));bysev[sev]=bysev.get(sev,0)+1
 covered=[s for s in stmts if bool(controls.get(s))]
 return {'policy_statements':len(stmts),'statements_with_controls':len(covered),'conformance_rate':len(covered)/len(stmts),'uncontrolled_statements':[s for s in stmts if s not in covered],'violation_count':len(viol),'violations_by_severity':bysev,'enforcement_review_needed':bool(viol) or len(covered)<len(stmts)},['The controls mapping reflects controls actually operating today.'],['Policy-on-paper conformance does not detect unrecorded violations.']
def _r1943(d,p):
 std=str(d.get('standard','')).strip()
 if not std:raise ValueError('standard required')
 clauses=_l(d,'clauses');conf=d.get('conformity')
 if not isinstance(conf,dict):raise ValueError('conformity mapping required')
 nc=[{'clause':c,'severity':str(conf.get(c,{}).get('severity','major')) if isinstance(conf.get(c),dict) else 'major'} for c in clauses if not conf.get(c) or (isinstance(conf.get(c),dict) and not conf.get(c).get('conforms'))]
 major=sum(1 for x in nc if x['severity']=='major')
 return {'standard':std,'clause_count':len(clauses),'conforming_clauses':len(clauses)-len(nc),'clause_coverage':(len(clauses)-len(nc))/len(clauses),'nonconformities':nc,'major_nonconformities':major,'certification_body_review':'eligible' if major==0 else 'not_eligible'},['The clause list is the complete clause inventory of the named standard revision.'],['Self-assessed conformity is not certification; only an accredited body can certify.']
def _r1944(d,p):
 controls=_l(d,'controls');exc=[c for c in controls if c.get('result')!='pass'];noev=[c.get('id') for c in controls if not c.get('evidence')]
 complete=not noev
 return {'controls_tested':len(controls),'passed':len(controls)-len(exc),'exceptions':exc,'exception_rate':len(exc)/len(controls),'controls_without_evidence':noev,'evidence_complete':complete,'audit_opinion':'unqualified' if not exc and complete else ('adverse' if len(exc)>len(controls)/2 else 'qualified')},['Tested controls are a representative sample of the control set in scope.'],['An unqualified opinion covers only the tested controls and period.']
def _r1945(d,p):
 req=_l(d,'required_artifacts');sub=d.get('submitted')
 if not isinstance(sub,dict):raise ValueError('submitted mapping required')
 acc=_bool(d,'accredited_body');due=int(_f(d.get('surveillance_audit_due_days',365),'surveillance_audit_due_days'));missing=[a for a in req if not sub.get(a)]
 return {'required_artifacts':len(req),'submitted_artifacts':len(req)-len(missing),'artifact_completeness':(len(req)-len(missing))/len(req),'missing_artifacts':missing,'accredited_body':acc,'surveillance_audit_due_days':due,'expiry_risk':due<=30,'certification_eligible':not missing and acc},['Submitted artifacts map to current, unexpired documents.'],['Eligibility is a readiness screen, not the certification decision.']
def _r1946(d,p):
 parts=_l(d,'partitions');et=int(_f(d.get('edge_cases_total',0),'edge_cases_total'));etested=int(_f(d.get('edge_cases_tested',0),'edge_cases_tested'))
 if et<0 or etested<0 or etested>et:raise ValueError('invalid edge case counts')
 reps=[]
 for x in parts:
  cases=int(_f(x.get('cases',0),'cases'));ok=int(_f(x.get('passed',0),'passed'))
  if cases<=0 or ok<0 or ok>cases:raise ValueError('invalid partition counts')
  reps.append({'partition':x.get('name'),'cases':cases,'passed':ok,'pass_rate':ok/cases})
 allpass=all(r['pass_rate']==1 for r in reps)
 return {'partition_results':reps,'partitions':len(reps),'overall_pass_rate':sum(r['passed'] for r in reps)/sum(r['cases'] for r in reps),'edge_case_coverage':etested/et if et else None,'adequacy_decision':'adequate' if allpass and (et==0 or etested==et) else 'inadequate'},['Partitions cover the declared input space; untested partitions are absent, not empty.'],['Adequacy is judged against the declared partition model, which may itself be incomplete.']
def _r1947(d,p):
 props=_l(d,'properties');bad=[x.get('name') for x in props if x.get('holds') is False];unchecked=[x.get('name') for x in props if not x.get('checked_cases')]
 return {'properties':len(props),'properties_verified':len(props)-len(bad)-len(unchecked),'counterexample_properties':bad,'unchecked_properties':unchecked,'proof_obligation_coverage':sum(1 for x in props if x.get('checked_cases'))/len(props),'verification_complete':not bad and not unchecked},['A property marked holds was discharged on the stated checked cases or proof.'],['Exhausted test-based checking is not proof; only the stated obligations are covered.']
def _r1948(d,p):
 needs=_l(d,'stakeholder_needs');report=[];unmet=[]
 for n in needs:
  crit=_l(n,'acceptance_criteria',0) if isinstance(n.get('acceptance_criteria'),list) else n.get('acceptance_criteria');met=n.get('met_criteria',[])
  if not isinstance(crit,list):raise ValueError('acceptance_criteria must be a list')
  ok=all(c in met for c in crit);report.append({'need':n.get('id'),'criteria':len(crit),'met':sum(1 for c in crit if c in met),'validated':ok})
  if not ok:unmet.append(n.get('id'))
 return {'needs':len(needs),'validated_needs':len(needs)-len(unmet),'validation_rate':(len(needs)-len(unmet))/len(needs),'per_need':report,'unmet_needs':unmet,'fit_for_purpose':not unmet},['The need list is traceable to real stakeholder input.'],['Fit-for-purpose holds only for the stated needs and criteria, in the validated context of use.']
def _r1949(d,p):
 claims=_l(d,'claims');ev=_l(d,'evidence_items',0);crit=_l(d,'critical_claim_ids',0);indep={e.get('id') for e in ev if e.get('independent')}
 supported=[c for c in claims if c.get('evidence_ids')];unsupport_crit=[c.get('id') for c in claims if c.get('id') in crit and not c.get('evidence_ids')]
 indepsupp=[c for c in claims if c.get('evidence_ids') and any(e in indep for e in c['evidence_ids'])]
 return {'claims':len(claims),'supported_claims':len(supported),'claim_support_rate':len(supported)/len(claims),'independent_evidence_claims':len(indepsupp),'independent_evidence_rate':len(indepsupp)/len(claims),'unsupported_critical_claims':unsupport_crit,'assurance_ready':len(supported)==len(claims) and not unsupport_crit and len(indepsupp)==len(claims)},['Evidence items are retrievable and independence is documented.'],['Assurance readiness reflects the argument as recorded; hidden defeats are not visible to it.']
def _r1950(d,p):
 cats=_l(d,'benchmark_categories');rep=[]
 for c in cats:
  s=_f(c.get('score'),'score');b=_f(c.get('baseline'),'baseline');rep.append({'category':c.get('category'),'score':s,'baseline':b,'gain':s-b})
 agg=sum(x['score'] for x in rep)/len(rep)
 return {'category_report':rep,'aggregate_score':agg,'strongest_category':max(rep,key=lambda x:x['gain'])['category'],'weakest_category':min(rep,key=lambda x:x['gain'])['category'],'capability_breadth':sum(1 for x in rep if x['gain']>0)/len(rep)},['Benchmark scores use published evaluation protocols on the stated model revision.'],['Benchmark aggregates do not predict performance on private or shifting distributions, and public benchmarks may be contaminated.']
def _r1951(d,p):
 tasks=_l(d,'downstream_tasks');scores=_v(d,'scores');base=_v(d,'baselines');_aligned(tasks,scores,base)
 ratios=[s/b for s,b in zip(scores,base) if b>0]
 return {'task_count':len(tasks),'task_scores':dict(zip(tasks,scores)),'mean_score':sum(scores)/len(scores),'mean_gain_over_baseline':sum(a-b for a,b in zip(scores,base))/len(scores),'tasks_below_baseline':[tasks[i] for i,(a,b) in enumerate(zip(scores,base)) if a<b],'mean_transfer_ratio':sum(ratios)/len(ratios) if ratios else None},['Baselines are the stated reference models evaluated under identical conditions.'],['Zero baselines are excluded from the transfer ratio; relative gains shrink as baselines improve.']
def _r1952(d,p):
 before=_v(d,'before_scores');after=_v(d,'after_scores');ret=_v(d,'retained_base_scores');_aligned(before,after);_aligned(before,ret);mg=sum(b-a for a,b in zip(before,after))/len(before);ming=_f(p.get('min_gain',.01),'min_gain')
 return {'mean_task_gain':mg,'base_retention_ratio':sum(ret)/sum(before) if sum(before) else None,'forgetting_rate':1-sum(ret)/sum(before) if sum(before) else None,'regressed_tasks':[i for i,(a,b) in enumerate(zip(before,after)) if b<a],'gain_material':mg>=ming},['Before/after pairs are the same tasks on the same split; retained scores measure base capability after tuning.'],['Fine-tune gains on chosen tasks do not rule out regressions on unmeasured behaviors.']
def _r1953(d,p):
 scr=_v(d,'scratch_scores');tra=_v(d,'transfer_scores');sn=_v(d,'scratch_examples');tn=_v(d,'transfer_examples');_aligned(scr,tra,sn,tn)
 if any(t<=0 for t in tn):raise ValueError('transfer_examples must be positive')
 return {'mean_performance_gain':sum(t-s for s,t in zip(scr,tra))/len(scr),'mean_sample_efficiency_ratio':sum(s/t for s,t in zip(sn,tn))/len(sn),'data_savings_percent':100*(1-sum(tn)/sum(sn)) if sum(sn)>0 else None,'positive_transfer_rate':sum(t>s for s,t in zip(scr,tra))/len(scr)},['Scratch and transfer runs share architecture, budget and evaluation.'],['Sample-efficiency ratios conflate data quality with transfer benefit when scratch data is weak.']
def _r1954(d,p):
 preds=_l(d,'predictions');targets=_l(d,'targets');_aligned(preds,targets);shots=int(_f(d.get('shots',-1),'shots'))
 if shots<1:raise ValueError('few-shot evaluation requires shots>=1')
 acc=sum(a==b for a,b in zip(preds,targets))/len(targets);zb=_f(d.get('zero_shot_baseline_accuracy',0),'zero_shot_baseline_accuracy')
 return {'shots':shots,'accuracy':acc,'examples':len(targets),'lift_over_zero_shot':acc-zb,'accuracy_per_shot':(acc-zb)/shots,'prompt_tokens':int(_f(d.get('prompt_tokens',0),'prompt_tokens'))},['Demonstrations are drawn from the task distribution and disjoint from evaluation items.'],['Per-shot lift is noisy at small shot counts; a single exemplar set is not a robust estimate.']
def _r1955(d,p):
 preds=_l(d,'predictions');targets=_l(d,'targets');_aligned(preds,targets);shots=int(_f(d.get('shots',0),'shots'))
 if shots!=0:raise ValueError('zero-shot evaluation requires shots=0')
 return {'shots':0,'accuracy':sum(a==b for a,b in zip(preds,targets))/len(targets),'examples':len(targets),'prompt_tokens':int(_f(d.get('prompt_tokens',0),'prompt_tokens')),'instruction_only':True},['No task examples appear anywhere in the prompt or system context.'],['Zero-shot accuracy reflects instruction and pretraining leakage, not pure generalization.']
def _r1956(d,p):
 counts=_v(d,'demonstration_counts');accs=_v(d,'accuracies');_aligned(counts,accs)
 if any(c<0 for c in counts):raise ValueError('demonstration counts must be >=0')
 pairs=sorted(zip(counts,accs));slope=(pairs[-1][1]-pairs[0][1])/(pairs[-1][0]-pairs[0][0]) if pairs[-1][0]>pairs[0][0] else None;tol=_f(p.get('plateau_tolerance',.01),'plateau_tolerance');used=int(_f(d.get('context_tokens_used',0),'context_tokens_used'));window=int(_f(d.get('context_window',0),'context_window'))
 if window<=0:raise ValueError('context_window must be positive')
 return {'learning_curve':[{'demonstrations':c,'accuracy':a} for c,a in pairs],'gain_per_demonstration':slope,'plateau_detected':len(pairs)>1 and abs(pairs[-1][1]-pairs[-2][1])<=tol,'context_utilization':min(1.0,used/window),'context_exhausted':used>=window},['Accuracies at each demonstration count use the same evaluation set.'],['In-context gains plateau and can reverse when demonstrations crowd out the query near the context limit.']
def _r1957(d,p):
 variants=_l(d,'variants');scores=_v(d,'scores');toks=_v(d,'token_counts');_aligned(variants,scores,toks)
 if any(t<=0 for t in toks):raise ValueError('token_counts must be positive')
 pen=_f(p.get('token_penalty',0),'token_penalty');util=[s-pen*t for s,t in zip(scores,toks)];i=max(range(len(util)),key=util.__getitem__)
 pareto=[j for j in range(len(variants)) if not any(scores[k]>=scores[j] and toks[k]<=toks[j] and (scores[k]>scores[j] or toks[k]<toks[j]) for k in range(len(variants)))]
 return {'selected_variant':variants[i],'selected_index':i,'utilities':util,'score':scores[i],'token_count':toks[i],'efficiency_score_per_token':scores[i]/toks[i],'pareto_optimal_variants':[variants[j] for j in pareto]},['The evaluation set is held out from prompt iteration.'],['Optimizing prompt variants on one eval set overfits it; re-validate the winner on fresh data.']
def _r1958(d,p):
 steps=_l(d,'steps');final=d.get('final_answer');expected=d.get('expected_answer');ver=d.get('step_verifications',[False]*len(steps))
 if not isinstance(ver,list) or len(ver)!=len(steps):raise ValueError('step_verifications must align with steps')
 firstun=next((i for i,v in enumerate(ver) if not v),None)
 return {'step_count':len(steps),'all_steps_have_claims':all(bool(str(x).strip()) for x in steps),'verified_steps':sum(bool(x) for x in ver),'verification_rate':sum(bool(x) for x in ver)/len(steps),'first_unverified_step_index':firstun,'final_correct':final==expected,'trace_exposed':bool(p.get('return_trace',False))},['Step verifications come from an independent checker, not the generating model.'],['Correct final answers do not prove hidden reasoning faithfulness; private reasoning need not be exposed.']
def _r1959(d,p):
 nodes=_l(d,'nodes');by={n['id']:n for n in nodes if 'id' in n}
 if len(by)!=len(nodes):raise ValueError('node ids must be unique')
 valid=[n for n in nodes if n.get('parent') is None or n.get('parent') in by]
 children={}
 for n in valid:children.setdefault(n.get('parent'),[]).append(n)
 leaves=[n for n in valid if not children.get(n.get('id'))]
 if not leaves:raise ValueError('no leaf nodes in search tree')
 best=max(leaves,key=lambda n:_f(n.get('score',0),'score'))
 path=[];seen=set();cur=best
 while cur and cur.get('id') not in seen:
  seen.add(cur.get('id'));path.append(cur.get('id'));cur=by.get(cur.get('parent'))
 path=list(reversed(path));branching=[len(v) for k,v in children.items() if k is not None]
 return {'node_count':len(nodes),'valid_node_count':len(valid),'leaf_count':len(leaves),'best_leaf_id':best['id'],'best_score':best.get('score',0),'best_path':path,'explored_depth':len(path),'mean_branching_factor':sum(branching)/len(branching) if branching else 0,'pruned_node_count':len(valid)-len(path)},['Node scores come from the stated evaluator and parents form a tree.'],['Best-first selection inherits the evaluator\'s biases; the best-scoring path is not verified correct.']

NAMES=['large_language_models','multimodal_ai','vision_language_models','text_to_image_generation','text_to_video_generation','text_to_3d_generation','text_to_audio_generation','music_generation','voice_cloning','deepfakes','ai_art','ai_writing','ai_coding','ai_agents','autonomous_agents','multi_agent_systems','agent_communication','agent_coordination','agent_negotiation','agent_learning','reinforcement_learning_from_human_feedback','constitutional_ai','ai_alignment','ai_safety','ai_ethics','explainable_ai','interpretable_ai','fair_ai','responsible_ai','trustworthy_ai','ai_governance','ai_regulation','ai_policy','ai_standards','ai_auditing','ai_certification','ai_testing','ai_verification','ai_validation','ai_assurance','foundation_models','pre_trained_models','fine_tuning','transfer_learning','few_shot_learning','zero_shot_learning','in_context_learning','prompt_engineering','chain_of_thought','tree_of_thought']
ROWS={n:1910+i for i,n in enumerate(NAMES)}
HANDLERS={'large_language_models':_r1910,'multimodal_ai':_r1911,'vision_language_models':_r1912,'text_to_image_generation':_r1913,'text_to_video_generation':_r1914,'text_to_3d_generation':_r1915,'text_to_audio_generation':_r1916,'music_generation':_r1917,'voice_cloning':_r1918,'deepfakes':_r1919,'ai_art':_r1920,'ai_writing':_r1921,'ai_coding':_r1922,'ai_agents':_r1923,'autonomous_agents':_r1924,'multi_agent_systems':_r1925,'agent_communication':_r1926,'agent_coordination':_r1927,'agent_negotiation':_r1928,'agent_learning':_r1929,'reinforcement_learning_from_human_feedback':_r1930,'constitutional_ai':_r1931,'ai_alignment':_r1932,'ai_safety':_r1933,'ai_ethics':_r1934,'explainable_ai':_r1935,'interpretable_ai':_r1936,'fair_ai':_r1937,'responsible_ai':_r1938,'trustworthy_ai':_r1939,'ai_governance':_r1940,'ai_regulation':_r1941,'ai_policy':_r1942,'ai_standards':_r1943,'ai_auditing':_r1944,'ai_certification':_r1945,'ai_testing':_r1946,'ai_verification':_r1947,'ai_validation':_r1948,'ai_assurance':_r1949,'foundation_models':_r1950,'pre_trained_models':_r1951,'fine_tuning':_r1952,'transfer_learning':_r1953,'few_shot_learning':_r1954,'zero_shot_learning':_r1955,'in_context_learning':_r1956,'prompt_engineering':_r1957,'chain_of_thought':_r1958,'tree_of_thought':_r1959}
SUMMARIES={'large_language_models':'Token-level likelihood, perplexity and context-window utilization of a supplied language-model trace','multimodal_ai':'Score-level late fusion across declared modalities with weight entropy and weakest-modality diagnostics','vision_language_models':'Image-caption embedding alignment with thresholded grounding rate and per-image misses','text_to_image_generation':'Prompt adherence, scored quality, requested-resolution fit and provenance/watermark flags for a generated image','text_to_video_generation':'Frame-quality trace analysis: temporal flicker, worst frame, and scored-frame coverage of the clip','text_to_3d_generation':'Mesh integrity statistics: manifold checks, bounding volume, face budget and face-to-vertex ratio','text_to_audio_generation':'Waveform statistics: sample-rate adequacy, crest factor, estimated loudness and clipping rate','music_generation':'Duration-weighted pitch-class histogram correlated with the declared key profile plus tempo stability','voice_cloning':'Consent/provenance/watermark release gate with identity-similarity and speaker-verification scores','deepfakes':'Forensic detector aggregation with manipulation-risk score, release block and recommended action','ai_art':'Reference-palette distance and rule-of-thirds composition scoring for a supplied artwork record','ai_writing':'Readability grade, citation coverage and duplication metrics for a drafted text','ai_coding':'Suite-level pass rates, coverage floor and static/dependency gates for a code change','ai_agents':'Human-supervised agent run audit: approval coverage over irreversible steps and execution safety','autonomous_agents':'Autonomy index, override/escalation rates and constraint-violation check from a run trace','multi_agent_systems':'Delegation-graph validity, depth and cycle detection across declared agents','agent_communication':'Message schema validity, protocol violations, unmatched replies and orphaned request correlations','agent_coordination':'Task-DAG audit: ownership gaps, unknown dependencies, cycle rejection and critical path length','agent_negotiation':'Reservation-utility offer selection with concession counting and advisory-only commitment','agent_learning':'Before/after score deltas with effect size and per-task regression list','reinforcement_learning_from_human_feedback':'Preference-pair reward margins, accuracy and its normal-approximation confidence interval','constitutional_ai':'Principle-critique-revision chain coverage with uncritiqued-principle detection','ai_alignment':'Intended-vs-observed objective gap with tolerance rate and worst-case identification','ai_safety':'Failure-mode risk priority numbers with unacceptable-hazard screening','ai_ethics':'Per-principle evidence coverage with explicit gaps and a review recommendation','explainable_ai':'Attribution ranking with share of total importance and a removal-based faithfulness drop','interpretable_ai':'Intrinsic model-shape audit: rule/depth complexity, monotonicity violations and surrogate fidelity','fair_ai':'Group selection rates, demographic-parity difference and equal-opportunity difference','responsible_ai':'Weighted dimension scorecard with ranking and maturity band','trustworthy_ai':'Calibration error, robustness floor and privacy-budget gate into a certificate-readiness flag','ai_governance':'Role/policy inventory completeness with review cadence and incident-process checks','ai_regulation':'Jurisdictional obligation checklist with evidence gaps; not legal advice','ai_policy':'Internal policy-to-control conformance with violation counts by severity','ai_standards':'Named-standard clause conformity with nonconformity severity and certification-body eligibility','ai_auditing':'Control-test exception rate, evidence completeness and audit-opinion grade','ai_certification':'Required-artifact completeness, accredited-body check and surveillance-expiry risk','ai_testing':'Input-partition pass rates and edge-case coverage into an adequacy decision','ai_verification':'Property-level verification with counterexamples and proof-obligation coverage','ai_validation':'Stakeholder-need traceability to acceptance criteria into a fit-for-purpose decision','ai_assurance':'Claim-support and independent-evidence rates with critical-claim exposure','foundation_models':'Benchmark-category report with aggregate score, breadth and per-category baseline gains','pre_trained_models':'Downstream task gains over named baselines with mean transfer ratio','fine_tuning':'Task gain, base-capability retention and forgetting rate for a tuned model','transfer_learning':'Performance gain and sample-efficiency ratio of transfer versus training from scratch','few_shot_learning':'Accuracy and per-shot lift over a declared zero-shot baseline (shots>=1 enforced)','zero_shot_learning':'Instruction-only accuracy with shots=0 enforced and prompt-token accounting','in_context_learning':'Accuracy-versus-demonstrations learning curve with slope, plateau and context-budget checks','prompt_engineering':'Token-penalized variant selection with efficiency and Pareto-optimal variant list','chain_of_thought':'Step-claim completeness, independent verification rate and final-answer correctness','tree_of_thought':'Search-tree audit: best-scoring leaf path, depth, branching factor and pruned share'}
INPUTS={'large_language_models':['token_log_probabilities: list of per-token log probs from the eval run','context_window: model context size'],'multimodal_ai':['modalities: modality label per score','modality_scores: one score per modality','weights: fusion weight per modality'],'vision_language_models':['image_ids: evaluated image identifiers','captions: paired captions','similarities: embedding similarity per pair'],'text_to_image_generation':['prompt','artifact_description: what the image actually shows','quality_scores: per-rater or per-metric quality scores','width/height vs requested_width/requested_height'],'text_to_video_generation':['prompt','artifact_description','frame_quality_scores: sampled per-frame scores','fps and duration_seconds'],'text_to_3d_generation':['vertex_count','face_count','non_manifold_edges','watertight: bool','bounding_box: {x,y,z} dimensions'],'text_to_audio_generation':['sample_rate_hz','duration_seconds','peak_amplitude and rms_amplitude (0-1)','clipping_samples and total_samples'],'music_generation':['note_events: {pitch_class 0-11, duration}','declared_key: pitch class 0-11','tempo_bpm_samples: tempo trace'],'voice_cloning':['consent_verified: bool','provenance: signed provenance record','watermark: bool','identity_similarity and speaker_verification_score'],'deepfakes':['consent_verified: bool','provenance','watermark: bool','face_swap_artifact_score, temporal_inconsistency, identity_similarity from detectors'],'ai_art':['palette: #rrggbb colors used','reference_palette: intended colors','composition_focal_point {x,y} and canvas {width,height}','style_match_scores'],'ai_writing':['text: the draft','sources: cited sources','claims: checkable claims extracted by the caller'],'ai_coding':['tests_passed/tests_total per suite','coverage_percent','static_analysis_issues','dependency_scan_clean: bool'],'ai_agents':['steps: run steps with irreversible/approved/blocked flags','goal_completed','human_overrides'],'autonomous_agents':['steps: run steps with human_assisted flags','human_overrides','escalation_events','constraint_violations','goal_completed'],'multi_agent_systems':['agents: declared agent ids','delegations: {from,to} edges'],'agent_communication':['messages: logged messages with sender/recipient/type/correlation_id'],'agent_coordination':['tasks: {id, owner, depends_on} records'],'agent_negotiation':['offers: the offers on the table','utilities: one utility per offer'],'agent_learning':['before_scores','after_scores on the same held-out tasks'],'reinforcement_learning_from_human_feedback':['chosen_rewards','rejected_rewards aligned per preference pair'],'constitutional_ai':['principles','critiques naming principles','revisions answering critiques'],'ai_alignment':['intended_scores','observed_scores on matched objectives'],'ai_safety':['hazard_severity','hazard_likelihood','detectability aligned per hazard'],'ai_ethics':['principles','evidence: principle -> supporting artifact'],'explainable_ai':['feature_names','feature_importance','score_full','score_without_top'],'interpretable_ai':['num_features_used','max_rule_depth','num_rules','monotonicity_checks','surrogate_fidelity'],'fair_ai':['groups','selected','positive_labels aligned per subject'],'responsible_ai':['dimensions','scores','weights'],'trustworthy_ai':['calibration_errors','robustness_scores','privacy_budget_epsilon'],'ai_governance':['roles: {name, responsibilities, filled}','policies','review_cadence_days','incident_process_documented: bool'],'ai_regulation':['jurisdiction','requirements: obligations','evidence: obligation -> artifact'],'ai_policy':['policy_statements','controls: statement -> operating control','violations: {statement, severity}'],'ai_standards':['standard: name and revision','clauses','conformity: clause -> assessment'],'ai_auditing':['controls: {id, result, evidence} test records'],'ai_certification':['required_artifacts','submitted: artifact -> document','accredited_body: bool','surveillance_audit_due_days'],'ai_testing':['partitions: {name, cases, passed}','edge_cases_total','edge_cases_tested'],'ai_verification':['properties: {name, holds, checked_cases}'],'ai_validation':['stakeholder_needs: {id, acceptance_criteria, met_criteria}'],'ai_assurance':['claims: {id, evidence_ids}','evidence_items: {id, independent}','critical_claim_ids'],'foundation_models':['benchmark_categories: {category, score, baseline}'],'pre_trained_models':['downstream_tasks','scores','baselines'],'fine_tuning':['before_scores','after_scores','retained_base_scores'],'transfer_learning':['scratch_scores','transfer_scores','scratch_examples','transfer_examples'],'few_shot_learning':['predictions','targets','shots (>=1)','zero_shot_baseline_accuracy'],'zero_shot_learning':['predictions','targets','shots (must be 0)'],'in_context_learning':['demonstration_counts','accuracies','context_tokens_used','context_window'],'prompt_engineering':['variants','scores','token_counts'],'chain_of_thought':['steps','final_answer','expected_answer','step_verifications'],'tree_of_thought':['nodes: {id, parent, score} search tree records']}

def run(method,data,params=None,seed=0):
 if method not in ROWS:raise ValueError(f'unsupported AI systems method {method}')
 if not isinstance(data,dict):raise ValueError('data must be an object')
 p=params or {}
 if not isinstance(p,dict):raise ValueError('params must be an object')
 out,assumptions,limits=HANDLERS[method](data,p)
 return {'method':method,'feature_row':ROWS[method],'inputs':{'data':data,'params':p},'assumptions':assumptions,'method_limits':limits,'output':out,'external_effects':'none: advisory evaluation only; any release or execution decision routes through human approval'}
