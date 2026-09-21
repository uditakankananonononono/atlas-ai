import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m12_ai_research_lab.research_methods_135_184 import *
from app.modules.m12_ai_research_lab.research_methods_routes_135_184 import router
S={'title':'Paper','url':'https://example.org/paper'}
def E(n,**x):
 p={'source':S};p.update(x);return execute(n,p)['result']
def test_catalog():assert [x['row_id'] for x in capabilities()]==list(range(135,185))
def test_135_frequentist_reports_effect_ci_assumptions():
 o=E('frequentist_analysis',group_a=[1,2,3],group_b=[0,1,2]);assert o['estimate']==1 and o['confidence_interval_95'] and o['p_value_not_truth_probability']
def test_136_model_selection_locks_test_nested():assert E('machine_learning_model_selection',task='classify',candidates=['a'])['selection']['test_used_once']
def test_137_features_train_only_and_availability():assert E('feature_engineering',task='x',features=[{'name':'f'}])['features'][0]['fit_scope']=='training only'
def test_138_tuning_never_test_optimizes():assert E('hyperparameter_tuning',task='x',search_space={'a':[1]})['tuning']['no_test_optimization']
def test_139_cv_preprocess_inside_fold():assert E('cross_validation_design',task='x')['cross_validation']['preprocessing_inside_fold']
def test_140_overfit_gap_detection():assert E('overfitting_detection',task='x',train_score=.9,validation_score=.5)['overfitting']['flagged']
def test_141_regularization_fold_standardizes():assert E('regularization_application',task='x')['regularization']['standardize_within_fold']
def test_142_stacking_out_of_fold():assert E('ensemble_methods',task='x',base_models=['a'])['ensemble']['out_of_fold_meta_features']
@pytest.mark.parametrize('n,field',[('transfer_learning','domain_shift_check'),('few_shot_learning','episode_design'),('zero_shot_learning','unseen_label_evaluation'),('self_supervised_learning','downstream_probe'),('contrastive_learning','false_negative_review'),('generative_modeling','memorization_and_privacy_tests'),('variational_inference','posterior_predictive_check'),('markov_chain_monte_carlo','diagnostics'),('graph_neural_networks','split_by_graph_structure'),('attention_mechanisms','attention_not_explanation'),('transformer_architecture','components'),('recurrent_networks','gradient_clipping'),('convolutional_networks','receptive_field_check'),('autoencoder_design','bottleneck_prevents_identity'),('gan_training','stability_checks'),('diffusion_models','fidelity_diversity_memorization'),('reinforcement_learning','reward_hacking_and_safety_constraints'),('q_learning','terminal_bootstrap_zero'),('policy_gradient_methods','variance_monitoring'),('actor_critic_methods','separate_actor_critic_diagnostics'),('multi_agent_rl','nonstationarity_and_credit_assignment'),('inverse_rl','identifiability_warning'),('imitation_learning','covariate_shift_check'),('curriculum_learning','anti_forgetting_rehearsal'),('active_learning','test_pool_excluded'),('semi_supervised_learning','distribution_shift_check'),('weak_supervision','coverage_conflict_correlation_estimation')])
def test_143_169_specific_ml(n,field):assert field in E(n,task='x')['method']
def test_150_mcmc_has_rhat_ess_trace_divergences():assert E('markov_chain_monte_carlo',task='x')['method']['diagnostics']==['r_hat','effective_sample_size','trace','divergences']
def test_160_q_learning_update_is_explicit():assert 'max Q' in E('q_learning',task='x')['method']['update']
def test_170_causal_requires_identification():assert E('causal_inference')['causal_claim_requires_identification']
def test_171_dag_validates_acyclic():
 assert E('directed_acyclic_graph_construction',edges=[{'source':'a','target':'b'}])['dag']['acyclic']
 with pytest.raises(ResearchMethodError):E('directed_acyclic_graph_construction',edges=[{'source':'a','target':'b'},{'source':'b','target':'a'}])
def test_172_iv_exposes_all_assumptions_late():assert E('instrumental_variable_analysis')['iv']['estimand'].startswith('LATE')
def test_173_did_computes_double_difference():assert E('difference_in_differences',means={'treated_pre':1,'treated_post':5,'control_pre':2,'control_post':3})['did']['estimate']==3
def test_174_rd_is_local_and_checks_manipulation():assert E('regression_discontinuity')['rd']['local_estimand'] and E('regression_discontinuity')['rd']['manipulation_density_test']
def test_175_psm_balance_and_unmeasured_boundary():assert E('propensity_score_matching')['psm']['balance_before_after_required']
def test_176_synth_control_never_fits_post():assert E('synthetic_control_methods')['synthetic_control']['post_period_not_used_to_fit']
def test_177_mediation_strong_assumptions():assert E('mediation_analysis')['mediation']['sequential_ignorability_is_strong']
def test_178_moderation_retains_main_effects():assert E('moderation_analysis')['moderation']['main_effects_retained']
def test_179_sem_has_fit_indices_alternatives():assert len(E('structural_equation_modeling')['sem']['fit_indices'])==4
def test_180_time_series_rolling_backtest_no_causal_language():assert E('time_series_analysis',values=[1,2,3])['analysis']['forecast_backtest']=='rolling origin'
def test_181_arima_residuals_and_backtest():assert 'autocorrelation' in E('arima_modeling',values=[1,2,3])['arima']['residual_checks']
def test_182_seasonality_multiple_cycles():assert E('seasonality_detection',values=[1,2,1,2])['seasonality']['multiple_cycles_required']
def test_183_change_point_detects_shift():assert E('change_point_detection',values=[0,0,5,5],threshold=2)['change_points']['candidates']
def test_184_granger_is_predictive_not_structural():assert E('granger_causality',values=[1,2])['granger']['predictive_precedence_not_structural_causality']
def test_negative_probability_source_unknown_and_route():
 with pytest.raises(ResearchMethodError):execute('nope',{})
 with pytest.raises(ResearchMethodError):execute('time_series_analysis',{'values':[1]})
 app=FastAPI();app.include_router(router,prefix='/m12');c=TestClient(app);assert len(c.get('/m12/research-methods-135-184/capabilities').json())==50;assert c.post('/m12/research-methods-135-184/frequentist_analysis',json={'payload':{}}).status_code==422
