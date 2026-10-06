from app.modules.m20_general_cognitive_worker.metacognition import BiasDetector,IntuitionEngine,PerspectiveSimulator,DevilsAdvocate,SteelmanEngine


def test_templates_and_cache_never_claim_bias_correction_intuition_or_probabilities():
 bias=BiasDetector().scan_with_correction('success is guaranteed')
 assert bias['status']=='marker_checklist_only' and not bias['capability_executed']
 assert 'corrected_prompt' not in bias and all(f['severity'] is None for f in bias['findings'])
 gut=IntuitionEngine().gut('unknown',skill_matches=[],fact_hits=[])
 assert gut.confidence is None and not gut.capability_executed
 comparison=IntuitionEngine().validate(gut,lambda:'plausible supplied text')
 assert comparison['validated'] is False and comparison['comparison_method']=='casefolded_substring'
 for v in PerspectiveSimulator().evaluate({'evidence_count':9999,'upside':9999}):
  assert v.score is None and not v.capability_executed
 for count in (0,1,100):
  r=DevilsAdvocate().stress_test(claim='we will win',assumptions=['market demand'],evidence=['junk']*count)
  assert r.residual_confidence is None and r.alternative_explanations==[] and not r.capability_executed
 steel=SteelmanEngine().strengthen(opposing_position='x',known_facts=['x']*100)
 assert steel.strongest_form=='' and not steel.capability_executed
