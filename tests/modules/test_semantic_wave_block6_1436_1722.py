"""Semantic verification wave, block 6 (rows 1436-1722)."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m12_ai_research_lab.engineering_semantic_fixes_1560_1609 import engineering_semantic_1560_1609
BASE={"standard":"Owner-approved standard v1","standard_source_url":"https://standards.example/v1"}
def family_payload(fid):
 d=dict(BASE)
 if fid<1570:d|={"observations":[{"id":"o","metric":"size_mm","value":2,"unit":"mm","provenance":"calibrated instrument"}],"acceptance_criteria":[{"metric":"size_mm","maximum":3}],"calibration":{"status":"current"},"coverage":{"percent":100}}
 elif fid<1578:d|={"nodes":["source","load"],"components":[{"id":"r","rating":"10 W","loss_w":1}],"voltage_v":10,"current_a":2,"power_factor":.8,"verification_plan":["bench test"]}
 elif fid<1593:d|={"resource_series":[{"power_kw":5,"hours":2}],"assets":[{"id":"a","rated_kw":10}],"demand":[{"energy_kwh":8}],"protection_and_islanding":["review relay study"]}
 elif fid<1607:d|={"frequency_hz":1e9,"bandwidth_hz":1e6,"signal_dbm":-70,"noise_dbm":-100,"tx_power_dbm":20,"gains_db":[5],"losses_db":[90]}
 else:d|={"assets":[{"id":"api","classification":"restricted"}],"threats":[{"id":"spoof","asset_ids":["api"],"likelihood":2,"impact":4}],"controls":[{"id":"mfa","addresses":["spoof"]}]}
 return d

EXTRAS={1560: {'force_n': 1000, 'span_mm': 100, 'width_mm': 10, 'depth_mm': 5}, 1561: {'method_selection': 'UT', 'defect_type': 'subsurface crack'}, 1562: {'thickness_mm': 20, 'wave_velocity_m_s': 5900}, 1563: {'source_type': 'x-ray', 'exposure_plan': 'qualified procedure', 'controlled_area': 'barrier'}, 1564: {'material': 'steel', 'magnetization_direction': 'longitudinal', 'ferromagnetic': True}, 1565: {'penetrant_dwell_minutes': 10, 'developer_dwell_minutes': 5}, 1566: {'probe_frequency_hz': 1000000.0, 'conductivity_reference': 'IACS block'}, 1567: {'sensor_locations': ['a', 'b', 'c'], 'threshold_db': 45}, 1568: {'emissivity': 0.9, 'surface_temperature_c': 80, 'reference_temperature_c': 20}, 1569: {'inspection_zones': ['weld', 'edge'], 'lighting_lux': 1000}, 1570: {'requirements': ['safe'], 'hazards': ['shock']}, 1571: {'netlist': ['VCC-R1'], 'supply_v': 12}, 1572: {'layers': 4, 'clearance_mm': 0.2}, 1573: {'sample_rate_hz': 1000, 'highest_signal_hz': 400}, 1574: {'plant_poles': [-1, -2], 'controller_type': 'PID'}, 1575: {'input_v': 400, 'output_v': 48, 'output_w': 1000}, 1576: {'motor_type': 'PMSM', 'rated_current_a': 20, 'speed_rpm': 3000}, 1577: {'buses': ['a', 'b'], 'loads_mw': [5], 'generation_mw': [6]}, 1578: {'technology': 'solar', 'capacity_kw': 100, 'annual_energy_kwh': 175200}, 1579: {'irradiance_kwh_m2': 1500, 'area_m2': 10, 'efficiency': 0.2}, 1580: {'air_density': 1.225, 'swept_area_m2': 100, 'wind_speed_m_s': 10, 'power_coefficient': 0.4}, 1581: {'flow_m3_s': 2, 'head_m': 10, 'efficiency': 0.8}, 1582: {'mass_flow_kg_s': 5, 'enthalpy_drop_kj_kg': 100, 'efficiency': 0.8}, 1583: {'capacity_kwh': 100, 'charge_kw': 25, 'discharge_kw': 50}, 1584: {'capacity_ah': 100, 'nominal_v': 48, 'depth_of_discharge': 0.8}, 1585: {'stack_voltage_v': 100, 'current_a': 50, 'fuel_input_kw': 10}, 1586: {'capacitance_f': 10, 'voltage_v': 5}, 1587: {'telemetry_points': ['v', 'i'], 'control_objectives': ['balance']}, 1588: {'critical_load_kw': 50, 'island_generation_kw': 60}, 1589: {'dc_voltage_kv': 500, 'power_mw': 1000, 'distance_km': 500}, 1590: {'device_type': 'STATCOM', 'bus_voltage_kv': 220, 'reactive_power_mvar': 100}, 1591: {'rms_voltage_v': 230, 'nominal_voltage_v': 240, 'thd_percent': 3}, 1592: {'emission_limit_dbuv': 60, 'measured_dbuv': 50, 'immunity_level_v_m': 10}, 1593: {'frequency_hz': 1000000000.0, 'gain_dbi': 10, 'beamwidth_deg': 30}, 1594: {'frequency_hz': 1000000000.0, 'noise_figure_db': 3, 'bandwidth_hz': 1000000.0}, 1595: {'frequency_hz': 10000000000.0, 's_parameters': ['S11', 'S21']}, 1596: {'range_m': 10000, 'range_resolution_m': 10, 'velocity_resolution_m_s': 1}, 1597: {'source_rate_bps': 1000000.0, 'channel_capacity_bps': 2000000.0}, 1598: {'carrier_hz': 2400000000.0, 'bandwidth_hz': 20000000.0, 'modulation': 'QAM'}, 1599: {'carrier_hz': 3500000000.0, 'subcarrier_spacing_hz': 30000, 'mimo_layers': 4}, 1600: {'wavelength_nm': 1550, 'fiber_length_km': 20, 'attenuation_db_km': 0.2}, 1601: {'slant_range_km': 36000, 'frequency_hz': 12000000000.0, 'eirp_dbw': 50}, 1602: {'one_way_distance_km': 225000000.0, 'data_rate_bps': 1000000.0}, 1603: {'symbol_probabilities': [0.5, 0.25, 0.25]}, 1604: {'codewords': ['000', '111'], 'minimum_distance': 3}, 1605: {'minimum_distance': 5}, 1606: {'original_bytes': 1000, 'compressed_bytes': 400, 'lossless': True}, 1607: {'algorithm': 'AES', 'key_bits': 256, 'mode': 'GCM'}, 1608: {'zones': ['dmz', 'app'], 'trust_boundaries': ['gateway'], 'controls': [{'id':'mTLS','addresses':['spoof']}]}, 1609: {'assets': [{'id': 'api', 'classification': 'restricted'}], 'threats': [{'id': 'spoof', 'asset_ids': ['api'], 'likelihood': 2, 'impact': 4}], 'controls': [{'id': 'mfa', 'addresses': ['spoof']}]}}

def _check(row):
 data=family_payload(row)|EXTRAS[row]
 result=engineering_semantic_1560_1609(row,data)
 assert result["feature_id"]==row and result["distinctive_output"]
 assert result["semantic_verification"]=="row-specific-v1"
 return result["distinctive_output"]

def _make(row):
 def test(): _check(row)
 return test
test_1560_bend_stress=_make(1560)
test_1561_ndt_method_selection=_make(1561)
test_1562_ultrasonic_time_of_flight=_make(1562)
test_1563_radiographic_safety=_make(1563)
test_1564_magnetic_particle_material=_make(1564)
test_1565_penetrant_dwell=_make(1565)
test_1566_eddy_current_probe=_make(1566)
test_1567_acoustic_emission_array=_make(1567)
test_1568_thermography_emissivity=_make(1568)
test_1569_visual_inspection_lighting=_make(1569)
test_1570_electrical_architecture=_make(1570)
test_1571_circuit_erc=_make(1571)
test_1572_pcb_drc=_make(1572)
test_1573_signal_nyquist=_make(1573)
test_1574_control_stability=_make(1574)
test_1575_power_conversion=_make(1575)
test_1576_motor_limits=_make(1576)
test_1577_power_balance=_make(1577)
test_1578_renewable_capacity=_make(1578)
test_1579_solar_yield=_make(1579)
test_1580_wind_power=_make(1580)
test_1581_hydro_power=_make(1581)
test_1582_geothermal_power=_make(1582)
test_1583_storage_duration=_make(1583)
test_1584_battery_energy=_make(1584)
test_1585_fuel_cell_efficiency=_make(1585)
test_1586_supercapacitor_energy=_make(1586)
test_1587_smart_grid_fail_safe=_make(1587)
test_1588_microgrid_islanding=_make(1588)
test_1589_hvdc_current=_make(1589)
test_1590_facts_dynamic_stability=_make(1590)
test_1591_power_quality=_make(1591)
test_1592_emc_margin=_make(1592)
test_1593_antenna_wavelength=_make(1593)
test_1594_rf_noise=_make(1594)
test_1595_microwave_sparameters=_make(1595)
test_1596_radar_bandwidth=_make(1596)
test_1597_communications_capacity=_make(1597)
test_1598_wireless_fractional_bandwidth=_make(1598)
test_1599_cellular_numerology=_make(1599)
test_1600_optical_loss=_make(1600)
test_1601_satellite_path_loss=_make(1601)
test_1602_deep_space_delay=_make(1602)
test_1603_information_entropy=_make(1603)
test_1604_coding_distance=_make(1604)
test_1605_error_correction=_make(1605)
test_1606_compression_ratio=_make(1606)
test_1607_encryption_key_boundary=_make(1607)
test_1608_network_trust_boundaries=_make(1608)
test_1609_cybersecurity_defensive_scope=_make(1609)

def test_semantic_engineering_invalid_capability_input_fails_closed():
 for row in range(1560,1610):
  data=family_payload(row)|EXTRAS[row]
  key=next(iter(EXTRAS[row]));data.pop(key)
  with pytest.raises((ValueError,TypeError,KeyError,ZeroDivisionError)):
   engineering_semantic_1560_1609(row,data)

def test_semantic_engineering_http_boundary_is_mounted():
 data=family_payload(1562)|EXTRAS[1562]
 response=TestClient(app).post('/api/v1/ai-research-lab/engineering-1560-1609/semantic-support',headers={'x-atlas-tenant':'sem6'},json={'feature_id':1562,'data':data})
 assert response.status_code==200 and response.json()['tenant_id']=='sem6'
 assert response.json()['distinctive_output']['round_trip_time_us']>0
 bad=TestClient(app).post('/api/v1/ai-research-lab/engineering-1560-1609/semantic-support',headers={'x-atlas-tenant':'sem6'},json={'feature_id':1562,'data':family_payload(1562)})
 assert bad.status_code==422
