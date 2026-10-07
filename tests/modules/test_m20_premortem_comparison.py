from app.modules.m20_general_cognitive_worker.foresight import PremortemEngine


def test_complete_supplied_risk_register_never_verifies_evidence_or_approval():
    supplied={'id':'r','cause':'fixture','severity':3,'occurrence':4,'detection':2,'owner':'supplied owner','mitigation':'supplied mitigation','test':'supplied test','evidence':['unverified receipt']}
    report=PremortemEngine().assess_register(goal='fixture',risks=[supplied])
    assert report['ready_for_owner_review'] and report['review_status_is_completeness_only']
    assert not report['probabilities_inferred'] and not report['evidence_verified'] and not report['external_actions_executed']
    assert report['risks'][0]['risk_priority_number']==24
    assert report['risks'][0]['control_status']=='supplied_evidence_unverified'
    supplied['evidence'][0]='caller changed'
    assert report['risks'][0]['evidence']==['unverified receipt']


def test_placeholder_premortem_scores_remain_labeled_unmeasured():
    report=PremortemEngine().analyze(goal='fixture',risks=['supplied risk'])
    assert report['causes'][0]['score']==0.35
    assert any('placeholder scores' in line for line in report['assumptions'])
