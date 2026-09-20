import json
from collections import Counter
from pathlib import Path
AUDIT=json.loads(Path('audits/additional-2000-features.json').read_text())
def test_owner_additional_doc_is_fully_rowized():
 assert len(AUDIT['rows'])==2009
 assert [x['id'] for x in AUDIT['rows']]==list(range(1,2010))
 assert Counter(x['category_id'] for x in AUDIT['rows'])==Counter({0:9,1:100,2:150,3:100,4:150,5:200,6:100,7:100,8:100,9:100,10:900})
def test_no_new_feature_is_falsely_verified_on_intake():
 assert AUDIT['counts']=={'verified-pushed':0,'thin':0,'missing':2009}
 assert all(x['status']=='missing' and x['requirement'] and x['boundary'] for x in AUDIT['rows'])

def test_live_doc_delta_is_exact_and_chain_of_thought_is_bounded():
 assert AUDIT['delta_from_schema_version_1']=={'added':9,'removed':0,'changed':0,'unchanged':2000}
 reasoning=next(x for x in AUDIT['rows'] if x['requirement']=='Chain-of-Thought Capture')
 assert 'owner-authored reasoning notes' in reasoning['boundary'] and 'no hidden chain-of-thought' in reasoning['boundary'].lower()
