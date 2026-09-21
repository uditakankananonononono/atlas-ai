"""Mechanical engineering and verification workbench, ledger rows 1510-1559.

Calculations are deterministic and auditable: inputs, units, assumptions and equations
are returned with the result. The workbench never represents a simulation or physical
test as performed merely because a calculation or plan was generated.
"""
from __future__ import annotations
import math
from statistics import fmean, pstdev
from typing import Any

METHODS = [
'mechanical_design','cad_modeling','finite_element_analysis','computational_fluid_dynamics','thermal_analysis','stress_analysis','fatigue_analysis','fracture_mechanics','materials_selection','material_properties','failure_analysis','reliability_engineering','maintainability_engineering','safety_engineering','human_factors_engineering','ergonomics','industrial_design','design_for_manufacturing','design_for_assembly','design_for_sustainability','design_for_six_sigma','tolerance_analysis','gdt','metrology','quality_control','quality_assurance','statistical_process_control','process_capability','measurement_systems_analysis','design_of_experiments','taguchi_methods','response_surface_methodology','robust_design','reliability_testing','accelerated_life_testing','environmental_testing','vibration_testing','shock_testing','thermal_cycling','humidity_testing','corrosion_testing','wear_testing','fatigue_testing','creep_testing','impact_testing','hardness_testing','tensile_testing','compression_testing','shear_testing','torsion_testing']
NAMES = {
'mechanical_design':'Mechanical Design','cad_modeling':'CAD Modeling','finite_element_analysis':'Finite Element Analysis','computational_fluid_dynamics':'Computational Fluid Dynamics','thermal_analysis':'Thermal Analysis','stress_analysis':'Stress Analysis','fatigue_analysis':'Fatigue Analysis','fracture_mechanics':'Fracture Mechanics','materials_selection':'Materials Selection','material_properties':'Material Properties','failure_analysis':'Failure Analysis','reliability_engineering':'Reliability Engineering','maintainability_engineering':'Maintainability Engineering','safety_engineering':'Safety Engineering','human_factors_engineering':'Human Factors Engineering','ergonomics':'Ergonomics','industrial_design':'Industrial Design','design_for_manufacturing':'Design for Manufacturing','design_for_assembly':'Design for Assembly','design_for_sustainability':'Design for Sustainability','design_for_six_sigma':'Design for Six Sigma','tolerance_analysis':'Tolerance Analysis','gdt':'GD&T','metrology':'Metrology','quality_control':'Quality Control','quality_assurance':'Quality Assurance','statistical_process_control':'Statistical Process Control','process_capability':'Process Capability','measurement_systems_analysis':'Measurement Systems Analysis','design_of_experiments':'Design of Experiments','taguchi_methods':'Taguchi Methods','response_surface_methodology':'Response Surface Methodology','robust_design':'Robust Design','reliability_testing':'Reliability Testing','accelerated_life_testing':'Accelerated Life Testing','environmental_testing':'Environmental Testing','vibration_testing':'Vibration Testing','shock_testing':'Shock Testing','thermal_cycling':'Thermal Cycling','humidity_testing':'Humidity Testing','corrosion_testing':'Corrosion Testing','wear_testing':'Wear Testing','fatigue_testing':'Fatigue Testing','creep_testing':'Creep Testing','impact_testing':'Impact Testing','hardness_testing':'Hardness Testing','tensile_testing':'Tensile Testing','compression_testing':'Compression Testing','shear_testing':'Shear Testing','torsion_testing':'Torsion Testing'}


def _num(d:dict,k:str, *, positive:bool=False, nonnegative:bool=False)->float:
    if k not in d: raise ValueError(f"missing numeric input: {k}")
    v=float(d[k])
    if not math.isfinite(v): raise ValueError(f"{k} must be finite")
    if positive and v<=0: raise ValueError(f"{k} must be > 0")
    if nonnegative and v<0: raise ValueError(f"{k} must be >= 0")
    return v

def _values(d:dict,k:str)->list[float]:
    v=[float(x) for x in d.get(k,[])]
    if not v or any(not math.isfinite(x) for x in v): raise ValueError(f"{k} requires finite observations")
    return v

def _summary(v:list[float])->dict:
    return {'count':len(v),'mean':fmean(v),'min':min(v),'max':max(v),'population_sd':pstdev(v)}

def _base(method:str,d:dict)->dict:
    if method not in METHODS: raise ValueError(f"unsupported engineering method: {method}")
    return {'method':method,'capability':NAMES[method],'artifact_status':'computed_not_physically_verified',
            'input_units':d.get('units',{}),'assumptions':d.get('assumptions',[]),
            'source_refs':d.get('source_refs',[]),'requires_engineer_review':True,
            'boundary':'A calculation or test plan is not a certified design, released drawing, simulation run, laboratory result, or safety approval.'}

def _mechanical(d):
    req=d.get('requirements',[]); loads=d.get('load_cases',[])
    return {'requirements':req,'load_cases':loads,'interfaces':d.get('interfaces',[]),'verification_matrix':[{'requirement_id':r.get('id'),'method':r.get('verification_method'),'acceptance':r.get('acceptance'),'covered':bool(r.get('verification_method') and r.get('acceptance'))} for r in req], 'uncovered_requirement_ids':[r.get('id') for r in req if not r.get('verification_method') or not r.get('acceptance')]}

def _cad(d):
    features=d.get('features',[]); seen=set(); errors=[]
    for f in features:
        missing=[x for x in f.get('references',[]) if x not in seen]
        if missing: errors.append({'feature':f.get('id'),'missing_references':missing})
        seen.add(f.get('id'))
    return {'feature_tree':features,'parameters':d.get('parameters',{}),'reference_errors':errors,'regeneration_ready':not errors and bool(features)}

def _fea(d):
    meshes=d.get('mesh_results',[]); qty=[float(x['result']) for x in meshes]
    conv=None if len(qty)<2 or qty[-1]==0 else abs(qty[-1]-qty[-2])/abs(qty[-1])*100
    return {'analysis_type':d.get('analysis_type'),'boundary_conditions':d.get('boundary_conditions',[]),'contacts':d.get('contacts',[]),'mesh_results':meshes,'last_mesh_change_percent':conv,'converged_to_percent':conv is not None and conv<=float(d.get('convergence_tolerance_percent',5)),'solver_run_claimed':False}

def _cfd(d):
    ins=sum(float(x) for x in d.get('mass_in',[])); outs=sum(float(x) for x in d.get('mass_out',[])); denom=max(abs(ins),1e-12)
    return {'domain':d.get('domain'),'boundary_conditions':d.get('boundary_conditions',[]),'turbulence_model':d.get('turbulence_model'),'mass_in':ins,'mass_out':outs,'mass_imbalance_percent':abs(ins-outs)/denom*100,'solver_run_claimed':False}

def _thermal(d):
    q=_num(d,'heat_w'); rs=[float(x) for x in d.get('thermal_resistances_k_per_w',[])]; ambient=_num(d,'ambient_c')
    if not rs or any(x<0 for x in rs): raise ValueError('thermal_resistances_k_per_w requires nonnegative values')
    return {'total_resistance_k_per_w':sum(rs),'temperature_rise_c':q*sum(rs),'predicted_hot_temperature_c':ambient+q*sum(rs),'equation':'T_hot = T_ambient + Q * sum(R)'}

def _stress(d):
    sx=_num(d,'sigma_x'); sy=float(d.get('sigma_y',0)); sz=float(d.get('sigma_z',0)); txy=float(d.get('tau_xy',0)); tyz=float(d.get('tau_yz',0)); tzx=float(d.get('tau_zx',0))
    vm=math.sqrt(((sx-sy)**2+(sy-sz)**2+(sz-sx)**2+6*(txy*txy+tyz*tyz+tzx*tzx))/2); strength=_num(d,'yield_strength',positive=True)
    return {'von_mises_stress':vm,'yield_strength':strength,'factor_of_safety':strength/vm if vm else None,'equation':'3D von Mises distortion-energy criterion'}

def _fatigue(d):
    damage=[]
    for x in d.get('cycles',[]):
        used=float(x['applied_cycles']); allowed=float(x['allowable_cycles']); damage.append({'applied_cycles':used,'allowable_cycles':allowed,'damage_fraction':used/allowed})
    total=sum(x['damage_fraction'] for x in damage)
    return {'cycle_damage':damage,'miner_sum':total,'passes_miner_rule':total<=float(d.get('damage_limit',1.0)),'equation':'Miner linear cumulative damage'}

def _fracture(d):
    y=float(d.get('geometry_factor',1)); s=_num(d,'stress',nonnegative=True); a=_num(d,'crack_length',positive=True); kic=_num(d,'fracture_toughness',positive=True); ki=y*s*math.sqrt(math.pi*a)
    return {'stress_intensity':ki,'fracture_toughness':kic,'margin_ratio':kic/ki if ki else None,'unstable_fracture_predicted':ki>=kic,'equation':'K_I = Y sigma sqrt(pi a)','unit_consistency_required':True}

def _materials(d):
    criteria=d.get('criteria',[]); out=[]
    for m in d.get('candidates',[]):
        missing=[c['id'] for c in criteria if c['id'] not in m.get('scores',{})]
        score=None if missing else sum(float(c['weight'])*float(m['scores'][c['id']]) for c in criteria)
        out.append({'material':m.get('material'),'weighted_score':score,'missing_criteria':missing,'constraints':m.get('constraints',[])})
    return {'decision_matrix':sorted(out,key=lambda x: x['weighted_score'] if x['weighted_score'] is not None else -math.inf,reverse=True),'criteria':criteria}

def _properties(d):
    props=[]
    for p in d.get('properties',[]): props.append({**p,'traceable':bool(p.get('value') is not None and p.get('unit') and p.get('source_ref') and p.get('condition'))})
    return {'properties':props,'untraceable_properties':[p.get('name') for p in props if not p['traceable']]}

def _failure(d):
    ev=set(d.get('evidence_ids',[])); hs=[]
    for h in d.get('hypotheses',[]):
        sup=[x for x in h.get('supporting_evidence_ids',[]) if x in ev]; con=[x for x in h.get('contrary_evidence_ids',[]) if x in ev]
        hs.append({**h,'verified_support_count':len(sup),'verified_contrary_count':len(con),'status':'candidate_not_root_cause'})
    return {'problem_statement':d.get('problem_statement'),'timeline':d.get('timeline',[]),'hypotheses':hs,'preservation_actions':d.get('preservation_actions',[]),'root_cause_claimed':False}

def _reliability(d):
    vals=[float(x) for x in d.get('component_reliabilities',[])];
    if not vals or any(x<0 or x>1 for x in vals): raise ValueError('component reliabilities must be probabilities')
    return {'series_reliability':math.prod(vals),'component_count':len(vals),'model':'independent series system'}

def _maintain(d):
    repairs=_values(d,'repair_durations_hours'); return {'mttr_hours':fmean(repairs),'repair_summary':_summary(repairs),'access_constraints':d.get('access_constraints',[]),'replaceable_units':d.get('replaceable_units',[])}

def _safety(d):
    hazards=[]
    for h in d.get('hazards',[]):
        s=int(h['severity']); o=int(h['occurrence']); det=int(h['detection']); hazards.append({**h,'rpn':s*o*det,'residual_risk_requires_acceptance':not bool(h.get('risk_owner_approval'))})
    return {'hazards':sorted(hazards,key=lambda x:x['rpn'],reverse=True),'stop_work_conditions':d.get('stop_work_conditions',[])}

def _human(d):
    tasks=[]
    for t in d.get('tasks',[]): tasks.append({**t,'use_error_risks':t.get('use_error_risks',[]),'critical':bool(t.get('safety_consequence'))})
    return {'users':d.get('users',[]),'tasks':tasks,'validation_participants':d.get('validation_participants',[]),'unvalidated':True}

def _ergo(d):
    return {'task':d.get('task'),'exposures':d.get('exposures',[]),'anthropometric_percentiles':d.get('anthropometric_percentiles',[]),'controls':d.get('controls',[]),'assessment_instrument':d.get('assessment_instrument'),'score':d.get('score'),'instrument_interpretation_requires_qualified_reviewer':True}

def _design(d,kind):
    return {'design_kind':kind,'user_needs':d.get('user_needs',[]),'concepts':d.get('concepts',[]),'selection_criteria':d.get('selection_criteria',[]),'prototype_evidence':d.get('prototype_evidence',[]),'release_ready':False}

def _dfm(d):
    checks=[]
    for f in d.get('features',[]):
        violations=[c['id'] for c in d.get('process_constraints',[]) if c.get('min') is not None and float(f.get(c['field'],math.inf))<float(c['min']) or c.get('max') is not None and float(f.get(c['field'],-math.inf))>float(c['max'])]
        checks.append({'feature_id':f.get('id'),'violations':violations})
    return {'process':d.get('process'),'feature_checks':checks,'all_features_manufacturable':all(not x['violations'] for x in checks)}

def _dfa(d):
    parts=d.get('parts',[]); essential=[p for p in parts if p.get('moves_relative') or p.get('different_material_required') or p.get('service_removal_required')]
    return {'part_count':len(parts),'theoretical_minimum_parts':len(essential),'combination_candidates':[p.get('id') for p in parts if p not in essential],'assembly_steps':d.get('assembly_steps',[])}

def _sustain(d):
    stages=d.get('lifecycle_stages',[]); totals={}
    for s in stages:
        for k,v in s.get('impacts',{}).items(): totals[k]=totals.get(k,0)+float(v)
    return {'lifecycle_stages':stages,'impact_totals':totals,'functional_unit':d.get('functional_unit'),'system_boundary':d.get('system_boundary'),'comparative_claim_review_required':True}

def _dfss(d): return {'ctqs':d.get('ctqs',[]),'dmadv_phase':d.get('dmadv_phase'),'verification_plan':d.get('verification_plan',[]),'open_ctq_ids':[x.get('id') for x in d.get('ctqs',[]) if not x.get('specification')]}

def _tol(d):
    ts=[abs(float(x)) for x in d.get('component_tolerances',[])]; nominal=sum(float(x) for x in d.get('component_nominals',[])); return {'nominal_stack':nominal,'worst_case_plus_minus':sum(ts),'rss_plus_minus':math.sqrt(sum(x*x for x in ts)),'distribution_assumption':'independent centered components for RSS only'}

def _gdt(d):
    frames=d.get('feature_control_frames',[]); return {'datum_reference_frame':d.get('datums',[]),'feature_control_frames':frames,'invalid_frames':[x.get('id') for x in frames if not x.get('characteristic') or not x.get('tolerance') or (x.get('requires_datum') and not x.get('datum_references'))],'standard_edition':d.get('standard_edition')}

def _metrology(d):
    us=[float(x) for x in d.get('standard_uncertainties',[])]; uc=math.sqrt(sum(x*x for x in us)); k=float(d.get('coverage_factor',2)); return {'standard_uncertainty':uc,'expanded_uncertainty':k*uc,'coverage_factor':k,'traceability_chain':d.get('traceability_chain',[]),'equation':'root-sum-square independent standard uncertainties'}

def _qc(d):
    vals=_values(d,'measurements'); lo=float(d['lower_spec']); hi=float(d['upper_spec']); bad=[{'index':i,'value':x} for i,x in enumerate(vals) if x<lo or x>hi]; return {'summary':_summary(vals),'nonconforming':bad,'yield_fraction':(len(vals)-len(bad))/len(vals),'disposition_requires_approval':True}

def _qa(d):
    req={x['id'] for x in d.get('requirements',[])}; covered={x for t in d.get('verification_records',[]) for x in t.get('requirement_ids',[])}; return {'requirements':sorted(req),'covered_requirement_ids':sorted(req&covered),'uncovered_requirement_ids':sorted(req-covered),'records':d.get('verification_records',[]),'release_authorized':False}

def _spc(d):
    v=_values(d,'values'); mean=fmean(v); sd=pstdev(v); return {'center_line':mean,'ucl_3sigma':mean+3*sd,'lcl_3sigma':mean-3*sd,'out_of_control_points':[{'index':i,'value':x} for i,x in enumerate(v) if abs(x-mean)>3*sd],'baseline_only':True}

def _capability(d):
    v=_values(d,'values'); mu=fmean(v); sd=pstdev(v); lo=float(d['lower_spec']); hi=float(d['upper_spec']);
    if sd==0: raise ValueError('capability undefined for zero observed variation')
    return {'mean':mu,'within_sigma_assumed':sd,'cp':(hi-lo)/(6*sd),'cpk':min((hi-mu)/(3*sd),(mu-lo)/(3*sd)),'stability_must_be_established_first':True}

def _msa(d):
    repeat=_num(d,'repeatability_variance',nonnegative=True); repro=_num(d,'reproducibility_variance',nonnegative=True); part=_num(d,'part_variance',nonnegative=True); grr=repeat+repro; total=grr+part
    return {'gage_rr_variance':grr,'total_variance':total,'gage_rr_percent_contribution':100*grr/total if total else None,'components':{'repeatability':repeat,'reproducibility':repro,'part_to_part':part}}

def _doe(d):
    factors=d.get('factors',{}); runs=[{}]
    for name,levels in factors.items(): runs=[{**r,name:v} for r in runs for v in levels]
    return {'design':'full_factorial','run_matrix':runs,'run_count':len(runs),'randomization_required':True,'replicates':int(d.get('replicates',1))}

def _taguchi(d):
    vals=_values(d,'responses'); goal=d.get('goal','larger');
    if goal=='larger': sn=-10*math.log10(fmean([1/(x*x) for x in vals]))
    elif goal=='smaller': sn=-10*math.log10(fmean([x*x for x in vals]))
    elif goal=='nominal': sn=10*math.log10(fmean(vals)**2/(pstdev(vals)**2)) if pstdev(vals) else math.inf
    else: raise ValueError('goal must be larger, smaller, or nominal')
    return {'goal':goal,'signal_to_noise_db':sn,'responses':vals,'orthogonal_array':d.get('orthogonal_array')}

def _rsm(d):
    co=d.get('coefficients',{}); x={k:float(v) for k,v in d.get('point',{}).items()}; y=float(co.get('intercept',0)); terms=[]
    for k,v in co.get('linear',{}).items(): y+=float(v)*x[k]; terms.append(k)
    for k,v in co.get('quadratic',{}).items(): y+=float(v)*x[k]**2; terms.append(f'{k}^2')
    for k,v in co.get('interaction',{}).items(): a,b=k.split('*'); y+=float(v)*x[a]*x[b]; terms.append(k)
    return {'predicted_response':y,'point':x,'model_terms':terms,'fit_statistics':d.get('fit_statistics',{}),'extrapolation_checked':False}

def _robust(d):
    scenarios=d.get('scenarios',[]); ys=[float(x['response']) for x in scenarios]; return {'scenario_summary':_summary(ys),'worst_case_response':min(ys) if d.get('objective','maximize')=='maximize' else max(ys),'noise_factors':d.get('noise_factors',[]),'objective':d.get('objective','maximize')}

def _reltest(d):
    n=int(_num(d,'units',positive=True)); failures=int(_num(d,'failures',nonnegative=True)); conf=float(d.get('confidence',.9));
    if failures>n or not 0<conf<1: raise ValueError('invalid failures or confidence')
    r0=(1-conf)**(1/n) if failures==0 else None
    return {'units':n,'failures':failures,'confidence':conf,'zero_failure_reliability_lower_bound':r0,'equation':'R_lower=(1-confidence)^(1/n), zero-failure case only'}

def _alt(d):
    ea=_num(d,'activation_energy_ev',positive=True); tuse=_num(d,'use_temperature_k',positive=True); ttest=_num(d,'test_temperature_k',positive=True); kb=8.617333262e-5; af=math.exp(ea/kb*(1/tuse-1/ttest))
    return {'acceleration_factor':af,'model':'Arrhenius','activation_energy_ev':ea,'use_temperature_k':tuse,'test_temperature_k':ttest,'mechanism_equivalence_must_be_validated':True}

def _env(d,kind): return {'test_type':kind,'profiles':d.get('profiles',[]),'specimen_count':d.get('specimen_count'),'preconditioning':d.get('preconditioning',[]),'measurements':d.get('measurements',[]),'acceptance_criteria':d.get('acceptance_criteria',[]),'test_executed':False}

def _vibration(d):
    psd=d.get('psd_points',[]); area=sum((float(b['frequency_hz'])-float(a['frequency_hz']))*(float(a['psd_g2_per_hz'])+float(b['psd_g2_per_hz']))/2 for a,b in zip(psd,psd[1:])); return {'grms':math.sqrt(max(area,0)),'integrated_psd_g2':area,'axes':d.get('axes',[]),'duration_per_axis':d.get('duration_per_axis'),'test_executed':False}

def _shock(d):
    peak=_num(d,'peak_acceleration_g',positive=True); duration=_num(d,'duration_ms',positive=True); shape=d.get('pulse_shape','half_sine'); factor={'half_sine':2/math.pi,'rectangular':1,'terminal_peak_sawtooth':.5}.get(shape)
    if factor is None: raise ValueError('unsupported pulse_shape')
    return {'pulse_shape':shape,'peak_acceleration_g':peak,'duration_ms':duration,'estimated_delta_velocity_m_per_s':peak*9.80665*duration/1000*factor,'test_executed':False}

def _corrosion(d):
    loss=_num(d,'mass_loss_g',nonnegative=True); density=_num(d,'density_g_cm3',positive=True); area=_num(d,'area_cm2',positive=True); hours=_num(d,'duration_hours',positive=True); return {'thickness_loss_cm':loss/(density*area),'penetration_rate_cm_per_hour':loss/(density*area*hours),'test_executed':False}

def _wear(d):
    vol=_num(d,'wear_volume_mm3',nonnegative=True); load=_num(d,'load_n',positive=True); dist=_num(d,'sliding_distance_m',positive=True); return {'specific_wear_rate_mm3_per_n_m':vol/(load*dist),'test_executed':False}

def _fatigue_test(d):
    pts=d.get('sn_points',[]); x=[math.log10(float(p['stress'])) for p in pts]; y=[math.log10(float(p['cycles'])) for p in pts]
    if len(pts)<2: raise ValueError('sn_points needs at least two points')
    xm,ym=fmean(x),fmean(y); den=sum((a-xm)**2 for a in x); slope=sum((a-xm)*(b-ym) for a,b in zip(x,y))/den; intercept=ym-slope*xm
    return {'basquin_log10_intercept':intercept,'basquin_slope':slope,'points':pts,'runouts':d.get('runouts',[]),'test_executed':False}

def _creep(d):
    times=_values(d,'time_hours'); strains=_values(d,'strain');
    if len(times)!=len(strains) or len(times)<2: raise ValueError('time_hours and strain need equal lengths')
    return {'interval_rates_per_hour':[(strains[i]-strains[i-1])/(times[i]-times[i-1]) for i in range(1,len(times))],'test_temperature':d.get('test_temperature'),'test_executed':False}

def _impact(d):
    before=_num(d,'initial_energy_j',nonnegative=True); after=_num(d,'remaining_energy_j',nonnegative=True); return {'absorbed_energy_j':before-after,'specimen_geometry':d.get('specimen_geometry'),'notch':d.get('notch'),'test_executed':False}

def _hardness(d): return {'scale':d.get('scale'),'summary':_summary(_values(d,'values')),'calibration_ref':d.get('calibration_ref'),'cross_scale_conversion_performed':False,'test_executed':False}

def _tensile(d):
    force=_num(d,'max_force_n',nonnegative=True); area=_num(d,'original_area_mm2',positive=True); gauge=_num(d,'original_gauge_length_mm',positive=True); final=float(d.get('final_gauge_length_mm',gauge)); return {'ultimate_tensile_strength_mpa':force/area,'elongation_percent':(final-gauge)/gauge*100,'yield_strength_mpa':d.get('yield_force_n') and float(d['yield_force_n'])/area,'test_executed':False}

def _compression(d): return {'compressive_stress_mpa':_num(d,'force_n',nonnegative=True)/_num(d,'area_mm2',positive=True),'compressive_strain':_num(d,'shortening_mm',nonnegative=True)/_num(d,'original_length_mm',positive=True),'test_executed':False}

def _shear(d): return {'average_shear_stress_mpa':_num(d,'force_n',nonnegative=True)/(_num(d,'shear_area_mm2',positive=True)*int(d.get('shear_planes',1))),'shear_planes':int(d.get('shear_planes',1)),'test_executed':False}

def _torsion(d):
    torque=_num(d,'torque_n_mm',nonnegative=True); radius=_num(d,'outer_radius_mm',positive=True); j=_num(d,'polar_moment_mm4',positive=True); length=_num(d,'gauge_length_mm',positive=True); angle=_num(d,'angle_rad',nonnegative=True); return {'maximum_shear_stress_mpa':torque*radius/j,'shear_modulus_mpa':torque*length/(j*angle) if angle else None,'test_executed':False}

DISPATCH={'mechanical_design':_mechanical,'cad_modeling':_cad,'finite_element_analysis':_fea,'computational_fluid_dynamics':_cfd,'thermal_analysis':_thermal,'stress_analysis':_stress,'fatigue_analysis':_fatigue,'fracture_mechanics':_fracture,'materials_selection':_materials,'material_properties':_properties,'failure_analysis':_failure,'reliability_engineering':_reliability,'maintainability_engineering':_maintain,'safety_engineering':_safety,'human_factors_engineering':_human,'ergonomics':_ergo,'industrial_design':lambda d:_design(d,'industrial'),'design_for_manufacturing':_dfm,'design_for_assembly':_dfa,'design_for_sustainability':_sustain,'design_for_six_sigma':_dfss,'tolerance_analysis':_tol,'gdt':_gdt,'metrology':_metrology,'quality_control':_qc,'quality_assurance':_qa,'statistical_process_control':_spc,'process_capability':_capability,'measurement_systems_analysis':_msa,'design_of_experiments':_doe,'taguchi_methods':_taguchi,'response_surface_methodology':_rsm,'robust_design':_robust,'reliability_testing':_reltest,'accelerated_life_testing':_alt,'environmental_testing':lambda d:_env(d,'environmental'),'vibration_testing':_vibration,'shock_testing':_shock,'thermal_cycling':lambda d:_env(d,'thermal_cycling'),'humidity_testing':lambda d:_env(d,'humidity'),'corrosion_testing':_corrosion,'wear_testing':_wear,'fatigue_testing':_fatigue_test,'creep_testing':_creep,'impact_testing':_impact,'hardness_testing':_hardness,'tensile_testing':_tensile,'compression_testing':_compression,'shear_testing':_shear,'torsion_testing':_torsion}

def engineering_support_1510_1559(method:str,data:dict[str,Any])->dict[str,Any]:
    if method not in DISPATCH: raise ValueError(f'unsupported engineering method: {method}')
    out=_base(method,data); out['result']=DISPATCH[method](data)
    out['evaluation']={'checks_performed':sorted(out['result']),'acceptance_criteria':data.get('acceptance_criteria',[]),'verification_plan':data.get('verification_plan',[]),'qualified_review_required':True}
    out['uncertainty']={'level':'not_quantified','drivers':['caller-supplied geometry, loads and material data','model-form and boundary-condition choices','measurement and manufacturing variation'],'physical_test_or_solver_execution_claimed':False}
    return out
