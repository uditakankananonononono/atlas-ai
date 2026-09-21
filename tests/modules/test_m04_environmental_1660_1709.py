import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m04_research_scientist.environmental_1660_1709 import ROWS,run
SIMPLE={
"bioremediation":{"initial_concentration":100,"final_concentration":25,"elapsed_days":10},"ecosystem_services":{"annual_quantities":[2,3],"unit_values":[10,20]},"biodiversity":{"species_counts":[5,3,2]},"conservation_biology":{"total_habitat_area":100,"protected_area":40},"protected_areas":{"total_habitat_area":100,"protected_area":40},"wildlife_management":{"population":100,"births":20,"deaths":10},"fisheries_management":{"catch":10,"effort":2,"biomass":100,"msy":12},"forestry":{"opening_stock":100,"growth":20,"harvest":10},
"precision_agriculture":{"baseline_input":100,"actual_input":70,"area":10,"yield":200},"vertical_farming":{"annual_yield":100,"footprint_area":10,"water_use":50,"energy_use":200},"aquaponics":{"feed_input":10,"fish_output":5,"plant_output":7,"water_use":20},"hydroponics":{"annual_yield":100,"footprint_area":10,"water_use":50,"energy_use":200},"urban_agriculture":{"annual_production":100,"area":5,"served_population":20},"food_security":{"available_food_kcal":20000,"required_food_kcal":18000,"people":10,"days":1},"food_systems":{"production":100,"loss":10},"sustainable_diets":{"daily_kcal":2000,"daily_ghg_kg":4,"daily_water_l":2000,"plant_protein_g":40,"total_protein_g":60},"food_waste":{"food_purchased":100,"food_wasted":20,"avoidable_waste":15},"environmental_health":{"population":100000,"cases":50,"deaths":2},"toxicology":{"dose":5,"response":.5,"control_response":.1},"risk_assessment":{"hazard_quotient":1.2,"cancer_slope_factor":.1,"lifetime_average_daily_dose":.001},"exposure_science":{"concentration":2,"intake_rate":3,"frequency":10,"duration":2,"body_weight":60,"averaging_time":100},"epidemiology":{"exposed_cases":20,"exposed_non_cases":80,"unexposed_cases":10,"unexposed_non_cases":90},
"environmental_impact_assessment":{"impacts":[{"name":"air","magnitude":.8,"sensitivity":.9,"likelihood":.9}]},"strategic_environmental_assessment":{"options":[{"name":"A","criterion_scores":[.8,.7]},{"name":"B","criterion_scores":[.4,.5]}]},"life_cycle_assessment":{"stages":[{"impacts":{"carbon":2}},{"impacts":{"carbon":3,"water":4}}],"functional_unit":"1 kg"},"carbon_footprinting":{"activity_data":[10,20],"emission_factors":[2,.5]},"water_footprinting":{"blue_water":10,"green_water":20,"grey_water":5,"production_units":5},"ecological_footprinting":{"biocapacity_demand":200,"population":10,"available_biocapacity":100},"material_flow_analysis":{"inputs":100,"products":60,"waste":20},"industrial_ecology":{"waste_output":50,"waste_reused_as_input":30,"virgin_input":70},"cleaner_production":{"baseline_waste":100,"current_waste":60,"production":200},"green_chemistry":{"desired_product_mass":50,"reactant_mass":80,"waste_mass":20},"green_engineering":{"useful_output":50,"energy_input":100,"material_input":80},"triple_bottom_line":{"people_score":.8,"planet_score":.7,"profit_score":.9}}
for m in ["agroecology","sustainable_agriculture","organic_farming","permaculture","regenerative_agriculture","sustainable_design","biomimicry","cradle_to_cradle","natural_capitalism"]:SIMPLE[m]={"metrics":{"a":.8,"b":.6}}
for m in ["environmental_justice","indigenous_rights","community_engagement","stakeholder_analysis"]:SIMPLE[m]={"groups":[{"population":10,"burden":.8,"participation":.2},{"population":20,"burden":.2,"participation":.7}]}
for m in ["environmental_policy","regulation","permitting"]:SIMPLE[m]={"requirements":[{"id":"a","met":True},{"id":"b","met":False}]}

def test_every_row_has_concept_output_and_audit_envelope():
 assert len(ROWS)==50 and sorted(ROWS.values())==list(range(1660,1710)) and set(SIMPLE)==set(ROWS)
 for m,d in SIMPLE.items():
  x=run(m,d);assert x["feature_row"]==ROWS[m] and x["output"]["method_limits"] and x["inputs"]==d

def test_key_scientific_accounting_semantics():
 assert run("bioremediation",SIMPLE["bioremediation"])["output"]["removal_efficiency"]==pytest.approx(.75)
 assert run("biodiversity",SIMPLE["biodiversity"])["output"]["richness"]==3
 assert run("epidemiology",SIMPLE["epidemiology"])["output"]["relative_risk"]==pytest.approx(2)
 assert run("life_cycle_assessment",SIMPLE["life_cycle_assessment"])["output"]["category_totals"]["carbon"]==5
 assert run("triple_bottom_line",SIMPLE["triple_bottom_line"])["output"]["weakest_dimension"]=="planet"

def test_validation_and_mounted_routes():
 with pytest.raises(ValueError):run("biodiversity",{"species_counts":[]})
 c=TestClient(app);h={"X-Tenant-ID":"env","X-Actor-ID":"tester"}
 assert len(c.get("/api/v1/research-scientist/environmental-1660-1709/methods",headers=h).json())==50
 r=c.post("/api/v1/research-scientist/environmental-1660-1709/analyze",headers=h,json={"method":"carbon_footprinting","data":SIMPLE["carbon_footprinting"]});assert r.status_code==200 and r.json()["feature_row"]==1697
 assert c.post("/api/v1/research-scientist/environmental-1660-1709/analyze",headers=h,json={"method":"bad","data":{}}).status_code==422
