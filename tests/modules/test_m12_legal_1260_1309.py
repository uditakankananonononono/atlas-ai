import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m12_ai_research_lab.legal_support import LEGAL_METHODS,ROW_IDS,legal_support
AUTH={"title":"Controlling source","citation":"X 1","source_url":"https://law.example/x","authority_type":"primary","jurisdiction":"J","last_checked_at":"2026-09-21","holding_or_rule":"supplied rule"}
BASE={"jurisdiction":"J","as_of":"2026-09-21"}
def payload(method):
 d=dict(BASE)
 if method in {"sentencing_guidelines","criminal_appeals","constitutional_law","first_amendment","fourth_amendment","due_process","equal_protection","administrative_law","regulatory_practice","agency_proceedings","judicial_review","international_law","treaties","human_rights","international_trade"}: d|={"authorities":[AUTH,{**AUTH,"citation":"Y 2","is_contrary":True}],"issues":[{"issue":"scope","elements_or_standard":["element"],"facts_supporting":["fact"],"missing_facts":[],"authority_citations":["X 1"]}]}
 elif method in {"arbitration","mediation","dispute_resolution","litigation_strategy","discovery","depositions","trial_preparation","evidence_analysis","witness_preparation","jury_selection","appellate_practice","legal_writing","legal_citations","brief_writing","oral_argument"}: d|={"authorities":[AUTH],"objectives":["preserve issue"],"tasks":[{"id":"t","task":"review record","evidence_refs":["e1"]}]}
 elif method in {"legal_ethics","professional_responsibility","conflicts_of_interest","attorney_client_privilege","legal_malpractice","pro_bono_practice","legal_aid","access_to_justice"}: d|={"authorities":[AUTH],"parties":[{"id":"p"}],"facts":["identity"],"duties":[{"duty":"loyalty","required_facts":["identity"]}]}
 elif method in {"legal_technology","e_discovery","legal_analytics","predictive_coding","document_review"}: d|={"documents":[{"id":"d","sha256":"abc","labels":["responsive"],"privilege_candidate":True}],"protocol":{"labels":["responsive"]},"validation_set":{"true_positive":8,"false_positive":2,"false_negative":2}}
 else:d|={"matters":[{"id":"m","budget":100,"entries":[{"amount":40}],"milestones":["review"]}],"controls":["approval"]}
 return d
@pytest.mark.parametrize('method',sorted(LEGAL_METHODS,key=lambda x:ROW_IDS[x]))
def test_every_ledger_row_has_real_bounded_implementation(method):
 o=legal_support(method,payload(method)); assert o['row_id']==ROW_IDS[method] and o['concept'] and o['review_required'] and o['boundary'] and o['disclaimer']
def test_doctrine_preserves_adverse_authority_and_missing_fact_status():
 d=payload('first_amendment');d['issues'][0]['missing_facts']=['forum'];o=legal_support('first_amendment',d);assert o['contrary_authorities'][0]['citation']=='Y 2' and o['issue_matrix'][0]['status']=='incomplete'
def test_predictive_coding_reports_validation_not_fake_certainty():
 o=legal_support('predictive_coding',payload('predictive_coding'));assert o['validation']=={'precision':.8,'recall':.8,'sample_size':12} and o['documents'][0]['human_review_status']=='pending'
def test_legal_billing_computes_variance_but_cannot_approve_invoice():
 o=legal_support('legal_billing',payload('legal_billing'));assert o['matter_summary'][0]['variance']==60 and o['matter_summary'][0]['billing_review_status']=='pending'
def test_rejects_missing_jurisdiction_source_and_unknown_method():
 with pytest.raises(ValueError):legal_support('constitutional_law',{'as_of':'2026-09-21'})
 with pytest.raises(ValueError):legal_support('constitutional_law',BASE|{'issues':[{'issue':'x'}],'authorities':[]})
 with pytest.raises(ValueError):legal_support('not_real',BASE)
def test_mounted_route_is_tenant_scoped_and_counsel_gated():
 r=TestClient(app).post('/api/v1/ai-research-lab/legal/support',headers={'x-atlas-tenant':'tenant-7'},json={'method':'legal_education','data':payload('legal_education')});assert r.status_code==200 and r.json()['tenant_id']=='tenant-7' and r.json()['requires_counsel_review']
