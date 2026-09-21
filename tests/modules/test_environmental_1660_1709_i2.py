import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m04_research_scientist.environmental_1660_1709 import *
C=["https://example.org/source"]

def test_row_1660_bioremediation_perturbs_domain_input_and_rejects_invalid_domain():
 d={'initial_concentration_mg_l':10.0,'final_concentration_mg_l':5.0,'volume_l':0.5,"citations":C}
 first=analyze_bioremediation(d)
 changed=analyze_bioremediation(d|{'initial_concentration_mg_l':20.0})
 assert first["feature_row"]==1660 and first["named_analysis"]=="analyze_bioremediation"
 assert first["analysis"]['contaminant_removed_g'] != changed["analysis"]['contaminant_removed_g']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_bioremediation(d|{'initial_concentration_mg_l':-1})

def test_row_1661_ecosystem_services_perturbs_domain_input_and_rejects_invalid_domain():
 d={'service_quantity':10.0,'unit_value_usd':5.0,'confidence_fraction':0.5,"citations":C}
 first=analyze_ecosystem_services(d)
 changed=analyze_ecosystem_services(d|{'service_quantity':20.0})
 assert first["feature_row"]==1661 and first["named_analysis"]=="analyze_ecosystem_services"
 assert first["analysis"]['confidence_adjusted_value_usd'] != changed["analysis"]['confidence_adjusted_value_usd']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_ecosystem_services(d|{'service_quantity':-1})

def test_row_1662_biodiversity_perturbs_domain_input_and_rejects_invalid_domain():
 d={'species_count':10.0,'individual_count':5.0,'evenness_fraction':0.5,"citations":C}
 first=analyze_biodiversity(d)
 changed=analyze_biodiversity(d|{'species_count':20.0})
 assert first["feature_row"]==1662 and first["named_analysis"]=="analyze_biodiversity"
 assert first["analysis"]['biodiversity_composite'] != changed["analysis"]['biodiversity_composite']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_biodiversity(d|{'species_count':-1})

def test_row_1663_conservation_biology_perturbs_domain_input_and_rejects_invalid_domain():
 d={'occupied_patches':10.0,'total_patches':5.0,'habitat_quality_fraction':0.5,"citations":C}
 first=analyze_conservation_biology(d)
 changed=analyze_conservation_biology(d|{'occupied_patches':20.0})
 assert first["feature_row"]==1663 and first["named_analysis"]=="analyze_conservation_biology"
 assert first["analysis"]['conservation_viability_index'] != changed["analysis"]['conservation_viability_index']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_conservation_biology(d|{'occupied_patches':-1})

def test_row_1664_protected_areas_perturbs_domain_input_and_rejects_invalid_domain():
 d={'protected_area_km2':10.0,'ecoregion_area_km2':5.0,'management_effectiveness_fraction':0.5,"citations":C}
 first=analyze_protected_areas(d)
 changed=analyze_protected_areas(d|{'protected_area_km2':20.0})
 assert first["feature_row"]==1664 and first["named_analysis"]=="analyze_protected_areas"
 assert first["analysis"]['effective_protection_fraction'] != changed["analysis"]['effective_protection_fraction']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_protected_areas(d|{'protected_area_km2':-1})

def test_row_1665_wildlife_management_perturbs_domain_input_and_rejects_invalid_domain():
 d={'population_count':10.0,'carrying_capacity':5.0,'annual_growth_fraction':0.5,"citations":C}
 first=analyze_wildlife_management(d)
 changed=analyze_wildlife_management(d|{'population_count':20.0})
 assert first["feature_row"]==1665 and first["named_analysis"]=="analyze_wildlife_management"
 assert first["analysis"]['projected_population'] != changed["analysis"]['projected_population']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_wildlife_management(d|{'population_count':-1})

def test_row_1666_fisheries_management_perturbs_domain_input_and_rejects_invalid_domain():
 d={'biomass_t':10.0,'carrying_capacity_t':5.0,'intrinsic_growth_per_year':0.5,"citations":C}
 first=analyze_fisheries_management(d)
 changed=analyze_fisheries_management(d|{'biomass_t':20.0})
 assert first["feature_row"]==1666 and first["named_analysis"]=="analyze_fisheries_management"
 assert first["analysis"]['surplus_production_t_per_year'] != changed["analysis"]['surplus_production_t_per_year']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_fisheries_management(d|{'biomass_t':-1})

def test_row_1667_forestry_perturbs_domain_input_and_rejects_invalid_domain():
 d={'area_ha':10.0,'annual_increment_m3_ha':5.0,'harvest_m3':0.5,"citations":C}
 first=analyze_forestry(d)
 changed=analyze_forestry(d|{'area_ha':20.0})
 assert first["feature_row"]==1667 and first["named_analysis"]=="analyze_forestry"
 assert first["analysis"]['net_stock_change_m3_year'] != changed["analysis"]['net_stock_change_m3_year']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_forestry(d|{'area_ha':-1})

def test_row_1668_agroecology_perturbs_domain_input_and_rejects_invalid_domain():
 d={'crop_yield_t_ha':10.0,'input_energy_gj_ha':5.0,'diversity_factor':0.5,"citations":C}
 first=analyze_agroecology(d)
 changed=analyze_agroecology(d|{'crop_yield_t_ha':20.0})
 assert first["feature_row"]==1668 and first["named_analysis"]=="analyze_agroecology"
 assert first["analysis"]['yield_energy_diversity_index'] != changed["analysis"]['yield_energy_diversity_index']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_agroecology(d|{'crop_yield_t_ha':-1})

def test_row_1669_sustainable_agriculture_perturbs_domain_input_and_rejects_invalid_domain():
 d={'yield_t':10.0,'water_m3':5.0,'soil_retention_fraction':0.5,"citations":C}
 first=analyze_sustainable_agriculture(d)
 changed=analyze_sustainable_agriculture(d|{'yield_t':20.0})
 assert first["feature_row"]==1669 and first["named_analysis"]=="analyze_sustainable_agriculture"
 assert first["analysis"]['water_adjusted_yield_t_m3'] != changed["analysis"]['water_adjusted_yield_t_m3']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_sustainable_agriculture(d|{'yield_t':-1})

def test_row_1670_organic_farming_perturbs_domain_input_and_rejects_invalid_domain():
 d={'organic_output_t':10.0,'total_output_t':5.0,'conversion_confidence':0.5,"citations":C}
 first=analyze_organic_farming(d)
 changed=analyze_organic_farming(d|{'organic_output_t':20.0})
 assert first["feature_row"]==1670 and first["named_analysis"]=="analyze_organic_farming"
 assert first["analysis"]['verified_organic_share'] != changed["analysis"]['verified_organic_share']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_organic_farming(d|{'organic_output_t':-1})

def test_row_1671_permaculture_perturbs_domain_input_and_rejects_invalid_domain():
 d={'useful_outputs':10.0,'external_inputs':5.0,'recycling_fraction':0.5,"citations":C}
 first=analyze_permaculture(d)
 changed=analyze_permaculture(d|{'useful_outputs':20.0})
 assert first["feature_row"]==1671 and first["named_analysis"]=="analyze_permaculture"
 assert first["analysis"]['system_integration_index'] != changed["analysis"]['system_integration_index']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_permaculture(d|{'useful_outputs':-1})

def test_row_1672_regenerative_agriculture_perturbs_domain_input_and_rejects_invalid_domain():
 d={'final_soil_carbon_t':10.0,'initial_soil_carbon_t':5.0,'area_ha':0.5,"citations":C}
 first=analyze_regenerative_agriculture(d)
 changed=analyze_regenerative_agriculture(d|{'final_soil_carbon_t':20.0})
 assert first["feature_row"]==1672 and first["named_analysis"]=="analyze_regenerative_agriculture"
 assert first["analysis"]['soil_carbon_gain_t_ha'] != changed["analysis"]['soil_carbon_gain_t_ha']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_regenerative_agriculture(d|{'final_soil_carbon_t':-1})

def test_row_1673_precision_agriculture_perturbs_domain_input_and_rejects_invalid_domain():
 d={'baseline_input_kg':10.0,'optimized_input_kg':5.0,'area_ha':0.5,"citations":C}
 first=analyze_precision_agriculture(d)
 changed=analyze_precision_agriculture(d|{'baseline_input_kg':20.0})
 assert first["feature_row"]==1673 and first["named_analysis"]=="analyze_precision_agriculture"
 assert first["analysis"]['input_saved_kg_ha'] != changed["analysis"]['input_saved_kg_ha']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_precision_agriculture(d|{'baseline_input_kg':-1})

def test_row_1674_vertical_farming_perturbs_domain_input_and_rejects_invalid_domain():
 d={'annual_output_kg':10.0,'floor_area_m2':5.0,'stacking_levels':0.5,"citations":C}
 first=analyze_vertical_farming(d)
 changed=analyze_vertical_farming(d|{'annual_output_kg':20.0})
 assert first["feature_row"]==1674 and first["named_analysis"]=="analyze_vertical_farming"
 assert first["analysis"]['output_kg_m2_level'] != changed["analysis"]['output_kg_m2_level']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_vertical_farming(d|{'annual_output_kg':-1})

def test_row_1675_aquaponics_perturbs_domain_input_and_rejects_invalid_domain():
 d={'fish_output_kg':10.0,'plant_output_kg':5.0,'water_m3':0.5,"citations":C}
 first=analyze_aquaponics(d)
 changed=analyze_aquaponics(d|{'fish_output_kg':20.0})
 assert first["feature_row"]==1675 and first["named_analysis"]=="analyze_aquaponics"
 assert first["analysis"]['combined_output_kg_m3'] != changed["analysis"]['combined_output_kg_m3']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_aquaponics(d|{'fish_output_kg':-1})

def test_row_1676_hydroponics_perturbs_domain_input_and_rejects_invalid_domain():
 d={'crop_output_kg':10.0,'nutrient_solution_m3':5.0,'recirculation_fraction':0.5,"citations":C}
 first=analyze_hydroponics(d)
 changed=analyze_hydroponics(d|{'crop_output_kg':20.0})
 assert first["feature_row"]==1676 and first["named_analysis"]=="analyze_hydroponics"
 assert first["analysis"]['recirculation_adjusted_productivity'] != changed["analysis"]['recirculation_adjusted_productivity']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_hydroponics(d|{'crop_output_kg':-1})

def test_row_1677_urban_agriculture_perturbs_domain_input_and_rejects_invalid_domain():
 d={'output_kg':10.0,'site_area_m2':5.0,'local_consumption_fraction':0.5,"citations":C}
 first=analyze_urban_agriculture(d)
 changed=analyze_urban_agriculture(d|{'output_kg':20.0})
 assert first["feature_row"]==1677 and first["named_analysis"]=="analyze_urban_agriculture"
 assert first["analysis"]['local_output_kg_m2'] != changed["analysis"]['local_output_kg_m2']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_urban_agriculture(d|{'output_kg':-1})

def test_row_1678_food_security_perturbs_domain_input_and_rejects_invalid_domain():
 d={'available_food_kcal':10.0,'population':5.0,'days':0.5,"citations":C}
 first=analyze_food_security(d)
 changed=analyze_food_security(d|{'available_food_kcal':20.0})
 assert first["feature_row"]==1678 and first["named_analysis"]=="analyze_food_security"
 assert first["analysis"]['kcal_person_day'] != changed["analysis"]['kcal_person_day']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_food_security(d|{'available_food_kcal':-1})

def test_row_1679_food_systems_perturbs_domain_input_and_rejects_invalid_domain():
 d={'edible_output_t':10.0,'primary_input_t':5.0,'distribution_efficiency':0.5,"citations":C}
 first=analyze_food_systems(d)
 changed=analyze_food_systems(d|{'edible_output_t':20.0})
 assert first["feature_row"]==1679 and first["named_analysis"]=="analyze_food_systems"
 assert first["analysis"]['system_efficiency'] != changed["analysis"]['system_efficiency']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_food_systems(d|{'edible_output_t':-1})

def test_row_1680_sustainable_diets_perturbs_domain_input_and_rejects_invalid_domain():
 d={'baseline_kgco2e':10.0,'diet_kgco2e':5.0,'nutrition_adequacy':0.5,"citations":C}
 first=analyze_sustainable_diets(d)
 changed=analyze_sustainable_diets(d|{'baseline_kgco2e':20.0})
 assert first["feature_row"]==1680 and first["named_analysis"]=="analyze_sustainable_diets"
 assert first["analysis"]['adequacy_adjusted_kgco2e_saved'] != changed["analysis"]['adequacy_adjusted_kgco2e_saved']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_sustainable_diets(d|{'baseline_kgco2e':-1})

def test_row_1681_food_waste_perturbs_domain_input_and_rejects_invalid_domain():
 d={'food_supplied_kg':10.0,'food_wasted_kg':5.0,'recovery_fraction':0.5,"citations":C}
 first=analyze_food_waste(d)
 changed=analyze_food_waste(d|{'food_supplied_kg':20.0})
 assert first["feature_row"]==1681 and first["named_analysis"]=="analyze_food_waste"
 assert first["analysis"]['unrecovered_waste_fraction'] != changed["analysis"]['unrecovered_waste_fraction']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_food_waste(d|{'food_supplied_kg':-1})

def test_row_1682_environmental_health_perturbs_domain_input_and_rejects_invalid_domain():
 d={'exposed_population':10.0,'exposure_fraction':5.0,'disease_rate':0.5,"citations":C}
 first=analyze_environmental_health(d)
 changed=analyze_environmental_health(d|{'exposed_population':20.0})
 assert first["feature_row"]==1682 and first["named_analysis"]=="analyze_environmental_health"
 assert first["analysis"]['attributable_cases'] != changed["analysis"]['attributable_cases']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_environmental_health(d|{'exposed_population':-1})

def test_row_1683_toxicology_perturbs_domain_input_and_rejects_invalid_domain():
 d={'dose_mg_kg_day':10.0,'reference_dose_mg_kg_day':5.0,'uncertainty_factor':0.5,"citations":C}
 first=analyze_toxicology(d)
 changed=analyze_toxicology(d|{'dose_mg_kg_day':20.0})
 assert first["feature_row"]==1683 and first["named_analysis"]=="analyze_toxicology"
 assert first["analysis"]['hazard_quotient_adjusted'] != changed["analysis"]['hazard_quotient_adjusted']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_toxicology(d|{'dose_mg_kg_day':-1})

def test_row_1684_risk_assessment_perturbs_domain_input_and_rejects_invalid_domain():
 d={'probability':10.0,'consequence_usd':5.0,'confidence_fraction':0.5,"citations":C}
 first=analyze_risk_assessment(d)
 changed=analyze_risk_assessment(d|{'probability':20.0})
 assert first["feature_row"]==1684 and first["named_analysis"]=="analyze_risk_assessment"
 assert first["analysis"]['expected_loss_usd'] != changed["analysis"]['expected_loss_usd']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_risk_assessment(d|{'probability':-1})

def test_row_1685_exposure_science_perturbs_domain_input_and_rejects_invalid_domain():
 d={'concentration_mg_m3':10.0,'inhalation_m3_day':5.0,'body_mass_kg':0.5,"citations":C}
 first=analyze_exposure_science(d)
 changed=analyze_exposure_science(d|{'concentration_mg_m3':20.0})
 assert first["feature_row"]==1685 and first["named_analysis"]=="analyze_exposure_science"
 assert first["analysis"]['dose_mg_kg_day'] != changed["analysis"]['dose_mg_kg_day']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_exposure_science(d|{'concentration_mg_m3':-1})

def test_row_1686_epidemiology_perturbs_domain_input_and_rejects_invalid_domain():
 d={'cases':10.0,'population':5.0,'person_years':0.5,"citations":C}
 first=analyze_epidemiology(d)
 changed=analyze_epidemiology(d|{'cases':20.0})
 assert first["feature_row"]==1686 and first["named_analysis"]=="analyze_epidemiology"
 assert first["analysis"]['incidence_per_100k_person_year'] != changed["analysis"]['incidence_per_100k_person_year']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_epidemiology(d|{'cases':-1})

def test_row_1687_environmental_justice_perturbs_domain_input_and_rejects_invalid_domain():
 d={'burden_index':10.0,'vulnerable_population_fraction':5.0,'representation_fraction':0.5,"citations":C}
 first=analyze_environmental_justice(d)
 changed=analyze_environmental_justice(d|{'burden_index':20.0})
 assert first["feature_row"]==1687 and first["named_analysis"]=="analyze_environmental_justice"
 assert first["analysis"]['inequity_priority_score'] != changed["analysis"]['inequity_priority_score']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_environmental_justice(d|{'burden_index':-1})

def test_row_1688_indigenous_rights_perturbs_domain_input_and_rejects_invalid_domain():
 d={'affected_rights':10.0,'rights_reviewed':5.0,'consent_evidence_fraction':0.5,"citations":C}
 first=analyze_indigenous_rights(d)
 changed=analyze_indigenous_rights(d|{'affected_rights':20.0})
 assert first["feature_row"]==1688 and first["named_analysis"]=="analyze_indigenous_rights"
 assert first["analysis"]['rights_due_diligence_coverage'] != changed["analysis"]['rights_due_diligence_coverage']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_indigenous_rights(d|{'affected_rights':-1})

def test_row_1689_community_engagement_perturbs_domain_input_and_rejects_invalid_domain():
 d={'participants':10.0,'eligible_population':5.0,'retention_fraction':0.5,"citations":C}
 first=analyze_community_engagement(d)
 changed=analyze_community_engagement(d|{'participants':20.0})
 assert first["feature_row"]==1689 and first["named_analysis"]=="analyze_community_engagement"
 assert first["analysis"]['retained_participation_fraction'] != changed["analysis"]['retained_participation_fraction']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_community_engagement(d|{'participants':-1})

def test_row_1690_stakeholder_analysis_perturbs_domain_input_and_rejects_invalid_domain():
 d={'influence_score':10.0,'interest_score':5.0,'evidence_confidence':0.5,"citations":C}
 first=analyze_stakeholder_analysis(d)
 changed=analyze_stakeholder_analysis(d|{'influence_score':20.0})
 assert first["feature_row"]==1690 and first["named_analysis"]=="analyze_stakeholder_analysis"
 assert first["analysis"]['stakeholder_priority_score'] != changed["analysis"]['stakeholder_priority_score']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_stakeholder_analysis(d|{'influence_score':-1})

def test_row_1691_environmental_policy_perturbs_domain_input_and_rejects_invalid_domain():
 d={'target_reduction_t':10.0,'achieved_reduction_t':5.0,'verification_fraction':0.5,"citations":C}
 first=analyze_environmental_policy(d)
 changed=analyze_environmental_policy(d|{'target_reduction_t':20.0})
 assert first["feature_row"]==1691 and first["named_analysis"]=="analyze_environmental_policy"
 assert first["analysis"]['verified_target_attainment'] != changed["analysis"]['verified_target_attainment']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_environmental_policy(d|{'target_reduction_t':-1})

def test_row_1692_regulation_perturbs_domain_input_and_rejects_invalid_domain():
 d={'requirements_met':10.0,'requirements_total':5.0,'evidence_confidence':0.5,"citations":C}
 first=analyze_regulation(d)
 changed=analyze_regulation(d|{'requirements_met':20.0})
 assert first["feature_row"]==1692 and first["named_analysis"]=="analyze_regulation"
 assert first["analysis"]['compliance_evidence_coverage'] != changed["analysis"]['compliance_evidence_coverage']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_regulation(d|{'requirements_met':-1})

def test_row_1693_permitting_perturbs_domain_input_and_rejects_invalid_domain():
 d={'conditions_satisfied':10.0,'conditions_total':5.0,'documentation_fraction':0.5,"citations":C}
 first=analyze_permitting(d)
 changed=analyze_permitting(d|{'conditions_satisfied':20.0})
 assert first["feature_row"]==1693 and first["named_analysis"]=="analyze_permitting"
 assert first["analysis"]['permit_readiness_fraction'] != changed["analysis"]['permit_readiness_fraction']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_permitting(d|{'conditions_satisfied':-1})

def test_row_1694_environmental_impact_assessment_perturbs_domain_input_and_rejects_invalid_domain():
 d={'baseline_impact':10.0,'mitigated_impact':5.0,'mitigation_confidence':0.5,"citations":C}
 first=analyze_environmental_impact_assessment(d)
 changed=analyze_environmental_impact_assessment(d|{'baseline_impact':20.0})
 assert first["feature_row"]==1694 and first["named_analysis"]=="analyze_environmental_impact_assessment"
 assert first["analysis"]['confidence_adjusted_impact_reduction'] != changed["analysis"]['confidence_adjusted_impact_reduction']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_environmental_impact_assessment(d|{'baseline_impact':-1})

def test_row_1695_strategic_environmental_assessment_perturbs_domain_input_and_rejects_invalid_domain():
 d={'alternatives_assessed':10.0,'material_alternatives':5.0,'evidence_coverage':0.5,"citations":C}
 first=analyze_strategic_environmental_assessment(d)
 changed=analyze_strategic_environmental_assessment(d|{'alternatives_assessed':20.0})
 assert first["feature_row"]==1695 and first["named_analysis"]=="analyze_strategic_environmental_assessment"
 assert first["analysis"]['strategic_coverage_fraction'] != changed["analysis"]['strategic_coverage_fraction']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_strategic_environmental_assessment(d|{'alternatives_assessed':-1})

def test_row_1696_life_cycle_assessment_perturbs_domain_input_and_rejects_invalid_domain():
 d={'activity_quantity':10.0,'emission_factor_kgco2e':5.0,'allocation_fraction':0.5,"citations":C}
 first=analyze_life_cycle_assessment(d)
 changed=analyze_life_cycle_assessment(d|{'activity_quantity':20.0})
 assert first["feature_row"]==1696 and first["named_analysis"]=="analyze_life_cycle_assessment"
 assert first["analysis"]['allocated_kgco2e'] != changed["analysis"]['allocated_kgco2e']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_life_cycle_assessment(d|{'activity_quantity':-1})

def test_row_1697_carbon_footprinting_perturbs_domain_input_and_rejects_invalid_domain():
 d={'scope1_tco2e':10.0,'scope2_tco2e':5.0,'scope3_tco2e':0.5,"citations":C}
 first=analyze_carbon_footprinting(d)
 changed=analyze_carbon_footprinting(d|{'scope1_tco2e':20.0})
 assert first["feature_row"]==1697 and first["named_analysis"]=="analyze_carbon_footprinting"
 assert first["analysis"]['total_tco2e'] != changed["analysis"]['total_tco2e']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_carbon_footprinting(d|{'scope1_tco2e':-1})

def test_row_1698_water_footprinting_perturbs_domain_input_and_rejects_invalid_domain():
 d={'blue_water_m3':10.0,'green_water_m3':5.0,'grey_water_m3':0.5,"citations":C}
 first=analyze_water_footprinting(d)
 changed=analyze_water_footprinting(d|{'blue_water_m3':20.0})
 assert first["feature_row"]==1698 and first["named_analysis"]=="analyze_water_footprinting"
 assert first["analysis"]['total_water_footprint_m3'] != changed["analysis"]['total_water_footprint_m3']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_water_footprinting(d|{'blue_water_m3':-1})

def test_row_1699_ecological_footprinting_perturbs_domain_input_and_rejects_invalid_domain():
 d={'consumption_gha':10.0,'biocapacity_gha':5.0,'population':0.5,"citations":C}
 first=analyze_ecological_footprinting(d)
 changed=analyze_ecological_footprinting(d|{'consumption_gha':20.0})
 assert first["feature_row"]==1699 and first["named_analysis"]=="analyze_ecological_footprinting"
 assert first["analysis"]['ecological_deficit_gha_person'] != changed["analysis"]['ecological_deficit_gha_person']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_ecological_footprinting(d|{'consumption_gha':-1})

def test_row_1700_material_flow_analysis_perturbs_domain_input_and_rejects_invalid_domain():
 d={'domestic_extraction_t':10.0,'imports_t':5.0,'exports_t':0.5,"citations":C}
 first=analyze_material_flow_analysis(d)
 changed=analyze_material_flow_analysis(d|{'domestic_extraction_t':20.0})
 assert first["feature_row"]==1700 and first["named_analysis"]=="analyze_material_flow_analysis"
 assert first["analysis"]['domestic_material_consumption_t'] != changed["analysis"]['domestic_material_consumption_t']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_material_flow_analysis(d|{'domestic_extraction_t':-1})

def test_row_1701_industrial_ecology_perturbs_domain_input_and_rejects_invalid_domain():
 d={'waste_output_t':10.0,'byproduct_reused_t':5.0,'virgin_input_t':0.5,"citations":C}
 first=analyze_industrial_ecology(d)
 changed=analyze_industrial_ecology(d|{'waste_output_t':20.0})
 assert first["feature_row"]==1701 and first["named_analysis"]=="analyze_industrial_ecology"
 assert first["analysis"]['industrial_symbiosis_ratio'] != changed["analysis"]['industrial_symbiosis_ratio']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_industrial_ecology(d|{'waste_output_t':-1})

def test_row_1702_cleaner_production_perturbs_domain_input_and_rejects_invalid_domain():
 d={'baseline_waste_t':10.0,'current_waste_t':5.0,'output_t':0.5,"citations":C}
 first=analyze_cleaner_production(d)
 changed=analyze_cleaner_production(d|{'baseline_waste_t':20.0})
 assert first["feature_row"]==1702 and first["named_analysis"]=="analyze_cleaner_production"
 assert first["analysis"]['waste_avoided_t_per_output_t'] != changed["analysis"]['waste_avoided_t_per_output_t']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_cleaner_production(d|{'baseline_waste_t':-1})

def test_row_1703_green_chemistry_perturbs_domain_input_and_rejects_invalid_domain():
 d={'product_mass_kg':10.0,'reactant_mass_kg':5.0,'hazard_weight':0.5,"citations":C}
 first=analyze_green_chemistry(d)
 changed=analyze_green_chemistry(d|{'product_mass_kg':20.0})
 assert first["feature_row"]==1703 and first["named_analysis"]=="analyze_green_chemistry"
 assert first["analysis"]['hazard_adjusted_atom_economy'] != changed["analysis"]['hazard_adjusted_atom_economy']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_green_chemistry(d|{'product_mass_kg':-1})

def test_row_1704_green_engineering_perturbs_domain_input_and_rejects_invalid_domain():
 d={'service_output':10.0,'energy_input_mj':5.0,'safety_factor':0.5,"citations":C}
 first=analyze_green_engineering(d)
 changed=analyze_green_engineering(d|{'service_output':20.0})
 assert first["feature_row"]==1704 and first["named_analysis"]=="analyze_green_engineering"
 assert first["analysis"]['safe_service_per_mj'] != changed["analysis"]['safe_service_per_mj']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_green_engineering(d|{'service_output':-1})

def test_row_1705_sustainable_design_perturbs_domain_input_and_rejects_invalid_domain():
 d={'functional_life_years':10.0,'embodied_kgco2e':5.0,'recyclability_fraction':0.5,"citations":C}
 first=analyze_sustainable_design(d)
 changed=analyze_sustainable_design(d|{'functional_life_years':20.0})
 assert first["feature_row"]==1705 and first["named_analysis"]=="analyze_sustainable_design"
 assert first["analysis"]['circular_service_years_per_kgco2e'] != changed["analysis"]['circular_service_years_per_kgco2e']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_sustainable_design(d|{'functional_life_years':-1})

def test_row_1706_biomimicry_perturbs_domain_input_and_rejects_invalid_domain():
 d={'functions_matched':10.0,'functions_required':5.0,'evidence_confidence':0.5,"citations":C}
 first=analyze_biomimicry(d)
 changed=analyze_biomimicry(d|{'functions_matched':20.0})
 assert first["feature_row"]==1706 and first["named_analysis"]=="analyze_biomimicry"
 assert first["analysis"]['validated_function_match'] != changed["analysis"]['validated_function_match']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_biomimicry(d|{'functions_matched':-1})

def test_row_1707_cradle_to_cradle_perturbs_domain_input_and_rejects_invalid_domain():
 d={'recyclable_mass_kg':10.0,'total_mass_kg':5.0,'material_health_fraction':0.5,"citations":C}
 first=analyze_cradle_to_cradle(d)
 changed=analyze_cradle_to_cradle(d|{'recyclable_mass_kg':20.0})
 assert first["feature_row"]==1707 and first["named_analysis"]=="analyze_cradle_to_cradle"
 assert first["analysis"]['safe_circular_mass_fraction'] != changed["analysis"]['safe_circular_mass_fraction']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_cradle_to_cradle(d|{'recyclable_mass_kg':-1})

def test_row_1708_natural_capitalism_perturbs_domain_input_and_rejects_invalid_domain():
 d={'resource_output':10.0,'resource_input':5.0,'natural_capital_retention':0.5,"citations":C}
 first=analyze_natural_capitalism(d)
 changed=analyze_natural_capitalism(d|{'resource_output':20.0})
 assert first["feature_row"]==1708 and first["named_analysis"]=="analyze_natural_capitalism"
 assert first["analysis"]['retention_adjusted_productivity'] != changed["analysis"]['retention_adjusted_productivity']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_natural_capitalism(d|{'resource_output':-1})

def test_row_1709_triple_bottom_line_perturbs_domain_input_and_rejects_invalid_domain():
 d={'people_score':10.0,'planet_score':5.0,'profit_score':0.5,"citations":C}
 first=analyze_triple_bottom_line(d)
 changed=analyze_triple_bottom_line(d|{'people_score':20.0})
 assert first["feature_row"]==1709 and first["named_analysis"]=="analyze_triple_bottom_line"
 assert first["analysis"]['balanced_tbl_score'] != changed["analysis"]['balanced_tbl_score']
 assert first["standards_and_sources"]["citations"]==C and first["safety_bounds"]["external_effects"] is False
 with pytest.raises(ValueError): analyze_triple_bottom_line(d|{'people_score':-1})

def test_environmental_rows_route_is_mounted_tenant_actor_scoped_and_fail_closed():
 c=TestClient(app)
 body={"data":{"initial_concentration_mg_l":10,"final_concentration_mg_l":5,"volume_l":100,"citations":C}}
 with pytest.MonkeyPatch.context() as mp:
  mp.setenv("ATLAS_ENV","production")
  assert c.post("/api/v1/research-scientist/environmental-1660-1709/1660",json=body).status_code==401
 r=c.post("/api/v1/research-scientist/environmental-1660-1709/1660",json=body,headers={"X-Atlas-Tenant":"tenant-a","X-Atlas-Actor":"actor-a"})
 assert r.status_code==200 and r.json()["tenant_id"]=="tenant-a" and r.json()["actor_id"]=="actor-a"
 bad=c.post("/api/v1/research-scientist/environmental-1660-1709/1660",json={"data":{}},headers={"X-Atlas-Tenant":"tenant-a","X-Atlas-Actor":"actor-a"})
 assert bad.status_code==422
