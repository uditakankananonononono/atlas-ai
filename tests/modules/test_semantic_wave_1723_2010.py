import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.runtime.semantic_wave_1723_2010 import report
from app.runtime.semantic_wave_routes_1723_2010 import router as report_router
from app.modules.m16_executive_dashboard.semantic_ai_routes_1910_1959 import router as ai_router
ROOT=Path(__file__).resolve().parents[2]
def test_all_288_rows_have_exact_pass_report_and_real_files():
 ledger=json.loads((ROOT/'audits/additional-2000-features.json').read_text())['rows'];r=report(ledger)
 assert [x['row_id'] for x in r]==list(range(1723,2011)) and all(x['outcome']=='pass' for x in r)
 for x in r:assert (ROOT/x['implementation_path']).is_file() and (ROOT/x['test_path']).is_file() and x['distinctive_invariant']
def test_2010_provenance_is_later_owner_input_not_features_doc():
 ledger=json.loads((ROOT/'audits/additional-2000-features.json').read_text())['rows'];x=report(ledger)[-1]
 assert x['row_id']==2010 and x['provenance']=='later_owner_input' and 'not the 2,000-feature Google Doc' in x['source_document']
def test_report_fails_closed_on_missing_row():
 ledger=json.loads((ROOT/'audits/additional-2000-features.json').read_text())['rows']
 try:report([x for x in ledger if x['id']!=1800])
 except ValueError as e:assert '1800' in str(e)
 else:raise AssertionError('missing row accepted')
def test_report_is_mounted():
 a=FastAPI();a.include_router(report_router);r=TestClient(a).get('/semantic-wave-1723-2010/report');assert r.status_code==200 and len(r.json())==288
def test_ai_rows_now_have_direct_mounted_http_success_and_invalid_input():
 a=FastAPI();a.include_router(ai_router);c=TestClient(a)
 methods=c.get('/ai-systems-1910-1959/methods');assert methods.status_code==200 and len(methods.json())==50
 ok=c.post('/ai-systems-1910-1959/analyze',json={'method':'zero_shot_learning','data':{'predictions':['a'],'targets':['a'],'shots':0}});assert ok.status_code==200 and ok.json()['feature_row']==1955
 bad=c.post('/ai-systems-1910-1959/analyze',json={'method':'zero_shot_learning','data':{'predictions':['a'],'targets':['a'],'shots':1}});assert bad.status_code==422
