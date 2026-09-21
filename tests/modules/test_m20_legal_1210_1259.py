import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.legal_support import PROFILES, legal_support
from app.modules.m20_general_cognitive_worker.routes import router

EXPECTED=[
'contract_drafting','contract_review','contract_negotiation','legal_research','case_law_analysis','statutory_interpretation','regulatory_compliance','legal_risk_assessment','due_diligence','mergers_acquisitions','corporate_governance','securities_law','intellectual_property','patent_drafting','patent_prosecution','trademark_registration','copyright_analysis','trade_secret_protection','licensing_agreements','technology_transfer','employment_law','labor_relations','discrimination_analysis','harassment_investigation','wrongful_termination','employment_contracts','non_compete_agreements','immigration_law','visa_applications','asylum_cases','refugee_law','family_law','divorce_proceedings','child_custody','adoption','estate_planning','wills_and_trusts','probate','real_estate_law','property_transactions','landlord_tenant','zoning_and_land_use','environmental_law','climate_regulation','pollution_control','natural_resources','energy_law','criminal_law','criminal_defense','prosecution_strategy']
AUTH={"id":"A1","title":"Controlling Act","url":"https://law.example/act","jurisdiction":"X","as_of":"2026-09-01","authority_type":"statute"}
BASE={"matter_name":"Example","jurisdiction":"X","as_of":"2026-09-21","authorities":[AUTH],"facts":["signed record exists"],"confirmed_inputs":[]}

def test_every_row_1210_1259_has_unique_real_profile_and_safe_output():
 assert list(PROFILES)==EXPECTED and len(PROFILES)==50
 for method in EXPECTED:
  out=legal_support(method,BASE)
  assert out['method']==method and len(out['workflow'])>=4 and len(out['intake_questions'])>=3
  assert out['source_quality']=={'total':1,'verified':1,'unverified_ids':[]}
  assert out['review']['can_file_or_send'] is False and 'not legal advice' in out['disclaimer']

def test_contract_drafting_preserves_clauses_and_detects_placeholders():
 d={**BASE,"clauses":[{"id":"payment","heading":"Payment","text":"Buyer pays [AMOUNT] in 30 days","fallback":"Net 45","defined_terms":["Buyer"]}],"defined_terms":{"Buyer":"Example Ltd"}}
 o=legal_support('contract_drafting',d)
 assert o['artifact']=='clause-indexed draft' and o['clauses'][0]['fallback']=='Net 45'
 assert o['clauses'][0]['review_flags']==['undefined placeholder'] and o['execution_blocked']

def test_case_analysis_requires_real_authority_links_and_tracks_contrary_law():
 d={**BASE,"issues":[{"issue":"Duty","rule":"Reasonable care","facts":["notice"],"unknowns":["causation"],"supporting_authority_ids":["A1"],"contrary_authority_ids":["A9"]}]}
 o=legal_support('case_law_analysis',d); issue=o['issues'][0]
 assert issue['missing_authority_ids']==['A9'] and issue['confidence']=='blocked' and issue['unknowns']==['causation']

def test_compliance_builds_auditable_control_gaps():
 d={**BASE,"obligations":[{"obligation":"File report","authority_ids":["A1"],"control":"quarterly review","owner":"compliance","evidence":["report-7"],"cadence":"quarterly"},{"obligation":"Retain logs","authority_ids":[],"evidence":[]}]}
 o=legal_support('regulatory_compliance',d)['obligation_control_matrix']
 assert o[0]['status']=='evidenced' and o[1]['status']=='gap'
 assert set(o[1]['gaps'])=={'authority not linked','control owner missing','operating evidence missing'}

def test_transaction_dependencies_and_human_execution_gate():
 d={**BASE,"checklist":[{"item":"board approval","owner":"secretary","status":"open","dependency_ids":["diligence"],"evidence":[]}]}
 o=legal_support('mergers_acquisitions',d)
 assert o['checklist'][0]['dependency_ids']==['diligence'] and o['execution_blocked']
 assert any('signing' in x for x in o['approval_gates'])

def test_deadlines_never_present_unverified_calculation_as_final():
 d={**BASE,"deadlines":[{"name":"appeal","date":"2026-10-01","source_authority_id":"A1","calculation":"30 days after order"}]}
 o=legal_support('criminal_law',d)
 assert o['deadlines'][0]['status']=='human verification required'

def test_asylum_workflow_is_trauma_informed_and_never_fabricates():
 o=legal_support('asylum_cases',{**BASE,"chronology":[{"date":"2025-02-01","event":"arrival"},{"date":"2024-01-01","event":"threat"}]})
 assert o['chronology'][0]['event']=='threat' and 'non-leading' in o['workflow'][0]

def test_prosecution_strategy_hard_codes_exculpatory_evidence_and_approval():
 o=legal_support('prosecution_strategy',{**BASE,"strategy_options":[{"option":"charge","benefits":["public safety"],"risks":["weak identity"],"authority_ids":["A1"]}]})
 assert 'exculpatory' in o['workflow'][2] and o['strategy_options'][0]['requires_approval']
 assert any('never suppress' in x for x in o['approval_gates'])

def test_missing_provenance_and_unknown_facts_block_review():
 o=legal_support('legal_research',{"jurisdiction":"X","authorities":[{"id":"bad","title":"Blog","url":"javascript:x"}],"unknowns":["forum"]})
 assert o['source_quality']['verified']==0 and o['review']['status']=='blocked'
 assert 'material facts remain unknown' in o['review']['blockers']

def test_route_is_mounted_at_module_boundary():
 app=FastAPI(); app.include_router(router); c=TestClient(app)
 r=c.post('/api/modules/20/legal/support',json={'method':'trademark_registration','data':BASE})
 assert r.status_code==200 and r.json()['module_id']==20 and r.json()['result']['artifact']=='clearance and filing worksheet'

def test_unknown_method_rejected_by_engine():
 with pytest.raises(ValueError): legal_support('not_a_method',BASE)

def test_legal_output_quantifies_provenance_and_uncertainty():
 o=legal_support('case_law_analysis',{**BASE,'tenant_id':'firm-a','issues':[{'issue':'duty','supporting_authority_ids':['A1']}]})
 assert o['tenant_id']=='firm-a' and o['evaluation']['authority_verification_rate']==1
 assert o['evaluation']['issue_support_rate']==1 and o['evaluation']['uncertainty_status']=='bounded'

def test_legal_workbench_rejects_cross_tenant_references():
 with pytest.raises(ValueError,match='cross-tenant'):
  legal_support('legal_research',{**BASE,'tenant_id':'a','resource_refs':[{'tenant_id':'b'}]})
