"""Focused tests for feature rows 1010-1034: tenant-bound analysis jobs with honest bounds."""
import pytest
from app.modules.m16_executive_dashboard import analysis
from app.modules.m16_executive_dashboard.schemas import *
from app.modules.m16_executive_dashboard.service import Service
class FakeAnalysisRepo:
    def __init__(self):self.jobs={}
    def save_analysis_job(self,j):self.jobs[j.id]=j;return j
    def get_analysis_job(self,i):return self.jobs.get(i)
    def list_analysis_jobs(self,method=None):
        out=sorted(self.jobs.values(),key=lambda j:j.created_at,reverse=True)
        return [j for j in out if method is None or j.method==method][:200]
def svc():return Service(FakeAnalysisRepo())
def run(s,method,data,params=None,seed=0):return s.run_analysis(AnalysisJobIn(method=method,data=data,params=params or {},seed=seed))
def test_row_1010_predictive_forecasts_future_outcomes():
    j=run(svc(),"predictive",{"x":[1,2,3,4],"y":[2,4,6,8],"future_x":[5,6]})
    assert j.feature_row==1010 and j.status=="completed"
    assert j.output["slope"]==2.0 and j.output["predictions"]==[10.0,12.0] and j.output["assumptions"] and j.output["method_limits"]
def test_row_1011_prescriptive_recommends_actions():
    j=run(svc(),"prescriptive",{"options":[{"name":"ship","score":9},{"name":"wait","score":4}]})
    assert j.feature_row==1011 and j.output["recommended"]["name"]=="ship"
def test_row_1012_descriptive_summarizes_past_data():
    o=run(svc(),"descriptive",{"values":[1,2,3,4,5]}).output
    assert o["mean"]==3.0 and o["median"]==3.0 and o["min"]==1.0 and o["max"]==5.0
def test_row_1013_diagnostic_explains_why_without_causal_overreach():
    j=run(svc(),"diagnostic",{"x":[1,2,3,4],"y":[2,4,6,8]})
    assert j.output["pearson_correlation"]==1.0
    assert any("cause" in a.lower() for a in j.output["assumptions"]+j.output["method_limits"])
def test_row_1014_eda_discovers_patterns():
    o=run(svc(),"eda",{"values":[1,2,2,3,4]}).output
    assert o["unique"]==4 and "skewness" in o and o["n"]==5
def test_row_1015_confirmatory_tests_hypotheses():
    o=run(svc(),"confirmatory",{"values":[1,2,3,4,5]},{"null_mean":0,"alpha":0.05}).output
    assert o["reject"] is True and o["p_value"]<0.05
def test_row_1016_inference_draws_conclusions():
    o=run(svc(),"inference",{"values":[1,2,3,4,5]}).output
    assert o["estimate"]==3.0 and o["standard_error"]>0
def test_row_1017_hypothesis_testing_tests_claims():
    o=run(svc(),"hypothesis_test",{"values":[10,11,12,13]},{"null_mean":5}).output
    assert o["reject"] is True and o["estimate"]==11.5
def test_row_1018_confidence_intervals_quantify_uncertainty():
    lo,hi=run(svc(),"confidence_interval",{"values":[1,2,3,4,5]}).output["interval"]
    assert lo<3.0<hi
def test_row_1019_bootstrap_resamples_for_inference():
    o=run(svc(),"bootstrap",{"values":[1,2,3,4,5]},{"draws":500},seed=7).output
    assert o["draws"]==500 and o["percentile_interval"][0]<=o["estimate"]<=o["percentile_interval"][1]
def test_row_1020_permutation_testing_without_assumptions():
    o=run(svc(),"permutation_test",{"group_a":[1,2,3],"group_b":[10,11,12]},{"draws":1000},seed=17).output
    assert o["p_value"]<0.1 and o["difference"]==9.0
def test_row_1021_nonparametric_avoids_distributional_assumptions():
    o=run(svc(),"nonparametric",{"group_a":[1,2,3],"group_b":[4,5,6]}).output
    assert o["u"]==0.0 and o["test"].startswith("mann_whitney")
def test_row_1022_robust_statistics_resist_outliers():
    o=run(svc(),"robust",{"values":[1,2,3,4,5,100]}).output
    assert o["median"]==3.5 and o["mad"]==1.5
def test_row_1023_outlier_detection_finds_anomalies():
    o=run(svc(),"outlier_detection",{"values":[1,1,2,1,2,100]}).output
    assert o["outliers"]==[{"index":5,"value":100.0}]
def test_row_1024_missing_data_imputation_fills_gaps():
    o=run(svc(),"imputation",{"values":[1,None,3]}).output
    assert o["imputed"]==[1,2.0,3] and o["missing_count"]==1
def test_row_1025_multiple_imputation_handles_uncertainty():
    o=run(svc(),"multiple_imputation",{"values":[1,None,3,None,5]},{"datasets":4},seed=7).output
    assert len(o["datasets"])==4 and all(len(d)==5 for d in o["datasets"]) and len({tuple(d) for d in o["datasets"]})>1
def test_row_1026_mle_finds_best_parameters():
    o=run(svc(),"mle",{"values":[2,4,6]}).output
    assert o["mu_mle"]==4.0 and abs(o["variance_mle"]-8/3)<1e-9
def test_row_1027_em_handles_latent_variables():
    means=sorted(run(svc(),"em",{"values":[1,1.1,.9,8,8.2,7.9]},{"iterations":80},seed=3).output["means"])
    assert means[0]<2 and means[1]>7
def test_row_1028_mcmc_samples_complex_distributions():
    o=run(svc(),"mcmc",{"values":[1,1.1,.9,1.05]},{"draws":3000},seed=11).output
    assert abs(o["posterior_mean"]-1.0125)<0.15 and 0<o["acceptance_rate"]<1
def test_row_1029_variational_fast_approximate_inference():
    o=run(svc(),"variational",{"values":[1,1.1,.9]}).output
    assert abs(o["posterior_mean"]-1.0)<0.05 and o["posterior_variance"]>0
def test_row_1030_gibbs_iterative_sampling():
    o=run(svc(),"gibbs",{"values":[1,1.1,.9,1.05]},{"draws":2000},seed=5).output
    assert abs(o["mu_mean"]-1.0125)<0.2 and o["precision_mean"]>0
def test_row_1031_metropolis_hastings_mcmc_algorithm():
    o=run(svc(),"metropolis_hastings",{"values":[2,2.1,1.9]},{"draws":3000},seed=23).output
    assert abs(o["posterior_mean"]-2.0)<0.2 and o["sampler"]=="random_walk_metropolis"
def test_row_1032_hmc_efficient_mcmc():
    o=run(svc(),"hmc",{"values":[1,1.1,.9,1.05]},{"draws":2000},seed=9).output
    assert abs(o["posterior_mean"]-1.0125)<0.1 and o["acceptance_rate"]>0.9
def test_row_1033_smc_particle_filtering():
    o=run(svc(),"smc",{"observations":[0.1,0.0,0.2,-0.1]},{"particles":500,"process_sd":0.2,"observation_sd":0.5},seed=13).output
    assert len(o["state_estimates"])==4 and all(0<e<=500 for e in o["effective_sample_sizes"])
def test_row_1034_particle_filters_track_dynamic_systems():
    obs=[5.0+0.1*((-1)**i) for i in range(8)]
    est=run(svc(),"particle_filter",{"observations":obs},{"particles":1000,"process_sd":0.3,"observation_sd":0.2},seed=29).output["state_estimates"]
    assert abs(est[-1]-5.0)<0.5 and len(est)==8
def test_analysis_jobs_persist_and_are_retrievable():
    s=svc();j=run(s,"descriptive",{"values":[1,2,3]})
    assert s.get_analysis_job(j.id).id==j.id
    assert j.id in [x.id for x in s.list_analysis_jobs()]
    assert s.list_analysis_jobs(method="bootstrap")==[]
def test_analysis_method_catalog_covers_rows_1010_1034():
    methods=svc().analysis_methods()
    assert len(methods)>=25 and {m.feature_row for m in methods} >= set(range(1010,1035))
    assert all(m.summary and m.required_inputs for m in methods)
def test_failed_jobs_are_stored_with_error_not_exception():
    s=svc()
    with pytest.raises(ValueError):s.run_analysis(AnalysisJobIn(method="nonsense"))
    j=run(s,"descriptive",{"values":[]})
    assert j.status=="failed" and j.error and j.output is None
def test_stochastic_methods_are_deterministic_per_seed():
    s=svc()
    a=run(s,"bootstrap",{"values":[1,2,3,4,5]},{"draws":300},seed=42).output
    b=run(s,"bootstrap",{"values":[1,2,3,4,5]},{"draws":300},seed=42).output
    assert a==b
def test_pure_run_rejects_bad_inputs():
    with pytest.raises(ValueError):analysis.run("predictive",{"x":[1],"y":[1,2]})
    with pytest.raises(ValueError):analysis.run("imputation",{"values":[None,None]})
def test_sql_repository_isolates_analysis_jobs_by_tenant():
    from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository
    a=SqlDashboardRepository("tenant-a","actor");b=SqlDashboardRepository("tenant-b","actor")
    sa=Service(a);j=run(sa,"descriptive",{"values":[1,2,3]})
    assert a.get_analysis_job(j.id) is not None
    assert b.get_analysis_job(j.id) is None
    assert j.id not in [x.id for x in b.list_analysis_jobs()]
