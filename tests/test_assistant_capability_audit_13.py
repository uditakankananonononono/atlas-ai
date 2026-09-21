import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.runtime.capability_audit_13 import audit,load_ledger,verify_row

def row(n):return load_ledger()['rows'][n-1]
def test_row_1_approval_center_current_evidence(): assert verify_row(row(1))['code_verified']
def test_row_2_modules_1_4_current_evidence(): assert verify_row(row(2))['mounted_modules']==[1,2,3,4] and verify_row(row(2))['code_verified']
def test_row_3_modules_5_6_current_evidence(): assert verify_row(row(3))['mounted_modules']==[5,6] and verify_row(row(3))['code_verified']
def test_row_4_modules_7_20_current_evidence(): assert verify_row(row(4))['mounted_modules']==list(range(7,21)) and verify_row(row(4))['code_verified']
def test_row_5_claire_current_evidence(): assert verify_row(row(5))['mounted_modules']==[21] and 'deception' in row(5)['failure_contract']
def test_row_6_tools_hub_current_evidence(): assert verify_row(row(6))['code_verified'] and 'provenance' in row(6)['failure_contract']
def test_row_7_billing_current_evidence(): assert verify_row(row(7))['code_verified'] and 'webhook' in row(7)['failure_contract']
def test_row_8_email_current_evidence(): assert verify_row(row(8))['code_verified'] and 'exact payload' in row(8)['failure_contract']
def test_row_9_calendar_current_evidence(): assert verify_row(row(9))['code_verified'] and 'conflicts' in row(9)['failure_contract']
def test_row_10_browsing_current_evidence(): assert verify_row(row(10))['code_verified'] and 'unsafe URLs' in row(10)['failure_contract']
def test_row_11_monitoring_current_evidence(): assert verify_row(row(11))['code_verified'] and 'twice' in row(11)['failure_contract']
def test_row_12_drafting_research_files_current_evidence(): assert verify_row(row(12))['code_verified'] and verify_row(row(12))['mounted_modules']==[3,4,15]
def test_row_13_deployment_is_honest_about_external_readiness():
 x=verify_row(row(13));assert x['code_verified'] and not x['production_ready'] and set(x['production_missing_attestations'])=={'secrets','tls','migrations','observability','backups'}
 y=verify_row(row(13),['secrets','tls','migrations','observability','backups']);assert y['production_ready']
def test_failure_invalid_ledger_shape_and_missing_evidence(tmp_path,monkeypatch):
 import app.runtime.capability_audit_13 as m
 p=tmp_path/'bad.json';p.write_text('{"schema_version":1,"row_count":13,"rows":[]}');monkeypatch.setattr(m,'LEDGER',p)
 with pytest.raises(RuntimeError):m.load_ledger()
 x=verify_row({'id':1,'surface':'x','module_ids':[999], 'required_evidence':['absent'], 'failure_contract':'fail'})
 assert not x['code_verified'] and x['missing_modules']==[999] and x['missing_files']==['absent']
def test_mounted_endpoints_and_unknown_row():
 c=TestClient(app);base='/api/v1/runtime/capability-audit-13'
 assert len(c.get(base+'/ledger').json()['rows'])==13
 r=c.post(base+'/verify',json={'production_attestations':[]});assert r.status_code==200 and r.json()['code_verified_count']==13 and not r.json()['production_ready']
 assert c.get(base+'/rows/14').status_code==404
