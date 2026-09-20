import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1063_synthetic_control_builds_convex_counterfactual():
 o=analysis.run('synthetic_control',{'treated_pre':[1,2,3],'donor_pre':[[1,2,3],[3,2,1]],'treated_post':6,'donor_post':[4,2]},{'iterations':3000,'learning_rate':.05})['output']
 assert sum(o['weights'])==pytest.approx(1) and all(w>=0 for w in o['weights']) and o['pre_rmspe']<.05 and o['effect']==pytest.approx(2,abs=.05)

def _match(method,params=None):return analysis.run(method,{'treated':[1,1,0,0],'outcome':[10,20,7,16],'covariates':[[0],[1],[0.1],[1.1]]},params or {})['output']
def test_row_1064_matching_standardizes_and_pairs_nearest():
 o=_match('matching_methods');assert o['matched_count']==2 and o['att']==pytest.approx(3.5)
def test_row_1065_psm_matches_on_estimated_score():
 o=_match('propensity_score_matching');assert o['matched_count']==2 and len(o['propensity_scores'])==4

def test_row_1066_cem_uses_only_overlap_strata():
 o=analysis.run('coarsened_exact_matching',{'treated':[1,1,0,0],'outcome':[10,20,7,16],'covariates':[[0],[1],[.1],[1.1]]},{'cutpoints':[[.5]]})['output']
 assert o['eligible_strata']==2 and o['att']==pytest.approx(3.5) and o['matched_count']==4

def test_row_1067_genetic_matching_uses_positive_caller_weights():
 o=_match('genetic_matching',{'covariate_weights':[2]});assert o['matched_count']==2
 with pytest.raises(ValueError):_match('genetic_matching',{'covariate_weights':[0]})

def test_matching_methods_reject_lack_of_overlap():
 with pytest.raises(ValueError):analysis.run('matching_methods',{'treated':[1,1],'outcome':[1,2],'covariates':[[0],[1]]})
