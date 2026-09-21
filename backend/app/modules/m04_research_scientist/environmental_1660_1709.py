"""Auditable environmental and sustainability calculators for ledger rows 1660-1709."""
from __future__ import annotations
import math, statistics
NAMES="""bioremediation ecosystem_services biodiversity conservation_biology protected_areas wildlife_management fisheries_management forestry agroecology sustainable_agriculture organic_farming permaculture regenerative_agriculture precision_agriculture vertical_farming aquaponics hydroponics urban_agriculture food_security food_systems sustainable_diets food_waste environmental_health toxicology risk_assessment exposure_science epidemiology environmental_justice indigenous_rights community_engagement stakeholder_analysis environmental_policy regulation permitting environmental_impact_assessment strategic_environmental_assessment life_cycle_assessment carbon_footprinting water_footprinting ecological_footprinting material_flow_analysis industrial_ecology cleaner_production green_chemistry green_engineering sustainable_design biomimicry cradle_to_cradle natural_capitalism triple_bottom_line""".split()
ROWS=dict(zip(NAMES,range(1660,1710)))
def _n(d,k,default=None):
 v=d.get(k,default)
 if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v):raise ValueError(f"{k} must be finite")
 return float(v)
def _v(d,k,n=1):
 v=d.get(k)
 if not isinstance(v,list) or len(v)<n or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in v):raise ValueError(f"{k} requires {n}+ finite values")
 return [float(x) for x in v]
def _ratio(a,b,k="denominator"):
 if b<=0:raise ValueError(f"{k} must be positive")
 return a/b
def _weighted(d):
 vals=d.get("metrics"); w=d.get("weights")
 if not isinstance(vals,dict) or not vals:raise ValueError("metrics mapping required")
 if w is None:w={k:1 for k in vals}
 if set(vals)!=set(w) or any(not 0<=float(x)<=1 for x in vals.values()) or any(float(x)<0 for x in w.values()) or sum(map(float,w.values()))<=0:raise ValueError("aligned normalized metrics and nonnegative weights required")
 z=sum(map(float,w.values()));return sum(float(vals[k])*float(w[k]) for k in vals)/z,{k:float(vals[k])*float(w[k])/z for k in vals}
def run(method,data):
 if method not in ROWS:raise ValueError(f"unsupported environmental method {method}")
 out={}; assumptions=[]; limits=["Calculator uses caller-supplied observations; it does not certify compliance, causality, rights, or sustainability."]
 if method=="bioremediation":
  c0=_n(data,"initial_concentration");ct=_n(data,"final_concentration");t=_n(data,"elapsed_days");out={"removal_efficiency":(c0-ct)/c0,"first_order_rate_per_day":math.log(c0/ct)/t,"half_life_days":math.log(2)/(math.log(c0/ct)/t)}
 elif method=="ecosystem_services":
  quantities=_v(data,"annual_quantities");values=_v(data,"unit_values");out={"annual_service_value":sum(a*b for a,b in zip(quantities,values)),"service_count":len(quantities)}
 elif method=="biodiversity":
  counts=_v(data,"species_counts");tot=sum(counts);p=[x/tot for x in counts if x>0];out={"richness":len(p),"shannon_index":-sum(x*math.log(x) for x in p),"simpson_diversity":1-sum(x*x for x in p),"evenness":(-sum(x*math.log(x) for x in p))/math.log(len(p)) if len(p)>1 else 1}
 elif method in {"conservation_biology","protected_areas"}:
  total=_n(data,"total_habitat_area");protected=_n(data,"protected_area");connected=_n(data,"connected_protected_area",protected);out={"protection_coverage":_ratio(protected,total),"connected_coverage":_ratio(connected,total),"unprotected_area":max(0,total-protected)}
 elif method=="wildlife_management":
  n=_n(data,"population");births=_n(data,"births");deaths=_n(data,"deaths");imm=_n(data,"immigration",0);emi=_n(data,"emigration",0);out={"projected_population":n+births-deaths+imm-emi,"finite_growth_rate":_ratio(n+births-deaths+imm-emi,n),"net_change":births-deaths+imm-emi}
 elif method=="fisheries_management":
  catch=_n(data,"catch");effort=_n(data,"effort");biomass=_n(data,"biomass");msy=_n(data,"msy");out={"catch_per_unit_effort":_ratio(catch,effort),"exploitation_rate":_ratio(catch,biomass),"catch_to_msy":_ratio(catch,msy),"over_msy":catch>msy}
 elif method=="forestry":
  opening=_n(data,"opening_stock");growth=_n(data,"growth");harvest=_n(data,"harvest");mortality=_n(data,"mortality",0);out={"closing_stock":opening+growth-harvest-mortality,"net_annual_increment":growth-mortality,"harvest_to_increment":_ratio(harvest,growth-mortality)}
 elif method in {"agroecology","sustainable_agriculture","organic_farming","permaculture","regenerative_agriculture"}:
  score,parts=_weighted(data);out={"practice_score":score,"contributions":parts,"framework":method}
 elif method=="precision_agriculture":
  baseline=_n(data,"baseline_input");actual=_n(data,"actual_input");area=_n(data,"area");yield0=_n(data,"yield");out={"input_savings":baseline-actual,"input_savings_rate":(baseline-actual)/baseline,"input_intensity":actual/area,"yield_per_input":yield0/actual}
 elif method in {"vertical_farming","hydroponics"}:
  y=_n(data,"annual_yield");foot=_n(data,"footprint_area");water=_n(data,"water_use");energy=_n(data,"energy_use");out={"yield_per_footprint":y/foot,"water_productivity":y/water,"energy_intensity":energy/y}
 elif method=="aquaponics":
  feed=_n(data,"feed_input");fish=_n(data,"fish_output");plants=_n(data,"plant_output");water=_n(data,"water_use");out={"combined_output":fish+plants,"feed_conversion_ratio":feed/fish,"water_productivity":(fish+plants)/water}
 elif method=="urban_agriculture":
  prod=_n(data,"annual_production");area=_n(data,"area");pop=_n(data,"served_population");out={"yield_per_area":prod/area,"food_per_capita":prod/pop}
 elif method=="food_security":
  avail=_n(data,"available_food_kcal");need=_n(data,"required_food_kcal");people=_n(data,"people");days=_n(data,"days");out={"kcal_per_person_day":avail/people/days,"adequacy_ratio":avail/need,"deficit_kcal":max(0,need-avail)}
 elif method=="food_systems":
  prod=_n(data,"production");loss=_n(data,"loss");imports=_n(data,"imports",0);exports=_n(data,"exports",0);out={"net_food_supply":prod-loss+imports-exports,"loss_rate":loss/prod,"import_dependency":imports/(prod+imports)}
 elif method=="sustainable_diets":
  kcal=_n(data,"daily_kcal");ghg=_n(data,"daily_ghg_kg");water=_n(data,"daily_water_l");plant=_n(data,"plant_protein_g");protein=_n(data,"total_protein_g");out={"ghg_per_1000_kcal":ghg/kcal*1000,"water_per_1000_kcal":water/kcal*1000,"plant_protein_share":plant/protein}
 elif method=="food_waste":
  purchased=_n(data,"food_purchased");waste=_n(data,"food_wasted");avoidable=_n(data,"avoidable_waste");out={"waste_rate":waste/purchased,"avoidable_share":avoidable/waste,"consumed":purchased-waste}
 elif method=="environmental_health":
  pop=_n(data,"population");cases=_n(data,"cases");deaths=_n(data,"deaths",0);out={"incidence_per_100k":cases/pop*100000,"mortality_per_100k":deaths/pop*100000,"case_fatality":deaths/cases if cases else 0}
 elif method=="toxicology":
  dose=_n(data,"dose");response=_n(data,"response");control=_n(data,"control_response",0);out={"dose":dose,"excess_response":response-control,"response_per_dose":(response-control)/dose}
 elif method=="risk_assessment":
  hazard=_n(data,"hazard_quotient");slope=_n(data,"cancer_slope_factor",0);dose=_n(data,"lifetime_average_daily_dose",0);out={"noncancer_hazard_index":hazard,"cancer_risk":slope*dose,"noncancer_concern":hazard>1}
 elif method=="exposure_science":
  conc=_n(data,"concentration");intake=_n(data,"intake_rate");freq=_n(data,"frequency");duration=_n(data,"duration");weight=_n(data,"body_weight");avg=_n(data,"averaging_time");out={"average_daily_dose":conc*intake*freq*duration/(weight*avg),"cumulative_intake":conc*intake*freq*duration}
 elif method=="epidemiology":
  a,b,c,d=[_n(data,k) for k in ("exposed_cases","exposed_non_cases","unexposed_cases","unexposed_non_cases")];re=a/(a+b);ru=c/(c+d);out={"risk_exposed":re,"risk_unexposed":ru,"relative_risk":re/ru,"risk_difference":re-ru,"odds_ratio":a*d/(b*c)}
 elif method in {"environmental_justice","indigenous_rights","community_engagement","stakeholder_analysis"}:
  groups=data.get("groups")
  if not isinstance(groups,list) or not groups:raise ValueError("groups required")
  burden=sum(_n(g,"population")*_n(g,"burden") for g in groups)/sum(_n(g,"population") for g in groups);participation=sum(_n(g,"population")*_n(g,"participation",0) for g in groups)/sum(_n(g,"population") for g in groups);out={"population_weighted_burden":burden,"population_weighted_participation":participation,"group_count":len(groups),"framework":method};limits += ["Distribution metrics cannot determine consent, legitimacy, treaty obligations, or rights compliance."]
 elif method in {"environmental_policy","regulation","permitting"}:
  req=data.get("requirements");
  if not isinstance(req,list) or not req:raise ValueError("requirements required")
  applicable=[x for x in req if x.get("applicable",True)];met=[x for x in applicable if x.get("met") is True];out={"applicable_requirements":len(applicable),"met_requirements":len(met),"completion_rate":len(met)/len(applicable) if applicable else 1,"unmet_ids":[x.get("id") for x in applicable if x.get("met") is not True]};limits += ["Checklist status is not a legal interpretation or permit decision."]
 elif method=="environmental_impact_assessment":
  impacts=data.get("impacts");
  if not isinstance(impacts,list) or not impacts:raise ValueError("impacts required")
  scores=[_n(x,"magnitude")*_n(x,"sensitivity")*_n(x,"likelihood") for x in impacts];out={"impact_scores":scores,"aggregate_score":sum(scores),"material_impacts":[impacts[i].get("name") for i,s in enumerate(scores) if s>=_n(data,"materiality_threshold",.5)]}
 elif method=="strategic_environmental_assessment":
  options=data.get("options");
  if not isinstance(options,list) or not options:raise ValueError("options required")
  scored=[{"name":x["name"],"score":sum(map(float,x["criterion_scores"]))/len(x["criterion_scores"])} for x in options];out={"ranked_options":sorted(scored,key=lambda x:x["score"],reverse=True)}
 elif method=="life_cycle_assessment":
  stages=data.get("stages");
  if not isinstance(stages,list) or not stages:raise ValueError("stages required")
  cats={};
  for s in stages:
   for k,v in s.get("impacts",{}).items():cats[k]=cats.get(k,0)+float(v)
  out={"category_totals":cats,"stage_count":len(stages),"functional_unit":data.get("functional_unit")}
 elif method=="carbon_footprinting":
  act=_v(data,"activity_data");fac=_v(data,"emission_factors");out={"co2e":sum(a*b for a,b in zip(act,fac)),"source_contributions":[a*b for a,b in zip(act,fac)]}
 elif method=="water_footprinting":
  blue=_n(data,"blue_water");green=_n(data,"green_water");grey=_n(data,"grey_water");units=_n(data,"production_units");out={"total_water_footprint":blue+green+grey,"water_per_unit":(blue+green+grey)/units,"components":{"blue":blue,"green":green,"grey":grey}}
 elif method=="ecological_footprinting":
  demand=_n(data,"biocapacity_demand");population=_n(data,"population");biocap=_n(data,"available_biocapacity");out={"footprint_per_capita":demand/population,"ecological_deficit":demand-biocap,"earth_equivalents":demand/biocap}
 elif method=="material_flow_analysis":
  inputs=_n(data,"inputs");products=_n(data,"products");waste=_n(data,"waste");exports=_n(data,"exports",0);out={"stock_accumulation":inputs-products-waste-exports,"material_efficiency":products/inputs,"waste_intensity":waste/products}
 elif method=="industrial_ecology":
  waste=_n(data,"waste_output");reused=_n(data,"waste_reused_as_input");virgin=_n(data,"virgin_input");out={"industrial_symbiosis_rate":reused/waste,"secondary_input_share":reused/(reused+virgin),"unrecovered_waste":waste-reused}
 elif method=="cleaner_production":
  base=_n(data,"baseline_waste");new=_n(data,"current_waste");prod=_n(data,"production");out={"waste_prevented":base-new,"prevention_rate":(base-new)/base,"current_waste_intensity":new/prod}
 elif method=="green_chemistry":
  desired=_n(data,"desired_product_mass");reactants=_n(data,"reactant_mass");waste=_n(data,"waste_mass");out={"atom_economy_proxy":desired/reactants,"e_factor":waste/desired,"process_mass_intensity":(reactants+waste)/desired}
 elif method=="green_engineering":
  useful=_n(data,"useful_output");energy=_n(data,"energy_input");material=_n(data,"material_input");out={"energy_efficiency":useful/energy,"material_efficiency":useful/material,"combined_resource_productivity":useful/(energy+material)}
 elif method in {"sustainable_design","biomimicry","cradle_to_cradle","natural_capitalism"}:
  score,parts=_weighted(data);out={"design_score":score,"contributions":parts,"framework":method}
 elif method=="triple_bottom_line":
  people=_n(data,"people_score");planet=_n(data,"planet_score");profit=_n(data,"profit_score");weights=data.get("weights",[1,1,1]);out={"people":people,"planet":planet,"profit":profit,"weighted_score":sum(x*float(w) for x,w in zip([people,planet,profit],weights))/sum(map(float,weights)),"weakest_dimension":["people","planet","profit"][[people,planet,profit].index(min(people,planet,profit))]}
 out["assumptions"]=assumptions;out["method_limits"]=limits
 return {"method":method,"feature_row":ROWS[method],"inputs":data,"output":out}
