"""One focused executable evidence case for each environmental row 1610-1659."""
import pytest
from app.modules.m16_executive_dashboard import analysis
from app.modules.m16_executive_dashboard import climate_environment_1610_1659 as env
B={'climate_modeling':({'radiative_forcing':[1,2,3]},{}),'global_warming_projections':({'annual_emissions':[40,35,30]},{}),'carbon_cycle_analysis':({'emissions':[10,11],'atmospheric_increase':[5,5]},{}),'ocean_acidification':({'baseline_ph':8.2,'current_ph':8.1},{}),'sea_level_rise':({'thermal_expansion':[1,2],'glacier_ice':[1,1],'ice_sheets':[.5,1],'land_water':[.1,.2]},{}),'extreme_weather':({'historical_return_period':100,'projected_return_period':25},{}),'climate_attribution':({'probability_factual':.2,'probability_counterfactual':.05},{}),'mitigation_strategies':({'names':['a','b'],'abatement':[10,20],'cost':[100,500]},{'budget':600}),'adaptation_planning':({'hazard_probability':[.1,.2],'exposure':[100,200],'vulnerability':[.5,.4],'risk_reduction':[.5,.25],'cost':[1,2]},{}),'carbon_capture':({'feed_co2':100,'capture_efficiency':.9,'energy_per_unit':2},{}),'carbon_sequestration':({'initial_stock':100,'final_stock':140,'years':10},{}),'negative_emissions':({'gross_removal':100,'lifecycle_emissions':15,'leakage_fraction':.1},{}),'geoengineering':({'forcing_change':-1,'regional_impact_scores':[.1,-.3,.2]},{}),'solar_radiation_management':({'albedo_change':.01},{}),'ocean_fertilization':({'area_km2':100,'carbon_export_per_km2':2,'deep_sequestration_fraction':.3,'durability_fraction':.5},{}),'afforestation':({'area_hectares':100,'annual_biomass_growth_t_per_ha':5,'years':10,'survival_fraction':.8},{}),'reforestation':({'area_hectares':100,'annual_biomass_growth_t_per_ha':5,'years':10,'survival_fraction':.8},{}),'biochar':({'biochar_mass':100,'carbon_fraction':.7,'stable_fraction':.8},{}),'soil_carbon':({'bulk_density_g_cm3':1.3,'depth_cm':30,'carbon_fraction':.02,'area_hectares':2},{}),'blue_carbon':({'area_hectares':20,'biomass_carbon_per_ha':5,'soil_carbon_per_ha':50,'disturbance_loss_fraction':.2},{}),'renewable_energy':({'capacity_mw':10,'capacity_factor':.3,'grid_emissions_t_per_mwh':.4},{}),'energy_efficiency':({'baseline_energy':1000,'post_measure_energy':700,'investment_cost':600,'energy_price':.2},{}),'sustainable_transport':({'distance_km':[10,20],'emission_factor_kg_per_km':[.2,.1],'occupancy':[1,2]},{}),'electric_vehicles':({'distance_km':15000,'kwh_per_km':.18,'grid_kg_per_kwh':.4,'ice_kg_per_km':.2,'embodied_emissions_difference_kg':3000},{}),'hydrogen_economy':({'electricity_input_mwh':100,'electrolyzer_efficiency':.7,'end_use_efficiency':.5,'grid_emissions_t_per_mwh':.1},{}),'circular_economy':({'virgin_input':40,'recycled_input':60,'recovered_output':70},{}),'waste_reduction':({'baseline_waste':100,'current_waste':70},{}),'recycling':({'waste_generated':100,'recycled_mass':60,'contamination_fraction':.1,'virgin_emissions_avoided_per_mass':2},{}),'composting':({'organic_feedstock':100,'compost_yield_fraction':.4,'avoided_landfill_emissions_per_mass':1,'process_emissions_per_mass':.1},{}),'anaerobic_digestion':({'volatile_solids':100,'methane_yield_m3_per_unit':.3,'capture_efficiency':.8},{}),'waste_to_energy':({'waste_mass':100,'lower_heating_value_mj_per_kg':10,'electrical_efficiency':.25,'grid_emissions_kg_per_kwh':.4,'direct_emissions_kg_per_mass':.1},{}),'landfill_management':({'degradable_carbon':100,'methane_generation_fraction':.5,'capture_efficiency':.7,'oxidation_fraction':.1},{}),'water_treatment':({'flow_m3':1000,'influent_concentration_mg_l':50,'effluent_concentration_mg_l':5,'dose_mg_l':10},{}),'wastewater_treatment':({'flow_m3':1000,'influent_bod_mg_l':200,'effluent_bod_mg_l':20},{}),'desalination':({'product_water_m3':100,'recovery_fraction':.5,'specific_energy_kwh_m3':3,'electricity_price':.1},{}),'water_conservation':({'baseline_demand':1000,'post_measure_demand':750},{}),'water_quality':({'values':[2,8],'standards':[5,10],'weights':[1,2]},{}),'groundwater_management':({'recharge':100,'pumping':60,'natural_discharge':20,'initial_storage':1000},{}),'watershed_management':({'rainfall_mm':100,'area_km2':10,'runoff_coefficient':.4},{}),'integrated_water_resources':({'supplies':[100,80,120],'demands':[90,100,110]},{}),'air_quality':({'concentration':35,'breakpoints':[{'c_low':0,'c_high':50,'i_low':0,'i_high':100}]},{}),'air_pollution_control':({'gas_flow':100,'inlet_concentration':.2,'control_efficiency':.9,'hours':10},{}),'emissions_monitoring':({'concentrations':[1,2,3],'flow_rates':[10,10,20]},{}),'atmospheric_chemistry':({'rate_constant':.01,'initial_concentration':100,'reactant_concentration':2,'time':10},{}),'indoor_air_quality':({'source_rate':100,'room_volume':200,'air_changes_per_hour':1,'outdoor_concentration':10},{}),'soil_health':({'indicator_values':[5,8],'target_values':[10,8],'weights':[1,2]},{}),'soil_remediation':({'initial_concentration':100,'decay_rate':.2,'time':10,'target_concentration':20},{}),'contaminated_land':({'concentrations':[1,2],'toxicity_factors':[.1,.2],'exposure_factors':[1,.5]},{}),'brownfield_redevelopment':({'annual_benefits':[100,100,100],'annual_costs':[20,20,20],'initial_remediation_cost':100},{'discount_rate':.05}),'phytoremediation':({'initial_soil_concentration':100,'plant_uptake_rate':.1,'biomass_factor':2,'time':5},{})}
@pytest.mark.parametrize('method,row',env.ROWS.items(),ids=[f'row_{row}_{method}' for method,row in env.ROWS.items()])
def test_every_row_is_mounted_and_computes(method,row):
 data,params=B[method];r=analysis.run(method,data,params,seed=7)
 assert r['feature_row']==row and r['method']==method and r['inputs']['data']==data
 assert isinstance(r['output'],dict) and r['output']
def test_conservation_and_mass_balance_examples():
 c=analysis.run('carbon_cycle_analysis',*B['carbon_cycle_analysis'])['output'];assert c['total_emissions']==pytest.approx(c['atmospheric_increase']+c['land_ocean_sink'])
 w=analysis.run('desalination',*B['desalination'])['output'];assert w['feed_water_m3']==pytest.approx(100+w['brine_m3'])
 l=analysis.run('landfill_management',*B['landfill_management'])['output'];assert l['methane_captured']+l['methane_emitted']<=l['methane_generated']
def test_science_specific_numeric_results():
 o=analysis.run('ocean_acidification',*B['ocean_acidification'])['output'];assert o['hydrogen_ion_multiplier']==pytest.approx(10**.1)
 a=analysis.run('climate_attribution',*B['climate_attribution'])['output'];assert a['risk_ratio']==4 and a['fraction_attributable_risk']==.75
 s=analysis.run('soil_carbon',*B['soil_carbon'])['output'];assert s['soil_carbon_tonnes']==pytest.approx(156)
def test_invalid_physical_inputs_fail_loudly():
 with pytest.raises(ValueError):analysis.run('desalination',{'product_water_m3':100,'recovery_fraction':0,'specific_energy_kwh_m3':3})
 with pytest.raises(ValueError):analysis.run('carbon_cycle_analysis',{'emissions':[1,2],'atmospheric_increase':[1]})
 with pytest.raises(ValueError):analysis.run('air_quality',{'concentration':500,'breakpoints':[{'c_low':0,'c_high':50,'i_low':0,'i_high':100}]})


def test_row_1610_climate_modeling_records_units_provenance_and_uncertainty():
 r=analysis.run('climate_modeling',{'radiative_forcing':[1,2,3]},{'source':'lab notebook 7','units':{'radiative_forcing':'W/m2','temperature_anomaly_path':'degC'},'relative_uncertainty':.1})
 assert r['feature_row']==1610
 assert r['provenance']['input_origin']=='lab notebook 7'
 assert len(r['provenance']['input_sha256'])==64 and not r['provenance']['observed_or_fetched_evidence']
 assert r['measurement_context']['caller_units']['radiative_forcing']=='W/m2'
 assert r['uncertainty']['level']=='caller-quantified'

def test_row_1622_geoengineering_is_advisory_and_requires_review():
 r=analysis.run('geoengineering',*B['geoengineering'])
 assert r['feature_row']==1622 and r['safety']=={'advisory_calculation_only':True,'external_effects_performed':False,'requires_qualified_review':True}
 assert 'governance' in r['method_limits'][0]

def test_row_1646_water_quality_preserves_caller_standard_without_claiming_compliance():
 data,params=B['water_quality'];r=analysis.run('water_quality',data,{'standard':'caller-supplied state table v2','units':{'values':'mg/L'}})
 assert r['feature_row']==1646 and r['measurement_context']['standard']=='caller-supplied state table v2'
 assert r['evaluation']['review_required'] and not r['uncertainty']['physical_or_policy_outcome_claimed']

def test_fraction_units_and_source_validation_fail_meaningfully():
 with pytest.raises(ValueError,match='capture_efficiency must be between 0 and 1'):
  analysis.run('carbon_capture',{'feed_co2':100,'capture_efficiency':1.2})
 with pytest.raises(ValueError,match='units must map'):
  analysis.run('renewable_energy',B['renewable_energy'][0],{'units':{'capacity_mw':''}})
 with pytest.raises(ValueError,match='source must be a non-empty'):
  analysis.run('soil_health',B['soil_health'][0],{'source':' '})
 with pytest.raises(ValueError,match='relative_uncertainty'):
  analysis.run('blue_carbon',B['blue_carbon'][0],{'relative_uncertainty':2})
