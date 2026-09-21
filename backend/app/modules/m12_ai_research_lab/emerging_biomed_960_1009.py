"""Fifty preclinical biomedical decision-support engines (ledger rows 960-1009).

The engines only analyse caller-supplied observations. They never diagnose, prescribe,
operate a device, design an executable wet-lab protocol, or claim evidence not supplied.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
import math
import statistics

NAMES = """regenerative_medicine stem_cell_therapy gene_therapy crispr_applications base_editing prime_editing epigenome_editing synthetic_biology metabolic_engineering protein_engineering directed_evolution enzyme_design antibody_design vaccine_design drug_discovery drug_repurposing personalized_medicine pharmacogenomics microbiome_engineering probiotic_design phage_therapy immunotherapy car_t_therapy checkpoint_inhibitors mrna_therapeutics nanomedicine targeted_drug_delivery theranostics liquid_biopsy wearable_sensors implantable_devices brain_computer_interfaces neural_prosthetics cochlear_implants retinal_implants deep_brain_stimulation optogenetics chemogenetics neurofeedback brain_mapping connectomics neural_decoding neural_encoding memory_prosthetics cognitive_enhancement nootropics neurostimulation transcranial_magnetic_stimulation focused_ultrasound neural_dust""".split()
ROWS = dict(zip(NAMES, range(960, 1010)))

@dataclass(frozen=True)
class Engine:
    row: int
    title: str
    mechanism: str
    evaluate: Callable[[dict[str, Any]], dict[str, Any]]


def _n(d: dict[str, Any], key: str, *, low: float | None = None, high: float | None = None) -> float:
    value = d.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    value = float(value)
    if low is not None and value < low or high is not None and value > high:
        raise ValueError(f"{key} outside allowed range [{low}, {high}]")
    return value


def _vector(d: dict[str, Any], key: str, *, minimum: int = 2, low: float | None = None) -> list[float]:
    values = d.get(key)
    if not isinstance(values, list) or len(values) < minimum:
        raise ValueError(f"{key} requires at least {minimum} observations")
    result = []
    for i, value in enumerate(values):
        result.append(_n({key: value}, key, low=low))
    return result


def _unit(d: dict[str, Any], quantity: str, allowed: set[str]) -> str:
    units = d.get("units")
    if not isinstance(units, dict) or units.get(quantity) not in allowed:
        raise ValueError(f"units.{quantity} must be one of {sorted(allowed)}")
    return str(units[quantity])


def _ratio(num: float, den: float, label: str) -> float:
    if den <= 0:
        raise ValueError(f"{label} denominator must be positive")
    return num / den


def _corr(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("paired vectors must have equal length")
    ma, mb = statistics.mean(a), statistics.mean(b)
    den = math.sqrt(sum((x-ma)**2 for x in a) * sum((y-mb)**2 for y in b))
    return sum((x-ma)*(y-mb) for x, y in zip(a, b))/den if den else 0.0


def _paired(change_name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def evaluate(d: dict[str, Any]) -> dict[str, Any]:
        before, after = _vector(d, "baseline_scores"), _vector(d, "followup_scores")
        if len(before) != len(after): raise ValueError("baseline_scores and followup_scores must align")
        delta = [b-a for a,b in zip(before,after)]
        return {change_name: statistics.mean(delta), "paired_changes": delta, "sample_size": len(delta)}
    return evaluate


def _editing(metric: str, extra: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def evaluate(d: dict[str, Any]) -> dict[str, Any]:
        edited, total = _n(d,"edited_reads",low=0), _n(d,"total_reads",low=1)
        affected = _n(d,extra,low=0)
        if edited > total or affected > total: raise ValueError("read counts cannot exceed total_reads")
        return {metric: edited/total, f"{extra}_rate": affected/total, "analysed_reads": int(total)}
    return evaluate


def _candidate_engine(score_field: str, criteria: tuple[str, ...]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Rank supplied, dimensionless evidence scores; does not generate a candidate."""
    def evaluate(d: dict[str, Any]) -> dict[str, Any]:
        candidates = d.get("candidates")
        if not isinstance(candidates,list) or not candidates: raise ValueError("candidates must be a nonempty list")
        weights=d.get("weights")
        if not isinstance(weights,dict) or set(weights)!=set(criteria): raise ValueError(f"weights must contain exactly {list(criteria)}")
        ws={k:_n(weights,k,low=0,high=1) for k in criteria}
        if not math.isclose(sum(ws.values()),1.0,abs_tol=1e-6): raise ValueError("weights must sum to 1")
        ranked=[]
        for c in candidates:
            if not isinstance(c,dict) or not isinstance(c.get("id"),str) or not c["id"]: raise ValueError("each candidate requires a nonempty id")
            scores=c.get("scores")
            if not isinstance(scores,dict) or set(scores)!=set(criteria): raise ValueError(f"candidate scores must contain exactly {list(criteria)}")
            vals={k:_n(scores,k,low=0,high=1) for k in criteria}
            ranked.append({"id":c["id"],score_field:sum(vals[k]*ws[k] for k in criteria),"criterion_scores":vals})
        ranked.sort(key=lambda item:item[score_field],reverse=True)
        return {"ranked_candidates":ranked,"ranking_metric":score_field,"criteria":list(criteria)}
    return evaluate


def _rates(effect_name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def evaluate(d: dict[str, Any]) -> dict[str, Any]:
        s,n,cs,cn=(_n(d,"successes",low=0),_n(d,"total",low=1),_n(d,"control_successes",low=0),_n(d,"control_total",low=1))
        if s>n or cs>cn: raise ValueError("successes cannot exceed totals")
        return {effect_name:s/n-cs/cn,"observed_rate":s/n,"control_rate":cs/cn,"sample_size":int(n)}
    return evaluate


def _classification(primary: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def evaluate(d: dict[str, Any]) -> dict[str, Any]:
        tp,fp,tn,fn=[_n(d,k,low=0) for k in ("true_positive","false_positive","true_negative","false_negative")]
        if tp+fn==0 or tn+fp==0: raise ValueError("both reference classes require observations")
        return {primary:tp/(tp+fn),"specificity":tn/(tn+fp),"precision":tp/(tp+fp) if tp+fp else 0.0,"observations":int(tp+fp+tn+fn)}
    return evaluate


def _signal(primary: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def evaluate(d: dict[str, Any]) -> dict[str, Any]:
        signal,reference=_vector(d,"signal"),_vector(d,"reference")
        if len(signal)!=len(reference): raise ValueError("signal and reference must align")
        rmse=math.sqrt(sum((a-b)**2 for a,b in zip(signal,reference))/len(signal))
        return {primary:rmse,"correlation":_corr(signal,reference),"samples":len(signal)}
    return evaluate


def _regenerative(d):
    _unit(d,"cells",{"cells"}); seeded=_n(d,"cells_seeded",low=1); viable=_n(d,"viable_cells",low=0); engrafted=_n(d,"engrafted_cells",low=0)
    if engrafted>viable or viable>seeded: raise ValueError("engrafted_cells <= viable_cells <= cells_seeded required")
    return {"tissue_repair_index":engrafted/seeded,"cell_viability":viable/seeded}
def _stem(d):
    _unit(d,"cells",{"cells"}); plated=_n(d,"cells_plated",low=1); colonies=_n(d,"colonies_formed",low=0); marker=_n(d,"lineage_marker_positive",low=0)
    if colonies>plated or marker>plated: raise ValueError("derived counts cannot exceed cells_plated")
    return {"clonogenic_fraction":colonies/plated,"lineage_marker_fraction":marker/plated}
def _metabolic(d):
    _unit(d,"product",{"mmol"}); _unit(d,"substrate",{"mmol"}); p=_n(d,"product_mmol",low=0); s=_n(d,"substrate_mmol",low=0.000001); theory=_n(d,"theoretical_molar_yield",low=0.000001)
    return {"molar_yield":p/s,"fraction_theoretical":p/s/theory}
def _microbiome(d):
    b,a=_vector(d,"abundance_before",low=0),_vector(d,"abundance_after",low=0)
    if len(a)!=len(b) or sum(a)<=0 or sum(b)<=0: raise ValueError("aligned positive-sum abundance vectors required")
    pa,pb=[x/sum(a) for x in a],[x/sum(b) for x in b]
    return {"shannon_change":-sum(x*math.log(x) for x in pa if x)+sum(x*math.log(x) for x in pb if x),"taxa":len(a)}
def _phage(d):
    _unit(d,"bacteria",{"CFU/mL"}); initial=_n(d,"initial_bacteria",low=1); final=_n(d,"final_bacteria",low=1); phage=_n(d,"phage_particles",low=0)
    return {"log10_bacterial_reduction":math.log10(initial/final),"input_moi":phage/initial}
def _cart(d):
    result=_rates("response_rate_difference")(d); base=_n(d,"baseline_car_t_cells",low=0.000001); result["car_t_expansion_fold"]=_n(d,"peak_car_t_cells",low=0)/base; return result
def _liquid(d):
    result=_classification("liquid_biopsy_sensitivity")(d); _unit(d,"limit_of_detection",{"ng/mL","copies/mL"}); result["limit_of_detection"]=_n(d,"limit_of_detection",low=0); return result
def _brain_mapping(d):
    values=_vector(d,"regional_activation"); labels=d.get("region_labels")
    if not isinstance(labels,list) or len(labels)!=len(values) or len(set(labels))!=len(labels): raise ValueError("unique region_labels must align")
    return {"peak_activation_region":labels[max(range(len(values)),key=values.__getitem__)],"regional_z_scores":[(x-statistics.mean(values))/(statistics.stdev(values) or 1) for x in values]}
def _connectomics(d):
    nodes,edges=d.get("nodes"),d.get("edges")
    if not isinstance(nodes,list) or len(nodes)<2 or len(set(nodes))!=len(nodes) or not isinstance(edges,list): raise ValueError("unique nodes and edge list required")
    degree={n:0 for n in nodes}
    for edge in edges:
        if not isinstance(edge,list) or len(edge)!=2 or edge[0] not in degree or edge[1] not in degree or edge[0]==edge[1]: raise ValueError("edges must join two known distinct nodes")
        degree[edge[0]]+=1; degree[edge[1]]+=1
    return {"connection_density":2*len(edges)/(len(nodes)*(len(nodes)-1)),"node_degree":degree}
def _encoding(d):
    x,y=_vector(d,"stimulus"),_vector(d,"response")
    if len(x)!=len(y) or statistics.pvariance(x)==0: raise ValueError("aligned, varying stimulus required")
    mx,my=statistics.mean(x),statistics.mean(y); slope=sum((a-mx)*(b-my) for a,b in zip(x,y))/sum((a-mx)**2 for a in x)
    return {"encoding_gain":slope,"encoding_intercept":my-slope*mx,"fit_correlation":_corr(x,y)}
def _neural_dust(d):
    _unit(d,"energy",{"mJ"}); tx=_n(d,"packets_transmitted",low=1); rx=_n(d,"packets_received",low=1)
    if rx>tx: raise ValueError("packets_received cannot exceed packets_transmitted")
    return {"packet_delivery_rate":rx/tx,"energy_per_received_packet_mj":_n(d,"energy_mj",low=0)/rx}

# Each key has its own biomedical mechanism and its own output vocabulary/input schema.
SPECS: dict[str, tuple[str,str,Callable[[dict[str,Any]],dict[str,Any]]]] = {
"regenerative_medicine":("Regenerative Medicine","quantifies viable-cell engraftment as a tissue-repair study endpoint",_regenerative),
"stem_cell_therapy":("Stem Cell Therapy","quantifies clonogenicity and lineage-marker observations",_stem),
"gene_therapy":("Gene Therapy","summarises transgene-positive reads and vector-integration burden",_editing("transgene_positive_fraction","vector_integration_reads")),
"crispr_applications":("CRISPR Applications","summarises guide-target editing and measured off-target reads",_editing("crispr_edit_fraction","off_target_reads")),
"base_editing":("Base Editing","summarises intended base conversion and bystander reads",_editing("intended_base_conversion_fraction","bystander_reads")),
"prime_editing":("Prime Editing","summarises intended prime edits and indel reads",_editing("prime_edit_fraction","indel_reads")),
"epigenome_editing":("Epigenome Editing","summarises target mark changes and non-target mark observations",_editing("target_mark_fraction","non_target_mark_reads")),
"synthetic_biology":("Synthetic Biology","ranks supplied circuit-characterisation evidence without designing organisms",_candidate_engine("circuit_characterisation_score",("expression_fidelity","containment_evidence","stability"))),
"metabolic_engineering":("Metabolic Engineering","compares observed molar yield with a supplied theoretical yield",_metabolic),
"protein_engineering":("Protein Engineering","ranks supplied fold, stability and activity assay evidence",_candidate_engine("protein_assay_score",("fold_confidence","stability","activity"))),
"directed_evolution":("Directed Evolution","ranks measured enrichment, activity and stability across variants",_candidate_engine("variant_selection_score",("enrichment","activity","stability"))),
"enzyme_design":("Enzyme Design","ranks catalytic efficiency, selectivity and stability assay evidence",_candidate_engine("enzyme_evidence_score",("catalytic_efficiency","selectivity","stability"))),
"antibody_design":("Antibody Design","ranks binding, specificity and developability evidence",_candidate_engine("antibody_evidence_score",("binding","specificity","developability"))),
"vaccine_design":("Vaccine Design","ranks supplied antigenicity, coverage and safety evidence",_candidate_engine("vaccine_evidence_score",("antigenicity","population_coverage","safety_evidence"))),
"drug_discovery":("Drug Discovery","ranks potency, selectivity and developability observations",_candidate_engine("discovery_evidence_score",("potency","selectivity","developability"))),
"drug_repurposing":("Drug Repurposing","ranks mechanistic, clinical and safety evidence for supplied compounds",_candidate_engine("repurposing_evidence_score",("mechanistic_evidence","clinical_evidence","safety_evidence"))),
"personalized_medicine":("Personalized Medicine","compares supplied patient-fit, evidence and feasibility scores",_candidate_engine("patient_fit_evidence_score",("patient_fit","evidence_quality","feasibility"))),
"pharmacogenomics":("Pharmacogenomics","ranks supplied gene-drug evidence, phenotype fit and actionability",_candidate_engine("gene_drug_evidence_score",("gene_drug_evidence","phenotype_fit","actionability"))),
"microbiome_engineering":("Microbiome Engineering","measures diversity change in supplied abundance profiles",_microbiome),
"probiotic_design":("Probiotic Design","ranks strain viability, function and safety evidence",_candidate_engine("probiotic_evidence_score",("viability","functional_evidence","safety_evidence"))),
"phage_therapy":("Phage Therapy","measures bacterial reduction and supplied multiplicity of infection",_phage),
"immunotherapy":("Immunotherapy","compares observed immune-response rates with a control",_rates("immune_response_rate_difference")),
"car_t_therapy":("CAR-T Therapy","summarises response and measured CAR-T expansion",_cart),
"checkpoint_inhibitors":("Checkpoint Inhibitors","compares observed checkpoint-response rates with a control",_rates("checkpoint_response_rate_difference")),
"mrna_therapeutics":("mRNA Therapeutics","ranks expression, stability and innate-response evidence",_candidate_engine("mrna_evidence_score",("expression","stability","innate_response_control"))),
"nanomedicine":("Nanomedicine","ranks physicochemical, biodistribution and safety evidence",_candidate_engine("nanomedicine_evidence_score",("physicochemical_fit","biodistribution_evidence","safety_evidence"))),
"targeted_drug_delivery":("Targeted Drug Delivery","ranks target uptake, off-target exposure and release evidence",_candidate_engine("delivery_evidence_score",("target_uptake","off_target_control","release_control"))),
"theranostics":("Theranostics","ranks diagnostic performance, therapeutic evidence and linkage",_candidate_engine("theranostic_evidence_score",("diagnostic_evidence","therapeutic_evidence","mechanistic_linkage"))),
"liquid_biopsy":("Liquid Biopsy","summarises classification performance and reported detection limit",_liquid),
"wearable_sensors":("Wearable Sensors","measures wearable signal error against a supplied reference",_signal("wearable_signal_rmse")),
"implantable_devices":("Implantable Devices","measures implant signal error against a supplied reference",_signal("implant_signal_rmse")),
"brain_computer_interfaces":("Brain-Computer Interfaces","summarises command-decoding classification performance",_classification("bci_command_sensitivity")),
"neural_prosthetics":("Neural Prosthetics","summarises intended-function decoding performance",_classification("prosthetic_function_sensitivity")),
"cochlear_implants":("Cochlear Implants","measures paired hearing-score change",_paired("mean_hearing_score_change")),
"retinal_implants":("Retinal Implants","measures paired vision-score change",_paired("mean_vision_score_change")),
"deep_brain_stimulation":("Deep Brain Stimulation","compares study response rates without controlling stimulation",_rates("dbs_response_rate_difference")),
"optogenetics":("Optogenetics","compares observed light-associated response rates in supplied study data",_rates("light_associated_response_difference")),
"chemogenetics":("Chemogenetics","compares observed ligand-associated response rates",_rates("ligand_associated_response_difference")),
"neurofeedback":("Neurofeedback","measures paired self-regulation score change",_paired("mean_self_regulation_change")),
"brain_mapping":("Brain Mapping","identifies peak supplied regional activation and standardised values",_brain_mapping),
"connectomics":("Connectomics","summarises density and degree in a supplied graph",_connectomics),
"neural_decoding":("Neural Decoding","summarises held-out label decoding performance, not thoughts",_classification("neural_label_decoding_sensitivity")),
"neural_encoding":("Neural Encoding","fits a descriptive linear stimulus-response relationship",_encoding),
"memory_prosthetics":("Memory Prosthetics","measures paired memory-task score change",_paired("mean_memory_task_change")),
"cognitive_enhancement":("Cognitive Enhancement","ranks supplied cognition, durability and safety observations",_candidate_engine("cognitive_evidence_score",("cognitive_effect","durability","safety_evidence"))),
"nootropics":("Nootropics","ranks supplied efficacy, adverse-event and evidence-quality observations",_candidate_engine("nootropic_evidence_score",("efficacy_evidence","adverse_event_control","evidence_quality"))),
"neurostimulation":("Neurostimulation","compares study response rates without operating a device",_rates("neurostimulation_response_difference")),
"transcranial_magnetic_stimulation":("Transcranial Magnetic Stimulation","compares TMS study response rates without prescribing parameters",_rates("tms_response_rate_difference")),
"focused_ultrasound":("Focused Ultrasound","compares focused-ultrasound study response rates without device control",_rates("focused_ultrasound_response_difference")),
"neural_dust":("Neural Dust","summarises packet delivery and measured energy use",_neural_dust),
}
ENGINES={key:Engine(ROWS[key],title,mechanism,evaluate) for key,(title,mechanism,evaluate) in SPECS.items()}
if set(ENGINES)!=set(ROWS): raise RuntimeError("engine registry does not cover rows 960-1009")


def _provenance(data: dict[str,Any]) -> dict[str,Any]:
    evidence=data.get("evidence")
    if not isinstance(evidence,dict): raise ValueError("evidence object is required")
    source_ids=evidence.get("source_ids"); quality=evidence.get("quality")
    if not isinstance(source_ids,list) or not source_ids or any(not isinstance(x,str) or not x.strip() for x in source_ids): raise ValueError("evidence.source_ids requires nonempty source identifiers")
    if quality not in {"low","moderate","high"}: raise ValueError("evidence.quality must be low, moderate, or high")
    assumptions=data.get("assumptions")
    if not isinstance(assumptions,list) or not assumptions or any(not isinstance(x,str) or not x.strip() for x in assumptions): raise ValueError("assumptions requires nonempty statements")
    uncertainty=data.get("uncertainty")
    if not isinstance(uncertainty,dict): raise ValueError("uncertainty object is required")
    level=_n(uncertainty,"confidence_level",low=0.5,high=0.999)
    lower=_n(uncertainty,"lower"); upper=_n(uncertainty,"upper")
    if lower>upper: raise ValueError("uncertainty.lower cannot exceed uncertainty.upper")
    return {"evidence":{"source_ids":source_ids,"quality":quality},"assumptions":assumptions,"uncertainty":{"confidence_level":level,"lower":lower,"upper":upper}}


def run(method: str, data: dict[str,Any], *, tenant_id: str="local", actor_id: str="local") -> dict[str,Any]:
    engine=ENGINES.get(method)
    if engine is None: raise ValueError(f"unsupported emerging-biomed method {method}")
    if not isinstance(data,dict): raise ValueError("data must be an object")
    provenance=_provenance(data)
    analysis=engine.evaluate(data)
    return {"method":method,"feature_row":engine.row,"title":engine.title,"mechanism":engine.mechanism,"analysis":analysis,**provenance,"execution_context":{"tenant_id":tenant_id,"actor_id":actor_id},"human_review_required":True,"decision_boundary":"Research decision support only. Not diagnosis, treatment selection, dosing, wet-lab execution, device control, or regulatory evidence."}
