"""Transparent negotiation and choice-support analysis for ledger rows 85-109.

The surface diagnoses incentives and designs user-autonomy-preserving options. It
never fabricates scarcity, authority, social proof, threats, or hidden priming.
"""
from __future__ import annotations
import math
NAMES=['information_asymmetry_exploitation','adverse_selection_detection','moral_hazard_prevention','screening_mechanism_design','commitment_device_creation','credible_threat_construction','bargaining_power_assessment','batna_identification','zopa_mapping','integrative_bargaining','anchoring_strategy','framing_effects_utilization','loss_aversion_leverage','social_proof_deployment','scarcity_creation','reciprocity_triggers','authority_positioning','consistency_commitment','liking_enhancement','unity_building','pre_suasion','priming_effects','nudge_design','choice_architecture','libertarian_paternalism']
ROWS={n:85+i for i,n in enumerate(NAMES)}
def _f(x,n):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError(f'{n} must be finite')
 return float(x)
def _v(d,k,n=1):
 x=d.get(k)
 if not isinstance(x,list) or len(x)<n:raise ValueError(f'{k} needs at least {n} values')
 return [_f(v,k) for v in x]
def _same(*xs):
 if len({len(x) for x in xs})!=1:raise ValueError('aligned arrays required')
def run(method,data):
 if method not in ROWS:raise ValueError(f'unsupported method {method}')
 limits=['Decision support only; disclose material facts, preserve voluntary choice, and obtain review before external use.'];out={}
 if method=='information_asymmetry_exploitation':
  known=set(data.get('known_by_proposer',[]));shared=set(data.get('shared_with_counterparty',[]));material=set(data.get('material_facts',[]));withheld=sorted(material&known-shared);out={'material_information_gap':withheld,'exploitation_blocked':bool(withheld),'required_disclosures':withheld};limits+=['Withholding material facts is flagged, not optimized.']
 elif method=='adverse_selection_detection':
  offered=_v(data,'offered_risk_scores');baseline=_f(data['population_mean_risk'],'population_mean_risk');mean=sum(offered)/len(offered);out={'offered_mean_risk':mean,'population_mean_risk':baseline,'selection_gap':mean-baseline,'adverse_selection_signal':mean>baseline+_f(data.get('alert_margin',0),'margin')}
 elif method=='moral_hazard_prevention':
  actions=data.get('actions');observable=data.get('observable');incentives=_v(data,'incentive_alignment')
  if not isinstance(actions,list) or not isinstance(observable,list):raise ValueError('actions and observable required')
  _same(actions,observable,incentives);out={'monitoring_gaps':[actions[i] for i,x in enumerate(observable) if not x],'misaligned_actions':[actions[i] for i,x in enumerate(incentives) if x<0],'recommended_controls':['make outcomes measurable','share downside and upside','audit exceptions']}
 elif method=='screening_mechanism_design':
  types=data.get('types');costs=_v(data,'signal_costs');benefits=_v(data,'benefits')
  if not isinstance(types,list):raise ValueError('types required')
  _same(types,costs,benefits);net=[b-c for b,c in zip(benefits,costs)];out={'type_options':[{'type':t,'net_utility':n} for t,n in zip(types,net)],'self_selection_separates':len(set(round(x,8) for x in net))==len(net)}
 elif method=='commitment_device_creation':
  goal=str(data.get('goal','')).strip();deadline=data.get('deadline');checkins=data.get('checkins',[])
  if not goal or not deadline or not isinstance(checkins,list):raise ValueError('goal, deadline and checkins required')
  out={'goal':goal,'deadline':deadline,'checkins':checkins,'reversible':bool(data.get('reversible',True)),'owner_controlled':True,'penalty':data.get('self_selected_penalty')};limits+=['Commitment remains revocable by its owner; coercive penalties are not created.']
 elif method=='credible_threat_construction':
  consequence=data.get('proposed_consequence');lawful=bool(data.get('lawful'));proportionate=bool(data.get('proportionate'));authorized=bool(data.get('authorized'));out={'proposed_consequence':consequence,'credible':lawful and proportionate and authorized,'may_communicate':lawful and proportionate and authorized,'blocked_reasons':[n for n,v in [('not_lawful',lawful),('not_proportionate',proportionate),('not_authorized',authorized)] if not v]};limits+=['No threat is generated; only legitimate, authorized consequences pass.']
 elif method=='bargaining_power_assessment':
  alternatives=_f(data['alternative_strength'],'alternative_strength');time=_f(data['time_pressure'],'time_pressure');info=_f(data['information_quality'],'information_quality');depend=_f(data['dependence'],'dependence');out={'power_score':alternatives+info-time-depend,'drivers':{'alternatives':alternatives,'information':info,'time_pressure':-time,'dependence':-depend}}
 elif method=='batna_identification':
  names=data.get('alternatives');values=_v(data,'values');costs=_v(data,'costs')
  if not isinstance(names,list):raise ValueError('alternatives required')
  _same(names,values,costs);net=[v-c for v,c in zip(values,costs)];i=max(range(len(net)),key=net.__getitem__);out={'batna':names[i],'batna_value':net[i],'ranked':sorted([{'alternative':n,'net_value':x} for n,x in zip(names,net)],key=lambda z:z['net_value'],reverse=True)}
 elif method=='zopa_mapping':
  seller=_f(data['seller_reservation'],'seller_reservation');buyer=_f(data['buyer_reservation'],'buyer_reservation');out={'zopa_exists':buyer>=seller,'lower_bound':seller,'upper_bound':buyer,'width':max(0,buyer-seller)}
 elif method=='integrative_bargaining':
  issues=data.get('issues');aweights=_v(data,'party_a_weights');bweights=_v(data,'party_b_weights')
  if not isinstance(issues,list):raise ValueError('issues required')
  _same(issues,aweights,bweights);out={'tradeoff_order':sorted([{'issue':i,'a_priority':a,'b_priority':b,'complementarity':abs(a-b)} for i,a,b in zip(issues,aweights,bweights)],key=lambda x:x['complementarity'],reverse=True),'joint_gain_potential':sum(abs(a-b) for a,b in zip(aweights,bweights))}
 elif method=='anchoring_strategy':
  objective=_f(data['objective_value'],'objective_value');low=_f(data['evidence_low'],'evidence_low');high=_f(data['evidence_high'],'evidence_high')
  if low>high:raise ValueError('invalid evidence range')
  anchor=min(high,max(low,objective));out={'evidence_based_anchor':anchor,'range':[low,high],'rationale_required':True};limits+=['Unsupported or deceptive anchors are rejected.']
 elif method in {'framing_effects_utilization','loss_aversion_leverage'}:
  gain=str(data.get('gain_frame',''));loss=str(data.get('loss_frame',''));facts=data.get('facts')
  if not gain or not loss or not facts:raise ValueError('balanced frames and facts required')
  out={'gain_frame':gain,'loss_frame':loss,'facts':facts,'balanced_presentation_required':True,'selected_frame':'both'};limits+=['One-sided framing and exploitation of loss aversion are blocked.']
 elif method in {'social_proof_deployment','scarcity_creation','authority_positioning'}:
  claim=data.get('claim');evidence=data.get('evidence');verified=bool(evidence);out={'claim':claim,'evidence':evidence,'verified':verified,'deployment_allowed':verified,'fabrication_blocked':not verified};limits+=['Claims must be current, attributable, and genuinely relevant.']
 elif method=='reciprocity_triggers':
  benefit=data.get('benefit');strings=bool(data.get('strings_attached'));out={'benefit':benefit,'allowed':bool(benefit) and not strings,'no_obligation_language':'This is offered without obligation.','blocked':strings};limits+=['Covert indebtedness triggers are blocked.']
 elif method=='consistency_commitment':
  prior=data.get('prior_commitment');current=data.get('current_choice');freely=bool(data.get('freely_chosen'));out={'prior_commitment':prior,'current_choice':current,'consistent':prior==current,'may_reference':freely,'revision_explicitly_allowed':True};limits+=['People may revise commitments without pressure.']
 elif method in {'liking_enhancement','unity_building'}:
  common=data.get('genuine_commonalities');
  if not isinstance(common,list):raise ValueError('genuine_commonalities required')
  out={'genuine_commonalities':common,'count':len(common),'fabricated_affinity_blocked':True,'usable':bool(common)}
 elif method in {'pre_suasion','priming_effects'}:
  context=data.get('context');disclosed=bool(data.get('disclosed'));out={'context':context,'disclosed':disclosed,'covert_influence_blocked':not disclosed,'allowed':disclosed and bool(context)};limits+=['Only transparent context-setting passes; covert priming is rejected.']
 elif method in {'nudge_design','choice_architecture','libertarian_paternalism'}:
  options=data.get('options');default=data.get('default');
  if not isinstance(options,list) or default not in options:raise ValueError('options and valid default required')
  easy=bool(data.get('easy_opt_out'));transparent=bool(data.get('transparent'));neutral=bool(data.get('alternatives_visible'));out={'options':options,'default':default,'easy_opt_out':easy,'transparent':transparent,'alternatives_visible':neutral,'autonomy_preserved':easy and transparent and neutral,'deployment_allowed':easy and transparent and neutral};limits+=['Defaults must not hide costs, obstruct exit, or remove alternatives.']
 else:raise AssertionError(method)
 out['method_limits']=limits;return {'method':method,'feature_row':ROWS[method],'inputs':data,'output':out}
