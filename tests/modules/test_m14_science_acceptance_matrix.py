from app.modules.m14_project_builder.acceptance_trace import build_acceptance_matrix
def test_science_acceptance_matrix_traces_artifacts_hashes_and_tests():
 out=build_acceptance_matrix(
  [{'id':'reproduce','criterion':'independent rerun agrees','artifact_ids':['results'],'test_ids':['rerun']}],
  [{'id':'results','sha256':'abc','uri':'artifact://results.csv'}],[{'id':'rerun','status':'passed','report':'42 passed'}])
 assert out['passed'] and len(out['matrix_sha256'])==64
 assert 'does not claim' in out['boundary']
def test_science_acceptance_matrix_exposes_failed_missing_and_orphan_evidence():
 out=build_acceptance_matrix(
  [{'id':'calibration','criterion':'calibration valid','artifact_ids':['curve','missing'],'test_ids':['qc','absent']}],
  [{'id':'curve','sha256':''},{'id':'orphan','sha256':'ok'}],[{'id':'qc','status':'failed'}])
 row=out['matrix'][0]
 assert not out['passed']
 assert row['gaps']=={'missing_artifacts':['missing'],'missing_tests':['absent'],'failed_tests':['qc'],'artifacts_without_sha256':['curve']}
 assert out['orphan_artifact_ids']==['orphan']
def test_acceptance_matrix_rejects_duplicate_criterion_ids():
 import pytest
 with pytest.raises(ValueError,match='unique'):build_acceptance_matrix([{'id':'x'},{'id':'x'}],[],[])
