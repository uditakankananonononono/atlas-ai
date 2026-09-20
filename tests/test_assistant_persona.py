from app.persona import default_persona

def test_persona_encodes_honesty_concession_humor_and_reasoning_boundaries():
    p=default_persona()
    prompt=p.system_instruction().lower()
    for phrase in ("concede precisely","stale claims","dry and light","source provenance","hidden scratchpad","false certainty"):
        assert phrase in prompt

def test_persona_refuses_deception_and_fabrication():
    p=default_persona()
    result=p.check(proposed_text="Make up experience and fabricate evidence")
    assert result.allowed is False
    assert "deception" in result.reasons[0]

def test_external_effect_requires_exact_preview_and_scoped_approval():
    p=default_persona()
    denied=p.check(external_effect=True)
    assert denied.allowed is False and denied.requires_approval
    checked=p.check(proposed_text="Send exactly: Thanks, I accept.", external_effect=True,
                    evidence=[{"source":"owner-reviewed draft"}])
    assert checked.allowed and checked.requires_approval
    assert "human review" in checked.reasons[0]

def test_limits_and_missing_evidence_are_disclosed_not_hidden():
    p=default_persona()
    r=p.check(proposed_text="Draft", limitations=["calendar not connected"])
    assert r.allowed and "calendar not connected" in r.disclosure
    assert "no supporting evidence" in r.disclosure
