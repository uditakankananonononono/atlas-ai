import copy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m12_ai_research_lab.emerging_biomed_960_1009 import ENGINES, ROWS, run

PROVENANCE={"evidence":{"source_ids":["study:demo-1"],"quality":"moderate"},"assumptions":["The supplied observations are comparable."],"uncertainty":{"confidence_level":.95,"lower":.1,"upper":.9}}
def with_provenance(payload): return {**payload,**copy.deepcopy(PROVENANCE)}
C={}
C["regenerative_medicine"]=with_provenance({"cells_seeded":100,"viable_cells":80,"engrafted_cells":40,"units":{"cells":"cells"}})
C["stem_cell_therapy"]=with_provenance({"cells_plated":100,"colonies_formed":20,"lineage_marker_positive":70,"units":{"cells":"cells"}})
EDIT={"gene_therapy":"vector_integration_reads","crispr_applications":"off_target_reads","base_editing":"bystander_reads","prime_editing":"indel_reads","epigenome_editing":"non_target_mark_reads"}
for method,extra in EDIT.items(): C[method]=with_provenance({"edited_reads":80,"total_reads":100,extra:2})
CRITERIA={
"synthetic_biology":("expression_fidelity","containment_evidence","stability"),"protein_engineering":("fold_confidence","stability","activity"),"directed_evolution":("enrichment","activity","stability"),"enzyme_design":("catalytic_efficiency","selectivity","stability"),"antibody_design":("binding","specificity","developability"),"vaccine_design":("antigenicity","population_coverage","safety_evidence"),"drug_discovery":("potency","selectivity","developability"),"drug_repurposing":("mechanistic_evidence","clinical_evidence","safety_evidence"),"personalized_medicine":("patient_fit","evidence_quality","feasibility"),"pharmacogenomics":("gene_drug_evidence","phenotype_fit","actionability"),"probiotic_design":("viability","functional_evidence","safety_evidence"),"mrna_therapeutics":("expression","stability","innate_response_control"),"nanomedicine":("physicochemical_fit","biodistribution_evidence","safety_evidence"),"targeted_drug_delivery":("target_uptake","off_target_control","release_control"),"theranostics":("diagnostic_evidence","therapeutic_evidence","mechanistic_linkage"),"cognitive_enhancement":("cognitive_effect","durability","safety_evidence"),"nootropics":("efficacy_evidence","adverse_event_control","evidence_quality")}
for method,criteria in CRITERIA.items():
 weights={k:1/3 for k in criteria}; scores={k:.8-i*.1 for i,k in enumerate(criteria)}
 C[method]=with_provenance({"weights":weights,"candidates":[{"id":"candidate-a","scores":scores}]})
C["metabolic_engineering"]=with_provenance({"product_mmol":8,"substrate_mmol":10,"theoretical_molar_yield":1,"units":{"product":"mmol","substrate":"mmol"}})
C["microbiome_engineering"]=with_provenance({"abundance_before":[2,8],"abundance_after":[5,5]})
C["phage_therapy"]=with_provenance({"initial_bacteria":1000000,"final_bacteria":1000,"phage_particles":10000000,"units":{"bacteria":"CFU/mL"}})
RATE_METHODS={"immunotherapy","checkpoint_inhibitors","deep_brain_stimulation","optogenetics","chemogenetics","neurostimulation","transcranial_magnetic_stimulation","focused_ultrasound"}
for method in RATE_METHODS:C[method]=with_provenance({"successes":8,"total":10,"control_successes":4,"control_total":10})
C["car_t_therapy"]=with_provenance({"successes":8,"total":10,"control_successes":4,"control_total":10,"peak_car_t_cells":100,"baseline_car_t_cells":10})
C["liquid_biopsy"]=with_provenance({"true_positive":9,"false_positive":1,"true_negative":8,"false_negative":2,"limit_of_detection":.01,"units":{"limit_of_detection":"ng/mL"}})
for method in ("wearable_sensors","implantable_devices"):C[method]=with_provenance({"signal":[1,2,3],"reference":[1,2,2.5]})
for method in ("brain_computer_interfaces","neural_prosthetics","neural_decoding"):C[method]=with_provenance({"true_positive":9,"false_positive":1,"true_negative":8,"false_negative":2})
for method in ("cochlear_implants","retinal_implants","neurofeedback","memory_prosthetics"):C[method]=with_provenance({"baseline_scores":[1,2,3],"followup_scores":[2,4,5]})
C["brain_mapping"]=with_provenance({"regional_activation":[1,4,2],"region_labels":["a","b","c"]})
C["connectomics"]=with_provenance({"nodes":["a","b","c"],"edges":[["a","b"],["b","c"]]})
C["neural_encoding"]=with_provenance({"stimulus":[1,2,3],"response":[2,4,6]})
C["neural_dust"]=with_provenance({"packets_transmitted":100,"packets_received":90,"energy_mj":9,"units":{"energy":"mJ"}})

def assert_row(method):
 result=run(method,C[method],tenant_id="tenant-a",actor_id="researcher-a")
 assert result["feature_row"]==ROWS[method] and result["analysis"]
 assert result["mechanism"]==ENGINES[method].mechanism
 assert result["human_review_required"] is True
 assert result["evidence"]["source_ids"]==["study:demo-1"]
 assert result["execution_context"]=={"tenant_id":"tenant-a","actor_id":"researcher-a"}

def test_row_960_regenerative_medicine(): assert_row("regenerative_medicine")
def test_row_961_stem_cell_therapy(): assert_row("stem_cell_therapy")
def test_row_962_gene_therapy(): assert_row("gene_therapy")
def test_row_963_crispr_applications(): assert_row("crispr_applications")
def test_row_964_base_editing(): assert_row("base_editing")
def test_row_965_prime_editing(): assert_row("prime_editing")
def test_row_966_epigenome_editing(): assert_row("epigenome_editing")
def test_row_967_synthetic_biology(): assert_row("synthetic_biology")
def test_row_968_metabolic_engineering(): assert_row("metabolic_engineering")
def test_row_969_protein_engineering(): assert_row("protein_engineering")
def test_row_970_directed_evolution(): assert_row("directed_evolution")
def test_row_971_enzyme_design(): assert_row("enzyme_design")
def test_row_972_antibody_design(): assert_row("antibody_design")
def test_row_973_vaccine_design(): assert_row("vaccine_design")
def test_row_974_drug_discovery(): assert_row("drug_discovery")
def test_row_975_drug_repurposing(): assert_row("drug_repurposing")
def test_row_976_personalized_medicine(): assert_row("personalized_medicine")
def test_row_977_pharmacogenomics(): assert_row("pharmacogenomics")
def test_row_978_microbiome_engineering(): assert_row("microbiome_engineering")
def test_row_979_probiotic_design(): assert_row("probiotic_design")
def test_row_980_phage_therapy(): assert_row("phage_therapy")
def test_row_981_immunotherapy(): assert_row("immunotherapy")
def test_row_982_car_t_therapy(): assert_row("car_t_therapy")
def test_row_983_checkpoint_inhibitors(): assert_row("checkpoint_inhibitors")
def test_row_984_mrna_therapeutics(): assert_row("mrna_therapeutics")
def test_row_985_nanomedicine(): assert_row("nanomedicine")
def test_row_986_targeted_drug_delivery(): assert_row("targeted_drug_delivery")
def test_row_987_theranostics(): assert_row("theranostics")
def test_row_988_liquid_biopsy(): assert_row("liquid_biopsy")
def test_row_989_wearable_sensors(): assert_row("wearable_sensors")
def test_row_990_implantable_devices(): assert_row("implantable_devices")
def test_row_991_brain_computer_interfaces(): assert_row("brain_computer_interfaces")
def test_row_992_neural_prosthetics(): assert_row("neural_prosthetics")
def test_row_993_cochlear_implants(): assert_row("cochlear_implants")
def test_row_994_retinal_implants(): assert_row("retinal_implants")
def test_row_995_deep_brain_stimulation(): assert_row("deep_brain_stimulation")
def test_row_996_optogenetics(): assert_row("optogenetics")
def test_row_997_chemogenetics(): assert_row("chemogenetics")
def test_row_998_neurofeedback(): assert_row("neurofeedback")
def test_row_999_brain_mapping(): assert_row("brain_mapping")
def test_row_1000_connectomics(): assert_row("connectomics")
def test_row_1001_neural_decoding(): assert_row("neural_decoding")
def test_row_1002_neural_encoding(): assert_row("neural_encoding")
def test_row_1003_memory_prosthetics(): assert_row("memory_prosthetics")
def test_row_1004_cognitive_enhancement(): assert_row("cognitive_enhancement")
def test_row_1005_nootropics(): assert_row("nootropics")
def test_row_1006_neurostimulation(): assert_row("neurostimulation")
def test_row_1007_transcranial_magnetic_stimulation(): assert_row("transcranial_magnetic_stimulation")
def test_row_1008_focused_ultrasound(): assert_row("focused_ultrasound")
def test_row_1009_neural_dust(): assert_row("neural_dust")

def test_registry_exact_and_mechanisms_are_row_specific():
 assert sorted(ROWS.values())==list(range(960,1010))
 assert set(C)==set(ROWS)==set(ENGINES)
 assert len({e.mechanism for e in ENGINES.values()})==50

@pytest.mark.parametrize("method",sorted(ROWS,key=ROWS.get))
def test_each_engine_rejects_missing_evidence(method):
 invalid=copy.deepcopy(C[method]); invalid.pop("evidence")
 with pytest.raises(ValueError,match="evidence"): run(method,invalid)

def test_invalid_biological_units_ranges_and_uncertainty_fail():
 invalid=copy.deepcopy(C["regenerative_medicine"]);invalid["units"]["cells"]="mg"
 with pytest.raises(ValueError,match="units.cells"):run("regenerative_medicine",invalid)
 invalid=copy.deepcopy(C["crispr_applications"]);invalid["edited_reads"]=101
 with pytest.raises(ValueError,match="cannot exceed"):run("crispr_applications",invalid)
 invalid=copy.deepcopy(C["liquid_biopsy"]);invalid["uncertainty"]["confidence_level"]=1.5
 with pytest.raises(ValueError,match="confidence_level"):run("liquid_biopsy",invalid)

def test_exact_mount_and_tenant_actor_isolation():
 client=TestClient(app); h1={"X-Tenant-ID":"tenant-a","X-Actor-ID":"actor-a"};h2={"X-Tenant-ID":"tenant-b","X-Actor-ID":"actor-b"}
 assert len(client.get("/api/v1/ai-research-lab/emerging-biomed-960-1009/methods",headers=h1).json())==50
 r1=client.post("/api/v1/ai-research-lab/emerging-biomed-960-1009/analyze",headers=h1,json={"method":"neural_dust","data":C["neural_dust"]})
 r2=client.post("/api/v1/ai-research-lab/emerging-biomed-960-1009/analyze",headers=h2,json={"method":"neural_dust","data":C["neural_dust"]})
 assert r1.status_code==r2.status_code==200
 assert r1.json()["execution_context"]=={"tenant_id":"tenant-a","actor_id":"actor-a"}
 assert r2.json()["execution_context"]=={"tenant_id":"tenant-b","actor_id":"actor-b"}
 assert client.post("/api/v1/ai-research-lab/emerging-biomed-960-1009/analyze",headers=h1,json={"method":"bad","data":PROVENANCE}).status_code==422
 assert client.post("/api/v1/ai-research-lab/emerging-biomed-960-1009/analyze",json={"method":"neural_dust","data":C["neural_dust"]}).status_code==422
