"""Exact supplied-input vectors. No physical validation or approval claim."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from test_engine_routes import CASES

EXPECTED=[
 {'n':2,'center_line':'1','moving_range_mean':'2','sigma_hat':'1.773049645','ucl':'6.319148936','lcl':'-4.319148936','flags':[],'sigma_estimator':'MRbar/1.128','baseline_only':True,'control_state_claimed':False,'process_intervention_advised':False},
 {'n':2,'mean':'1','sigma_within':'1.773049645','sigma_overall':'1.414213562','cp':'0.564','cpu':'0.564','cpl':'0.564','cpk':'0.564','pp':'0.707106781','ppu':'0.707106781','ppl':'0.707106781','ppk':'0.707106781','within_sigma_estimator':'MRbar/1.128','overall_sigma_estimator':'sample standard deviation (n-1)','normality_assumed':True,'stability_established':False,'process_acceptance_claimed':False},
 {'grand_mean':'3','parts':2,'operators':2,'replicates':2,'variance_components':{'repeatability':'2','interaction':'0','operator':'0','reproducibility':'0','part_to_part':'8','gage_rr':'2','total':'10'},'percent_contribution':{'repeatability':'20','reproducibility':'0','gage_rr':'20','part_to_part':'80'},'standard_deviations':{'repeatability':'1.414213562','interaction':'0','operator':'0','reproducibility':'0','part_to_part':'2.828427125','gage_rr':'1.414213562','total':'3.16227766'},'truncated_components':['interaction'],'gauge_approval_claimed':False},
 {'design_type':'full_factorial','fraction':'2^2','factor_count':2,'base_factors':['A','B'],'generated_factors':[],'run_count':4,'run_matrix':[{'A':-1,'B':-1},{'A':1,'B':-1},{'A':-1,'B':1},{'A':1,'B':1}],'defining_relation':[],'alias_classes':[],'resolution':None,'run_order':'standard order, not randomized','randomization_required':True,'experiment_executed':False,'causal_claims_made':False},
 {'goal':'smaller','run_count':1,'runs':[{'id':'one','levels':[1],'response_count':1,'signal_to_noise_db':'0.000000'}],'factor_summaries':[{'factor':'A','observed_levels':[1],'balanced':True,'level_mean_sn':{'1':'0.000000'}}],'array_status':'pairwise_balanced','robustness_certified':False,'requires_engineer_review':True,'scope':'declared_runs_array_and_sn_bookkeeping_only'},
 {'factor_count':1,'point_count':3,'term_names':['1','x','x^2'],'design_matrix':[['1','0','0'],['1','1','1'],['1','2','4']],'design_rank':3,'residual_degrees_of_freedom':0,'full_column_rank':True,'response_sum':'8','response_mean':'8/3','fit_executed':False,'prediction_validated':False,'release_authorized':False,'physical_validity_verified':False,'scope':'caller_supplied_bookkeeping_only'},
 {'objective':'maximize','scenario_count':2,'scenarios':[{'id':'a','control':{'c':'1'},'noise':{'n':'0'},'response':'1/3'},{'id':'b','control':{'c':'1'},'noise':{'n':'1'},'response':'2/3'}],'response_mean':'1/2','response_range':'1/3','population_variance':'1/36','worst_case_response':'1/3','robustness_guaranteed':False,'release_authorized':False,'physical_validity_verified':False,'scope':'caller_supplied_bookkeeping_only'}]
EMPTY_DETAILS=[
 'SPC1536: invalid_series_id: series_id requires non-blank text',
 'PROCAP1537: invalid_study_id: study_id requires non-blank text',
 'MEASYS1538: invalid_study_id: study_id requires non-blank text',
 'DESEXP1539: invalid_design_id: design_id requires non-blank text',
 'TAGUCH1540:unknown_fields:packet','RESPSU1541: packet schema','ROBUST1542: packet schema']
EXTRA_DETAILS=['SPC1536: unknown key in payload','PROCAP1537: unknown key in payload','MEASYS1538: unknown key in payload','DESEXP1539: unknown key in payload','TAGUCH1540:unknown_fields:packet','RESPSU1541: packet schema','ROBUST1542: packet schema']

@pytest.fixture
def mounted(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    return TestClient(app)

@pytest.mark.parametrize('index',range(7))
def test_exact_hand_vector(mounted,oidc_auth_headers,index):
    engine,entry,data,key,value=CASES[index]
    r=mounted.post('/api/v1/api/modules/20/engineering/'+engine+'/run',json={'data':deepcopy(data)},headers=oidc_auth_headers('vector-tenant','vector-actor'))
    assert r.status_code==200,r.text
    out=r.json()
    assert {k:out[k] for k in EXPECTED[index]}==EXPECTED[index]
    assert out['tenant_id']=='vector-tenant' and out['actor_id']=='vector-actor'

@pytest.mark.parametrize('index',range(7))
def test_exact_engine_refusal_details(mounted,oidc_auth_headers,index):
    engine,entry,data,key,value=CASES[index]
    path='/api/v1/api/modules/20/engineering/'+engine+'/run'
    for packet,detail in [({},EMPTY_DETAILS[index]),(dict(deepcopy(data),zz=True),EXTRA_DETAILS[index])]:
        r=mounted.post(path,json={'data':packet},headers=oidc_auth_headers())
        assert r.status_code==422
        assert r.json()=={'detail':detail}
