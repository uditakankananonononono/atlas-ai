import json
from collections import Counter
from pathlib import Path
AUDIT=json.loads(Path('audits/additional-2000-features.json').read_text())
def test_owner_additional_doc_is_fully_rowized():
 assert len(AUDIT['rows'])==2010
 assert [x['id'] for x in AUDIT['rows']]==list(range(1,2011))
 assert Counter(x['category_id'] for x in AUDIT['rows'])==Counter({0:10,1:100,2:150,3:100,4:150,5:200,6:100,7:100,8:100,9:100,10:900})
def test_feature_counts_match_current_verified_evidence():
 assert AUDIT['counts']=={'verified-pushed':178,'thin':3,'missing':1829}
 assert all(x['requirement'] and x['boundary'] for x in AUDIT['rows'])
 assert {x['status'] for x in AUDIT['rows']} <= {'verified-pushed','thin','missing'}

def test_live_doc_delta_is_exact_and_chain_of_thought_is_bounded():
 assert AUDIT['delta_from_schema_version_1']=={'added':9,'removed':0,'changed':0,'unchanged':2000}
 reasoning=next(x for x in AUDIT['rows'] if x['requirement']=='Chain-of-Thought Capture')
 assert 'owner-authored reasoning notes' in reasoning['boundary'] and 'no hidden chain-of-thought' in reasoning['boundary'].lower()

def test_flipped_rows_have_commit_and_test_evidence():
 for x in AUDIT['rows']:
  if x['status']!='missing':
   assert len(x['evidence']['commit'])==40
   assert Path(x['evidence']['implementation_path']).exists()
   assert Path(x['evidence']['test_path']).exists()


def test_latest_live_doc_delta_and_application_boundary():
 assert AUDIT["schema_version"]==4
 assert AUDIT["changed_requirements"][0]["requirement"] == "Universal multi-field creation, application structuring, tool discovery and resilient result-seeking"
 assert AUDIT["delta_from_schema_version_3"]=={"added":1,"removed":0,"changed":0,"unchanged":2009}
 universal=AUDIT["rows"][0]
 assert "signs me up for competitions" in universal["description"]
 assert "exact-preview human review" in universal["boundary"]
 assert "never evade detection" in universal["boundary"]
