"""Auditable environmental engineering calculations for feature rows 1610-1659.

Pure functions only: caller supplies measurements/scenarios, units are returned,
and projections expose assumptions and material limits. Nothing operates physical
infrastructure or claims a regulatory determination.
"""
from __future__ import annotations
import math
NAMES=['climate_modeling','global_warming_projections','carbon_cycle_analysis','ocean_acidification','sea_level_rise','extreme_weather','climate_attribution','mitigation_strategies','adaptation_planning','carbon_capture','carbon_sequestration','negative_emissions','geoengineering','solar_radiation_management','ocean_fertilization','afforestation','reforestation','biochar','soil_carbon','blue_carbon','renewable_energy','energy_efficiency','sustainable_transport','electric_vehicles','hydrogen_economy','circular_economy','waste_reduction','recycling','composting','anaerobic_digestion','waste_to_energy','landfill_management','water_treatment','wastewater_treatment','desalination','water_conservation','water_quality','groundwater_management','watershed_management','integrated_water_resources','air_quality','air_pollution_control','emissions_monitoring','atmospheric_chemistry','indoor_air_quality','soil_health','soil_remediation','contaminated_land','brownfield_redevelopment','phytoremediation']
ROWS={name:1610+i for i,name in enumerate(NAMES)}
SUMMARIES={name:name.replace('_',' ').title() for name in NAMES}
INPUTS={name:['documented caller-supplied measurements and scenario parameters'] for name in NAMES}
def _f(x,n):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError(f'{n} must be finite')
 return float(x)
def _v(d,k,n=1):
 x=d.get(k)
 if not isinstance(x,list) or len(x)<n:raise ValueError(f'{k} needs at least {n} values')
 return [_f(a,k) for a in x]
def _aligned(*x):
 if len({len(a) for a in x})!=1:raise ValueError('aligned arrays required')
def _positive(x,n,zero=False):
 x=_f(x,n)
 if x<0 if zero else x<=0:raise ValueError(f'{n} must be {"nonnegative" if zero else "positive"}')
 return x
def _base(method,data,params):return {'method':method,'feature_row':ROWS[method],'inputs':{'data':data,'params':params},'assumptions':[],'method_limits':[]}
def run(method,data,params=None,seed=0):
 if method not in ROWS:raise ValueError(f'unsupported environmental method {method}')
 p=params or {};o=_base(method,data,p);a=o['assumptions'];lim=o['method_limits'];out={}
 if method=='climate_modeling':
  forcing=_v(data,'radiative_forcing');feedback=_positive(p.get('feedback_parameter',1.2),'feedback_parameter');capacity=_positive(p.get('heat_capacity',10),'heat_capacity');dt=_positive(p.get('time_step',1),'time_step');t=_f(data.get('initial_temperature_anomaly',0),'initial_temperature_anomaly');path=[]
  for f in forcing:t+=dt*(f-feedback*t)/capacity;path.append(t)
  out={'temperature_anomaly_path':path,'equilibrium_anomaly_for_last_forcing':forcing[-1]/feedback,'energy_imbalance_last':forcing[-1]-feedback*t};a+=['Zero-dimensional energy-balance model with constant feedback and heat capacity.'];lim+=['No spatial circulation, aerosols, clouds, internal variability or coupled carbon cycle.']
 elif method=='global_warming_projections':
  emissions=_v(data,'annual_emissions');tcre=_positive(p.get('tcre_c_per_1000_gtco2',.45),'tcre');cum=0;path=[]
  for e in emissions:cum+=e;path.append(cum/1000*tcre)
  out={'cumulative_emissions_gtco2':cum,'warming_path_c':path,'warming_c':path[-1]};a+=['Linear transient climate response to cumulative CO2 emissions.'];lim+=['CO2-only scenario; not an assessed probabilistic projection.']
 elif method=='carbon_cycle_analysis':
  emissions=_v(data,'emissions');atmos=_v(data,'atmospheric_increase');_aligned(emissions,atmos);sink=[e-g for e,g in zip(emissions,atmos)];out={'total_emissions':sum(emissions),'atmospheric_increase':sum(atmos),'land_ocean_sink':sum(sink),'airborne_fraction':sum(atmos)/sum(emissions) if sum(emissions) else None,'annual_sink':sink};a+=['Mass terms use the same carbon units and periods.']
 elif method=='ocean_acidification':
  ph0=_f(data['baseline_ph'],'baseline_ph');ph1=_f(data['current_ph'],'current_ph');h0=10**(-ph0);h1=10**(-ph1);out={'ph_change':ph1-ph0,'hydrogen_ion_multiplier':h1/h0,'hydrogen_concentration_baseline':h0,'hydrogen_concentration_current':h1};lim+=['pH alone does not solve carbonate alkalinity or saturation state.']
 elif method=='sea_level_rise':
  thermal=_v(data,'thermal_expansion');glacier=_v(data,'glacier_ice');sheets=_v(data,'ice_sheets');land=_v(data,'land_water');_aligned(thermal,glacier,sheets,land);total=[sum(x) for x in zip(thermal,glacier,sheets,land)];out={'component_totals':{'thermal':sum(thermal),'glacier':sum(glacier),'ice_sheets':sum(sheets),'land_water':sum(land)},'annual_total':total,'cumulative_rise':sum(total)}
 elif method=='extreme_weather':
  old=_positive(data['historical_return_period'],'historical_return_period');new=_positive(data['projected_return_period'],'projected_return_period');years=_positive(p.get('horizon_years',30),'horizon_years');out={'frequency_multiplier':old/new,'historical_annual_probability':1/old,'projected_annual_probability':1/new,'projected_at_least_one_probability':1-(1-1/new)**years};a+=['Independent stationary annual exceedance probability within each climate state.']
 elif method=='climate_attribution':
  pf=_f(data['probability_factual'],'probability_factual');pc=_f(data['probability_counterfactual'],'probability_counterfactual')
  if not 0<=pf<=1 or not 0<pc<=1:raise ValueError('probabilities must be in [0,1], counterfactual >0')
  out={'risk_ratio':pf/pc,'fraction_attributable_risk':1-pc/pf if pf else None,'probability_change':pf-pc};a+=['Factual and counterfactual ensembles are comparable and event definition is pre-specified.']
 elif method=='mitigation_strategies':
  names=data.get('names');abat=_v(data,'abatement');cost=_v(data,'cost');
  if not isinstance(names,list):raise ValueError('names required')
  _aligned(names,abat,cost);rows=sorted([{'name':n,'abatement':q,'cost':c,'cost_per_unit':c/q if q>0 else None} for n,q,c in zip(names,abat,cost)],key=lambda x:math.inf if x['cost_per_unit'] is None else x['cost_per_unit']);budget=_f(p.get('budget',math.inf),'budget');spent=removed=0
  for r in rows:
   if spent+r['cost']<=budget:spent+=r['cost'];removed+=r['abatement']
  out={'marginal_abatement_curve':rows,'selected_abatement':removed,'selected_cost':spent}
 elif method=='adaptation_planning':
  hazards=_v(data,'hazard_probability');exposure=_v(data,'exposure');vuln=_v(data,'vulnerability');reduction=_v(data,'risk_reduction');cost=_v(data,'cost');_aligned(hazards,exposure,vuln,reduction,cost);before=[h*e*v for h,e,v in zip(hazards,exposure,vuln)];benefit=[r*x for r,x in zip(reduction,before)];out={'baseline_expected_loss':sum(before),'residual_expected_loss':sum(x-y for x,y in zip(before,benefit)),'benefit_cost_ratios':[b/c if c else None for b,c in zip(benefit,cost)],'priority_order':sorted(range(len(cost)),key=lambda i:benefit[i]/cost[i] if cost[i] else math.inf,reverse=True)}
 elif method=='carbon_capture':
  feed=_positive(data['feed_co2'],'feed_co2',True);eff=_f(data['capture_efficiency'],'capture_efficiency');energy=_positive(data.get('energy_per_unit',0),'energy_per_unit',True)
  if not 0<=eff<=1:raise ValueError('capture_efficiency must be 0..1')
  cap=feed*eff;out={'captured_co2':cap,'residual_co2':feed-cap,'energy_requirement':cap*energy}
 elif method=='carbon_sequestration':
  initial=_positive(data['initial_stock'],'initial_stock',True);final=_positive(data['final_stock'],'final_stock',True);years=_positive(data['years'],'years');perm=_f(p.get('permanence_factor',1),'permanence_factor');out={'gross_stock_change':final-initial,'annual_sequestration':(final-initial)/years,'permanence_adjusted_sequestration':(final-initial)*perm}
 elif method=='negative_emissions':
  removed=_positive(data['gross_removal'],'gross_removal',True);lifecycle=_positive(data.get('lifecycle_emissions',0),'lifecycle_emissions',True);leak=_f(data.get('leakage_fraction',0),'leakage_fraction');out={'net_removal':removed*(1-leak)-lifecycle,'gross_removal':removed,'lifecycle_emissions':lifecycle,'leakage':removed*leak}
 elif method=='geoengineering':
  forcing=_f(data['forcing_change'],'forcing_change');feedback=_positive(p.get('feedback_parameter',1.2),'feedback_parameter');side=_v(data,'regional_impact_scores');out={'equilibrium_temperature_effect':forcing/feedback,'mean_regional_impact':sum(side)/len(side),'worst_absolute_regional_impact':max(map(abs,side))};lim+=['Scenario screening only; governance, termination shock and ecological risk need separate assessment.']
 elif method=='solar_radiation_management':
  solar=_positive(p.get('solar_constant',1361),'solar_constant');albedo=_f(data['albedo_change'],'albedo_change');feedback=_positive(p.get('feedback_parameter',1.2),'feedback_parameter');forcing=-solar*albedo/4;out={'radiative_forcing':forcing,'equilibrium_temperature_effect':forcing/feedback};lim+=['Global-mean albedo approximation; precipitation and regional effects omitted.']
 elif method=='ocean_fertilization':
  area=_positive(data['area_km2'],'area_km2');export=_positive(data['carbon_export_per_km2'],'carbon_export_per_km2',True);depth=_f(data['deep_sequestration_fraction'],'deep_sequestration_fraction');dur=_f(data['durability_fraction'],'durability_fraction');out={'exported_carbon':area*export,'durable_deep_carbon':area*export*depth*dur};lim+=['Does not infer ecosystem safety, nutrient limitation, N2O or verification feasibility.']
 elif method in {'afforestation','reforestation'}:
  area=_positive(data['area_hectares'],'area_hectares');growth=_positive(data['annual_biomass_growth_t_per_ha'],'growth',True);cf=_f(p.get('carbon_fraction',.47),'carbon_fraction');years=_positive(data['years'],'years');surv=_f(data.get('survival_fraction',1),'survival_fraction');carbon=area*growth*cf*years*surv;out={'biomass_carbon_t':carbon,'co2_equivalent_t':carbon*44/12,'annual_co2_equivalent_t':carbon*44/12/years}
 elif method=='biochar':
  mass=_positive(data['biochar_mass'],'biochar_mass',True);carbon=_f(data['carbon_fraction'],'carbon_fraction');stable=_f(data['stable_fraction'],'stable_fraction');out={'stable_carbon':mass*carbon*stable,'co2_equivalent':mass*carbon*stable*44/12,'unstable_carbon':mass*carbon*(1-stable)}
 elif method=='soil_carbon':
  bulk=_positive(data['bulk_density_g_cm3'],'bulk_density');depth=_positive(data['depth_cm'],'depth');cf=_positive(data['carbon_fraction'],'carbon_fraction',True);area=_positive(data.get('area_hectares',1),'area_hectares');stock=bulk*depth*cf*100*area;out={'soil_carbon_tonnes':stock,'co2_equivalent_tonnes':stock*44/12};a+=['Rock-fragment correction is zero; carbon fraction is dry-mass fraction.']
 elif method=='blue_carbon':
  area=_positive(data['area_hectares'],'area_hectares');biomass=_positive(data['biomass_carbon_per_ha'],'biomass',True);soil=_positive(data['soil_carbon_per_ha'],'soil',True);loss=_f(data.get('disturbance_loss_fraction',0),'loss');out={'ecosystem_carbon':area*(biomass+soil),'retained_carbon':area*(biomass+soil)*(1-loss),'avoided_co2_if_protected':area*(biomass+soil)*loss*44/12}
 elif method=='renewable_energy':
  cap=_positive(data['capacity_mw'],'capacity');cf=_f(data['capacity_factor'],'capacity_factor');hours=_positive(p.get('hours',8760),'hours');grid=_f(data.get('grid_emissions_t_per_mwh',0),'grid_emissions');gen=cap*cf*hours;out={'generation_mwh':gen,'avoided_emissions_t':gen*grid}
 elif method=='energy_efficiency':
  baseline=_positive(data['baseline_energy'],'baseline_energy',True);after=_positive(data['post_measure_energy'],'post_measure_energy',True);cost=_positive(data.get('investment_cost',0),'cost',True);price=_positive(data.get('energy_price',0),'price',True);save=baseline-after;annual=save*price;out={'energy_savings':save,'savings_fraction':save/baseline if baseline else None,'annual_cost_savings':annual,'simple_payback_years':cost/annual if annual>0 else None}
 elif method=='sustainable_transport':
  distances=_v(data,'distance_km');factors=_v(data,'emission_factor_kg_per_km');occupancy=_v(data,'occupancy');_aligned(distances,factors,occupancy);em=[d*f for d,f in zip(distances,factors)];out={'total_emissions_kg':sum(em),'passenger_km':sum(d*o for d,o in zip(distances,occupancy)),'emissions_per_passenger_km':sum(em)/sum(d*o for d,o in zip(distances,occupancy))}
 elif method=='electric_vehicles':
  km=_positive(data['distance_km'],'distance');cons=_positive(data['kwh_per_km'],'consumption');grid=_positive(data['grid_kg_per_kwh'],'grid',True);ice=_positive(data['ice_kg_per_km'],'ice',True);emb=_f(data.get('embodied_emissions_difference_kg',0),'embodied');annual_saving=km*(ice-cons*grid);out={'ev_use_emissions_kg':km*cons*grid,'ice_use_emissions_kg':km*ice,'annual_operational_savings_kg':annual_saving,'carbon_payback_years':emb/annual_saving if annual_saving>0 else None}
 elif method=='hydrogen_economy':
  electricity=_positive(data['electricity_input_mwh'],'electricity',True);electrolyzer=_f(data['electrolyzer_efficiency'],'efficiency');fuelcell=_f(data.get('end_use_efficiency',1),'end_use_efficiency');grid=_positive(data.get('grid_emissions_t_per_mwh',0),'grid',True);out={'hydrogen_energy_mwh':electricity*electrolyzer,'useful_energy_mwh':electricity*electrolyzer*fuelcell,'round_trip_efficiency':electrolyzer*fuelcell,'production_emissions_t':electricity*grid}
 elif method=='circular_economy':
  virgin=_positive(data['virgin_input'],'virgin',True);recycled=_positive(data['recycled_input'],'recycled',True);recovered=_positive(data['recovered_output'],'recovered',True);total=virgin+recycled;out={'recycled_input_share':recycled/total if total else None,'output_recovery_rate':recovered/total if total else None,'material_circularity_proxy':(recycled+recovered)/(2*total) if total else None}
 elif method=='waste_reduction':
  base=_positive(data['baseline_waste'],'baseline',True);current=_positive(data['current_waste'],'current',True);out={'waste_avoided':base-current,'reduction_fraction':(base-current)/base if base else None}
 elif method=='recycling':
  waste=_positive(data['waste_generated'],'waste',True);recycled=_positive(data['recycled_mass'],'recycled',True);contam=_f(data.get('contamination_fraction',0),'contamination');factor=_positive(data.get('virgin_emissions_avoided_per_mass',0),'factor',True);net=recycled*(1-contam);out={'gross_diversion_rate':recycled/waste if waste else None,'net_recovered_mass':net,'net_diversion_rate':net/waste if waste else None,'avoided_emissions':net*factor}
 elif method=='composting':
  feed=_positive(data['organic_feedstock'],'feedstock',True);yieldf=_f(data['compost_yield_fraction'],'yield');avoided=_positive(data.get('avoided_landfill_emissions_per_mass',0),'avoided',True);process=_positive(data.get('process_emissions_per_mass',0),'process',True);out={'compost_output':feed*yieldf,'net_avoided_emissions':feed*(avoided-process)}
 elif method=='anaerobic_digestion':
  feed=_positive(data['volatile_solids'],'solids',True);yieldm=_positive(data['methane_yield_m3_per_unit'],'yield',True);capture=_f(data['capture_efficiency'],'capture');energy=_positive(p.get('methane_energy_kwh_m3',10),'energy');meth=feed*yieldm*capture;out={'captured_methane_m3':meth,'energy_kwh':meth*energy,'uncaptured_methane_m3':feed*yieldm*(1-capture)}
 elif method=='waste_to_energy':
  mass=_positive(data['waste_mass'],'mass',True);lhv=_positive(data['lower_heating_value_mj_per_kg'],'lhv',True);eff=_f(data['electrical_efficiency'],'efficiency');grid=_positive(data.get('grid_emissions_kg_per_kwh',0),'grid',True);direct=_positive(data.get('direct_emissions_kg_per_mass',0),'direct',True);kwh=mass*lhv/3.6*eff;out={'electricity_kwh':kwh,'direct_emissions_kg':mass*direct,'avoided_grid_emissions_kg':kwh*grid,'net_emissions_kg':mass*direct-kwh*grid}
 elif method=='landfill_management':
  waste=_positive(data['degradable_carbon'],'carbon',True);methane_fraction=_f(data['methane_generation_fraction'],'fraction');capture=_f(data['capture_efficiency'],'capture');oxid=_f(data.get('oxidation_fraction',0),'oxidation');generated=waste*methane_fraction;out={'methane_generated':generated,'methane_captured':generated*capture,'methane_emitted':generated*(1-capture)*(1-oxid)}
 elif method=='water_treatment':
  flow=_positive(data['flow_m3'],'flow',True);cin=_positive(data['influent_concentration_mg_l'],'influent',True);cout=_positive(data['effluent_concentration_mg_l'],'effluent',True);dose=_positive(data.get('dose_mg_l',0),'dose',True);out={'removal_efficiency':(cin-cout)/cin if cin else None,'pollutant_removed_kg':flow*(cin-cout)/1000,'chemical_required_kg':flow*dose/1000}
 elif method=='wastewater_treatment':
  flow=_positive(data['flow_m3'],'flow',True);bodin=_positive(data['influent_bod_mg_l'],'influent',True);bodout=_positive(data['effluent_bod_mg_l'],'effluent',True);yieldf=_positive(p.get('sludge_yield_kg_per_kg',.5),'yield',True);removed=flow*(bodin-bodout)/1000;out={'bod_removed_kg':removed,'removal_efficiency':(bodin-bodout)/bodin if bodin else None,'sludge_production_kg':removed*yieldf}
 elif method=='desalination':
  product=_positive(data['product_water_m3'],'product',True);recovery=_f(data['recovery_fraction'],'recovery');
  if not 0<recovery<=1:raise ValueError('recovery_fraction must be in (0,1]')
  energy=_positive(data['specific_energy_kwh_m3'],'energy',True);price=_positive(data.get('electricity_price',0),'price',True);out={'feed_water_m3':product/recovery,'brine_m3':product/recovery-product,'energy_kwh':product*energy,'energy_cost':product*energy*price}
 elif method=='water_conservation':
  base=_positive(data['baseline_demand'],'baseline',True);after=_positive(data['post_measure_demand'],'after',True);out={'water_saved':base-after,'conservation_fraction':(base-after)/base if base else None}
 elif method=='water_quality':
  values=_v(data,'values');standards=_v(data,'standards');weights=_v(data,'weights');_aligned(values,standards,weights)
  if any(s<=0 for s in standards) or sum(weights)<=0:raise ValueError('positive standards and weight total required')
  subs=[min(100,100*v/s) for v,s in zip(values,standards)];out={'subindices':subs,'weighted_quality_index':sum(q*w for q,w in zip(subs,weights))/sum(weights),'exceedances':[i for i,(v,s) in enumerate(zip(values,standards)) if v>s]};lim+=['Generic normalized index; jurisdiction-specific WQI direction and thresholds may differ.']
 elif method=='groundwater_management':
  recharge=_positive(data['recharge'],'recharge',True);pumping=_positive(data['pumping'],'pumping',True);natural=_positive(data.get('natural_discharge',0),'natural_discharge',True);storage=_f(data.get('initial_storage',0),'storage');change=recharge-pumping-natural;out={'storage_change':change,'ending_storage':storage+change,'sustainable_yield_gap':recharge-natural-pumping}
 elif method=='watershed_management':
  rain=_positive(data['rainfall_mm'],'rainfall',True);area=_positive(data['area_km2'],'area');coeff=_f(data['runoff_coefficient'],'coefficient');runoff=rain/1000*area*1e6*coeff;out={'runoff_volume_m3':runoff,'infiltration_and_losses_m3':rain/1000*area*1e6-runoff}
 elif method=='integrated_water_resources':
  supply=_v(data,'supplies');demand=_v(data,'demands');_aligned(supply,demand);balances=[x-y for x,y in zip(supply,demand)];out={'period_balances':balances,'total_balance':sum(balances),'reliability_fraction':sum(x>=0 for x in balances)/len(balances),'maximum_deficit':max([max(0,-x) for x in balances])}
 elif method=='air_quality':
  c=_positive(data['concentration'],'concentration',True);breaks=data.get('breakpoints')
  if not isinstance(breaks,list) or not breaks:raise ValueError('breakpoints required')
  selected=None
  for b in breaks:
   if b['c_low']<=c<=b['c_high']:selected=b;break
  if not selected:raise ValueError('concentration outside breakpoint table')
  aqi=(selected['i_high']-selected['i_low'])/(selected['c_high']-selected['c_low'])*(c-selected['c_low'])+selected['i_low'];out={'aqi':round(aqi),'raw_aqi':aqi,'band':selected};a+=['Breakpoint table and averaging period are supplied by caller for the applicable pollutant/jurisdiction.']
 elif method=='air_pollution_control':
  flow=_positive(data['gas_flow'],'flow',True);cin=_positive(data['inlet_concentration'],'inlet',True);eff=_f(data['control_efficiency'],'efficiency');hours=_positive(data.get('hours',1),'hours');out={'inlet_mass':flow*cin*hours,'removed_mass':flow*cin*hours*eff,'outlet_mass':flow*cin*hours*(1-eff),'outlet_concentration':cin*(1-eff)}
 elif method=='emissions_monitoring':
  conc=_v(data,'concentrations');flow=_v(data,'flow_rates');_aligned(conc,flow);rates=[c*f for c,f in zip(conc,flow)];out={'mass_rates':rates,'mean_mass_rate':sum(rates)/len(rates),'total_mass_for_unit_intervals':sum(rates),'peak_mass_rate':max(rates)}
 elif method=='atmospheric_chemistry':
  k=_positive(data['rate_constant'],'rate_constant',True);a0=_positive(data['initial_concentration'],'concentration',True);react=_positive(data['reactant_concentration'],'reactant',True);time=_positive(data['time'],'time',True);pseudo=k*react;out={'remaining_concentration':a0*math.exp(-pseudo*time),'lifetime':1/pseudo if pseudo else None,'fraction_reacted':1-math.exp(-pseudo*time)};a+=['Reactant remains constant, giving pseudo-first-order kinetics.']
 elif method=='indoor_air_quality':
  source=_positive(data['source_rate'],'source',True);volume=_positive(data['room_volume'],'volume');ach=_positive(data['air_changes_per_hour'],'ach');outdoor=_positive(data.get('outdoor_concentration',0),'outdoor',True);removal=_positive(data.get('additional_removal_per_hour',0),'removal',True);lam=ach+removal;out={'steady_state_concentration':outdoor+source/(volume*lam),'air_exchange_rate_per_hour':ach,'total_removal_rate_per_hour':lam}
 elif method=='soil_health':
  vals=_v(data,'indicator_values');targets=_v(data,'target_values');weights=_v(data,'weights');_aligned(vals,targets,weights)
  if any(t<=0 for t in targets) or sum(weights)<=0:raise ValueError('positive targets and weights required')
  scores=[min(1,v/t) for v,t in zip(vals,targets)];out={'indicator_scores':scores,'soil_health_index':sum(s*w for s,w in zip(scores,weights))/sum(weights)}
 elif method=='soil_remediation':
  c0=_positive(data['initial_concentration'],'initial',True);k=_positive(data['decay_rate'],'decay',True);time=_positive(data['time'],'time',True);target=_positive(data.get('target_concentration',0),'target',True);ct=c0*math.exp(-k*time);out={'final_concentration':ct,'removal_fraction':1-ct/c0 if c0 else None,'meets_target':ct<=target,'time_to_target':math.log(c0/target)/k if 0<target<c0 else 0 if target>=c0 else None}
 elif method=='contaminated_land':
  concentrations=_v(data,'concentrations');tox=_v(data,'toxicity_factors');exposure=_v(data,'exposure_factors');_aligned(concentrations,tox,exposure);risks=[c*t*e for c,t,e in zip(concentrations,tox,exposure)];threshold=_f(p.get('risk_threshold',1),'threshold');out={'pathway_risks':risks,'total_risk_index':sum(risks),'exceeds_threshold':sum(risks)>threshold}
 elif method=='brownfield_redevelopment':
  benefits=_v(data,'annual_benefits');costs=_v(data,'annual_costs');_aligned(benefits,costs);initial=_positive(data.get('initial_remediation_cost',0),'initial',True);rate=_f(p.get('discount_rate',.05),'rate');npv=-initial+sum((b-c)/(1+rate)**(i+1) for i,(b,c) in enumerate(zip(benefits,costs)));out={'redevelopment_npv':npv,'financially_positive':npv>=0,'initial_remediation_cost':initial};lim+=['Financial screen excludes unpriced health, justice, ecology and planning impacts.']
 elif method=='phytoremediation':
  c0=_positive(data['initial_soil_concentration'],'initial',True);k=_positive(data['plant_uptake_rate'],'uptake',True);biomass=_positive(data['biomass_factor'],'biomass',True);time=_positive(data['time'],'time',True);ct=c0*math.exp(-k*biomass*time);out={'final_soil_concentration':ct,'removed_concentration':c0-ct,'removal_fraction':1-ct/c0 if c0 else None};a+=['First-order uptake with constant viable biomass and no contaminant rebound.']
 else:raise AssertionError(method)
 o['output']=out
 o['evaluation']={'computed_outputs':sorted(out),'scenario_or_standard':p.get('scenario') or p.get('standard'),'validation_data_supplied':bool(data.get('validation_data')),'review_required':True}
 o['uncertainty']={'level':'not_quantified','drivers':['input-data quality','scenario choice','model structure and excluded feedbacks'],'physical_or_policy_outcome_claimed':False}
 return o
