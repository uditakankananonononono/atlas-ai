from datetime import datetime,timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m19_idea_incubator.business_models import Provenance
from app.modules.m19_idea_incubator.research_models import *
from app.modules.m19_idea_incubator.research_service import ResearchAnalysisService
from app.modules.m19_idea_incubator.research_router import router
P=Provenance(source_id="doi:example",source_type="public_source",uri="https://doi.org/example",observed_at=datetime.now(timezone.utc))
def req(row,inputs):return ResearchAnalysisRequest(feature=row,inputs=inputs,provenance=[P],confidence=.8)
def svc():return ResearchAnalysisService()
def assert_bound(a):assert a.claims["invented_studies"] is False and a.claims["evidence_bound"] is True and a.provenance[0].source_id=="doi:example"

def test_row_115_power_with_method_caveat():
 a=svc().analyze("i",req(115,{"effect_size":.5,"alpha":.05,"power":.8,"groups":2}));assert a.analysis["sample_size_per_group"]>=63;assert "Normal approximation" in a.uncertainty.limitations[0];assert_bound(a)
def test_row_120_meta_analysis():
 a=svc().analyze("i",req(120,{"studies":[{"id":"a","effect":.2,"standard_error":.1},{"id":"b","effect":.4,"standard_error":.2}]}));assert round(a.analysis["fixed_effect"],2)==.24;assert a.analysis["sample_size"]==2;assert a.uncertainty.interval_low is not None;assert_bound(a)
def test_row_121_effect_sizes():
 a=svc().analyze("i",req(121,{"treatment_mean":12,"control_mean":10,"treatment_sd":2,"control_sd":2,"treatment_n":20,"control_n":20}));assert a.analysis["cohens_d"]==1;assert a.analysis["hedges_g"]<1;assert_bound(a)
def test_row_134_bayesian_update():
 a=svc().analyze("i",req(134,{"successes":8,"trials":10,"prior_alpha":1,"prior_beta":1}));assert a.analysis["posterior_alpha"]==9 and a.analysis["posterior_beta"]==3;assert a.analysis["posterior_mean"]==.75;assert_bound(a)

ROWS={110:{"studies":[{"id":"s","finding":"f"}],"research_question":"q","inclusion_criteria":["i"],"exclusion_criteria":["e"]},111:{"papers":["a","b"],"citations":[["a","b"]]},112:{"included_studies":["s"],"dimensions":["population"],"observed_coverage":{"population":["p"]}},113:{"observed_pattern":"p","theory":"t","population":"p","outcome":"o","falsifier":"f"},114:{"hypothesis":"h","outcome":"o","factors":["f"],"constraints":["c"],"analysis_plan":"a"},116:{"exposure":"e","outcome":"o","candidate_variables":["v"],"temporal_order":["e","o"],"causal_assumptions":["a"]},117:{"units":["u"],"arms":["c","t"],"allocation_ratio":[1,1],"strata":["s"],"seed_policy":"record"},118:{"roles":["participant","analyst"],"assignments":["blind"],"blinded_roles":["participant"],"unblinding_rule":"emergency"},119:{"original_protocol":"p","target_effect":.2,"deviations":["none"],"materials":["m"],"analysis_plan":"a"},122:{"studies":["s"],"effect_sizes":[.2],"standard_errors":[.1],"search_scope":"registered+published"},123:{"outcomes":["o"],"predictors":["p"],"subgroups":["s"],"transformations":["none"],"stopping_rules":["n=100"]},124:{"hypotheses":["h"],"outcomes":["o"],"exclusions":["e"],"sample_size_rule":"n=100","analysis_plan":"a","timestamp_policy":"before data"},125:{"data_plan":"d","code_plan":"c","materials_plan":"m","license":"MIT","repository":"r","privacy_constraints":["p"]},126:{"artifacts":["a"],"environment":"python","steps":["s"],"expected_outputs":["o"],"checksums":["c"]},127:{"manuscript_sections":["m"],"claims":["c"],"methods":["m"],"limitations":["l"],"target_audience":"a"},128:{"manuscript_scope":"s","methods":["m"],"audience":"a","candidate_venues":["v"],"venue_policies":["p"]},129:{"historical_comparables":[{"citations":10}],"field":"f","publication_year":2026,"documented_features":["open"]},130:{"background":"b","objective":"o","methods":"m","results":"r","limitations":"l","conclusion":"c"},131:{"study_design":"d","population":"p","intervention_or_exposure":"i","outcome":"o","main_finding":"f"},132:{"data":[1,2],"variables":["x"],"figure_purpose":"compare","uncertainty_encoding":"CI","accessibility":"palette"},133:{"outcome_type":"continuous","design":"parallel","groups":2,"paired":False,"distribution_assumptions":["normal"],"estimand":"mean difference"}}
@pytest.mark.parametrize("row,inputs",sorted(ROWS.items()))
def test_row_named_research_artifacts(row,inputs):
 a=svc().analyze("i",req(row,inputs));assert a.analysis["source_bound"] is True;assert a.inputs==inputs;assert_bound(a)
def test_row_110_scope_caveat():assert "only supplied studies" in svc().analyze("i",req(110,ROWS[110])).uncertainty.limitations[0]
def test_row_111_citation_is_not_influence_claim():assert "not endorsement" in svc().analyze("i",req(111,ROWS[111])).uncertainty.limitations[0]
def test_row_112_gap_caveat():assert "not proof" in svc().analyze("i",req(112,ROWS[112])).uncertainty.limitations[0]
def test_row_129_no_impact_prediction():
 a=svc().analyze("i",req(129,ROWS[129]));assert a.claims["impact_prediction"]=="scenario_only";assert "not predicted" in a.uncertainty.limitations[0]
def test_row_132_figure_spec_only():assert "not rendered" in svc().analyze("i",req(132,ROWS[132])).uncertainty.limitations[0]
def test_missing_inputs_fail_not_fabricate():
 with pytest.raises(ValueError,match="missing required inputs"):svc().analyze("i",req(110,{"studies":[1]}))
def test_no_provenance_rejected():
 with pytest.raises(Exception):ResearchAnalysisRequest(feature=110,inputs={"x":1},provenance=[],confidence=.5)
def test_mounted_api():
 app=FastAPI();app.include_router(router);c=TestClient(app);r=c.post("/portfolio/ideas/x/research-analyses",json=req(134,{"successes":4,"trials":5}).model_dump(mode="json"));assert r.status_code==201 and r.json()["analysis"]["posterior_alpha"]==5
