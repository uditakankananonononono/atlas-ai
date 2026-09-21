import json
from pathlib import Path
A=json.loads(Path('audits/module-23-study-abroad.json').read_text())
def test_m23_full_spec_is_rowized_and_esai_grounded():
 assert len(A['rows'])==62
 assert A['counts']=={'thin':0,'missing':0,'verified-pushed':62}
 assert all(x.startswith('https://www.esai.ai') for x in A['esai_sources'])
def test_m23_verified_rows_have_code_and_tests():
 for r in A['rows']:
  if r['status']=='verified-pushed':
   assert Path(r['evidence']['implementation']).exists() and Path(r['evidence']['test']).exists()
