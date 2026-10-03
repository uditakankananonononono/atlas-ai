"""Regression tests for observed false claims, not full M23 acceptance."""
import math
import pytest
from app.modules.m23_study_abroad.lifecycle_unverified_01_62 import run
from app.modules.m23_study_abroad.service import Service
from app.modules.m23_study_abroad.schemas import StudentProfileIn, UniversityIn

def output(method, data):
    return run(method, data)['output']

def test_regex_does_not_claim_loaded_nlp():
    x = output('nlp_stack', {'text': 'Apply 2027-02-30 to Oxford University'})
    assert x['bert_ready'] is False
    assert x['pipeline'] == ['python_regex']
    assert x['dates'] == []
    assert x['entity_candidates']
    assert x['semantic_model_loaded'] is False

@pytest.mark.parametrize('claim', [True, False, 'approved', {'approved': True}, 1])
def test_caller_boolean_never_authorizes_submission(claim):
    x = output('submission_approval', {'artifact':'application','module0_approval':claim})
    assert x['submission_allowed'] is False
    assert x['state'] == 'blocked'
    assert x['approval_verified'] is False

@pytest.mark.parametrize('records', [
    [{'official_url':'garbage','checked_at':'now'}],
    [{'official_url':'https://u.example/a','checked_at':'garbage'}],
    [{'official_url':'https://u.example/a','checked_at':'2999-01-01'}],
    [{'official_url':'https://u.example/a','checked_at':'2026-01-01','source_verified':True}],
])
def test_input_metadata_does_not_become_verification(records):
    x = output('official_monitoring', {'records':records})
    assert x['verified_records'] == []
    assert x['coverage'] == 0
    assert x['verification_performed'] is False

def test_valid_metadata_coverage_and_invalid_calendar_date():
    x = output('program_intelligence', {'records':[
        {'official_url':'https://u.example/a','checked_at':'2026-01-01'},
        {'official_url':'https://u.example/a','checked_at':'2026-02-30'}]})
    assert x['metadata_coverage'] == .5
    assert x['coverage'] == 0

def test_missing_admission_probability_is_unknown():
    x = output('fit_scoring', {'schools':[{'name':'A','fit':.7}]})
    assert x['schools'][0]['probability'] is None
    assert x['schools'][0]['bucket'] == 'unavailable'
    assert x['counts']['unavailable'] == 1

@pytest.mark.parametrize('value', [-.1,1.1,float('nan'),float('inf'),True,'bad'])
def test_invalid_probability_rejected(value):
    with pytest.raises(ValueError):
        output('fit_scoring', {'schools':[{'name':'A','estimated_admit_probability':value}]})

def test_service_fit_labels_heuristic_and_does_not_predict_admission():
    profile=StudentProfileIn(values=[],turning_points=[],strengths=[],goals=['science'])
    u=UniversityIn(id='u',name='U',country='US',programs=['Computer Science'],official_url='https://u.example')
    x=Service().fit(profile,[u])[0]
    assert x['scoring_method'] == 'substring_budget_heuristic'
    assert x['band'] == 'unavailable'
    assert x['admission_probability'] is None
    assert x['evidence']['budget_fit'] is None

def test_backend_lists_and_language_catalog_are_not_execution():
    for method,data in [('collectors',{'collectors':[]}),('multi_provider_ai',{'providers':[{'healthy':True}]}),('languages_12',{'language':'Assamese'}),('vector_embeddings',{'query':[1,0],'items':[]})]:
        x=output(method,data)
        assert x['execution_performed'] is False
        assert x['input_provenance'] == 'caller_supplied_unverified'

@pytest.mark.parametrize('stamp', ['2026-01-01T00:00:00', '2999-01-01T00:00:00Z','2026-02-30','now'])
def test_invalid_or_ambiguous_metadata_timestamps(stamp):
    x=output('official_monitoring',{'records':[{'official_url':'https://u.example/a','checked_at':stamp}]})
    assert x['metadata_coverage'] == 0

@pytest.mark.parametrize('url', ['not-a-url','https://','https://user:pass@u.example/a','https://bad host/a','javascript:alert(1)'])
def test_malformed_metadata_urls(url):
    x=output('official_monitoring',{'records':[{'official_url':url,'checked_at':'2026-01-01'}]})
    assert x['metadata_coverage'] == 0

def test_supplied_probability_is_named_not_prediction():
    x=output('fit_scoring',{'schools':[{'name':'A','estimated_admit_probability':0.8}]})['schools'][0]
    assert x['probability_source']=='caller_supplied_unverified'
    assert x['bucket_method']=='caller_probability_threshold_heuristic'

def test_ranking_and_hash_are_not_global_data_or_semantics():
    x=output('top_institutions',{'institutions':[{'name':'A','rank':1,'official_source':'garbage'}]})
    assert x['rankings_verified'] is False and x['dataset_loaded'] is False
    assert output('identity_embedding',{'identity_text':'scientist'})['semantic_model_loaded'] is False

def test_mounted_boolean_approval_and_invalid_probability():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m23_study_abroad.lifecycle_routes_01_62 import router
    app=FastAPI();app.include_router(router);client=TestClient(app)
    x=client.post('/lifecycle-workbench/analyze',json={'method':'submission_approval','data':{'artifact':'A','module0_approval':True,'approval_id':'forged'}})
    assert x.status_code==200 and x.json()['output']['submission_allowed'] is False
    x=client.post('/lifecycle-workbench/analyze',json={'method':'fit_scoring','data':{'schools':[{'name':'A','estimated_admit_probability':1.2}]}})
    assert x.status_code==422
