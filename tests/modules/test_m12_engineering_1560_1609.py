import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m12_ai_research_lab.engineering_support_1560_1609 import FEATURES,engineering_support_1560_1609
BASE={'standard':'Owner-approved standard v1','standard_source_url':'https://standards.example/v1'}
def payload(fid):
 d=dict(BASE)
 if fid<1570:d|={'observations':[{'id':'o','metric':'size_mm','value':2,'unit':'mm','provenance':'calibrated instrument'}],'acceptance_criteria':[{'metric':'size_mm','maximum':3}],'calibration':{'status':'current'},'coverage':{'percent':100}}
 elif fid<1578:d|={'nodes':['source','load'],'components':[{'id':'r','rating':'10 W','loss_w':1}],'voltage_v':10,'current_a':2,'power_factor':.8,'verification_plan':['bench test']}
 elif fid<1593:d|={'resource_series':[{'power_kw':5,'hours':2}],'assets':[{'id':'a','rated_kw':10}],'demand':[{'energy_kwh':8}],'protection_and_islanding':['review relay study']}
 elif fid<1607:d|={'frequency_hz':1e9,'bandwidth_hz':1e6,'signal_dbm':-70,'noise_dbm':-100,'tx_power_dbm':20,'gains_db':[5],'losses_db':[90]}
 else:d|={'assets':[{'id':'api','classification':'restricted'}],'threats':[{'id':'spoof','asset_ids':['api'],'likelihood':2,'impact':4}],'controls':[{'id':'mfa','addresses':['spoof']}]}
 return d
@pytest.mark.parametrize('fid',range(1560,1610))
def test_every_owner_row_is_exact_and_implemented(fid):
 o=engineering_support_1560_1609(fid,payload(fid));assert o['feature_id']==fid and o['concept']==FEATURES[fid] and o['review_required'] and o['boundary'] and o['disclaimer']
def test_ndt_screening_retains_provenance_calibration_and_coverage():
 o=engineering_support_1560_1609(1562,payload(1562));assert o['observations'][0]['screening_result']=='pass' and o['observations'][0]['provenance']=='calibrated instrument' and o['coverage']['percent']==100
def test_electrical_power_calculations_are_unit_explicit():
 o=engineering_support_1560_1609(1571,payload(1571));assert o['calculations']=={'apparent_power_va':20,'real_power_w':16,'declared_losses_w':1,'efficiency':.9375}
def test_energy_scenario_computes_generation_net_and_capacity_factor():
 o=engineering_support_1560_1609(1584,payload(1584));assert o['energy_summary']=={'generated_kwh':10,'demand_kwh':8,'net_kwh':2,'capacity_factor':.5}
def test_comms_link_budget_and_shannon_bound_are_traceable():
 o=engineering_support_1560_1609(1603,payload(1603));assert o['link_budget']['estimated_received_dbm']==-65 and o['physics']['shannon_upper_bound_bps']>9e6
def test_security_is_defensive_and_never_claims_control_effectiveness():
 o=engineering_support_1560_1609(1609,payload(1609));assert o['threat_model'][0]['inherent_score']==8 and o['threat_model'][0]['residual_status']=='requires_validation' and 'No exploitation' in o['boundary']
def test_invalid_inputs_fail_closed():
 with pytest.raises(ValueError):engineering_support_1560_1609(1594,BASE|{'frequency_hz':0,'bandwidth_hz':1,'signal_dbm':1,'noise_dbm':0})
 with pytest.raises(ValueError):engineering_support_1560_1609(1559,BASE)
def test_route_is_mounted_and_tenant_scoped():
 r=TestClient(app).post('/api/v1/ai-research-lab/engineering-1560-1609/support',headers={'x-atlas-tenant':'t-1560'},json={'feature_id':1609,'data':payload(1609)});assert r.status_code==200 and r.json()['tenant_id']=='t-1560' and r.json()['concept']=='Cybersecurity'
