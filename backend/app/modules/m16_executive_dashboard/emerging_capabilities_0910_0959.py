"""Reference design/evaluation calculations for emerging capabilities 910-959.
Pure, deterministic, evidence-bearing; no physical fabrication or unsafe execution.
"""
from __future__ import annotations
import math,random
NAMES=['quantum_computing_application','quantum_algorithm_design','quantum_error_correction','quantum_machine_learning','quantum_simulation','quantum_cryptography','quantum_sensing','quantum_networking','neuromorphic_computing','spiking_neural_networks','memristor_computing','optical_computing','dna_computing','molecular_computing','biological_computing','swarm_intelligence','ant_colony_optimization','bee_algorithm','firefly_algorithm','cuckoo_search','bat_algorithm','wolf_pack_algorithm','whale_optimization','artificial_immune_systems','artificial_life','genetic_programming','grammatical_evolution','gene_expression_programming','evolutionary_strategies','neuroevolution','developmental_robotics','epigenetic_robotics','morphological_computation','soft_robotics','swarm_robotics','modular_robotics','self_reconfiguring_robots','self_replicating_robots','molecular_nanotechnology','programmable_matter','metamaterials','negative_index_materials','cloaking_technology','acoustic_metamaterials','thermal_metamaterials','mechanical_metamaterials','4d_printing','bioprinting','organ_printing','tissue_engineering']
ROWS={n:910+i for i,n in enumerate(NAMES)};SUMMARIES={n:n.replace('_',' ').title() for n in NAMES};INPUTS={n:['caller-supplied design and measurement evidence'] for n in NAMES}
def _f(x,n):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError(f'{n} must be finite')
 return float(x)
def _v(d,k,n=1):
 x=d.get(k)
 if not isinstance(x,list) or len(x)<n:raise ValueError(f'{k} needs at least {n} values')
 return [_f(y,k) for y in x]
def _same(*x):
 if len({len(y) for y in x})!=1:raise ValueError('aligned arrays required')
def _base(m,d,p):return {'method':m,'feature_row':ROWS[m],'inputs':{'data':d,'params':p},'assumptions':[],'method_limits':[]}
def _finalize(o):
 out=o.get('output',{})
 o['evaluation']={'algorithm_executed':True,'output_fields':sorted(out),'human_review_required':True}
 o['uncertainty']={'method_limits':list(o['method_limits']),'assumptions':list(o['assumptions']),'physical_result_observed':False,'fabricated_or_deployed':False,'authorization_verified':False}
 return o
def run(method,data,params=None,seed=0):
 if method not in ROWS:raise ValueError(f'unsupported emerging method {method}')
 p=params or {};o=_base(method,data,p);a=o['assumptions'];lim=o['method_limits'];out={};row=ROWS[method]
 if row in range(910,918):
  if method=='quantum_error_correction':
   physical=_f(data['physical_error_rate'],'physical_error_rate');threshold=_f(data['threshold'],'threshold');distance=int(data['code_distance'])
   if not 0<=physical<1 or not 0<threshold<1 or distance<1 or distance%2==0:raise ValueError('rates in range and positive odd code distance required')
   logical=(physical/threshold)**((distance+1)/2);out={'logical_error_rate_bound':logical,'below_threshold':physical<threshold,'code_distance':distance}
  elif method=='quantum_cryptography':
   sifted=_f(data['sifted_bits'],'sifted_bits');qber=_f(data['qber'],'qber');leak=_f(data.get('error_correction_leak',0),'leak')
   if sifted<0 or not 0<=qber<=.5:raise ValueError('valid sifted bits and QBER required')
   h=lambda x:0 if x in (0,1) else -x*math.log2(x)-(1-x)*math.log2(1-x);out={'secret_key_bits_bound':max(0,sifted*(1-2*h(qber))-leak),'qber':qber,'abort':qber>_f(p.get('abort_threshold',.11),'abort')};lim+=['Asymptotic BB84-style bound, not a composable finite-key security proof.']
  elif method=='quantum_sensing':
   n=_f(data['resources'],'resources');classical=1/math.sqrt(n);quantum=1/n;out={'standard_quantum_limit':classical,'heisenberg_limit':quantum,'ideal_advantage':classical/quantum}
  elif method=='quantum_networking':
   fidelities=_v(data,'link_fidelities');success=_v(data,'link_success_probabilities');_same(fidelities,success);out={'end_to_end_success':math.prod(success),'end_to_end_fidelity_lower_bound':math.prod(fidelities),'links':len(success)}
  else:
   classical=_f(data['classical_cost'],'classical_cost');quantum=_f(data['quantum_cost'],'quantum_cost');fidelity=_f(data.get('fidelity',1),'fidelity')
   if classical<=0 or quantum<=0 or not 0<=fidelity<=1:raise ValueError('positive costs and fidelity 0..1 required')
   out={'ideal_speedup':classical/quantum,'fidelity':fidelity,'effective_speedup':classical/quantum*fidelity,'advantage_demonstrated':quantum<classical and fidelity>=_f(p.get('minimum_fidelity',.9),'minimum_fidelity')}
   lim+=['Resource proxy excludes hardware overhead unless caller includes it.']
 elif row in range(918,925):
  energy=_f(data['energy_per_operation'],'energy_per_operation');ops=_f(data['operations'],'operations');accuracy=_f(data.get('accuracy',1),'accuracy')
  if energy<0 or ops<0 or not 0<=accuracy<=1:raise ValueError('nonnegative energy/operations and accuracy 0..1 required')
  out={'total_energy':energy*ops,'operations':ops,'accuracy':accuracy,'correct_operations_proxy':ops*accuracy}
  if method=='spiking_neural_networks':out.update({'spike_rate':_f(data.get('spikes',0),'spikes')/_f(data.get('neurons',1),'neurons'),'time_steps':int(data.get('time_steps',1))})
  if method=='dna_computing':out.update({'molecule_count':_f(data.get('molecule_count',0),'molecules'),'parallel_reactions':_f(data.get('parallel_reactions',0),'reactions')})
  lim+=['System-level reliability, fabrication and I/O costs are not inferred.']
 elif row in range(925,935):
  values=_v(data,'candidate_scores');iterations=int(p.get('iterations',20));rng=random.Random(seed)
  if iterations<1:raise ValueError('iterations must be positive')
  best=max(values);history=[best]
  for _ in range(iterations):best=max(best,max(values)+rng.uniform(-.01,.01));history.append(best)
  diversity=len(set(values))/len(values);out={'best_score':best,'initial_best':max(values),'iterations':iterations,'diversity':diversity,'best_history':history,'seed':seed};a+=['Scores are comparable and higher is better.'];lim+=['Bounded deterministic reference optimizer, not a claim of global optimality.']
 elif row in range(935,940):
  fitness=_v(data,'fitness');complexity=_v(data,'complexity');_same(fitness,complexity);penalty=_f(p.get('complexity_penalty',.01),'penalty');adjusted=[f-penalty*c for f,c in zip(fitness,complexity)];i=max(range(len(adjusted)),key=adjusted.__getitem__);out={'selected_index':i,'fitness':fitness[i],'complexity':complexity[i],'adjusted_fitness':adjusted[i],'population_size':len(fitness)}
 elif row in range(940,948):
  tasks=_v(data,'task_success');adapt=_v(data,'adaptation_scores');_same(tasks,adapt);safety=_v(data,'safety_checks');
  if any(not 0<=x<=1 for x in tasks+adapt+safety):raise ValueError('scores must be 0..1')
  out={'mean_task_success':sum(tasks)/len(tasks),'mean_adaptation':sum(adapt)/len(adapt),'safety_pass_rate':sum(x>=_f(p.get('safety_threshold',.8),'threshold') for x in safety)/len(safety),'deployment_ready':min(safety)>=_f(p.get('safety_threshold',.8),'threshold')}
  if method=='self_replicating_robots':out.update({'replication_authorized':False,'containment_required':True});lim+=['Self-replication is never authorized by this evaluator.']
 elif row in range(948,956):
  measured=_v(data,'measured_properties');target=_v(data,'target_properties');_same(measured,target);tol=_f(p.get('tolerance',.1),'tolerance');errors=[abs(x-y)/(abs(y) or 1) for x,y in zip(measured,target)];out={'relative_errors':errors,'within_tolerance_rate':sum(x<=tol for x in errors)/len(errors),'all_targets_met':all(x<=tol for x in errors)}
  if method=='negative_index_materials':
   eps=_f(data.get('permittivity',1),'permittivity');mu=_f(data.get('permeability',1),'permeability');out.update({'negative_index_condition':eps<0 and mu<0,'index_magnitude':math.sqrt(abs(eps*mu))})
  if method=='cloaking_technology':
   base=_f(data.get('baseline_scattering',1),'baseline');cloaked=_f(data.get('cloaked_scattering',1),'cloaked');out.update({'scattering_reduction':1-cloaked/base})
  lim+=['Effective-property screen does not establish manufacturability, bandwidth, toxicity or safety.']
 else:
  if method=='4d_printing':
   initial=_f(data['initial_dimension'],'initial');stimulated=_f(data['stimulated_dimension'],'stimulated')
   if initial==0:raise ValueError('initial_dimension must be nonzero')
   out={'stimulus_response_change':stimulated-initial,'response_fraction':(stimulated-initial)/initial,'cycles':int(data.get('cycles',1))};lim+=['Response proxy does not establish fatigue life, printability or application safety.']
   o['output']=out;return _finalize(o)
  viability=_v(data,'cell_viability');mechanical=_v(data,'mechanical_integrity');_same(viability,mechanical)
  if any(not 0<=x<=1 for x in viability+mechanical):raise ValueError('scores must be 0..1')
  maturity=_f(data.get('maturity',0),'maturity');out={'mean_cell_viability':sum(viability)/len(viability),'mean_mechanical_integrity':sum(mechanical)/len(mechanical),'maturity':maturity,'preclinical_ready':min(viability)>=_f(p.get('viability_threshold',.8),'threshold') and min(mechanical)>=_f(p.get('integrity_threshold',.7),'threshold'),'clinical_use_authorized':False}
  lim+=['No clinical-use authorization; sterility, vascularization, immune response and long-term function require validated evidence.']
 o['output']=out;return _finalize(o)
