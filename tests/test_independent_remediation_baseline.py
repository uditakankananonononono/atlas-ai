import json
from pathlib import Path


def test_remediation_baseline_keeps_conservative_counts_and_evidence_rules():
    baseline=json.loads(Path('audits/independent-remediation-baseline.json').read_text())
    assert baseline['technical_spec']=={'total':229,'substantiated':47,'thin_or_unsubstantiated':173,'missing':9}
    assert baseline['expanded_features']=={'total':2010,'focused_test_locator_resolves':304,'thin_or_unsubstantiated':1706,'proven_absent':0}
    assert baseline['second_design']=={'substantive_paragraphs':217,'verified':0,'unverified':217}
    rules=' '.join(baseline['rules'])
    assert 'path' in rules and 'failure path' in rules and 'acceptance artifact' in rules
