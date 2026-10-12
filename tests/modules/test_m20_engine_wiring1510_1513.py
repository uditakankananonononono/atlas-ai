import pytest
from fastapi.testclient import TestClient
from app.main import app

CASES=[
(1510,'mechanical-design/1510/evaluate',{'requirements':[{'id':'r1','verification_method':'test','acceptance':'limit'},{'id':'r2'}]},'summary','covered_count',1),
(1511,'cad-modeling/1511/evaluate',{'features':[{'id':'base'},{'id':'next','references':['base']}]},'summary','feature_count',2),
(1512,'axial-fea/1512/solve',{'model':'1d_axial_linear_elastic','units':{'length':'m','force':'N','modulus':'Pa','area':'m^2'},'nodes':[{'id':'a','x':0},{'id':'b','x':1}],'elements':[{'id':'e','nodes':['a','b'],'E':10,'A':2}],'loads':[{'node':'b','force':4}],'displacements':[{'node':'a','value':0}]},None,None,.2),
(1513,'flow-balance/1513/evaluate',{'ports':[{'id':'in','direction':'in','mass_flow_kg_per_s':10},{'id':'out','direction':'out','mass_flow_kg_per_s':9}],'closure_tolerance_percent':5},None,'mass_imbalance_percent','10')]

@pytest.mark.parametrize('row,suffix,data,parent,key,expected',CASES)
def test_mounted_dedicated_engine_owner_route(row,suffix,data,parent,key,expected,monkeypatch,oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV','production')
    client=TestClient(app,raise_server_exceptions=False)
    path='/api/v1/api/modules/20/'+suffix
    assert client.post(path,json={'data':data}).status_code==401
    headers=oidc_auth_headers('owner-tenant','actor')
    result=client.post(path,headers=headers,json={'data':data})
    assert result.status_code==200,result.text
    value=result.json();assert value['tenant_id']=='owner-tenant'and value['actor_id']=='actor'
    if row==1512:
        assert next(n['displacement']for n in value['nodes']if n['id']=='b')==pytest.approx(expected)
        assert value['safety_certified']is False and value['requires_engineer_review']is True
    else:
        assert value['row']==row and value['human_review_required']is True
        assert (value[parent][key]if parent else value[key])==expected
    for extra in ({'tenant_id':'foreign'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'foreign'}]}):
        assert client.post(path,headers=headers,json={'data':data,**extra}).status_code==403
    assert client.post(path,headers=headers,json={'data':{}}).status_code==422
