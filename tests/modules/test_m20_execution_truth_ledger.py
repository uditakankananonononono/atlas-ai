import pytest
from app.modules.m20_general_cognitive_worker.execution_truth import execution_truth_ledger
def test_truth_ledger_preserves_all_states_and_counts_verified_fraction():
 out=execution_truth_ledger([{'id':'p','claim':'workflow drafted','state':'planned'},{'id':'s','claim':'model run','state':'simulated'},{'id':'e','claim':'message sent','state':'externally_executed','evidence_ids':['receipt']},{'id':'v','claim':'result reproduced','state':'independently_verified','evidence_ids':['report'],'verifier':'lab-b'}])
 assert out['counts']=={'planned':1,'simulated':1,'externally_executed':1,'independently_verified':1}
 assert out['verified_fraction']==.25 and out['items'][0]['state']=='planned'
 assert 'never promoted' in out['boundary']
def test_truth_ledger_blocks_execution_or_verification_without_evidence():
 with pytest.raises(ValueError,match='evidence_ids'):execution_truth_ledger([{'id':'x','claim':'sent','state':'externally_executed'}])
 with pytest.raises(ValueError,match='verifier'):execution_truth_ledger([{'id':'x','claim':'checked','state':'independently_verified','evidence_ids':['r']}])
