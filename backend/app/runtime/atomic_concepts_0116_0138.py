"""Atomic concepts 116-138: explicit, reviewable reference implementations."""
from __future__ import annotations
import math,re
IDS=['125.1','125.2','131.1','131.2','162.1','162.2','267.1','267.2','271.1','271.2','274.1','274.2','295.1','295.2','295.3','304.1','304.2','316.1','316.2','320.1','320.2','332.1','332.2']
REQ=['Research-data sharing compliance','Research-code sharing compliance','Attention-grabbing title candidate generation','Title-accuracy validation','Value-function learning','Policy learning','Dramatic-tension creation','Dramatic-tension release','Trope-conforming expectation analysis','Trope-subverting alternative','Lyric meter constraint','Lyric rhyme constraint','Squash principle application','Stretch principle application','Anticipation principle application','Beat programming','Groove programming','Visualization aesthetic-quality validation','Visualization clarity validation','Anatomical illustration planning','Procedure illustration planning','Aircraft design support','Spacecraft design support']
REG=dict(zip(IDS,REQ))
REFS={'open_science':'https://www.gofair.foundation/fair-principles','actor_critic':'http://incompleteideas.net/book/6/node7.html','aerospace':'https://www.nasa.gov/reference/systems-engineering-handbook/'}
def execute(i,d):
 if i not in REG:raise ValueError('unknown atomic concept')
 out={'atomic_row_id':i,'requirement':REG[i]}
 if i=='125.1':
  required=['persistent_identifier','license','metadata','repository','access_conditions','provenance'];missing=[x for x in required if not d.get(x)];out|={'fair_data_checklist':{x:bool(d.get(x)) for x in required},'missing':missing,'compliant':not missing,'reference':REFS['open_science']}
 elif i=='125.2':
  required=['repository_url','license','version_tag','environment_lock','readme','tests'];missing=[x for x in required if not d.get(x)];out|={'software_sharing_checklist':{x:bool(d.get(x)) for x in required},'missing':missing,'reproducibility_ready':not missing,'reference':REFS['open_science']}
 elif i=='131.1':
  finding=str(d.get('main_finding','')).strip();population=str(d.get('population','')).strip();design=str(d.get('design','')).strip()
  if not finding or not population:raise ValueError('main finding and population required')
  out|={'candidates':[f'{finding}: Evidence from {population}',f'{finding} in {population}',f'{design}: {finding}' if design else f'Study: {finding}'],'clickbait_forbidden':True}
 elif i=='131.2':
  title=str(d.get('title',''));claims=d.get('supported_claims',[]);unsupported=[c for c in d.get('title_claims',[]) if c not in claims];out|={'unsupported_claims':unsupported,'accurate':not unsupported and bool(title),'causal_language_allowed':d.get('design')=='randomized_controlled_trial'}
 elif i in {'162.1','162.2'}:
  rewards=d.get('rewards');values=d.get('values');probs=d.get('action_probabilities');actions=d.get('actions')
  if not isinstance(rewards,list) or not rewards:raise ValueError('reward sequence required')
  gamma=float(d.get('gamma',.99));alpha=float(d.get('alpha',.1));v=float(values[0] if values else 0);td=[]
  for r in rewards:delta=float(r)+gamma*v-v;v+=alpha*delta;td.append(delta)
  if i=='162.1':out|={'updated_value':v,'td_errors':td,'gamma':gamma,'reference':REFS['actor_critic']}
  else:
   if not isinstance(actions,list) or not isinstance(probs,list) or len(actions)!=len(probs):raise ValueError('aligned actions/probabilities required')
   adv=td[-1];logits=[math.log(max(float(p),1e-9))+(alpha*adv if j==int(d.get('chosen_index',0)) else 0) for j,p in enumerate(probs)];z=sum(math.exp(x) for x in logits);out|={'updated_policy':dict(zip(actions,[math.exp(x)/z for x in logits])),'advantage':adv,'reference':REFS['actor_critic']}
 elif i in {'267.1','267.2'}:
  scene=d.get('scene');stakes=d.get('stakes');clock=d.get('time_pressure');unknown=d.get('uncertainty');
  if not scene or not stakes:raise ValueError('scene and stakes required')
  if i=='267.1':out|={'tension_beats':[{'beat':'goal','content':scene},{'beat':'stakes','content':stakes},{'beat':'uncertainty','content':unknown},{'beat':'clock','content':clock},{'beat':'complication','content':d.get('complication')}],'escalation_requires_causality':True}
  else:out|={'release_beats':['answer one uncertainty','permit consequential action','show immediate cost','leave next question open'],'catharsis_without_erasing_consequence':True,'resolved_question':d.get('resolved_question')}
 elif i in {'271.1','271.2'}:
  trope=d.get('trope');promise=d.get('audience_promise');
  if not trope or not promise:raise ValueError('trope and audience promise required')
  if i=='271.1':out|={'expected_beats':d.get('conventional_beats',[]),'audience_promise':promise,'core_pleasure_to_preserve':d.get('core_pleasure')}
  else:out|={'subversion':d.get('subversion'),'preserved_promise':promise,'seeded_evidence':d.get('seeded_evidence',[]),'shock_only':False}
 elif i in {'274.1','274.2'}:
  lines=d.get('lines');
  if not isinstance(lines,list) or len(lines)<2:raise ValueError('two or more lyric lines required')
  if i=='274.1':
   counts=[len(re.findall(r'[aeiouy]+',x.lower())) for x in lines];target=int(d.get('target_syllables',counts[0]));out|={'estimated_syllables':counts,'target':target,'within_tolerance':[abs(x-target)<=1 for x in counts],'stress_review_required':True}
  else:
   endings=[re.sub(r'[^a-z]','',x.lower().split()[-1])[-3:] for x in lines];scheme=d.get('scheme','AA');out|={'rhyme_endings':endings,'scheme':scheme,'scheme_satisfied':all(endings[j]==endings[0] for j,c in enumerate(scheme) if c==scheme[0]),'slant_rhyme_requires_human_review':True}
 elif i in {'295.1','295.2','295.3'}:
  volume=float(d.get('volume',0));
  if volume<=0:raise ValueError('positive reference volume required')
  if i=='295.1':
   sy=float(d.get('scale_y',.7));out|={'scale_y':sy,'scale_x':1/math.sqrt(sy),'volume_preservation':True,'contact_emphasis':True}
  elif i=='295.2':
   sy=float(d.get('scale_y',1.4));out|={'scale_y':sy,'scale_x':1/math.sqrt(sy),'volume_preservation':True,'motion_direction':d.get('motion_direction')}
  else:out|={'pre_action_pose':d.get('pre_action_pose'),'action_pose':d.get('action_pose'),'opposing_direction':True,'readability_frames':max(1,int(d.get('readability_frames',3)))}
 elif i in {'304.1','304.2'}:
  bpm=float(d.get('bpm',0));steps=int(d.get('steps',16))
  if not 20<=bpm<=400 or steps not in {8,12,16,24,32}:raise ValueError('valid BPM and grid required')
  pattern=d.get('pattern',[1 if x%4==0 else 0 for x in range(steps)])
  if len(pattern)!=steps:raise ValueError('pattern/grid mismatch')
  if i=='304.1':out|={'bpm':bpm,'grid_steps':steps,'onsets':[x for x,v in enumerate(pattern) if v],'bar_duration_seconds':240/bpm}
  else:
   swing=float(d.get('swing',.55));out|={'swing_ratio':swing,'microtiming_offsets':[0 if x%2==0 else (swing-.5)*60/bpm*2 for x in range(steps)],'velocity_curve':d.get('velocities',[100]*steps),'humanization_seed_required_for_randomness':True}
 elif i in {'316.1','316.2'}:
  chart=d.get('chart',{});enc=chart.get('encodings',{});marks=int(chart.get('marks',0))
  if marks<=0:raise ValueError('nonempty chart specification required')
  if i=='316.1':out|={'aesthetic_checks':{'palette_coherent':bool(chart.get('palette')),'typography_hierarchy':bool(chart.get('title')),'data_ink_ratio_proxy':min(1,marks/max(marks+int(chart.get('decorations',0)),1))},'beauty_never_overrides_accuracy':True}
  else:out|={'clarity_checks':{'title_states_message':bool(chart.get('title')),'axes_labeled':all(enc.get(x) for x in ('x','y')),'units_present':bool(chart.get('units')),'color_not_only_channel':bool(chart.get('redundant_encoding')),'uncertainty_shown':bool(chart.get('uncertainty'))},'zero_baseline_required_for_bar':chart.get('type')=='bar'}
 elif i in {'320.1','320.2'}:
  sources=d.get('references');
  if not isinstance(sources,list) or not sources:raise ValueError('authoritative anatomical references required')
  if i=='320.1':out|={'view':d.get('view'),'structures':d.get('structures',[]),'layers':d.get('layers',[]),'orientation_labels':['anterior','posterior','left','right'],'reference_ids':[x['id'] for x in sources],'clinical_review_required':True}
  else:out|={'procedure_steps':d.get('steps',[]),'panel_sequence':['baseline','access','critical action','closure','aftercare'],'hazards':d.get('hazards',[]),'not_surgical_instruction':True,'clinical_review_required':True}
 elif i in {'332.1','332.2'}:
  req=d.get('requirements');
  if not isinstance(req,dict) or not req:raise ValueError('traceable mission requirements required')
  if i=='332.1':out|={'mission':d.get('mission'),'requirements':req,'trade_studies':['wing loading','thrust-to-weight','range/payload','stability/control','structures','propulsion','safety/certification'],'verification_matrix':{k:'analysis/test/inspection TBD' for k in req},'flightworthy_claim':False,'reference':REFS['aerospace']}
  else:out|={'mission':d.get('mission'),'requirements':req,'budgets':['mass','power','data','link','thermal','delta-v'],'subsystems':['payload','GNC','C&DH','communications','power','thermal','structures','propulsion'],'verification_matrix':{k:'analysis/test/inspection TBD' for k in req},'launch_ready_claim':False,'reference':REFS['aerospace']}
 return out
