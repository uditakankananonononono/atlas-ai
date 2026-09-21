import pytest
from app.core.depth_quality import attach_quality, quality_envelope


def test_quality_contract_reports_missing_inputs_uncited_evidence_and_no_side_effects():
    q=quality_envelope(domain='legal',method='contract_review',inputs={'document':'x'},result={'issues':[]},required_inputs=['document','jurisdiction'],evidence=[{'text':'claim'}],assumptions=['unsigned draft'])
    assert q['evaluation']['missing_inputs']==['jurisdiction']
    assert q['evaluation']['uncited_evidence_items']==1
    assert q['evaluation']['status']=='needs_review'
    assert q['uncertainty']['level']=='high'
    assert q['review_gate']=='licensed_attorney_review' and q['side_effects']=='none'


def test_quality_contract_never_turns_completeness_into_outcome_confidence():
    q=quality_envelope(domain='finance',method='npv',inputs={'cashflows':[1]},result={'npv':1},required_inputs=['cashflows'])
    assert q['evaluation']['input_completeness']==1
    assert q['uncertainty']['basis']=='coverage_and_declared_assumptions_not_outcome_probability'
    assert 'confidence' not in q and 'probability' not in q


def test_quality_contract_rejects_unknown_domain_and_overwrite():
    with pytest.raises(ValueError): quality_envelope(domain='physical',method='x',inputs={},result={})
    with pytest.raises(ValueError): attach_quality({'quality':{}},domain='education',method='x',inputs={})
