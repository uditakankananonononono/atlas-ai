import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m12_ai_research_lab.emerging_biomed_960_1009 import ROWS,run
C={}
for m in ["regenerative_medicine","stem_cell_therapy"]:C[m]={"cells_seeded":100,"viable_cells":80,"engrafted_cells":40,"baseline_function":2,"followup_function":3}
for m in ["gene_therapy","crispr_applications","base_editing","prime_editing","epigenome_editing"]:C[m]={"edited_reads":80,"total_reads":100,"off_target_reads":2,"bystander_reads":3}
for m in ["synthetic_biology","protein_engineering","directed_evolution","enzyme_design","antibody_design","vaccine_design","drug_discovery","drug_repurposing","personalized_medicine","pharmacogenomics","probiotic_design","immunotherapy","checkpoint_inhibitors","mrna_therapeutics","nanomedicine","targeted_drug_delivery","theranostics","cognitive_enhancement","nootropics"]:C[m]={"weights":[.7,.3],"candidates":[{"id":"a","metrics":[.8,.5]},{"id":"b","metrics":[.6,.9]}]}
C.update({"metabolic_engineering":{"product_moles":8,"substrate_moles":10,"theoretical_yield":1,"biomass":2,"hours":4},"microbiome_engineering":{"abundance_before":[2,8],"abundance_after":[5,5]},"phage_therapy":{"initial_bacteria":1000000,"final_bacteria":1000,"phage_particles":10000000},"car_t_therapy":{"successes":8,"total":10,"control_successes":4,"control_total":10,"peak_car_t_cells":100,"baseline_car_t_cells":10},"liquid_biopsy":{"true_positive":9,"false_positive":1,"true_negative":8,"false_negative":2,"limit_of_detection":.01}})
for m in ["wearable_sensors","implantable_devices"]:C[m]={"signal":[1,2,3],"reference":[1,2,2.5],"valid_samples":90,"expected_samples":100}
for m in ["brain_computer_interfaces","neural_prosthetics","neural_decoding"]:C[m]={"true_positive":9,"false_positive":1,"true_negative":8,"false_negative":2,"bits_correct":100,"minutes":5}
for m in ["cochlear_implants","retinal_implants","memory_prosthetics"]:C[m]={"baseline_scores":[1,2,3],"followup_scores":[2,4,5],"responder_threshold":1}
for m in ["deep_brain_stimulation","optogenetics","chemogenetics","neurofeedback","neurostimulation","transcranial_magnetic_stimulation","focused_ultrasound"]:C[m]={"successes":8,"total":10,"control_successes":4,"control_total":10,"adverse_events":1,"frequency_hz":10,"intensity":.5,"duration_minutes":20}
C.update({"brain_mapping":{"regional_activation":[1,4,2],"region_labels":["a","b","c"]},"connectomics":{"nodes":["a","b","c"],"edges":[["a","b"],["b","c"]]},"neural_encoding":{"stimulus":[1,2,3],"response":[2,4,6]},"neural_dust":{"packets_transmitted":100,"packets_received":90,"energy_mj":9,"hours":5}})

def test_case_registry_covers_exact_ledger_range():
 assert set(C)==set(ROWS) and sorted(ROWS.values())==list(range(960,1010))

@pytest.mark.parametrize("method", sorted(ROWS, key=ROWS.get))
def test_every_row_is_concept_specific_auditable_and_bounded(method):
 data=C[method]; result=run(method,data)
 assert result["feature_row"]==ROWS[method]
 assert result["inputs"]==data
 assert result["output"] and any("not medical advice" in x for x in result["output"]["method_limits"])

def test_scientific_semantics():
 assert run("crispr_applications",C["crispr_applications"])["output"]["edit_efficiency"]==.8
 assert run("phage_therapy",C["phage_therapy"])["output"]["log10_reduction"]==3
 assert run("liquid_biopsy",C["liquid_biopsy"])["output"]["sensitivity"]==pytest.approx(9/11)
 assert run("neural_encoding",C["neural_encoding"])["output"]["linear_gain"]==2

def test_negative_paths_and_mounted_boundary():
 with pytest.raises(ValueError):run("crispr_applications",{"edited_reads":2,"total_reads":0})
 with pytest.raises(ValueError):run("brain_mapping",{"regional_activation":[1,2],"region_labels":["x"]})
 c=TestClient(app);h={"X-Tenant-ID":"bio","X-Actor-ID":"researcher"}
 assert len(c.get('/api/v1/ai-research-lab/emerging-biomed-960-1009/methods',headers=h).json())==50
 r=c.post('/api/v1/ai-research-lab/emerging-biomed-960-1009/analyze',headers=h,json={"method":"neural_dust","data":C["neural_dust"]});assert r.status_code==200 and r.json()["feature_row"]==1009
 assert c.post('/api/v1/ai-research-lab/emerging-biomed-960-1009/analyze',headers=h,json={"method":"bad"}).status_code==422
