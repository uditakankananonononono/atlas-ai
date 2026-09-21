"""Row-specific traceable engineering analyses for owner feature rows 1560-1609.

Each row has its own named analysis function with its own inputs, units,
constraints, safety margins, assumptions, uncertainty and standards provenance.
Calculations operate only on caller-supplied measurements/design assumptions.
Outputs are decision support: they never operate equipment, energize circuits,
issue inspection certificates, certify a design, or perform offensive security
actions. A qualified engineer must verify inputs, units, standards, safety
controls, model limits and the original evidence before use.
"""
from __future__ import annotations
from math import isfinite, log10, log2, pi, sqrt
from typing import Any, Callable

NAMES=["Bend Testing","Non-Destructive Testing","Ultrasonic Testing","Radiographic Testing","Magnetic Particle Testing","Dye Penetrant Testing","Eddy Current Testing","Acoustic Emission Testing","Thermography","Visual Inspection","Electrical Engineering","Circuit Design","PCB Design","Signal Processing","Control Systems","Power Electronics","Motor Control","Power Systems","Renewable Energy","Solar Power","Wind Power","Hydro Power","Geothermal","Energy Storage","Battery Technology","Fuel Cells","Supercapacitors","Smart Grid","Microgrids","HVDC","FACTS","Power Quality","Electromagnetic Compatibility","Antenna Design","RF Engineering","Microwave Engineering","Radar Systems","Communications Systems","Wireless Communications","5G/6G","Optical Communications","Satellite Communications","Deep Space Communications","Information Theory","Coding Theory","Error Correction","Compression","Encryption","Network Security","Cybersecurity"]
FEATURES={1560+i:n for i,n in enumerate(NAMES)}

DISCLAIMER=("Engineering decision support only. A qualified engineer must verify inputs, units, standards, safety controls, model limits and the original evidence before use.")
BETZ_LIMIT=0.593
LIGHT_SPEED_M_S=299792458.0

def _finite(value:Any,name:str)->float:
    try:v=float(value)
    except (TypeError,ValueError):raise ValueError(f"{name} must be numeric")
    if not isfinite(v):raise ValueError(f"{name} must be finite")
    return v

def _req(d:dict[str,Any],*keys:str)->None:
    missing=[k for k in keys if d.get(k) in (None,[],{})]
    if missing:raise ValueError("missing required inputs: "+", ".join(missing))

def _num(d:dict[str,Any],key:str,unit:str|None=None,positive:bool=False,nonnegative:bool=False)->float:
    """Numeric input with optional unit and domain validation.

    Unit contract: when a canonical unit is declared, a caller-supplied
    '<key>_unit' field must match it exactly, so unit mismatch fails closed
    instead of silently converting a wrong-dimensioned value.
    """
    if d.get(key) is None:raise ValueError(f"missing required input: {key}")
    if unit is not None:
        declared=d.get(f"{key}_unit",unit)
        if declared!=unit:raise ValueError(f"unit mismatch for {key}: expected {unit}, got {declared}")
    v=_finite(d[key],key)
    if positive and v<=0:raise ValueError(f"{key} must be positive")
    if nonnegative and v<0:raise ValueError(f"{key} must be nonnegative")
    return v

def _fraction(d:dict[str,Any],key:str,lower_open:bool=True)->float:
    v=_num(d,key)
    lo=v<=0 if lower_open else v<0
    if lo or v>1:raise ValueError(f"{key} must be in (0, 1]")
    return v

def _base(fid:int,d:dict[str,Any])->dict[str,Any]:
    if fid not in FEATURES:raise ValueError("feature_id must be 1560-1609")
    if not d.get("standard") or not d.get("standard_source_url"):raise ValueError("standard and standard_source_url are required")
    return {"feature_id":fid,"concept":FEATURES[fid],"standard":d["standard"],"standard_source_url":d["standard_source_url"],"assumptions":list(d.get("assumptions",[])),"unknowns":list(d.get("unknowns",[])),"constraints":[],"review_required":True,"disclaimer":DISCLAIMER}

def _uncertainty(*drivers:str)->dict[str,Any]:
    return {"level":"not_quantified","drivers":list(drivers),"certification_or_physical_execution_claimed":False}

def _finish(fid:int,d:dict[str,Any],fn_name:str,analysis:dict[str,Any],boundary:str,constraints:list[str]|None=None,uncertainty:dict[str,Any]|None=None)->dict[str,Any]:
    o=_base(fid,d)
    o["named_analysis"]=fn_name
    o["analysis"]=analysis
    o["boundary"]=boundary
    o["constraints"]=constraints or []
    o["uncertainty"]=uncertainty or _uncertainty("caller-supplied physical inputs","model simplifications","calibration and operating environment")
    return o

INSPECTION_BOUNDARY="Screening and measurement analysis on supplied data only. Indications are not defect characterization; a certified inspector controls method qualification, calibration, coverage, interpretation, disposition and the signed report."
DESIGN_BOUNDARY="Preliminary design analysis only. It does not create a construction-ready design, safety certification or control command. Qualified engineers verify topology, ratings, tolerances, protection, stability, layout, code and test evidence before energization."
ENERGY_BOUNDARY="Scenario model, not dispatch, interconnection approval, protection settings, equipment control or investment advice. Engineers and operators validate resource data, degradation, grid studies, safety, environmental impacts and contingencies."
COMMS_BOUNDARY="Analytical link/design estimate only, not a spectrum authorization, transmission command, orbital/radar tasking, guaranteed range or equipment certification. Validate propagation, interference, hardware, licensing, exposure and measured performance."
SECURITY_BOUNDARY="Defensive assessment only. No exploitation, credential access, scanning, encryption-key operation or network change is performed. Authorized security owners validate scope, controls, legal authority, testing and residual risk."

def analyze_bend_testing(d:dict[str,Any])->dict[str,Any]:
    """Row 1560 Bend Testing: three-point bend flexural stress and margin."""
    force=_num(d,"force_n","N",positive=True);span=_num(d,"span_mm","mm",positive=True)
    width=_num(d,"width_mm","mm",positive=True);depth=_num(d,"depth_mm","mm",positive=True)
    stress=3*force*span/(2*width*depth**2)
    analysis={"fixture":"three_point_bend","flexural_stress_mpa":stress,"section_modulus_mm3":width*depth**2/6}
    constraints=[]
    if d.get("allowable_flexural_stress_mpa") is not None:
        allowable=_num(d,"allowable_flexural_stress_mpa","MPa",positive=True)
        analysis["allowable_flexural_stress_mpa"]=allowable
        analysis["safety_margin_ratio"]=allowable/stress
        if allowable/stress<1:constraints.append("flexural stress exceeds supplied allowable: redesign or reject")
    return _finish(1560,d,"analyze_bend_testing",analysis,INSPECTION_BOUNDARY,constraints,_uncertainty("load cell calibration","specimen geometry tolerances","support span alignment"))

def analyze_non_destructive_testing(d:dict[str,Any])->dict[str,Any]:
    """Row 1561 NDT: method-to-defect capability screening."""
    _req(d,"method_selection","defect_type")
    method=str(d["method_selection"]);defect=str(d["defect_type"]).lower()
    surface_methods={"PT","MT","VT","ET","dye penetrant","magnetic particle","visual","eddy current"}
    volumetric="subsurface" in defect or "internal" in defect or "volumetric" in defect
    suited=not (volumetric and method in surface_methods)
    analysis={"method_selection":method,"target_defect":d["defect_type"],"destructive":False,"method_class":"volumetric" if method in {"UT","RT","ultrasonic","radiographic"} else "surface","method_suited_to_defect_location":suited}
    constraints=[] if suited else ["selected method is surface-only but the target defect is volumetric: select a volumetric method"]
    return _finish(1561,d,"analyze_non_destructive_testing",analysis,INSPECTION_BOUNDARY,constraints)

def analyze_ultrasonic_testing(d:dict[str,Any])->dict[str,Any]:
    """Row 1562 Ultrasonic Testing: time-of-flight thickness relationships."""
    thickness=_num(d,"thickness_mm","mm",positive=True);velocity=_num(d,"wave_velocity_m_s","m/s",positive=True)
    round_trip_us=2*(thickness/1000)/velocity*1e6
    analysis={"round_trip_time_us":round_trip_us,"couplant_required":True,"velocity_calibration_block_required":True}
    if d.get("measured_echo_time_us") is not None:
        echo=_num(d,"measured_echo_time_us","us",positive=True)
        estimated=echo/1e6*velocity/2*1000
        analysis["measured_echo_time_us"]=echo
        analysis["estimated_thickness_mm"]=estimated
        analysis["thickness_deviation_mm"]=estimated-thickness
    return _finish(1562,d,"analyze_ultrasonic_testing",analysis,INSPECTION_BOUNDARY,uncertainty=_uncertainty("wave velocity assumption","couplant and probe condition","instrument timebase calibration"))

def analyze_radiographic_testing(d:dict[str,Any])->dict[str,Any]:
    """Row 1563 Radiographic Testing: exposure geometry and safety boundary."""
    _req(d,"source_type","exposure_plan","controlled_area")
    analysis={"source_type":d["source_type"],"exposure_plan":d["exposure_plan"],"radiation_safety_boundary":d["controlled_area"],"controlled_area_verified_by_radiation_safety_officer":False}
    if all(d.get(k) is not None for k in ("focal_spot_mm","object_detector_distance_mm","source_object_distance_mm")):
        focal=_num(d,"focal_spot_mm","mm",positive=True);odd=_num(d,"object_detector_distance_mm","mm",nonnegative=True);sod=_num(d,"source_object_distance_mm","mm",positive=True)
        analysis["geometric_unsharpness_mm"]=focal*odd/sod
    return _finish(1563,d,"analyze_radiographic_testing",analysis,INSPECTION_BOUNDARY,["ionizing radiation: controlled area, dosimetry and regulatory licensing are mandatory and are not verified here"])

def analyze_magnetic_particle_testing(d:dict[str,Any])->dict[str,Any]:
    """Row 1564 Magnetic Particle Testing: ferromagnetic material boundary."""
    _req(d,"material","magnetization_direction")
    if d.get("ferromagnetic") is not True:raise ValueError("infeasible input: magnetic particle testing requires a verified ferromagnetic material")
    analysis={"material":d["material"],"ferromagnetic_material_verified":True,"magnetization_direction":d["magnetization_direction"],"indication_detectability_note":"defects must interrupt the induced flux; orientations parallel to flux may be missed","demagnetization_required_after_test":True}
    if d.get("test_piece_lift_n") is not None:
        lift=_num(d,"test_piece_lift_n","N",positive=True);required=_num(d,"required_lift_n","N",positive=True) if d.get("required_lift_n") is not None else 45.0
        analysis["lifting_force_margin_n"]=lift-required
        if lift<required:raise ValueError("infeasible input: magnetic particle test piece lifting force below the required margin")
    return _finish(1564,d,"analyze_magnetic_particle_testing",analysis,INSPECTION_BOUNDARY,["surface or near-surface ferromagnetic discontinuities only"])

def analyze_dye_penetrant_testing(d:dict[str,Any])->dict[str,Any]:
    """Row 1565 Dye Penetrant Testing: dwell-time window screening."""
    penetrant=_num(d,"penetrant_dwell_minutes","min",positive=True);developer=_num(d,"developer_dwell_minutes","min",positive=True)
    analysis={"penetrant_dwell_minutes":penetrant,"developer_dwell_minutes":developer,"surface_breaking_only":True,"pre_cleaning_required":True}
    constraints=[]
    if not 5<=penetrant<=30:constraints.append("penetrant dwell outside the typical 5-30 minute qualified window: confirm against the written procedure")
    if not 1<=developer<=30:constraints.append("developer dwell outside the typical 1-30 minute window: confirm against the written procedure")
    return _finish(1565,d,"analyze_dye_penetrant_testing",analysis,INSPECTION_BOUNDARY,constraints)

def analyze_eddy_current_testing(d:dict[str,Any])->dict[str,Any]:
    """Row 1566 Eddy Current Testing: skin-depth (standard depth of penetration)."""
    frequency=_num(d,"probe_frequency_hz","Hz",positive=True)
    _req(d,"conductivity_reference")
    analysis={"probe_frequency_hz":frequency,"conductivity_reference":d["conductivity_reference"],"skin_effect_considered":True,"phase_analysis_required_for_characterization":True}
    if d.get("conductivity_s_m") is not None:
        sigma=_num(d,"conductivity_s_m","S/m",positive=True);mur=_num(d,"relative_permeability",positive=True) if d.get("relative_permeability") is not None else 1.0
        delta_m=1/sqrt(pi*frequency*4e-7*pi*mur*sigma)
        analysis["standard_depth_of_penetration_mm"]=delta_m*1000
    return _finish(1566,d,"analyze_eddy_current_testing",analysis,INSPECTION_BOUNDARY,uncertainty=_uncertainty("probe lift-off","material conductivity and permeability spread","instrument calibration"))

def analyze_acoustic_emission_testing(d:dict[str,Any])->dict[str,Any]:
    """Row 1567 Acoustic Emission Testing: sensor array localization feasibility."""
    _req(d,"sensor_locations","threshold_db")
    sensors=list(d["sensor_locations"]);threshold=_num(d,"threshold_db","dB",positive=True)
    count=len(sensors)
    analysis={"sensor_count":count,"threshold_db":threshold,"source_location_requires_triangulation":True,"planar_localization_feasible":count>=3}
    constraints=[] if count>=3 else ["fewer than three sensors: planar source localization by triangulation is not feasible with this array"]
    return _finish(1567,d,"analyze_acoustic_emission_testing",analysis,INSPECTION_BOUNDARY,constraints)

def analyze_thermography(d:dict[str,Any])->dict[str,Any]:
    """Row 1568 Thermography: emissivity-corrected temperature difference."""
    emissivity=_fraction(d,"emissivity")
    surface=_num(d,"surface_temperature_c","C");reference=_num(d,"reference_temperature_c","C")
    analysis={"delta_temperature_c":surface-reference,"emissivity":emissivity,"reflected_temperature_correction_required":True,"quantitative_measurement_requires_thermal_tuning":True}
    return _finish(1568,d,"analyze_thermography",analysis,INSPECTION_BOUNDARY,uncertainty=_uncertainty("emissivity estimate","reflected apparent temperature","camera drift and focus"))

def analyze_visual_inspection(d:dict[str,Any])->dict[str,Any]:
    """Row 1569 Visual Inspection: zone coverage and lighting adequacy."""
    _req(d,"inspection_zones")
    zones=list(d["inspection_zones"]);lighting=_num(d,"lighting_lux","lux",positive=True)
    analysis={"zone_count":len(zones),"lighting_lux":lighting,"direct_and_remote_aids_recorded":True,"lighting_adequate":lighting>=500}
    constraints=[] if lighting>=500 else ["lighting below 500 lux: general visual inspection lighting minimum not met"]
    return _finish(1569,d,"analyze_visual_inspection",analysis,INSPECTION_BOUNDARY,constraints)

def analyze_electrical_engineering(d:dict[str,Any])->dict[str,Any]:
    """Row 1570 Electrical Engineering: requirements-to-hazard architecture review."""
    _req(d,"requirements","hazards")
    requirements=list(d["requirements"]);hazards=list(d["hazards"])
    mitigations=set(d.get("mitigated_hazards",[]))
    unmitigated=[h for h in hazards if h not in mitigations]
    analysis={"requirement_count":len(requirements),"hazard_count":len(hazards),"unmitigated_hazards":unmitigated,"architecture_review":"required"}
    constraints=[f"hazard '{h}' has no recorded mitigation" for h in unmitigated]
    return _finish(1570,d,"analyze_electrical_engineering",analysis,DESIGN_BOUNDARY,constraints)

def analyze_circuit_design(d:dict[str,Any])->dict[str,Any]:
    """Row 1571 Circuit Design: netlist power-budget and ERC screening."""
    _req(d,"netlist")
    supply=_num(d,"supply_v","V",positive=True);netlist=list(d["netlist"])
    analysis={"net_count":len(netlist),"supply_v":supply,"erc_required":True}
    if d.get("loads"):
        currents=[_finite(x,"load current_a") if isinstance(x,(int,float)) else _finite(x.get("current_a"),"load current_a") for x in d["loads"]]
        if any(c<0 for c in currents):raise ValueError("load currents must be nonnegative")
        analysis["total_load_current_a"]=sum(currents)
        analysis["total_load_power_w"]=sum(currents)*supply
        if d.get("supply_current_limit_a") is not None:
            limit=_num(d,"supply_current_limit_a","A",positive=True)
            analysis["supply_current_margin_a"]=limit-analysis["total_load_current_a"]
            if analysis["supply_current_margin_a"]<0:raise ValueError("infeasible input: total load current exceeds the supply current limit")
    return _finish(1571,d,"analyze_circuit_design",analysis,DESIGN_BOUNDARY)

def analyze_pcb_design(d:dict[str,Any])->dict[str,Any]:
    """Row 1572 PCB Design: layer stack and voltage clearance screening."""
    layers=int(_num(d,"layers",positive=True));clearance=_num(d,"clearance_mm","mm",positive=True)
    analysis={"layer_count":layers,"minimum_clearance_mm":clearance,"drc_required":True}
    if d.get("voltage_v") is not None:
        voltage=_num(d,"voltage_v","V",nonnegative=True)
        required=0.13+0.005*voltage
        analysis["voltage_v"]=voltage
        analysis["required_clearance_mm"]=required
        analysis["clearance_margin_mm"]=clearance-required
        if clearance<required:raise ValueError("infeasible input: supplied clearance is below the required spacing for the declared voltage")
    return _finish(1572,d,"analyze_pcb_design",analysis,DESIGN_BOUNDARY)

def analyze_signal_processing(d:dict[str,Any])->dict[str,Any]:
    """Row 1573 Signal Processing: Nyquist sampling adequacy."""
    fs=_num(d,"sample_rate_hz","Hz",positive=True);fmax=_num(d,"highest_signal_hz","Hz",positive=True)
    ratio=fs/fmax
    analysis={"nyquist_rate_hz":2*fmax,"nyquist_ratio":ratio,"aliases_without_filter":ratio<2,"anti_alias_filter_required":ratio<2.5}
    constraints=[] if ratio>=2 else ["sample rate below the Nyquist rate: captured spectrum aliases and cannot be reconstructed"]
    return _finish(1573,d,"analyze_signal_processing",analysis,DESIGN_BOUNDARY,constraints)

def analyze_control_systems(d:dict[str,Any])->dict[str,Any]:
    """Row 1574 Control Systems: plant pole screening before loop design."""
    _req(d,"plant_poles","controller_type")
    poles=[_finite(p,"plant pole") for p in d["plant_poles"]]
    unstable=[p for p in poles if p>0]
    analysis={"plant_poles":poles,"controller_type":d["controller_type"],"open_loop_unstable_poles":unstable,"closed_loop_stability_unverified":True,"stability_margins_must_be_measured_or_simulated":True}
    constraints=["plant has right-half-plane poles: the loop must be actively stabilized and verified" if unstable else "open-loop plant poles are stable; closed-loop margins still unverified"]
    return _finish(1574,d,"analyze_control_systems",analysis,DESIGN_BOUNDARY,constraints)

def analyze_power_electronics(d:dict[str,Any])->dict[str,Any]:
    """Row 1575 Power Electronics: conversion ratio and loss screening."""
    vin=_num(d,"input_v","V",positive=True);vout=_num(d,"output_v","V",positive=True);pout=_num(d,"output_w","W",positive=True)
    analysis={"conversion_ratio":vout/vin,"output_w":pout,"output_current_a":pout/vout,"switching_loss_measurement_required":True,"thermal_design_required":True}
    if d.get("losses_w") is not None:
        losses=_num(d,"losses_w","W",nonnegative=True)
        if pout+losses<=0:raise ValueError("infeasible input: nonpositive converter input power")
        analysis["estimated_efficiency"]=pout/(pout+losses)
        if analysis["estimated_efficiency"]>1:raise ValueError("infeasible input: converter efficiency cannot exceed 1")
    return _finish(1575,d,"analyze_power_electronics",analysis,DESIGN_BOUNDARY)

def analyze_motor_control(d:dict[str,Any])->dict[str,Any]:
    """Row 1576 Motor Control: current-limit and torque screening."""
    _req(d,"motor_type")
    rated=_num(d,"rated_current_a","A",positive=True);speed=_num(d,"speed_rpm","rpm",positive=True)
    analysis={"motor_type":d["motor_type"],"rated_current_a":rated,"speed_rpm":speed,"current_limit_required":True,"overspeed_protection_required":True}
    if d.get("commanded_current_a") is not None:
        commanded=_num(d,"commanded_current_a","A",nonnegative=True)
        if commanded>rated:raise ValueError("infeasible input: commanded current exceeds the motor rated current")
        analysis["commanded_current_a"]=commanded
        analysis["current_margin_a"]=rated-commanded
    if d.get("power_w") is not None:
        power=_num(d,"power_w","W",nonnegative=True)
        analysis["estimated_torque_nm"]=power*60/(2*pi*speed)
    return _finish(1576,d,"analyze_motor_control",analysis,DESIGN_BOUNDARY)

def analyze_power_systems(d:dict[str,Any])->dict[str,Any]:
    """Row 1577 Power Systems: generation-load balance screening."""
    _req(d,"buses","loads_mw","generation_mw")
    buses=list(d["buses"]);loads=[_num({"v":x},"v","MW",nonnegative=True) for x in d["loads_mw"]];generation=[_num({"v":x},"v","MW",nonnegative=True) for x in d["generation_mw"]]
    balance=sum(generation)-sum(loads)
    analysis={"bus_count":len(buses),"total_load_mw":sum(loads),"total_generation_mw":sum(generation),"power_balance_mw":balance,"load_flow_required":True,"n_minus_1_contingency_study_required":True}
    constraints=[] if abs(balance)<=0.05*max(sum(loads),1e-9) else ["generation-load imbalance exceeds 5% of load: dispatch or shedding study required before operation"]
    return _finish(1577,d,"analyze_power_systems",analysis,ENERGY_BOUNDARY,constraints)

def analyze_renewable_energy(d:dict[str,Any])->dict[str,Any]:
    """Row 1578 Renewable Energy: capacity factor feasibility."""
    _req(d,"technology")
    capacity=_num(d,"capacity_kw","kW",positive=True);annual=_num(d,"annual_energy_kwh","kWh",nonnegative=True)
    factor=annual/(capacity*8760)
    if factor>1:raise ValueError("infeasible input: annual energy implies a capacity factor above 1")
    analysis={"technology":d["technology"],"capacity_factor":factor,"resource_variability_unmodeled":True}
    return _finish(1578,d,"analyze_renewable_energy",analysis,ENERGY_BOUNDARY)

def analyze_solar_power(d:dict[str,Any])->dict[str,Any]:
    """Row 1579 Solar Power: irradiance-to-energy estimate."""
    irradiance=_num(d,"irradiance_kwh_m2","kWh/m2",positive=True);area=_num(d,"area_m2","m2",positive=True);efficiency=_fraction(d,"efficiency")
    analysis={"estimated_energy_kwh":irradiance*area*efficiency,"plane_of_array_irradiance_kwh_m2":irradiance,"shading_study_required":True,"soiling_and_temperature_derates_unmodeled":True}
    return _finish(1579,d,"analyze_solar_power",analysis,ENERGY_BOUNDARY)

def analyze_wind_power(d:dict[str,Any])->dict[str,Any]:
    """Row 1580 Wind Power: Betz-limited aerodynamic power."""
    density=_num(d,"air_density","kg/m3",positive=True);area=_num(d,"swept_area_m2","m2",positive=True);speed=_num(d,"wind_speed_m_s","m/s",positive=True)
    cp=_num(d,"power_coefficient",positive=True)
    if cp>BETZ_LIMIT:raise ValueError("infeasible input: power coefficient exceeds the Betz limit (0.593)")
    analysis={"wind_power_w":0.5*density*area*speed**3*cp,"betz_limit_power_w":0.5*density*area*speed**3*BETZ_LIMIT,"weibull_resource_study_required":True,"cut_in_cut_out_unmodeled":True}
    return _finish(1580,d,"analyze_wind_power",analysis,ENERGY_BOUNDARY)

def analyze_hydro_power(d:dict[str,Any])->dict[str,Any]:
    """Row 1581 Hydro Power: hydraulic power from flow and head."""
    flow=_num(d,"flow_m3_s","m3/s",positive=True);head=_num(d,"head_m","m",positive=True);efficiency=_fraction(d,"efficiency")
    analysis={"hydraulic_power_w":1000*9.80665*flow*head*efficiency,"environmental_flow_required":True,"cavitation_review_required":True}
    return _finish(1581,d,"analyze_hydro_power",analysis,ENERGY_BOUNDARY)

def analyze_geothermal(d:dict[str,Any])->dict[str,Any]:
    """Row 1582 Geothermal: enthalpy-drop thermal power."""
    mass=_num(d,"mass_flow_kg_s","kg/s",positive=True);enthalpy=_num(d,"enthalpy_drop_kj_kg","kJ/kg",positive=True);efficiency=_fraction(d,"efficiency")
    analysis={"thermal_power_kw":mass*enthalpy*efficiency,"reservoir_reinjection_review":True,"scaling_and_corrosion_review_required":True}
    return _finish(1582,d,"analyze_geothermal",analysis,ENERGY_BOUNDARY)

def analyze_energy_storage(d:dict[str,Any])->dict[str,Any]:
    """Row 1583 Energy Storage: charge/discharge duration screening."""
    capacity=_num(d,"capacity_kwh","kWh",positive=True);charge=_num(d,"charge_kw","kW",positive=True);discharge=_num(d,"discharge_kw","kW",positive=True)
    analysis={"charge_duration_h":capacity/charge,"discharge_duration_h":capacity/discharge,"power_to_energy_ratio":discharge/capacity,"round_trip_efficiency_unmodeled":True}
    return _finish(1583,d,"analyze_energy_storage",analysis,ENERGY_BOUNDARY)

def analyze_battery_technology(d:dict[str,Any])->dict[str,Any]:
    """Row 1584 Battery Technology: usable energy with DoD boundary."""
    ah=_num(d,"capacity_ah","Ah",positive=True);voltage=_num(d,"nominal_v","V",positive=True);dod=_fraction(d,"depth_of_discharge")
    analysis={"nameplate_energy_wh":ah*voltage,"usable_energy_wh":ah*voltage*dod,"depth_of_discharge":dod,"thermal_runaway_controls_required":True,"bms_required":True}
    return _finish(1584,d,"analyze_battery_technology",analysis,ENERGY_BOUNDARY,["usable energy assumes the declared depth of discharge; cycle-life impact of DoD is not modeled"])

def analyze_fuel_cells(d:dict[str,Any])->dict[str,Any]:
    """Row 1585 Fuel Cells: stack electrical efficiency boundary."""
    voltage=_num(d,"stack_voltage_v","V",positive=True);current=_num(d,"current_a","A",positive=True);fuel=_num(d,"fuel_input_kw","kW",positive=True)
    efficiency=voltage*current/1000/fuel
    if efficiency>1:raise ValueError("infeasible input: computed fuel cell efficiency exceeds 1")
    analysis={"stack_electrical_power_kw":voltage*current/1000,"electrical_efficiency":efficiency,"hydrogen_safety_review":True,"water_and_thermal_management_review_required":True}
    return _finish(1585,d,"analyze_fuel_cells",analysis,ENERGY_BOUNDARY)

def analyze_supercapacitors(d:dict[str,Any])->dict[str,Any]:
    """Row 1586 Supercapacitors: stored energy and voltage derating."""
    capacitance=_num(d,"capacitance_f","F",positive=True);voltage=_num(d,"voltage_v","V",positive=True)
    analysis={"stored_energy_j":0.5*capacitance*voltage**2,"usable_energy_note":"full discharge to 0 V is impractical; usable energy depends on the minimum operating voltage","voltage_derating_required":True,"cell_balancing_required":True}
    if d.get("rated_voltage_v") is not None:
        rated=_num(d,"rated_voltage_v","V",positive=True)
        if voltage>rated:raise ValueError("infeasible input: operating voltage exceeds the supercapacitor rated voltage")
        analysis["rated_voltage_v"]=rated
        analysis["voltage_margin_v"]=rated-voltage
    return _finish(1586,d,"analyze_supercapacitors",analysis,ENERGY_BOUNDARY)

def analyze_smart_grid(d:dict[str,Any])->dict[str,Any]:
    """Row 1587 Smart Grid: telemetry and fail-safe objective screening."""
    _req(d,"telemetry_points","control_objectives")
    points=list(d["telemetry_points"]);objectives=list(d["control_objectives"])
    analysis={"telemetry_count":len(points),"control_objectives":objectives,"cyber_physical_fail_safe_required":True,"telecontrol_commands_not_issued":True}
    return _finish(1587,d,"analyze_smart_grid",analysis,ENERGY_BOUNDARY,["analytics only: no telecontrol, switching or dispatch command is produced"])

def analyze_microgrids(d:dict[str,Any])->dict[str,Any]:
    """Row 1588 Microgrids: islanded supply adequacy."""
    load=_num(d,"critical_load_kw","kW",nonnegative=True);generation=_num(d,"island_generation_kw","kW",nonnegative=True)
    margin=generation-load
    analysis={"island_margin_kw":margin,"island_supply_adequate":margin>=0,"black_start_plan_required":True,"resynchronization_protection_required":True}
    constraints=[] if margin>=0 else ["islanded generation below critical load: load shedding scheme required"]
    return _finish(1588,d,"analyze_microgrids",analysis,ENERGY_BOUNDARY,constraints)

def analyze_hvdc(d:dict[str,Any])->dict[str,Any]:
    """Row 1589 HVDC: dc current from power and voltage."""
    voltage=_num(d,"dc_voltage_kv","kV",positive=True);power=_num(d,"power_mw","MW",positive=True);distance=_num(d,"distance_km","km",positive=True)
    analysis={"dc_current_a":power*1e6/(voltage*1000),"transmission_distance_km":distance,"converter_and_line_loss_study_required":True,"reactive_support_at_converter_required":True}
    return _finish(1589,d,"analyze_hvdc",analysis,ENERGY_BOUNDARY)

def analyze_facts(d:dict[str,Any])->dict[str,Any]:
    """Row 1590 FACTS: reactive compensation rating screening."""
    _req(d,"device_type")
    voltage=_num(d,"bus_voltage_kv","kV",positive=True);reactive=_num(d,"reactive_power_mvar","Mvar")
    analysis={"device_type":d["device_type"],"bus_voltage_kv":voltage,"reactive_power_mvar":reactive,"dynamic_stability_study_required":True,"protection_coordination_review_required":True}
    if d.get("device_rating_mvar") is not None:
        rating=_num(d,"device_rating_mvar","Mvar",positive=True)
        if abs(reactive)>rating:raise ValueError("infeasible input: requested reactive power exceeds the FACTS device rating")
        analysis["device_rating_mvar"]=rating
        analysis["rating_margin_mvar"]=rating-abs(reactive)
    return _finish(1590,d,"analyze_facts",analysis,ENERGY_BOUNDARY)

def analyze_power_quality(d:dict[str,Any])->dict[str,Any]:
    """Row 1591 Power Quality: voltage deviation and THD screening."""
    rms=_num(d,"rms_voltage_v","V",nonnegative=True);nominal=_num(d,"nominal_voltage_v","V",positive=True);thd=_num(d,"thd_percent","%",nonnegative=True)
    deviation=100*(rms-nominal)/nominal
    analysis={"voltage_deviation_percent":deviation,"thd_percent":thd,"within_typical_plus_minus_10_percent_band":abs(deviation)<=10,"thd_above_8_percent_general_system_reference":thd>8,"harmonic_source_identification_required":thd>8}
    constraints=[]
    if abs(deviation)>10:constraints.append("voltage deviation outside the typical +/-10% band: investigate regulation and loading")
    if thd>8:constraints.append("THD above the 8% general-system reference level: harmonic study required")
    return _finish(1591,d,"analyze_power_quality",analysis,ENERGY_BOUNDARY,constraints)

def analyze_electromagnetic_compatibility(d:dict[str,Any])->dict[str,Any]:
    """Row 1592 EMC: emission margin screening; no compliance claim."""
    limit=_num(d,"emission_limit_dbuv","dBuV");measured=_num(d,"measured_dbuv","dBuV");immunity=_num(d,"immunity_level_v_m","V/m",positive=True)
    margin=limit-measured
    analysis={"emission_margin_db":margin,"emission_below_limit":margin>=0,"design_margin_met_6db":margin>=6,"immunity_level_v_m":immunity,"compliance_claimed":False,"accredited_lab_measurement_required":True}
    constraints=[] if margin>=6 else ["emission margin below 6 dB design margin: layout, filtering or shielding review required"]
    return _finish(1592,d,"analyze_electromagnetic_compatibility",analysis,DESIGN_BOUNDARY,constraints)

def analyze_antenna_design(d:dict[str,Any])->dict[str,Any]:
    """Row 1593 Antenna Design: gain vs beamwidth consistency boundary."""
    frequency=_num(d,"frequency_hz","Hz",positive=True);gain=_num(d,"gain_dbi","dBi");beam=_num(d,"beamwidth_deg","deg",positive=True)
    if beam>360:raise ValueError("beamwidth_deg must be at most 360")
    max_directivity_dbi=10*log10(41253/(beam**2))
    if gain>max_directivity_dbi+0.5:raise ValueError("infeasible input: declared gain exceeds the directivity consistent with the declared beamwidth")
    analysis={"wavelength_m":LIGHT_SPEED_M_S/frequency,"gain_dbi":gain,"beamwidth_deg":beam,"approximate_max_directivity_dbi":max_directivity_dbi,"pattern_measurement_required":True}
    return _finish(1593,d,"analyze_antenna_design",analysis,COMMS_BOUNDARY)

def analyze_rf_engineering(d:dict[str,Any])->dict[str,Any]:
    """Row 1594 RF Engineering: thermal noise floor with noise figure."""
    _num(d,"frequency_hz","Hz",positive=True);nf=_num(d,"noise_figure_db","dB",nonnegative=True);bw=_num(d,"bandwidth_hz","Hz",positive=True)
    analysis={"thermal_noise_floor_dbm":-174+10*log10(bw)+nf,"noise_figure_db":nf,"linearity_test_required":True,"cascaded_noise_analysis_required":True}
    return _finish(1594,d,"analyze_rf_engineering",analysis,COMMS_BOUNDARY)

def analyze_microwave_engineering(d:dict[str,Any])->dict[str,Any]:
    """Row 1595 Microwave Engineering: S-parameter passivity screening."""
    _num(d,"frequency_hz","Hz",positive=True)
    _req(d,"s_parameters")
    params=list(d["s_parameters"])
    analysis={"s_parameter_count":len(params),"fixture_deembedding_required":True,"vna_calibration_required":True}
    magnitudes=[]
    for p in params:
        if isinstance(p,dict) and p.get("magnitude") is not None:
            mag=_num({"v":p["magnitude"]},"v",nonnegative=True)
            if mag>1:raise ValueError("infeasible input: S-parameter magnitude above 1 violates passivity for a passive network")
            magnitudes.append({"name":p.get("name","S?"),"magnitude":mag})
    if magnitudes:analysis["passivity_screened_parameters"]=magnitudes
    return _finish(1595,d,"analyze_microwave_engineering",analysis,COMMS_BOUNDARY)

def analyze_radar_systems(d:dict[str,Any])->dict[str,Any]:
    """Row 1596 Radar Systems: bandwidth needed for range resolution."""
    range_m=_num(d,"range_m","m",positive=True);resolution=_num(d,"range_resolution_m","m",positive=True);velocity=_num(d,"velocity_resolution_m_s","m/s",positive=True)
    analysis={"required_bandwidth_hz":LIGHT_SPEED_M_S/(2*resolution),"instrumented_range_m":range_m,"velocity_resolution_m_s":velocity,"spectrum_authorization_required":True,"emission_control_review_required":True}
    return _finish(1596,d,"analyze_radar_systems",analysis,COMMS_BOUNDARY,["radar analysis only: no transmission is commanded and spectrum use requires authorization"])

def analyze_communications_systems(d:dict[str,Any])->dict[str,Any]:
    """Row 1597 Communications Systems: source rate vs channel capacity."""
    source=_num(d,"source_rate_bps","bps",positive=True);capacity=_num(d,"channel_capacity_bps","bps",positive=True)
    margin=capacity-source
    analysis={"capacity_margin_bps":margin,"channel_supports_source":margin>=0,"end_to_end_error_budget_required":True}
    constraints=[] if margin>=0 else ["channel capacity below source rate: add coding/compression or a wider channel"]
    return _finish(1597,d,"analyze_communications_systems",analysis,COMMS_BOUNDARY,constraints)

def analyze_wireless_communications(d:dict[str,Any])->dict[str,Any]:
    """Row 1598 Wireless Communications: fractional bandwidth screening."""
    carrier=_num(d,"carrier_hz","Hz",positive=True);bw=_num(d,"bandwidth_hz","Hz",positive=True)
    _req(d,"modulation")
    if bw>carrier:raise ValueError("infeasible input: bandwidth exceeds the carrier frequency")
    analysis={"carrier_hz":carrier,"fractional_bandwidth":bw/carrier,"modulation":d["modulation"],"link_test_required":True,"regulatory_emission_mask_review_required":True}
    return _finish(1598,d,"analyze_wireless_communications",analysis,COMMS_BOUNDARY)

def analyze_cellular_5g_6g(d:dict[str,Any])->dict[str,Any]:
    """Row 1599 5G/6G: numerology and MIMO layer screening."""
    carrier=_num(d,"carrier_hz","Hz",positive=True);scs=_num(d,"subcarrier_spacing_hz","Hz",positive=True);layers=int(_num(d,"mimo_layers",positive=True))
    analysis={"numerology_ratio":carrier/scs,"mimo_layers":layers,"band_determination_required":carrier>=1e9,"standards_release_required":True,"no_network_attach_or_signaling_performed":True}
    return _finish(1599,d,"analyze_cellular_5g_6g",analysis,COMMS_BOUNDARY,["3GPP release alignment and band plan must be confirmed by the radio engineer; Atlas performs no network signaling"])

def analyze_optical_communications(d:dict[str,Any])->dict[str,Any]:
    """Row 1600 Optical Communications: fiber attenuation budget."""
    wavelength=_num(d,"wavelength_nm","nm",positive=True);length=_num(d,"fiber_length_km","km",positive=True);attenuation=_num(d,"attenuation_db_km","dB/km",nonnegative=True)
    analysis={"fiber_loss_db":length*attenuation,"wavelength_nm":wavelength,"in_common_telecom_window":wavelength in (850,1310,1550) or 1260<=wavelength<=1625,"dispersion_budget_required":True,"eye_safety_class_review_required":True}
    return _finish(1600,d,"analyze_optical_communications",analysis,COMMS_BOUNDARY)

def analyze_satellite_communications(d:dict[str,Any])->dict[str,Any]:
    """Row 1601 Satellite Communications: free-space path loss estimate."""
    slant=_num(d,"slant_range_km","km",positive=True);frequency=_num(d,"frequency_hz","Hz",positive=True);eirp=_num(d,"eirp_dbw","dBW")
    fspl=92.45+20*log10(slant)+20*log10(frequency/1e9)
    analysis={"free_space_path_loss_db":fspl,"eirp_dbw":eirp,"rain_fade_margin_required":True,"itu_coordination_and_licensing_required":True}
    return _finish(1601,d,"analyze_satellite_communications",analysis,COMMS_BOUNDARY)

def analyze_deep_space_communications(d:dict[str,Any])->dict[str,Any]:
    """Row 1602 Deep Space Communications: light-time delay analysis."""
    distance=_num(d,"one_way_distance_km","km",positive=True);rate=_num(d,"data_rate_bps","bps",positive=True)
    light_time=distance*1000/LIGHT_SPEED_M_S
    analysis={"one_way_light_time_s":light_time,"round_trip_light_time_s":2*light_time,"data_rate_bps":rate,"delay_tolerant_protocol_required":True,"real_time_control_infeasible":light_time>1}
    return _finish(1602,d,"analyze_deep_space_communications",analysis,COMMS_BOUNDARY,["long light-time makes real-time control infeasible: autonomy and delay-tolerant networking are required"])

def analyze_information_theory(d:dict[str,Any])->dict[str,Any]:
    """Row 1603 Information Theory: Shannon entropy of a source."""
    _req(d,"symbol_probabilities")
    probs=[_finite(p,"symbol probability") for p in d["symbol_probabilities"]]
    if not probs or any(p<=0 or p>1 for p in probs):raise ValueError("symbol probabilities must be in (0, 1]")
    if abs(sum(probs)-1)>1e-6:raise ValueError("symbol probabilities must sum to 1")
    analysis={"entropy_bits_per_symbol":-sum(p*log2(p) for p in probs),"alphabet_size":len(probs),"source_coding_lower_bound":True}
    return _finish(1603,d,"analyze_information_theory",analysis,COMMS_BOUNDARY)

def analyze_coding_theory(d:dict[str,Any])->dict[str,Any]:
    """Row 1604 Coding Theory: minimum-distance error detection capability."""
    _req(d,"codewords")
    distance=int(_num(d,"minimum_distance",positive=True))
    analysis={"codeword_count":len(d["codewords"]),"minimum_distance":distance,"detectable_errors":distance-1,"bounded_distance_decoder_assumed":True}
    return _finish(1604,d,"analyze_coding_theory",analysis,COMMS_BOUNDARY)

def analyze_error_correction(d:dict[str,Any])->dict[str,Any]:
    """Row 1605 Error Correction: minimum-distance correction capability."""
    distance=int(_num(d,"minimum_distance",positive=True))
    analysis={"minimum_distance":distance,"correctable_errors":(distance-1)//2,"detectable_errors":distance-1,"decoder_validation_required":True}
    return _finish(1605,d,"analyze_error_correction",analysis,COMMS_BOUNDARY)

def analyze_compression(d:dict[str,Any])->dict[str,Any]:
    """Row 1606 Compression: ratio screening with lossless round-trip check."""
    original=_num(d,"original_bytes","bytes",positive=True);compressed=_num(d,"compressed_bytes","bytes",positive=True)
    lossless=bool(d.get("lossless"))
    analysis={"compression_ratio":original/compressed,"compressed_fraction":compressed/original,"lossless":lossless,"round_trip_test_required":lossless}
    constraints=["lossless claim with expansion: verify round-trip equality on the real payload"] if lossless and compressed>original else []
    return _finish(1606,d,"analyze_compression",analysis,COMMS_BOUNDARY,constraints)

DEPRECATED_ALGORITHMS={"des","rc4","3des","md5","sha1"}

def analyze_encryption(d:dict[str,Any])->dict[str,Any]:
    """Row 1607 Encryption: algorithm/key-strength screening; no key handling."""
    _req(d,"algorithm","mode")
    algorithm=str(d["algorithm"]);key_bits=int(_num(d,"key_bits",positive=True));mode=str(d["mode"])
    if algorithm.lower() in DEPRECATED_ALGORITHMS:raise ValueError(f"infeasible input: {algorithm} is deprecated and must not be selected")
    if key_bits<128:raise ValueError("infeasible input: key_bits below the 128-bit minimum")
    if mode.upper()=="ECB":raise ValueError("infeasible input: ECB mode leaks structure and is not an approved mode")
    analysis={"algorithm":algorithm,"key_bits":key_bits,"mode":mode,"key_material_handled":False,"approved_library_required":True,"formal_protocol_review_required":True}
    return _finish(1607,d,"analyze_encryption",analysis,SECURITY_BOUNDARY,["Atlas never generates, stores or operates key material; an approved cryptographic library and owner-controlled HSM/KMS are required"])

def analyze_network_security(d:dict[str,Any])->dict[str,Any]:
    """Row 1608 Network Security: zone/boundary control coverage."""
    _req(d,"zones","trust_boundaries","controls")
    zones=list(d["zones"]);boundaries=list(d["trust_boundaries"]);controls=list(d["controls"])
    guarded=set()
    for c in controls:
        if isinstance(c,dict):guarded.update(c.get("addresses",[]))
    unguarded=[b for b in boundaries if b not in guarded]
    analysis={"zone_count":len(zones),"trust_boundary_count":len(boundaries),"control_count":len(controls),"unguarded_trust_boundaries":unguarded,"deny_by_default":True,"segmentation_review_required":True}
    constraints=[f"trust boundary '{b}' has no mapped control" for b in unguarded]
    return _finish(1608,d,"analyze_network_security",analysis,SECURITY_BOUNDARY,constraints)

def analyze_cybersecurity(d:dict[str,Any])->dict[str,Any]:
    """Row 1609 Cybersecurity: defensive risk-register screening."""
    _req(d,"assets","threats","controls")
    assets=list(d["assets"]);threats=list(d["threats"]);controls=list(d["controls"])
    risks=[]
    for t in threats:
        likelihood=_finite(t.get("likelihood"),"likelihood");impact=_finite(t.get("impact"),"impact")
        if not (1<=likelihood<=5 and 1<=impact<=5):raise ValueError("likelihood and impact must be on the 1-5 risk scale")
        mapped=[c.get("id") for c in controls if isinstance(c,dict) and t.get("id") in c.get("addresses",[])]
        risks.append({"threat_id":t.get("id"),"asset_ids":t.get("asset_ids",[]),"likelihood":likelihood,"impact":impact,"inherent_score":likelihood*impact,"mapped_controls":mapped,"residual_status":"requires_validation"})
    analysis={"asset_count":len(assets),"threat_count":len(threats),"control_count":len(controls),"risk_register":risks,"authorized_defensive_scope_only":True,"written_authorization_required_for_any_testing":True}
    return _finish(1609,d,"analyze_cybersecurity",analysis,SECURITY_BOUNDARY)

ANALYSES:dict[int,Callable[[dict[str,Any]],dict[str,Any]]]={
    1560:analyze_bend_testing,1561:analyze_non_destructive_testing,1562:analyze_ultrasonic_testing,
    1563:analyze_radiographic_testing,1564:analyze_magnetic_particle_testing,1565:analyze_dye_penetrant_testing,
    1566:analyze_eddy_current_testing,1567:analyze_acoustic_emission_testing,1568:analyze_thermography,
    1569:analyze_visual_inspection,1570:analyze_electrical_engineering,1571:analyze_circuit_design,
    1572:analyze_pcb_design,1573:analyze_signal_processing,1574:analyze_control_systems,
    1575:analyze_power_electronics,1576:analyze_motor_control,1577:analyze_power_systems,
    1578:analyze_renewable_energy,1579:analyze_solar_power,1580:analyze_wind_power,
    1581:analyze_hydro_power,1582:analyze_geothermal,1583:analyze_energy_storage,
    1584:analyze_battery_technology,1585:analyze_fuel_cells,1586:analyze_supercapacitors,
    1587:analyze_smart_grid,1588:analyze_microgrids,1589:analyze_hvdc,1590:analyze_facts,
    1591:analyze_power_quality,1592:analyze_electromagnetic_compatibility,1593:analyze_antenna_design,
    1594:analyze_rf_engineering,1595:analyze_microwave_engineering,1596:analyze_radar_systems,
    1597:analyze_communications_systems,1598:analyze_wireless_communications,1599:analyze_cellular_5g_6g,
    1600:analyze_optical_communications,1601:analyze_satellite_communications,1602:analyze_deep_space_communications,
    1603:analyze_information_theory,1604:analyze_coding_theory,1605:analyze_error_correction,
    1606:analyze_compression,1607:analyze_encryption,1608:analyze_network_security,1609:analyze_cybersecurity,
}
assert len(ANALYSES)==50 and set(ANALYSES)==set(FEATURES)

def engineering_support_1560_1609(feature_id:int,data:dict[str,Any])->dict[str,Any]:
    """Dispatch one owner row to its named engineering analysis."""
    analysis=ANALYSES.get(feature_id)
    if analysis is None:raise ValueError("feature_id must be 1560-1609")
    return analysis(data)
