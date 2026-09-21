import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1078_post_selection_intervals_widen_for_multiplicity():
 o=analysis.run('post_selection_inference',{'estimates':[1,2,3],'standard_errors':[.2,.2,.2],'selected_indices':[1,2]})['output'];assert o['selection_count']==2 and (o['selected'][0]['selection_adjusted_interval'][1]-o['selected'][0]['selection_adjusted_interval'][0])>(o['selected'][0]['naive_interval'][1]-o['selected'][0]['naive_interval'][0])
def test_row_1079_selective_p_value_conditions_on_threshold():
 o=analysis.run('selective_inference',{'estimate':3,'standard_error':1,'selection_threshold':2})['output'];assert 0<o['conditional_one_sided_p_value']<1 and o['conditional_one_sided_p_value']>.0013

def test_row_1080_simultaneous_intervals_are_family_adjusted():
 o=analysis.run('simultaneous_inference',{'estimates':[1,2],'standard_errors':[.1,.2]},{'correction':'sidak','alpha':.05,'critical_value':2.24})['output'];assert o['family_confidence']==.95 and o['per_comparison_alpha']<.05 and o['intervals'][0]==pytest.approx([.776,1.224])
def test_row_1081_bh_fdr_stepup_and_adjusted_pvalues():
 o=analysis.run('false_discovery_rate_control',{'p_values':[.001,.01,.03,.2]},{'alpha':.05})['output'];assert o['rejected_indices']==[0,1,2] and all(0<=v<=1 for v in o['adjusted_p_values'])
def test_row_1082_holm_fwer_is_stepdown_monotone():
 o=analysis.run('family_wise_error_rate',{'p_values':[.001,.02,.04,.5]},{'alpha':.05,'method':'holm'})['output'];assert o['rejected_indices']==[0] and o['adjusted_p_values'][0]<=o['adjusted_p_values'][1]<=o['adjusted_p_values'][2]
def test_inference_rejects_invalid_selection_and_pvalues():
 with pytest.raises(ValueError):analysis.run('selective_inference',{'estimate':1,'standard_error':1,'selection_threshold':2})
 with pytest.raises(ValueError):analysis.run('false_discovery_rate_control',{'p_values':[1.2]})
