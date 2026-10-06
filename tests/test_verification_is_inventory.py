"""Negative certification tests. File existence and ledger text cannot prove behavior."""
import json
from pathlib import Path
from app.semantic_verification_862_1148 import validate
from app.runtime.semantic_verification_1149_1435 import verify_evidence, report as middle
from app.runtime.semantic_wave_1723_2010 import report as wave
ROOT=Path(__file__).resolve().parents[1]


def test_all_three_legacy_inventories_refuse_behavior_certification():
    first=validate()
    assert first['passed'] is False
    assert first['counts']['pass']==0
    assert first['counts']['unverified']==287
    second=middle()
    assert second['passed']==0
    assert second['unverified']==287
    ledger=json.loads((ROOT/'audits/additional-2000-features.json').read_text())['rows']
    third=wave(ledger)
    assert len(third)==288
    assert all(r['outcome']=='unverified' and not r['fixed'] for r in third)


def test_row_number_in_source_and_matching_paths_cannot_pass(tmp_path,monkeypatch):
    import app.runtime.semantic_verification_1149_1435 as verifier
    (tmp_path/'source.py').write_text('row = 1149\ndef run(): return "pass"\n')
    (tmp_path/'test.py').write_text('def test_row_1149(): assert 1149 == 1149\n')
    monkeypatch.setattr(verifier,'ROOT',tmp_path)
    r=verify_evidence({'id':1149,'requirement':'real computation','evidence':{'implementation_path':'source.py','test_path':'test.py'}})
    assert r['artifact_checks_passed']
    assert not r['pass']
    assert r['status']=='unverified'
