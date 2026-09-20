import json
from pathlib import Path
A=json.loads(Path('audits/esai-feature-parity.json').read_text())
def test_esai_surface_is_officially_sourced_and_rowized():
 assert len(A['rows'])==35
 assert all(x.startswith('https://www.esai.ai/') for x in A['sources'])
 assert any(r['feature']=='Common App integration' for r in A['rows'])
def test_no_ghostwriting_is_verified():
 row=next(x for x in A['rows'] if x['feature']=='Student-owned no-ghostwriting workflow');assert row['status']=='verified-pushed'
