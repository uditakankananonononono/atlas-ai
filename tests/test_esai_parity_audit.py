import json
from pathlib import Path
A=json.loads(Path('audits/esai-feature-parity.json').read_text())
def test_esai_surface_is_officially_sourced_and_rowized():
 assert len(A['rows'])==35
 assert all(x.startswith('https://www.esai.ai/') for x in A['sources'])
 assert any(r['feature']=='Common App integration' for r in A['rows'])
def test_no_ghostwriting_is_verified():
 row=next(x for x in A['rows'] if x['feature']=='Student-owned no-ghostwriting workflow');assert row['status']=='verified-pushed'

def test_enhanced_career_parity_rows_have_commit_route_and_focused_tests():
 ids={7,9,21,22,23,24,25,26,27}
 rows=[r for r in A['rows'] if r['id'] in ids]
 assert len(rows)==9 and all(r['status']=='verified-pushed' for r in rows)
 assert all(len(r['evidence']['commit'])==40 and 'routes.py' in r['evidence']['implementation'] and Path(r['evidence']['test']).exists() for r in rows)
 assert all(r.get('enhancement') for r in rows)

def test_all_esai_rows_are_verified_with_enhanced_remaining_batch():
 assert all(r['status']=='verified-pushed' for r in A['rows'])
 ids={2,6,8,10,16,29,30,31,32,34}
 rows=[r for r in A['rows'] if r['id'] in ids]
 assert all(len(r['evidence']['commit'])==40 and Path(r['evidence']['test']).exists() and r.get('enhancement') for r in rows)
