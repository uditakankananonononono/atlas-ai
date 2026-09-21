import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.context import require_tenant, TenantContext
from app.modules.m12_ai_research_lab.clinical_rows_1110_1209 import ROW_HANDLERS, ROW_METHODS, execute_clinical_row

SRC={'source_url':'https://guidelines.test/validated','source_title':'Validated guideline'}

def test_all_100_rows_have_distinct_named_callable_and_method():
    assert set(ROW_HANDLERS)==set(range(1110,1210))
    assert len({handler.__name__ for handler in ROW_HANDLERS.values()})==100
    for row,handler in ROW_HANDLERS.items():
        assert handler.__name__.startswith(f'row_{row}_')
        assert ROW_METHODS[row] in handler.__name__

def test_row_1125_executes_calibrated_readmission_model_with_provenance():
    model={'name':'M','version':'2','intercept':-2,'coefficients':{'age':.1},'link':'logistic','thresholds':[{'minimum':0,'label':'low'}],'source':SRC,'validation_population':'cohort','calibration':{'slope':1}}
    out=execute_clinical_row(1125,{'factors':{'age':20},'model':model})
    assert out['named_function']=='row_1125_readmission_prediction'
    assert out['result']['probability']==pytest.approx(.5)
    assert out['evidence_provenance']==[SRC]
    assert any(x['metric']=='probability' for x in out['calibrated_metrics'])
    assert out['clinician_review']['required']

def test_row_1196_marks_immediate_suicide_response_without_autonomous_action():
    out=execute_clinical_row(1196,{'safety':{'imminent_intent':True,'active_attempt':False,'immediate_danger':False,'cannot_stay_safe':False},'source':SRC})
    assert out['urgent_response']['required'] is True
    assert 'do not wait' in out['urgent_response']['instruction']
    assert 'does not diagnose, prescribe' in out['clinician_review']['boundary']

def test_row_execution_refuses_missing_evidence_and_unknown_row():
    with pytest.raises(ValueError,match='source_url'): execute_clinical_row(1203,{'measures':[{'numerator':1,'denominator':2}],'source':{}})
    with pytest.raises(ValueError,match='between 1110 and 1209'): execute_clinical_row(999,{'source':SRC})

def test_mounted_row_catalog_and_row_route_fail_closed():
    app.dependency_overrides[require_tenant]=lambda:TenantContext(tenant_id='t',actor_id='u')
    client=TestClient(app)
    catalog=client.get('/api/v1/ai-research-lab/clinical/rows')
    assert catalog.status_code==200 and len(catalog.json())==100
    bad=client.post('/api/v1/ai-research-lab/clinical/1203/execute',json={'data':{'measures':[],'source':SRC}})
    assert bad.status_code==422
    app.dependency_overrides.clear()
