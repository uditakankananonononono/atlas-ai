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


def test_no_default_risk_probabilities_or_invented_skill_gain():
 from app.modules.m20_general_cognitive_worker.metacognition import CounterfactualEngine,FlowStateManager,ReframingEngine,PlanningHorizonController
 from app.modules.m20_general_cognitive_worker.schemas import Episode,EpisodeOutcome
 ep=Episode(task_id='t',goal='x',actions=[],outcome=EpisodeOutcome.FAILED)
 out=CounterfactualEngine().simulate(ep,[{'action':'anything','risk':'read'},{'action':'other','risk':'irreversible'}])
 assert out['status']=='outcome_model_unavailable' and out['best_alternative'] is None
 assert all(a['estimated_success_probability'] is None for a in out['alternatives'])
 tasks=FlowStateManager().structure_work([{'difficulty':.6}]*20,skill=.4)
 assert all(t['zone']=='anxiety' and t['skill_assumption']==.4 and not t['capability_executed'] for t in tasks)
 assert ReframingEngine().reframe('failed').status=='marker_template_only'
 assert not ReframingEngine().reframe('failed').capability_executed
 assert PlanningHorizonController().horizon(uncertainty=.2,time_available_minutes=90)['status']=='hand_written_planning_policy'
 assert not PlanningHorizonController().horizon(uncertainty=.2,time_available_minutes=90)['capability_executed']


def test_evidence_counts_never_invent_confidence_or_learning_value():
 from app.modules.m20_general_cognitive_worker.metacognition import CalibrationEngine,CuriosityEngine
 c=CalibrationEngine()
 for count in (0,1,10000):
  claim=c.assess_claim('unverified',.99,evidence_count=count)
  assert claim.flagged is None and not claim.capability_executed
  assert c._confidence_ceiling(count) is None
  c.resolve(claim.id,True)
 assert c.calibration_error() is not None
 assert c.adjusted_confidence(.8) is None
 curiosity=CuriosityEngine();curiosity._gap_counts={'a':1,'b':10000}
 items=curiosity.allocate(idle_budget=10)
 assert all(i.expected_learning_value is None and not i.capability_executed for i in items)
 assert sum(i.allocated_budget for i in items)<=10.001
