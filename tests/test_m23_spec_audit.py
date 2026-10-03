import json
from collections import Counter
from pathlib import Path
A=json.loads(Path('audits/module-23-study-abroad.json').read_text())
def test_m23_full_spec_is_rowized_without_self_certification():
 assert len(A['rows'])==62
 assert A['counts']==dict(Counter(r['status'] for r in A['rows']))
 assert set(A['counts']) <= {'VERIFIED','SCOPED','PARTIAL','OVERSTATED','UNSUPPORTED'}
 assert all(r['status']=='PARTIAL' and r['previous_status']=='verified-pushed' for r in A['rows'])
 assert all(x.startswith('https://www.esai.ai') for x in A['esai_sources'])
def test_m23_evidence_is_traceable_not_acceptance():
 for r in A['rows']:
  assert r['status_basis']
  assert Path(r['evidence']['implementation']).exists() and Path(r['evidence']['test']).exists()
