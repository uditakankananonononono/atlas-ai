import pytest
from app.modules.m20_general_cognitive_worker.cognitive_learning_860_909 import execute
from app.modules.m16_executive_dashboard.emerging_capabilities_0910_0959 import run as emerging
from app.modules.m12_ai_research_lab.emerging_biomed_960_1009 import run as biomed
from app.modules.m16_executive_dashboard.analysis import run as analyze
from app.modules.m12_ai_research_lab.clinical_support import clinical_support

SRC={'source_url':'https://example.test/evidence','observed_at':'2026-09-21'}

def test_cognitive_reports_coverage_and_unresolved_evidence():
 result=execute(862,{'sources':[{'source_id':'s','observed_at':'2026-09-21'}],'inputs':{'problem':'p','constraints':['c'],'ideation_methods':['brainwriting']}})
 assert result['evaluation']['stage_coverage']<1
 assert result['uncertainty']['unresolved_stages']==result['evidence_gaps']
 assert result['uncertainty']['confidence_claimed'] is False

def test_emerging_reports_nonexecution_and_method_limits():
 result=emerging('quantum_error_correction',{'physical_error_rate':.001,'threshold':.01,'code_distance':3})
 assert result['output']['logical_error_rate_bound']==pytest.approx(.01)
 assert result['evaluation']['algorithm_executed']
 assert result['uncertainty']['fabricated_or_deployed'] is False
 with pytest.raises(ValueError):emerging('quantum_error_correction',{'physical_error_rate':float('nan'),'threshold':.01,'code_distance':3})

def test_biomed_reports_research_only_uncertainty():
 result=biomed('liquid_biopsy',{'true_positive':8,'false_positive':2,'true_negative':9,'false_negative':1,'limit_of_detection':.01})
 assert result['output']['sensitivity']==pytest.approx(8/9)
 assert result['uncertainty']['clinical_effect_established'] is False
 assert result['evaluation']['qualified_review_required']

def test_analytics_reports_assumptions_and_invalid_input():
 result=analyze('confidence_interval',{'values':[1,2,3,4]})
 assert result['evaluation']['algorithm_executed']
 assert result['uncertainty']['external_validity_established'] is False
 assert result['output']['method_limits']==result['uncertainty']['method_limits']
 with pytest.raises(ValueError):analyze('predictive',{'x':[1,1],'y':[1,2],'future_x':[3]})

def test_clinical_dispatcher_never_claims_diagnosis_or_authorization():
 result=clinical_support('health_equity_analysis',{'groups':[{'group_token':'a','values':{'access':.8}},{'group_token':'b','values':{'access':.5}}],'metrics':['access'],'source':SRC})
 assert result['metric_gaps'][0]['absolute_gap']==pytest.approx(.3)
 assert result['evaluation']['qualified_clinician_review_required']
 assert result['uncertainty']['diagnosis_or_treatment_authorized'] is False
