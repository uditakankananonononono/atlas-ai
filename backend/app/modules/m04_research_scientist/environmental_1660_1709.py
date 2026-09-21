"""Row-specific, side-effect-free environmental analyses for owner rows 1660-1709."""
from __future__ import annotations
import hashlib,json,math
from typing import Any,Callable

def _inputs(data:dict[str,Any], keys:tuple[str,str,str]):
 if not isinstance(data,dict): raise TypeError("data must be a mapping")
 vals=[]
 for key in keys:
  value=data.get(key)
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0: raise ValueError(f"{key} must be a finite nonnegative number")
  vals.append(float(value))
 if vals[1]==0: raise ValueError(f"{keys[1]} must be positive")
 citations=data.get("citations")
 if not isinstance(citations,list) or not citations or any(not isinstance(x,str) or not x.startswith(("https://","doi:")) for x in citations): raise ValueError("citations must contain source URLs or DOI identifiers")
 return (*vals,citations)

def _result(row:int,name:str,keys:tuple[str,str,str],data:dict[str,Any],metric:str,value:float,unit:str,assumption:str):
 if not math.isfinite(value): raise ValueError("computed result is outside the finite domain")
 canonical=json.dumps({k:data[k] for k in keys}|{"citations":data["citations"]},sort_keys=True,separators=(",",":"))
 return {"feature_row":row,"capability":name.replace("_"," ").title(),"named_analysis":f"analyze_{name}","analysis":{metric:value},"units":{metric:unit},"standards_and_sources":{"citations":data["citations"],"input_sha256":hashlib.sha256(canonical.encode()).hexdigest()},"assumptions":[assumption],"uncertainty":{"status":"not quantified","required_next":"supply measurement distributions or confidence intervals"},"safety_bounds":{"external_effects":False,"decision_status":"screening only; expert and jurisdictional review required"}}

def analyze_bioremediation(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('initial_concentration_mg_l','final_concentration_mg_l','volume_l'))
 value=(a-b)*c/1000
 return _result(1660,'bioremediation',('initial_concentration_mg_l','final_concentration_mg_l','volume_l'),data,'contaminant_removed_g',value,'contaminant removed g',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_ecosystem_services(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('service_quantity','unit_value_usd','confidence_fraction'))
 value=a*b*c
 return _result(1661,'ecosystem_services',('service_quantity','unit_value_usd','confidence_fraction'),data,'confidence_adjusted_value_usd',value,'confidence adjusted value usd',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_biodiversity(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('species_count','individual_count','evenness_fraction'))
 value=a*b*c
 return _result(1662,'biodiversity',('species_count','individual_count','evenness_fraction'),data,'biodiversity_composite',value,'biodiversity composite',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_conservation_biology(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('occupied_patches','total_patches','habitat_quality_fraction'))
 value=(a/b)*c
 return _result(1663,'conservation_biology',('occupied_patches','total_patches','habitat_quality_fraction'),data,'conservation_viability_index',value,'conservation viability index',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_protected_areas(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('protected_area_km2','ecoregion_area_km2','management_effectiveness_fraction'))
 value=(a/b)*c
 return _result(1664,'protected_areas',('protected_area_km2','ecoregion_area_km2','management_effectiveness_fraction'),data,'effective_protection_fraction',value,'effective protection fraction',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_wildlife_management(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('population_count','carrying_capacity','annual_growth_fraction'))
 value=a+(a*c)*(1-a/b)
 return _result(1665,'wildlife_management',('population_count','carrying_capacity','annual_growth_fraction'),data,'projected_population',value,'projected population',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_fisheries_management(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('biomass_t','carrying_capacity_t','intrinsic_growth_per_year'))
 value=c*a*(1-a/b)
 return _result(1666,'fisheries_management',('biomass_t','carrying_capacity_t','intrinsic_growth_per_year'),data,'surplus_production_t_per_year',value,'surplus production t per year',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_forestry(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('area_ha','annual_increment_m3_ha','harvest_m3'))
 value=a*b-c
 return _result(1667,'forestry',('area_ha','annual_increment_m3_ha','harvest_m3'),data,'net_stock_change_m3_year',value,'net stock change m3 year',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_agroecology(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('crop_yield_t_ha','input_energy_gj_ha','diversity_factor'))
 value=a*c/b
 return _result(1668,'agroecology',('crop_yield_t_ha','input_energy_gj_ha','diversity_factor'),data,'yield_energy_diversity_index',value,'yield energy diversity index',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_sustainable_agriculture(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('yield_t','water_m3','soil_retention_fraction'))
 value=a*c/b
 return _result(1669,'sustainable_agriculture',('yield_t','water_m3','soil_retention_fraction'),data,'water_adjusted_yield_t_m3',value,'water adjusted yield t m3',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_organic_farming(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('organic_output_t','total_output_t','conversion_confidence'))
 value=(a/b)*c
 return _result(1670,'organic_farming',('organic_output_t','total_output_t','conversion_confidence'),data,'verified_organic_share',value,'verified organic share',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_permaculture(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('useful_outputs','external_inputs','recycling_fraction'))
 value=a*(1+c)/b
 return _result(1671,'permaculture',('useful_outputs','external_inputs','recycling_fraction'),data,'system_integration_index',value,'system integration index',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_regenerative_agriculture(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('final_soil_carbon_t','initial_soil_carbon_t','area_ha'))
 value=(a-b)/c
 return _result(1672,'regenerative_agriculture',('final_soil_carbon_t','initial_soil_carbon_t','area_ha'),data,'soil_carbon_gain_t_ha',value,'soil carbon gain t ha',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_precision_agriculture(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('baseline_input_kg','optimized_input_kg','area_ha'))
 value=(a-b)/c
 return _result(1673,'precision_agriculture',('baseline_input_kg','optimized_input_kg','area_ha'),data,'input_saved_kg_ha',value,'input saved kg ha',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_vertical_farming(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('annual_output_kg','floor_area_m2','stacking_levels'))
 value=a/(b*c)
 return _result(1674,'vertical_farming',('annual_output_kg','floor_area_m2','stacking_levels'),data,'output_kg_m2_level',value,'output kg m2 level',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_aquaponics(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('fish_output_kg','plant_output_kg','water_m3'))
 value=(a+b)/c
 return _result(1675,'aquaponics',('fish_output_kg','plant_output_kg','water_m3'),data,'combined_output_kg_m3',value,'combined output kg m3',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_hydroponics(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('crop_output_kg','nutrient_solution_m3','recirculation_fraction'))
 value=a*(1+c)/b
 return _result(1676,'hydroponics',('crop_output_kg','nutrient_solution_m3','recirculation_fraction'),data,'recirculation_adjusted_productivity',value,'recirculation adjusted productivity',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_urban_agriculture(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('output_kg','site_area_m2','local_consumption_fraction'))
 value=a*c/b
 return _result(1677,'urban_agriculture',('output_kg','site_area_m2','local_consumption_fraction'),data,'local_output_kg_m2',value,'local output kg m2',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_food_security(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('available_food_kcal','population','days'))
 value=a/(b*c)
 return _result(1678,'food_security',('available_food_kcal','population','days'),data,'kcal_person_day',value,'kcal person day',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_food_systems(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('edible_output_t','primary_input_t','distribution_efficiency'))
 value=(a/b)*c
 return _result(1679,'food_systems',('edible_output_t','primary_input_t','distribution_efficiency'),data,'system_efficiency',value,'system efficiency',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_sustainable_diets(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('baseline_kgco2e','diet_kgco2e','nutrition_adequacy'))
 value=(a-b)*c
 return _result(1680,'sustainable_diets',('baseline_kgco2e','diet_kgco2e','nutrition_adequacy'),data,'adequacy_adjusted_kgco2e_saved',value,'adequacy adjusted kgco2e saved',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_food_waste(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('food_supplied_kg','food_wasted_kg','recovery_fraction'))
 value=b/a*(1-c)
 return _result(1681,'food_waste',('food_supplied_kg','food_wasted_kg','recovery_fraction'),data,'unrecovered_waste_fraction',value,'unrecovered waste fraction',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_environmental_health(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('exposed_population','exposure_fraction','disease_rate'))
 value=a*b*c
 return _result(1682,'environmental_health',('exposed_population','exposure_fraction','disease_rate'),data,'attributable_cases',value,'attributable cases',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_toxicology(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('dose_mg_kg_day','reference_dose_mg_kg_day','uncertainty_factor'))
 value=(a/b)*c
 return _result(1683,'toxicology',('dose_mg_kg_day','reference_dose_mg_kg_day','uncertainty_factor'),data,'hazard_quotient_adjusted',value,'hazard quotient adjusted',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_risk_assessment(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('probability','consequence_usd','confidence_fraction'))
 value=a*b*c
 return _result(1684,'risk_assessment',('probability','consequence_usd','confidence_fraction'),data,'expected_loss_usd',value,'expected loss usd',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_exposure_science(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('concentration_mg_m3','inhalation_m3_day','body_mass_kg'))
 value=a*b/c
 return _result(1685,'exposure_science',('concentration_mg_m3','inhalation_m3_day','body_mass_kg'),data,'dose_mg_kg_day',value,'dose mg kg day',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_epidemiology(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('cases','population','person_years'))
 value=(a/b)*100000/c
 return _result(1686,'epidemiology',('cases','population','person_years'),data,'incidence_per_100k_person_year',value,'incidence per 100k person year',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_environmental_justice(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('burden_index','vulnerable_population_fraction','representation_fraction'))
 value=a*b*(1-c)
 return _result(1687,'environmental_justice',('burden_index','vulnerable_population_fraction','representation_fraction'),data,'inequity_priority_score',value,'inequity priority score',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_indigenous_rights(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('affected_rights','rights_reviewed','consent_evidence_fraction'))
 value=(a/b)*c
 return _result(1688,'indigenous_rights',('affected_rights','rights_reviewed','consent_evidence_fraction'),data,'rights_due_diligence_coverage',value,'rights due diligence coverage',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_community_engagement(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('participants','eligible_population','retention_fraction'))
 value=(a/b)*c
 return _result(1689,'community_engagement',('participants','eligible_population','retention_fraction'),data,'retained_participation_fraction',value,'retained participation fraction',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_stakeholder_analysis(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('influence_score','interest_score','evidence_confidence'))
 value=a*b*c
 return _result(1690,'stakeholder_analysis',('influence_score','interest_score','evidence_confidence'),data,'stakeholder_priority_score',value,'stakeholder priority score',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_environmental_policy(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('target_reduction_t','achieved_reduction_t','verification_fraction'))
 value=(b/a)*c
 return _result(1691,'environmental_policy',('target_reduction_t','achieved_reduction_t','verification_fraction'),data,'verified_target_attainment',value,'verified target attainment',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_regulation(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('requirements_met','requirements_total','evidence_confidence'))
 value=(a/b)*c
 return _result(1692,'regulation',('requirements_met','requirements_total','evidence_confidence'),data,'compliance_evidence_coverage',value,'compliance evidence coverage',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_permitting(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('conditions_satisfied','conditions_total','documentation_fraction'))
 value=(a/b)*c
 return _result(1693,'permitting',('conditions_satisfied','conditions_total','documentation_fraction'),data,'permit_readiness_fraction',value,'permit readiness fraction',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_environmental_impact_assessment(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('baseline_impact','mitigated_impact','mitigation_confidence'))
 value=(a-b)*c
 return _result(1694,'environmental_impact_assessment',('baseline_impact','mitigated_impact','mitigation_confidence'),data,'confidence_adjusted_impact_reduction',value,'confidence adjusted impact reduction',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_strategic_environmental_assessment(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('alternatives_assessed','material_alternatives','evidence_coverage'))
 value=(a/b)*c
 return _result(1695,'strategic_environmental_assessment',('alternatives_assessed','material_alternatives','evidence_coverage'),data,'strategic_coverage_fraction',value,'strategic coverage fraction',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_life_cycle_assessment(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('activity_quantity','emission_factor_kgco2e','allocation_fraction'))
 value=a*b*c
 return _result(1696,'life_cycle_assessment',('activity_quantity','emission_factor_kgco2e','allocation_fraction'),data,'allocated_kgco2e',value,'allocated kgco2e',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_carbon_footprinting(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('scope1_tco2e','scope2_tco2e','scope3_tco2e'))
 value=a+b+c
 return _result(1697,'carbon_footprinting',('scope1_tco2e','scope2_tco2e','scope3_tco2e'),data,'total_tco2e',value,'total tco2e',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_water_footprinting(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('blue_water_m3','green_water_m3','grey_water_m3'))
 value=a+b+c
 return _result(1698,'water_footprinting',('blue_water_m3','green_water_m3','grey_water_m3'),data,'total_water_footprint_m3',value,'total water footprint m3',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_ecological_footprinting(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('consumption_gha','biocapacity_gha','population'))
 value=((a-b)/c)
 return _result(1699,'ecological_footprinting',('consumption_gha','biocapacity_gha','population'),data,'ecological_deficit_gha_person',value,'ecological deficit gha person',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_material_flow_analysis(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('domestic_extraction_t','imports_t','exports_t'))
 value=a+b-c
 return _result(1700,'material_flow_analysis',('domestic_extraction_t','imports_t','exports_t'),data,'domestic_material_consumption_t',value,'domestic material consumption t',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_industrial_ecology(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('waste_output_t','byproduct_reused_t','virgin_input_t'))
 value=b/(a+c)
 return _result(1701,'industrial_ecology',('waste_output_t','byproduct_reused_t','virgin_input_t'),data,'industrial_symbiosis_ratio',value,'industrial symbiosis ratio',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_cleaner_production(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('baseline_waste_t','current_waste_t','output_t'))
 value=(a-b)/c
 return _result(1702,'cleaner_production',('baseline_waste_t','current_waste_t','output_t'),data,'waste_avoided_t_per_output_t',value,'waste avoided t per output t',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_green_chemistry(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('product_mass_kg','reactant_mass_kg','hazard_weight'))
 value=a/b*(1-c)
 return _result(1703,'green_chemistry',('product_mass_kg','reactant_mass_kg','hazard_weight'),data,'hazard_adjusted_atom_economy',value,'hazard adjusted atom economy',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_green_engineering(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('service_output','energy_input_mj','safety_factor'))
 value=a*c/b
 return _result(1704,'green_engineering',('service_output','energy_input_mj','safety_factor'),data,'safe_service_per_mj',value,'safe service per mj',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_sustainable_design(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('functional_life_years','embodied_kgco2e','recyclability_fraction'))
 value=a*(1+c)/b
 return _result(1705,'sustainable_design',('functional_life_years','embodied_kgco2e','recyclability_fraction'),data,'circular_service_years_per_kgco2e',value,'circular service years per kgco2e',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_biomimicry(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('functions_matched','functions_required','evidence_confidence'))
 value=(a/b)*c
 return _result(1706,'biomimicry',('functions_matched','functions_required','evidence_confidence'),data,'validated_function_match',value,'validated function match',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_cradle_to_cradle(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('recyclable_mass_kg','total_mass_kg','material_health_fraction'))
 value=(a/b)*c
 return _result(1707,'cradle_to_cradle',('recyclable_mass_kg','total_mass_kg','material_health_fraction'),data,'safe_circular_mass_fraction',value,'safe circular mass fraction',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_natural_capitalism(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('resource_output','resource_input','natural_capital_retention'))
 value=a*c/b
 return _result(1708,'natural_capitalism',('resource_output','resource_input','natural_capital_retention'),data,'retention_adjusted_productivity',value,'retention adjusted productivity',"Inputs share the stated boundary, period, and measurement basis.")

def analyze_triple_bottom_line(data:dict[str,Any])->dict[str,Any]:
 a,b,c,citations=_inputs(data,('people_score','planet_score','profit_score'))
 value=(a*b*c)**(1/3)
 return _result(1709,'triple_bottom_line',('people_score','planet_score','profit_score'),data,'balanced_tbl_score',value,'balanced tbl score',"Inputs share the stated boundary, period, and measurement basis.")

ANALYSES:dict[int,Callable[[dict[str,Any]],dict[str,Any]]]={
 1660:analyze_bioremediation,
 1661:analyze_ecosystem_services,
 1662:analyze_biodiversity,
 1663:analyze_conservation_biology,
 1664:analyze_protected_areas,
 1665:analyze_wildlife_management,
 1666:analyze_fisheries_management,
 1667:analyze_forestry,
 1668:analyze_agroecology,
 1669:analyze_sustainable_agriculture,
 1670:analyze_organic_farming,
 1671:analyze_permaculture,
 1672:analyze_regenerative_agriculture,
 1673:analyze_precision_agriculture,
 1674:analyze_vertical_farming,
 1675:analyze_aquaponics,
 1676:analyze_hydroponics,
 1677:analyze_urban_agriculture,
 1678:analyze_food_security,
 1679:analyze_food_systems,
 1680:analyze_sustainable_diets,
 1681:analyze_food_waste,
 1682:analyze_environmental_health,
 1683:analyze_toxicology,
 1684:analyze_risk_assessment,
 1685:analyze_exposure_science,
 1686:analyze_epidemiology,
 1687:analyze_environmental_justice,
 1688:analyze_indigenous_rights,
 1689:analyze_community_engagement,
 1690:analyze_stakeholder_analysis,
 1691:analyze_environmental_policy,
 1692:analyze_regulation,
 1693:analyze_permitting,
 1694:analyze_environmental_impact_assessment,
 1695:analyze_strategic_environmental_assessment,
 1696:analyze_life_cycle_assessment,
 1697:analyze_carbon_footprinting,
 1698:analyze_water_footprinting,
 1699:analyze_ecological_footprinting,
 1700:analyze_material_flow_analysis,
 1701:analyze_industrial_ecology,
 1702:analyze_cleaner_production,
 1703:analyze_green_chemistry,
 1704:analyze_green_engineering,
 1705:analyze_sustainable_design,
 1706:analyze_biomimicry,
 1707:analyze_cradle_to_cradle,
 1708:analyze_natural_capitalism,
 1709:analyze_triple_bottom_line,
}
def execute_environmental_row(row_id:int,data:dict[str,Any])->dict[str,Any]:
 try: fn=ANALYSES[row_id]
 except KeyError as exc: raise ValueError("row_id must be 1660..1709") from exc
 return fn(data)

# Compatibility for the earlier method-addressed route; still dispatches only to
# the row-specific named computations above.
ROWS={fn.__name__.removeprefix('analyze_'):row for row,fn in ANALYSES.items()}
def run(method:str,data:dict[str,Any],params:dict[str,Any]|None=None,seed:int=0)->dict[str,Any]:
    if params:
        data={**data,**params}
    try: row=ROWS[method]
    except KeyError as exc: raise ValueError(f'unsupported environmental method {method}') from exc
    # Preserve the original method-addressed contract while the row-addressed
    # route exposes the stricter cited screening computations.
    if "citations" not in data:
        from .environmental_1660_1709_legacy import run as legacy_run
        return legacy_run(method,data)
    return execute_environmental_row(row,data)
