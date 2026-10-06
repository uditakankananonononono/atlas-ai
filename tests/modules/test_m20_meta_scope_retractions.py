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


def test_role_patterns_dedup_failures_and_no_probabilistic_world_or_decay_claim():
 from app.modules.m20_general_cognitive_worker.metacognition import MetaLearner,WorldModelRegistry,KnowledgeDecayModeler
 from app.modules.m20_general_cognitive_worker.schemas import Episode,EpisodeOutcome,ActionRecord
 from app.modules.m20_general_cognitive_worker.semantic_memory import SemanticMemory
 learner=MetaLearner()
 failed=Episode(task_id='t',goal='alpha',actions=[ActionRecord(tool='web_search'),ActionRecord(tool='draft_email')],outcome=EpisodeOutcome.FAILED)
 assert learner.abstract(failed) is None
 good=Episode(task_id='t',goal='alpha',actions=failed.actions,outcome=EpisodeOutcome.SUCCEEDED)
 learner.abstract(good);learner.abstract(good)
 assert learner.transfer('beta')[0]['successes']==1
 assert not learner.transfer('beta')[0]['capability_executed']
 r=WorldModelRegistry();r.register('x',{});r.apply_evidence('x',supported=True,weight=10000)
 assert r.models['x'].posterior is None
 memory=SemanticMemory();memory.remember('price',kind='price',decay_rate=10000)
 forecast=KnowledgeDecayModeler().forecast(memory)
 assert forecast[0]['age_days']>=0 and forecast[0]['predicted_freshness'] is None
 assert forecast[0]['refresh_by'] is None and not forecast[0]['capability_executed']


def test_conflict_pruning_never_detaches_or_runs_descendant_effects():
 from app.modules.m20_general_cognitive_worker.metacognition import GoalHierarchyManager
 from app.modules.m20_general_cognitive_worker.schemas import PlanNode,TaskState
 bad=PlanNode(title='fake review');send=PlanNode(title='send review',depends_on=[bad.id]);share=PlanNode(title='share it',depends_on=[send.id]);free=PlanNode(title='read public docs')
 out=GoalHierarchyManager().restructure([bad,send,share,free])
 assert all(n.state==TaskState.CANCELLED for n in [bad,send,share])
 assert send.depends_on==[bad.id] and share.depends_on==[send.id]
 assert out['remaining_steps']==['read public docs'] and not out['capability_executed']
 assert set(out['blocked_by_cancelled_prerequisite'])=={send.id,share.id}


def test_conflict_pruning_preserves_terminal_history_and_rejects_self_dependency():
 import pytest
 from app.modules.m20_general_cognitive_worker.metacognition import GoalHierarchyManager
 from app.modules.m20_general_cognitive_worker.schemas import PlanNode,TaskState
 m=GoalHierarchyManager();bad=PlanNode(title='fake review')
 done=PlanNode(title='already sent',depends_on=[bad.id],state=TaskState.SUCCEEDED)
 failed=PlanNode(title='failed send',depends_on=[bad.id],state=TaskState.FAILED)
 out=m.restructure([bad,done,failed])
 assert done.state==TaskState.SUCCEEDED and failed.state==TaskState.FAILED
 assert set(out['already_executed_dependents'])=={done.id,failed.id}
 selfnode=PlanNode(title='x');selfnode.depends_on=[selfnode.id]
 with pytest.raises(ValueError):m.restructure([selfnode])


def test_semantic_memory_no_fixed_freshness_even_at_extreme_caller_decay():
 from app.modules.m20_general_cognitive_worker.semantic_memory import SemanticMemory
 m=SemanticMemory()
 for rate in (0,1,10000):
  f=m.remember('unverified',decay_rate=rate)
  assert m.freshness(f.id) is None
 assert m.due_for_refresh()==[]


def test_rumination_and_candidate_weights_not_predictive_confidence():
 from app.modules.m20_general_cognitive_worker.executive import MetaReasoner,MCTSRuminator
 from app.modules.m20_general_cognitive_worker.mcts import BoundedMCTS
 from app.modules.m20_general_cognitive_worker.schemas import PlanNode
 n=PlanNode(title='read')
 candidate=MetaReasoner().score_candidates([n],wm_context='',ltm_hits=3)[0]
 assert not hasattr(candidate,'progress_probability') and not hasattr(candidate,'information_gain')
 assert MCTSRuminator(seed=1).ruminate([n])['expected_success'] is None
 r=BoundedMCTS(seed=1,max_simulations=4).search([n]).as_dict()
 assert r['status']=='uct_search_over_heuristic_rollout' and not r['predictive_model_available']
 assert 'unfitted' in r['assumptions']['success_probability']
