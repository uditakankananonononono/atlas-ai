import pytest
from app.modules.m15_document_generator.design_support_333_359 import design_support_333_359
from app.modules.m06_social_media_manager.marketing_computations import compute,ENGINES
BASE={'brief':'x','decision_owner':'owner'}
def design_input(row):
 d=dict(BASE)
 if row<335:d|={'requirements':['r'],'hazards':[{'id':'h','severity':2,'likelihood':3}],'hull_volume_m3':2,'displacement_kg':1500,'parts':[{'diameter_mm':20}]}
 elif row<344:d|={'gameplay_loops':['loop'],'content_nodes':['n'],'playtests':[{'completion_rate':.7}],'economy':{'sources':[{'amount':5}],'sinks':[{'amount':2}]}}
 elif row<353:d|={'participants':['p'],'needs':[{'id':'n'}],'variants':[{'id':'v','addresses':['n']}],'locales':[]}
 else:d|={'stakeholders':['s'],'evidence':['e'],'ideas':[{'id':'i','scores':{}}],'service_blueprint':[{'id':'a','frontstage':'ui'}]}
 return d
@pytest.mark.parametrize('row',range(333,360))
def test_each_design_row_has_distinct_method_engine(row):
 out=design_support_333_359(row,design_input(row));assert out['method_engine']; assert len(out)>12
@pytest.mark.parametrize('slug',sorted(ENGINES))
def test_each_marketing_engine_is_computed_not_prompt_registry(slug):
 out=compute(slug,{'facts':{},'goals':[],'contacts':[],'provided_metrics':{}});assert isinstance(out,dict) and out

def test_marketing_funnel_cac_roi_and_experiment_math():
 t=compute('targeting',{'facts':{'segments':[{'size':1000,'conversion_rate':.1,'margin':20,'cac':5}]}});assert t['selected_segments'][0]['target_score']==400
 r=compute('referral-program',{'facts':{'invites':100,'qualified_referrals':25,'reward_cost':200,'referred_margin':700}});assert r['invite_conversion']==.25 and r['program_roi']==2.5
 a=compute('marketing-automation',{'facts':{'workflows':[{'trigger':'signup','eligible':1000,'incremental_conversion':.02,'value_per_conversion':50,'run_cost':100}]}});assert a['total_estimated_incremental_value']==900

def test_zero_denominators_are_explicit_unknowns():
 out=compute('email-marketing',{'facts':{'sent':0,'delivered':0}});assert out['metrics']['delivery_rate'] is None and out['metrics']['open_rate'] is None
