"""Practitioner-depth contracts for feature rows 101-287."""
from datetime import datetime, timezone
from app.modules.m20_general_cognitive_worker.negotiation_behavior_0085_0109 import run as negotiate
from app.modules.m12_ai_research_lab.research_methods_135_184 import execute as research
from app.modules.m04_research_scientist.quant_methods_185_234 import run as quant
from app.modules.m20_general_cognitive_worker.optimization_story_235_280 import execute as workbench
from app.modules.m19_idea_incubator.research_service import ResearchAnalysisService
from app.modules.m19_idea_incubator.research_models import ResearchAnalysisRequest
from app.modules.m19_idea_incubator.business_models import Provenance
SRC={'title':'Reference','url':'https://example.org/ref'}

def test_101_109_report_execution_evaluation_uncertainty_and_boundary():
 cases={'authority_positioning':{'claim':'qualified','evidence':['registry']},'consistency_commitment':{'prior_commitment':'a','current_choice':'a','freely_chosen':True},'liking_enhancement':{'genuine_commonalities':['shared project']},'unity_building':{'genuine_commonalities':['team']},'pre_suasion':{'context':'agenda','disclosed':True},'priming_effects':{'context':'agenda','disclosed':True},'nudge_design':{'options':['a','b'],'default':'a','disclosed':True},'choice_architecture':{'options':['a','b'],'default':'a','disclosed':True},'libertarian_paternalism':{'options':['a','b'],'default':'a','disclosed':True}}
 for method,payload in cases.items():
  out=negotiate(method,payload);assert out['evaluation']['method_specific'] and out['uncertainty']['human_review_required'] and out['boundary']

def test_110_research_has_evaluation_and_uncertainty():
 p=Provenance(source_id='doi:x',source_type='public_source',uri='https://doi.org/x',observed_at=datetime.now(timezone.utc))
 r=ResearchAnalysisRequest(feature=110,inputs={'studies':[{'id':'s'}],'research_question':'q','inclusion_criteria':['i'],'exclusion_criteria':['e']},provenance=[p],confidence=.8)
 a=ResearchAnalysisService().analyze('idea',r);assert a.analysis['evaluation']['method_specific'] and a.analysis['uncertainty_report']['expert_review_required']

def test_135_184_have_method_evaluation_uncertainty():
 cases=[('frequentist_analysis',{'group_a':[1,2],'group_b':[2,3]}),('machine_learning_model_selection',{'task':'classify','candidates':['x']}),('causal_inference',{}),('time_series_analysis',{'values':[1,2,3]})]
 for name,args in cases:
  out=research(name,{'source':SRC,**args});assert out['evaluation']['diagnostics_required'] and out['uncertainty']['expert_review_required']

def test_185_quant_reports_reference_evaluation_uncertainty():
 d={'sources':[{'source_id':'d','observed_at':'2026-01-01T00:00:00Z'}],'x':[1,2,3,4],'y':[2,4,6,8]}
 out=quant(185,d);assert out['evaluation']['reference_result_only'] and out['uncertainty']['expert_review_required']

def test_235_280_distinct_review_envelopes():
 a=workbench('admm',{'source':SRC,'objective':{'expression':'x^2'}});b=workbench('dialogue_writing',{'source':SRC,'premise':'Two rivals cooperate'})
 assert 'convergence' in a['evaluation']['review_checks'] and 'continuity' in b['evaluation']['review_checks']
 assert a['uncertainty']['human_review_required'] and b['uncertainty']['human_review_required']
