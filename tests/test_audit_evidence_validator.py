import json
from pathlib import Path
import importlib.util
_spec=importlib.util.spec_from_file_location('audit_validator',Path('scripts/validate_audit_evidence.py'))
_module=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_module)
validate=_module.validate

def test_validator_rejects_file_only_and_missing_node_but_accepts_real_node(tmp_path):
    test=tmp_path/'test_product.py';test.write_text('def test_behavior():\n assert 2+2==4\n')
    ledger=tmp_path/'ledger.json';ledger.write_text(json.dumps({'rows':[
      {'id':1,'test_evidence':str(test)+'::test_behavior'},
      {'id':2,'test_evidence':str(test)},
      {'id':3,'test_evidence':str(test)+'::test_absent'}]}))
    report=validate(ledger)
    assert report['resolvable_nodes']==1 and report['unresolved']==2
    assert report['results'][0]['resolved']
    assert report['results'][1]['reason']=='shared file only; no pytest node'
    assert report['results'][2]['reason']=='pytest node not found'

def test_checked_in_report_preserves_unresolved_rows_instead_of_upgrading_them():
    report=json.loads(Path('audits/evidence-resolution-report.json').read_text())
    by_name={Path(r['ledger']).name:r for r in report['reports']}
    assert by_name['technical-spec-line-by-line.json']['total']==229
    assert by_name['technical-spec-line-by-line.json']['unresolved']>0
    assert by_name['additional-2000-features.json']['total']==2010
    assert by_name['additional-2000-features.json']['unresolved']>0
