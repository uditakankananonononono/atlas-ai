import pytest
from app.modules.m23_study_abroad.evidence_matrix import build_evidence_matrix
def test_application_matrix_links_owner_and_official_evidence_and_names_missing_inputs():
 out=build_evidence_matrix(
  [{'id':'deadline','text':'Apply by Jan 1','official_source_ids':['program']}],
  [{'id':'lab','text':'I restarted the science club','owner_record_ids':['activity']},{'id':'award','text':'I won an award'}],
  [{'id':'activity','text':'verified owner activity record'}],[{'id':'program','url':'https://example.edu/apply'}])
 assert not out['ready'] and out['coverage']==.6667
 assert out['missing_inputs']==[{'kind':'essay_claim','id':'award','needed':'owner record or official source'}]
 assert 'do not prove' in out['boundary']
def test_matrix_exposes_broken_references_and_rejects_blank_rows():
 out=build_evidence_matrix([{'id':'r','text':'transcript','official_source_ids':['missing']}],[],[],[])
 assert out['rows'][0]['missing_official_source_ids']==['missing']
 with pytest.raises(ValueError,match='id and text'):build_evidence_matrix([{'id':'r'}],[],[],[])
