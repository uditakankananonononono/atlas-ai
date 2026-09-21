"""Traceable engineering workbench for owner feature rows 1560-1609.

Calculations operate only on supplied measurements/design assumptions. Outputs retain
units, provenance, acceptance criteria, uncertainty, and mandatory qualified review.
They never operate equipment, energize circuits, issue inspection certificates, or
perform offensive security actions.
"""
from __future__ import annotations
from math import log2,log10,isfinite
from typing import Any
NAMES=["Bend Testing","Non-Destructive Testing","Ultrasonic Testing","Radiographic Testing","Magnetic Particle Testing","Dye Penetrant Testing","Eddy Current Testing","Acoustic Emission Testing","Thermography","Visual Inspection","Electrical Engineering","Circuit Design","PCB Design","Signal Processing","Control Systems","Power Electronics","Motor Control","Power Systems","Renewable Energy","Solar Power","Wind Power","Hydro Power","Geothermal","Energy Storage","Battery Technology","Fuel Cells","Supercapacitors","Smart Grid","Microgrids","HVDC","FACTS","Power Quality","Electromagnetic Compatibility","Antenna Design","RF Engineering","Microwave Engineering","Radar Systems","Communications Systems","Wireless Communications","5G/6G","Optical Communications","Satellite Communications","Deep Space Communications","Information Theory","Coding Theory","Error Correction","Compression","Encryption","Network Security","Cybersecurity"]
FEATURES={1560+i:n for i,n in enumerate(NAMES)}
INSPECTION=set(range(1560,1570)); ELECTRICAL=set(range(1570,1578)); ENERGY=set(range(1578,1593)); COMMS=set(range(1593,1607)); SECURITY=set(range(1607,1610))
DISCLAIMER="Engineering decision support only. A qualified engineer must verify inputs, units, standards, safety controls, model limits and the original evidence before use."
def _finite(x:Any,name:str)->float:
 try:v=float(x)
 except (TypeError,ValueError):raise ValueError(f"{name} must be numeric")
 if not isfinite(v):raise ValueError(f"{name} must be finite")
 return v
def _base(fid:int,d:dict)->dict:
 if fid not in FEATURES:raise ValueError("feature_id must be 1560-1609")
 if not d.get("standard") or not d.get("standard_source_url"):raise ValueError("standard and standard_source_url are required")
 return {"feature_id":fid,"concept":FEATURES[fid],"standard":d["standard"],"standard_source_url":d["standard_source_url"],"assumptions":d.get("assumptions",[]),"unknowns":d.get("unknowns",[]),"review_required":True,"disclaimer":DISCLAIMER}
def _inspection(fid:int,d:dict)->dict:
 o=_base(fid,d); observations=d.get("observations",[]);criteria=d.get("acceptance_criteria",[])
 if not observations or not criteria:raise ValueError("observations and acceptance_criteria are required")
 evaluated=[]
 for x in observations:
  if not x.get("id") or not x.get("provenance"):raise ValueError("each observation needs id and provenance")
  value=_finite(x.get("value"),"observation value"); limit=next((c for c in criteria if c.get("metric")==x.get("metric")),None)
  verdict="not_evaluated" if not limit else "pass" if (value<=_finite(limit["maximum"],"maximum") if "maximum" in limit else value>=_finite(limit["minimum"],"minimum")) else "indication_for_review"
  evaluated.append({**x,"value":value,"criterion":limit,"screening_result":verdict})
 o.update({"observations":evaluated,"calibration":d.get("calibration",{}),"coverage":d.get("coverage",{}),"limitations":d.get("limitations",[]),"boundary":"Screening against supplied criteria only. Indications are not defect characterization; a certified inspector controls method qualification, calibration, coverage, interpretation, disposition and signed report."});return o
def _electrical(fid:int,d:dict)->dict:
 o=_base(fid,d);nodes=d.get("nodes",[]);components=d.get("components",[])
 if not nodes or not components:raise ValueError("nodes and components are required")
 voltage=_finite(d.get("voltage_v"),"voltage_v");current=_finite(d.get("current_a"),"current_a");pf=_finite(d.get("power_factor",1),"power_factor")
 if not 0<=pf<=1:raise ValueError("power_factor must be in [0,1]")
 loss=sum(_finite(c.get("loss_w",0),"loss_w") for c in components); apparent=abs(voltage*current); real=apparent*pf
 o.update({"nodes":nodes,"components":components,"calculations":{"apparent_power_va":apparent,"real_power_w":real,"declared_losses_w":loss,"efficiency":(real-loss)/real if real else None},"constraints":d.get("constraints",[]),"verification_plan":d.get("verification_plan",[]),"boundary":"Preliminary design analysis only. It does not create a construction-ready design, safety certification or control command. Qualified engineers verify topology, ratings, tolerances, protection, stability, layout, code and test evidence before energization."});return o
def _energy(fid:int,d:dict)->dict:
 o=_base(fid,d);series=d.get("resource_series",[]);assets=d.get("assets",[])
 if not series or not assets:raise ValueError("resource_series and assets are required")
 hours=sum(_finite(x.get("hours",0),"hours") for x in series); generated=sum(_finite(x.get("power_kw",0),"power_kw")*_finite(x.get("hours",0),"hours") for x in series); rated=sum(_finite(x.get("rated_kw",0),"rated_kw") for x in assets); denom=rated*hours
 demand=sum(_finite(x.get("energy_kwh",0),"energy_kwh") for x in d.get("demand",[]));
 o.update({"resource_series":series,"assets":assets,"energy_summary":{"generated_kwh":generated,"demand_kwh":demand,"net_kwh":generated-demand,"capacity_factor":generated/denom if denom else None},"constraints":d.get("constraints",[]),"protection_and_islanding":d.get("protection_and_islanding",[]),"boundary":"Scenario model, not dispatch, interconnection approval, protection settings, equipment control or investment advice. Engineers and operators validate resource data, degradation, grid studies, safety, environmental impacts and contingencies."});return o
def _comms(fid:int,d:dict)->dict:
 o=_base(fid,d);f=_finite(d.get("frequency_hz"),"frequency_hz");bw=_finite(d.get("bandwidth_hz"),"bandwidth_hz");signal=_finite(d.get("signal_dbm"),"signal_dbm");noise=_finite(d.get("noise_dbm"),"noise_dbm")
 if f<=0 or bw<=0:raise ValueError("frequency and bandwidth must be positive")
 snr_db=signal-noise;snr=10**(snr_db/10);capacity=bw*log2(1+snr);wavelength=299792458/f
 tx=_finite(d.get("tx_power_dbm",signal),"tx_power_dbm");gains=sum(_finite(x,"gain") for x in d.get("gains_db",[]));losses=sum(_finite(x,"loss") for x in d.get("losses_db",[]));received=tx+gains-losses
 o.update({"link_budget":{"tx_power_dbm":tx,"gains_db":gains,"losses_db":losses,"estimated_received_dbm":received,"declared_signal_dbm":signal,"noise_dbm":noise,"snr_db":snr_db},"physics":{"frequency_hz":f,"wavelength_m":wavelength,"bandwidth_hz":bw,"shannon_upper_bound_bps":capacity},"spectrum_or_channel":d.get("spectrum_or_channel",{}),"modulation_or_code":d.get("modulation_or_code",{}),"validation_plan":d.get("validation_plan",[]),"boundary":"Analytical link/design estimate only, not a spectrum authorization, transmission command, orbital/radar tasking, guaranteed range or equipment certification. Validate propagation, interference, hardware, licensing, exposure and measured performance."});return o
def _security(fid:int,d:dict)->dict:
 o=_base(fid,d);assets=d.get("assets",[]);threats=d.get("threats",[]);controls=d.get("controls",[])
 if not assets or not threats:raise ValueError("assets and threats are required")
 risks=[]
 for t in threats:
  likelihood=_finite(t.get("likelihood"),"likelihood");impact=_finite(t.get("impact"),"impact");matched=[c for c in controls if t.get("id") in c.get("addresses",[])];risks.append({"threat_id":t.get("id"),"asset_ids":t.get("asset_ids",[]),"likelihood":likelihood,"impact":impact,"inherent_score":likelihood*impact,"mapped_controls":[c.get("id") for c in matched],"residual_status":"requires_validation"})
 o.update({"assets":assets,"threat_model":risks,"controls":controls,"data_classification":d.get("data_classification",{}),"incident_plan":d.get("incident_plan",[]),"boundary":"Defensive assessment only. No exploitation, credential access, scanning, encryption-key operation or network change is performed. Authorized security owners validate scope, controls, legal authority, testing and residual risk."});return o
def engineering_support_1560_1609(feature_id:int,data:dict[str,Any])->dict[str,Any]:
 if feature_id in INSPECTION:return _inspection(feature_id,data)
 if feature_id in ELECTRICAL:return _electrical(feature_id,data)
 if feature_id in ENERGY:return _energy(feature_id,data)
 if feature_id in COMMS:return _comms(feature_id,data)
 if feature_id in SECURITY:return _security(feature_id,data)
 raise ValueError("feature_id must be 1560-1609")
