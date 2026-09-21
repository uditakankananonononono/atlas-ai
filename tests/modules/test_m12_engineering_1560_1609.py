"""Named row-level tests for the 50 engineering analyses, owner rows 1560-1609.

Every row has a named analysis function with its own units, constraints, safety
margins, assumptions and uncertainty. Tests prove: distinct keyed behavior per
row, unit-mismatch detection, infeasible/physics-boundary and safety-boundary
fail-closed behavior, typed validation, mounted tenant-scoped routes.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m12_ai_research_lab import engineering_support_1560_1609 as eng
from app.modules.m12_ai_research_lab.engineering_semantic_fixes_1560_1609 import engineering_semantic_1560_1609

BASE={"standard":"Owner-approved standard v1","standard_source_url":"https://standards.example/v1","assumptions":["nominal conditions"],"unknowns":["field variance"]}

def row(fid,**kw):return dict(BASE)|kw

def test_row_1560_bend_testing():
    o=eng.analyze_bend_testing(row(1560,force_n=1000,span_mm=100,width_mm=10,depth_mm=5,allowable_flexural_stress_mpa=800))
    assert o["named_analysis"]=="analyze_bend_testing" and o["analysis"]["flexural_stress_mpa"]==600
    assert o["analysis"]["section_modulus_mm3"]==pytest.approx(41.6666667) and o["analysis"]["safety_margin_ratio"]==pytest.approx(800/600)

def test_row_1561_non_destructive_testing():
    o=eng.analyze_non_destructive_testing(row(1561,method_selection="UT",defect_type="subsurface crack"))
    assert o["analysis"]["method_suited_to_defect_location"] is True and o["analysis"]["method_class"]=="volumetric" and o["analysis"]["destructive"] is False
    bad=eng.analyze_non_destructive_testing(row(1561,method_selection="PT",defect_type="subsurface crack"))
    assert bad["analysis"]["method_suited_to_defect_location"] is False and bad["constraints"]

def test_row_1562_ultrasonic_testing():
    o=eng.analyze_ultrasonic_testing(row(1562,thickness_mm=20,wave_velocity_m_s=5900,measured_echo_time_us=6.779661016949152))
    assert o["analysis"]["round_trip_time_us"]==pytest.approx(6.7796610) and o["analysis"]["estimated_thickness_mm"]==pytest.approx(20)
    assert o["analysis"]["thickness_deviation_mm"]==pytest.approx(0,abs=1e-6)

def test_row_1563_radiographic_testing():
    o=eng.analyze_radiographic_testing(row(1563,source_type="x-ray",exposure_plan="qualified procedure",controlled_area="barrier",focal_spot_mm=2,object_detector_distance_mm=10,source_object_distance_mm=100))
    assert o["analysis"]["geometric_unsharpness_mm"]==pytest.approx(0.2) and o["analysis"]["controlled_area_verified_by_radiation_safety_officer"] is False

def test_row_1564_magnetic_particle_testing():
    o=eng.analyze_magnetic_particle_testing(row(1564,material="steel",magnetization_direction="longitudinal",ferromagnetic=True,test_piece_lift_n=60,required_lift_n=45))
    assert o["analysis"]["lifting_force_margin_n"]==15 and o["analysis"]["demagnetization_required_after_test"] is True

def test_row_1565_dye_penetrant_testing():
    o=eng.analyze_dye_penetrant_testing(row(1565,penetrant_dwell_minutes=10,developer_dwell_minutes=5))
    assert o["analysis"]["surface_breaking_only"] is True and o["constraints"]==[]
    out=eng.analyze_dye_penetrant_testing(row(1565,penetrant_dwell_minutes=60,developer_dwell_minutes=5))
    assert any("qualified window" in c for c in out["constraints"])

def test_row_1566_eddy_current_testing():
    o=eng.analyze_eddy_current_testing(row(1566,probe_frequency_hz=1e6,conductivity_reference="IACS block",conductivity_s_m=5.8e7,relative_permeability=1.0))
    assert o["analysis"]["standard_depth_of_penetration_mm"]==pytest.approx(0.0661,rel=1e-3)

def test_row_1567_acoustic_emission_testing():
    o=eng.analyze_acoustic_emission_testing(row(1567,sensor_locations=["a","b","c"],threshold_db=45))
    assert o["analysis"]["sensor_count"]==3 and o["analysis"]["planar_localization_feasible"] is True
    two=eng.analyze_acoustic_emission_testing(row(1567,sensor_locations=["a","b"],threshold_db=45))
    assert two["analysis"]["planar_localization_feasible"] is False and two["constraints"]

def test_row_1568_thermography():
    o=eng.analyze_thermography(row(1568,emissivity=0.9,surface_temperature_c=80,reference_temperature_c=20))
    assert o["analysis"]["delta_temperature_c"]==60 and o["analysis"]["reflected_temperature_correction_required"] is True

def test_row_1569_visual_inspection():
    o=eng.analyze_visual_inspection(row(1569,inspection_zones=["weld","edge"],lighting_lux=1000))
    assert o["analysis"]["lighting_adequate"] is True and o["analysis"]["zone_count"]==2
    dim=eng.analyze_visual_inspection(row(1569,inspection_zones=["weld"],lighting_lux=200))
    assert dim["analysis"]["lighting_adequate"] is False and dim["constraints"]

def test_row_1570_electrical_engineering():
    o=eng.analyze_electrical_engineering(row(1570,requirements=["safe isolation"],hazards=["shock","arc flash"],mitigated_hazards=["shock"]))
    assert o["analysis"]["hazard_count"]==2 and o["analysis"]["unmitigated_hazards"]==["arc flash"] and o["constraints"]

def test_row_1571_circuit_design():
    o=eng.analyze_circuit_design(row(1571,netlist=["VCC-R1","R1-GND"],supply_v=12,loads=[{"current_a":1},{"current_a":2}],supply_current_limit_a=4))
    assert o["analysis"]["total_load_current_a"]==3 and o["analysis"]["total_load_power_w"]==36 and o["analysis"]["supply_current_margin_a"]==1

def test_row_1572_pcb_design():
    o=eng.analyze_pcb_design(row(1572,layers=4,clearance_mm=0.2,voltage_v=10))
    assert o["analysis"]["required_clearance_mm"]==pytest.approx(0.18) and o["analysis"]["clearance_margin_mm"]==pytest.approx(0.02)

def test_row_1573_signal_processing():
    o=eng.analyze_signal_processing(row(1573,sample_rate_hz=1000,highest_signal_hz=400))
    assert o["analysis"]["nyquist_ratio"]==2.5 and o["analysis"]["aliases_without_filter"] is False
    low=eng.analyze_signal_processing(row(1573,sample_rate_hz=600,highest_signal_hz=400))
    assert low["analysis"]["aliases_without_filter"] is True and low["constraints"]

def test_row_1574_control_systems():
    o=eng.analyze_control_systems(row(1574,plant_poles=[-1,-2],controller_type="PID"))
    assert o["analysis"]["open_loop_unstable_poles"]==[] and o["analysis"]["closed_loop_stability_unverified"] is True
    unstable=eng.analyze_control_systems(row(1574,plant_poles=[0.5,-2],controller_type="PID"))
    assert unstable["analysis"]["open_loop_unstable_poles"]==[0.5]

def test_row_1575_power_electronics():
    o=eng.analyze_power_electronics(row(1575,input_v=400,output_v=48,output_w=1000,losses_w=50))
    assert o["analysis"]["conversion_ratio"]==pytest.approx(0.12) and o["analysis"]["estimated_efficiency"]==pytest.approx(1000/1050)

def test_row_1576_motor_control():
    o=eng.analyze_motor_control(row(1576,motor_type="PMSM",rated_current_a=20,speed_rpm=3000,commanded_current_a=15,power_w=5000))
    assert o["analysis"]["current_margin_a"]==5 and o["analysis"]["estimated_torque_nm"]==pytest.approx(15.9155,rel=1e-3)

def test_row_1577_power_systems():
    o=eng.analyze_power_systems(row(1577,buses=["a","b"],loads_mw=[5],generation_mw=[5.1]))
    assert o["analysis"]["power_balance_mw"]==pytest.approx(0.1) and o["constraints"]==[]
    short=eng.analyze_power_systems(row(1577,buses=["a"],loads_mw=[10],generation_mw=[6]))
    assert short["analysis"]["power_balance_mw"]==-4 and short["constraints"]

def test_row_1578_renewable_energy():
    o=eng.analyze_renewable_energy(row(1578,technology="solar",capacity_kw=100,annual_energy_kwh=175200))
    assert o["analysis"]["capacity_factor"]==pytest.approx(0.2)

def test_row_1579_solar_power():
    o=eng.analyze_solar_power(row(1579,irradiance_kwh_m2=1500,area_m2=10,efficiency=0.2))
    assert o["analysis"]["estimated_energy_kwh"]==3000 and o["analysis"]["shading_study_required"] is True

def test_row_1580_wind_power():
    o=eng.analyze_wind_power(row(1580,air_density=1.225,swept_area_m2=100,wind_speed_m_s=10,power_coefficient=0.4))
    assert o["analysis"]["wind_power_w"]==pytest.approx(24500) and o["analysis"]["betz_limit_power_w"]==pytest.approx(0.5*1.225*100*1000*0.593)

def test_row_1581_hydro_power():
    o=eng.analyze_hydro_power(row(1581,flow_m3_s=2,head_m=10,efficiency=0.8))
    assert o["analysis"]["hydraulic_power_w"]==pytest.approx(1000*9.80665*2*10*0.8)

def test_row_1582_geothermal():
    o=eng.analyze_geothermal(row(1582,mass_flow_kg_s=5,enthalpy_drop_kj_kg=100,efficiency=0.8))
    assert o["analysis"]["thermal_power_kw"]==400 and o["analysis"]["reservoir_reinjection_review"] is True

def test_row_1583_energy_storage():
    o=eng.analyze_energy_storage(row(1583,capacity_kwh=100,charge_kw=25,discharge_kw=50))
    assert o["analysis"]["charge_duration_h"]==4 and o["analysis"]["discharge_duration_h"]==2 and o["analysis"]["power_to_energy_ratio"]==0.5

def test_row_1584_battery_technology():
    o=eng.analyze_battery_technology(row(1584,capacity_ah=100,nominal_v=48,depth_of_discharge=0.8))
    assert o["analysis"]["usable_energy_wh"]==3840 and o["analysis"]["bms_required"] is True

def test_row_1585_fuel_cells():
    o=eng.analyze_fuel_cells(row(1585,stack_voltage_v=100,current_a=50,fuel_input_kw=10))
    assert o["analysis"]["electrical_efficiency"]==pytest.approx(0.5) and o["analysis"]["hydrogen_safety_review"] is True

def test_row_1586_supercapacitors():
    o=eng.analyze_supercapacitors(row(1586,capacitance_f=10,voltage_v=5,rated_voltage_v=5.5))
    assert o["analysis"]["stored_energy_j"]==125 and o["analysis"]["voltage_margin_v"]==pytest.approx(0.5)

def test_row_1587_smart_grid():
    o=eng.analyze_smart_grid(row(1587,telemetry_points=["v","i"],control_objectives=["balance"]))
    assert o["analysis"]["telemetry_count"]==2 and o["analysis"]["telecontrol_commands_not_issued"] is True

def test_row_1588_microgrids():
    o=eng.analyze_microgrids(row(1588,critical_load_kw=50,island_generation_kw=60))
    assert o["analysis"]["island_margin_kw"]==10 and o["analysis"]["island_supply_adequate"] is True
    deficit=eng.analyze_microgrids(row(1588,critical_load_kw=80,island_generation_kw=60))
    assert deficit["analysis"]["island_supply_adequate"] is False and deficit["constraints"]

def test_row_1589_hvdc():
    o=eng.analyze_hvdc(row(1589,dc_voltage_kv=500,power_mw=1000,distance_km=500))
    assert o["analysis"]["dc_current_a"]==2000

def test_row_1590_facts():
    o=eng.analyze_facts(row(1590,device_type="STATCOM",bus_voltage_kv=220,reactive_power_mvar=100,device_rating_mvar=150))
    assert o["analysis"]["rating_margin_mvar"]==50

def test_row_1591_power_quality():
    o=eng.analyze_power_quality(row(1591,rms_voltage_v=230,nominal_voltage_v=240,thd_percent=3))
    assert o["analysis"]["voltage_deviation_percent"]==pytest.approx(-4.166667) and o["analysis"]["thd_above_8_percent_general_system_reference"] is False
    dirty=eng.analyze_power_quality(row(1591,rms_voltage_v=230,nominal_voltage_v=240,thd_percent=12))
    assert dirty["constraints"] and dirty["analysis"]["harmonic_source_identification_required"] is True

def test_row_1592_electromagnetic_compatibility():
    o=eng.analyze_electromagnetic_compatibility(row(1592,emission_limit_dbuv=60,measured_dbuv=50,immunity_level_v_m=10))
    assert o["analysis"]["emission_margin_db"]==10 and o["analysis"]["compliance_claimed"] is False and o["constraints"]==[]
    tight=eng.analyze_electromagnetic_compatibility(row(1592,emission_limit_dbuv=60,measured_dbuv=58,immunity_level_v_m=10))
    assert tight["constraints"]

def test_row_1593_antenna_design():
    o=eng.analyze_antenna_design(row(1593,frequency_hz=1e9,gain_dbi=10,beamwidth_deg=30))
    assert o["analysis"]["wavelength_m"]==pytest.approx(0.299792458) and o["analysis"]["approximate_max_directivity_dbi"]==pytest.approx(16.6118,rel=1e-3)

def test_row_1594_rf_engineering():
    o=eng.analyze_rf_engineering(row(1594,frequency_hz=1e9,noise_figure_db=3,bandwidth_hz=1e6))
    assert o["analysis"]["thermal_noise_floor_dbm"]==pytest.approx(-111)

def test_row_1595_microwave_engineering():
    o=eng.analyze_microwave_engineering(row(1595,frequency_hz=1e10,s_parameters=[{"name":"S11","magnitude":0.5}]))
    assert o["analysis"]["passivity_screened_parameters"]==[{"name":"S11","magnitude":0.5}]

def test_row_1596_radar_systems():
    o=eng.analyze_radar_systems(row(1596,range_m=10000,range_resolution_m=10,velocity_resolution_m_s=1))
    assert o["analysis"]["required_bandwidth_hz"]==pytest.approx(299792458/20)

def test_row_1597_communications_systems():
    o=eng.analyze_communications_systems(row(1597,source_rate_bps=1e6,channel_capacity_bps=2e6))
    assert o["analysis"]["capacity_margin_bps"]==1e6 and o["analysis"]["channel_supports_source"] is True

def test_row_1598_wireless_communications():
    o=eng.analyze_wireless_communications(row(1598,carrier_hz=2.4e9,bandwidth_hz=2e7,modulation="QAM"))
    assert o["analysis"]["fractional_bandwidth"]==pytest.approx(2e7/2.4e9)

def test_row_1599_5g_6g():
    o=eng.analyze_cellular_5g_6g(row(1599,carrier_hz=3.5e9,subcarrier_spacing_hz=30000,mimo_layers=4))
    assert o["analysis"]["numerology_ratio"]==pytest.approx(3.5e9/30000) and o["analysis"]["no_network_attach_or_signaling_performed"] is True

def test_row_1600_optical_communications():
    o=eng.analyze_optical_communications(row(1600,wavelength_nm=1550,fiber_length_km=20,attenuation_db_km=0.2))
    assert o["analysis"]["fiber_loss_db"]==4 and o["analysis"]["in_common_telecom_window"] is True

def test_row_1601_satellite_communications():
    o=eng.analyze_satellite_communications(row(1601,slant_range_km=36000,frequency_hz=12e9,eirp_dbw=50))
    assert o["analysis"]["free_space_path_loss_db"]==pytest.approx(205.16,rel=1e-3)

def test_row_1602_deep_space_communications():
    o=eng.analyze_deep_space_communications(row(1602,one_way_distance_km=2.25e8,data_rate_bps=1e6))
    assert o["analysis"]["one_way_light_time_s"]==pytest.approx(750.52,rel=1e-4) and o["analysis"]["real_time_control_infeasible"] is True

def test_row_1603_information_theory():
    o=eng.analyze_information_theory(row(1603,symbol_probabilities=[0.5,0.25,0.25]))
    assert o["analysis"]["entropy_bits_per_symbol"]==pytest.approx(1.5) and o["analysis"]["source_coding_lower_bound"] is True

def test_row_1604_coding_theory():
    o=eng.analyze_coding_theory(row(1604,codewords=["000","111"],minimum_distance=3))
    assert o["analysis"]["detectable_errors"]==2 and o["analysis"]["codeword_count"]==2

def test_row_1605_error_correction():
    o=eng.analyze_error_correction(row(1605,minimum_distance=5))
    assert o["analysis"]["correctable_errors"]==2 and o["analysis"]["detectable_errors"]==4

def test_row_1606_compression():
    o=eng.analyze_compression(row(1606,original_bytes=1000,compressed_bytes=400,lossless=True))
    assert o["analysis"]["compression_ratio"]==2.5 and o["analysis"]["round_trip_test_required"] is True

def test_row_1607_encryption():
    o=eng.analyze_encryption(row(1607,algorithm="AES",key_bits=256,mode="GCM"))
    assert o["analysis"]["key_material_handled"] is False and o["analysis"]["approved_library_required"] is True

def test_row_1608_network_security():
    o=eng.analyze_network_security(row(1608,zones=["dmz","app"],trust_boundaries=["gateway"],controls=[{"id":"mTLS","addresses":["spoof"]}]))
    assert o["analysis"]["unguarded_trust_boundaries"]==["gateway"] and o["analysis"]["deny_by_default"] is True and o["constraints"]

def test_row_1609_cybersecurity():
    o=eng.analyze_cybersecurity(row(1609,assets=[{"id":"api","classification":"restricted"}],threats=[{"id":"spoof","asset_ids":["api"],"likelihood":2,"impact":4}],controls=[{"id":"mfa","addresses":["spoof"]}]))
    risk=o["analysis"]["risk_register"][0]
    assert risk["inherent_score"]==8 and risk["residual_status"]=="requires_validation" and o["analysis"]["authorized_defensive_scope_only"] is True

VALID_INPUTS={
 1560:{"force_n":1000,"span_mm":100,"width_mm":10,"depth_mm":5},
 1561:{"method_selection":"UT","defect_type":"subsurface crack"},
 1562:{"thickness_mm":20,"wave_velocity_m_s":5900},
 1563:{"source_type":"x-ray","exposure_plan":"qualified procedure","controlled_area":"barrier"},
 1564:{"material":"steel","magnetization_direction":"longitudinal","ferromagnetic":True},
 1565:{"penetrant_dwell_minutes":10,"developer_dwell_minutes":5},
 1566:{"probe_frequency_hz":1e6,"conductivity_reference":"IACS block"},
 1567:{"sensor_locations":["a","b","c"],"threshold_db":45},
 1568:{"emissivity":0.9,"surface_temperature_c":80,"reference_temperature_c":20},
 1569:{"inspection_zones":["weld","edge"],"lighting_lux":1000},
 1570:{"requirements":["safe"],"hazards":["shock"]},
 1571:{"netlist":["VCC-R1"],"supply_v":12},
 1572:{"layers":4,"clearance_mm":0.2},
 1573:{"sample_rate_hz":1000,"highest_signal_hz":400},
 1574:{"plant_poles":[-1,-2],"controller_type":"PID"},
 1575:{"input_v":400,"output_v":48,"output_w":1000},
 1576:{"motor_type":"PMSM","rated_current_a":20,"speed_rpm":3000},
 1577:{"buses":["a","b"],"loads_mw":[5],"generation_mw":[6]},
 1578:{"technology":"solar","capacity_kw":100,"annual_energy_kwh":175200},
 1579:{"irradiance_kwh_m2":1500,"area_m2":10,"efficiency":0.2},
 1580:{"air_density":1.225,"swept_area_m2":100,"wind_speed_m_s":10,"power_coefficient":0.4},
 1581:{"flow_m3_s":2,"head_m":10,"efficiency":0.8},
 1582:{"mass_flow_kg_s":5,"enthalpy_drop_kj_kg":100,"efficiency":0.8},
 1583:{"capacity_kwh":100,"charge_kw":25,"discharge_kw":50},
 1584:{"capacity_ah":100,"nominal_v":48,"depth_of_discharge":0.8},
 1585:{"stack_voltage_v":100,"current_a":50,"fuel_input_kw":10},
 1586:{"capacitance_f":10,"voltage_v":5},
 1587:{"telemetry_points":["v","i"],"control_objectives":["balance"]},
 1588:{"critical_load_kw":50,"island_generation_kw":60},
 1589:{"dc_voltage_kv":500,"power_mw":1000,"distance_km":500},
 1590:{"device_type":"STATCOM","bus_voltage_kv":220,"reactive_power_mvar":100},
 1591:{"rms_voltage_v":230,"nominal_voltage_v":240,"thd_percent":3},
 1592:{"emission_limit_dbuv":60,"measured_dbuv":50,"immunity_level_v_m":10},
 1593:{"frequency_hz":1e9,"gain_dbi":10,"beamwidth_deg":30},
 1594:{"frequency_hz":1e9,"noise_figure_db":3,"bandwidth_hz":1e6},
 1595:{"frequency_hz":1e10,"s_parameters":["S11","S21"]},
 1596:{"range_m":10000,"range_resolution_m":10,"velocity_resolution_m_s":1},
 1597:{"source_rate_bps":1e6,"channel_capacity_bps":2e6},
 1598:{"carrier_hz":2.4e9,"bandwidth_hz":2e7,"modulation":"QAM"},
 1599:{"carrier_hz":3.5e9,"subcarrier_spacing_hz":30000,"mimo_layers":4},
 1600:{"wavelength_nm":1550,"fiber_length_km":20,"attenuation_db_km":0.2},
 1601:{"slant_range_km":36000,"frequency_hz":12e9,"eirp_dbw":50},
 1602:{"one_way_distance_km":2.25e8,"data_rate_bps":1e6},
 1603:{"symbol_probabilities":[0.5,0.25,0.25]},
 1604:{"codewords":["000","111"],"minimum_distance":3},
 1605:{"minimum_distance":5},
 1606:{"original_bytes":1000,"compressed_bytes":400,"lossless":True},
 1607:{"algorithm":"AES","key_bits":256,"mode":"GCM"},
 1608:{"zones":["dmz","app"],"trust_boundaries":["gateway"],"controls":[{"id":"mTLS","addresses":["gateway"]}]},
 1609:{"assets":[{"id":"api","classification":"restricted"}],"threats":[{"id":"spoof","asset_ids":["api"],"likelihood":2,"impact":4}],"controls":[{"id":"mfa","addresses":["spoof"]}]},
}

def test_all_50_rows_have_named_analyses_with_distinct_keyed_behavior():
    assert set(eng.ANALYSES)==set(range(1560,1610)) and len(eng.ANALYSES)==50
    names={fn.__name__ for fn in eng.ANALYSES.values()}
    assert len(names)==50 and all(n.startswith("analyze_") for n in names)
    key_sets=set();outputs=set()
    for fid,fn in eng.ANALYSES.items():
        o=fn(row(fid,**VALID_INPUTS[fid]))
        assert o["feature_id"]==fid and o["concept"]==eng.FEATURES[fid]
        assert o["named_analysis"]==fn.__name__ and o["review_required"] and o["boundary"] and o["disclaimer"]
        assert o["uncertainty"]["certification_or_physical_execution_claimed"] is False
        key_sets.add(tuple(sorted(o["analysis"])))
        outputs.add(str(sorted(o["analysis"].items())))
    assert len(key_sets)==50 and len(outputs)==50

@pytest.mark.parametrize("fid",range(1560,1610))
def test_dispatcher_routes_every_row_to_its_named_analysis(fid):
    o=eng.engineering_support_1560_1609(fid,row(fid,**VALID_INPUTS[fid]))
    assert o["named_analysis"]==eng.ANALYSES[fid].__name__ and o["feature_id"]==fid

@pytest.mark.parametrize("fid",range(1560,1610))
def test_missing_capability_input_fails_closed_per_row(fid):
    inputs=dict(VALID_INPUTS[fid]);first=next(iter(inputs));inputs.pop(first)
    with pytest.raises((ValueError,TypeError,KeyError)):
        eng.engineering_support_1560_1609(fid,row(fid,**inputs))

@pytest.mark.parametrize("fid,key,unit",[
 (1560,"span_mm","cm"),(1560,"force_n","kN"),(1562,"thickness_mm","in"),(1562,"wave_velocity_m_s","mm/s"),
 (1566,"probe_frequency_hz","kHz"),(1572,"clearance_mm","mil"),(1580,"wind_speed_m_s","km/h"),
 (1584,"nominal_v","mV"),(1589,"dc_voltage_kv","V"),(1600,"wavelength_nm","um"),(1602,"one_way_distance_km","mi"),
])
def test_unit_mismatch_is_detected_and_fails_closed(fid,key,unit):
    with pytest.raises(ValueError,match="unit mismatch"):
        eng.engineering_support_1560_1609(fid,row(fid,**VALID_INPUTS[fid])|{f"{key}_unit":unit})

@pytest.mark.parametrize("fid,override",[
 (1580,{"power_coefficient":0.7}),          # Betz limit violated
 (1585,{"current_a":300}),                  # efficiency above 1
 (1578,{"annual_energy_kwh":900000}),       # capacity factor above 1
 (1572,{"voltage_v":1000}),                 # clearance below voltage spacing
 (1576,{"commanded_current_a":25}),         # over-rated current command
 (1586,{"voltage_v":5,"rated_voltage_v":4}),# supercapacitor overvoltage
 (1590,{"reactive_power_mvar":100,"device_rating_mvar":50}),  # FACTS over rating
 (1593,{"gain_dbi":30}),                    # gain impossible for the beamwidth
 (1598,{"bandwidth_hz":3e9}),               # bandwidth above carrier
 (1603,{"symbol_probabilities":[0.5,0.4]}), # probabilities do not sum to 1
 (1607,{"algorithm":"DES"}),                # deprecated algorithm
 (1607,{"key_bits":64}),                    # below 128-bit minimum
 (1607,{"mode":"ECB"}),                     # disapproved mode
 (1564,{"ferromagnetic":False}),            # non-ferromagnetic material
 (1595,{"s_parameters":[{"name":"S21","magnitude":1.4}]}),  # passivity violated
 (1609,{"threats":[{"id":"spoof","asset_ids":["api"],"likelihood":9,"impact":4}]}),  # off-scale risk input
])
def test_infeasible_or_safety_boundary_input_fails_closed(fid,override):
    with pytest.raises(ValueError):
        eng.engineering_support_1560_1609(fid,row(fid,**VALID_INPUTS[fid])|override)

def test_typed_validation_rejects_non_numeric_and_non_finite():
    with pytest.raises(ValueError):eng.analyze_bend_testing(row(1560,force_n="high",span_mm=100,width_mm=10,depth_mm=5))
    with pytest.raises(ValueError):eng.analyze_bend_testing(row(1560,force_n=float("nan"),span_mm=100,width_mm=10,depth_mm=5))
    with pytest.raises(ValueError):eng.analyze_wind_power(row(1580,air_density=1.225,swept_area_m2=100,wind_speed_m_s=0,power_coefficient=0.4))

def test_unknown_row_and_missing_provenance_fail_closed():
    with pytest.raises(ValueError):eng.engineering_support_1560_1609(1559,row(1560,**VALID_INPUTS[1560]))
    with pytest.raises(ValueError):eng.engineering_support_1560_1609(1610,row(1560,**VALID_INPUTS[1560]))
    with pytest.raises(ValueError):eng.engineering_support_1560_1609(1560,{"force_n":1,"span_mm":1,"width_mm":1,"depth_mm":1})

def test_support_route_is_mounted_and_tenant_scoped():
    client=TestClient(app)
    r=client.post("/api/v1/ai-research-lab/engineering-1560-1609/support",headers={"x-atlas-tenant":"t-a"},json={"feature_id":1580,"data":row(1580,**VALID_INPUTS[1580])})
    assert r.status_code==200 and r.json()["tenant_id"]=="t-a" and r.json()["named_analysis"]=="analyze_wind_power"
    r2=client.post("/api/v1/ai-research-lab/engineering-1560-1609/support",headers={"x-atlas-tenant":"t-b"},json={"feature_id":1580,"data":row(1580,**VALID_INPUTS[1580])})
    assert r2.json()["tenant_id"]=="t-b" and r2.json()["tenant_id"]!=r.json()["tenant_id"]
    bad=client.post("/api/v1/ai-research-lab/engineering-1560-1609/support",headers={"x-atlas-tenant":"t-a"},json={"feature_id":1580,"data":row(1580,power_coefficient=0.7)})
    assert bad.status_code==422

def test_semantic_route_is_mounted_with_row_specific_evidence():
    client=TestClient(app)
    r=client.post("/api/v1/ai-research-lab/engineering-1560-1609/semantic-support",headers={"x-atlas-tenant":"t-sem"},json={"feature_id":1560,"data":row(1560,**VALID_INPUTS[1560])})
    body=r.json()
    assert r.status_code==200 and body["tenant_id"]=="t-sem" and body["semantic_verification"]=="row-specific-v1"
    assert body["distinctive_output"]["flexural_stress_mpa"]==600 and body["named_analysis"]=="analyze_bend_testing"
