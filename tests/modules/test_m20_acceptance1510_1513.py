"""Closed-scoped supplied-engine acceptance; no simulation or release approval."""
import copy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.mechanical_design1510 import evaluate_design_review
from app.modules.m20_general_cognitive_worker.cad_modeling1511 import evaluate_feature_tree
from app.modules.m20_general_cognitive_worker.axial_fea1512 import solve_axial_bar
from app.modules.m20_general_cognitive_worker.computational_fluid_dynamics1513 import evaluate_flow_balance

MECHAN={'requirements':[{'id':'R2','verification_method':'test','acceptance':'<= 5 mm','load_cases':['L1']},{'id':'R1','verification_method':'','acceptance':'x','load_cases':[]}],'load_cases':[{'id':'L1'},{'id':'L2'}],'interfaces':['I1'],'units':{'length':'mm'},'assumptions':['a'],'source_refs':['ref1']}
CAD={'features':[{'id':'F1'},{'id':'F2','references':['F1'],'parameters':['w']},{'id':'F3','references':['F2','F1']}],'parameters':{'w':'5','u':'9'}}
CAD_BAD_ORDER={'features':[{'id':'A','references':['B']},{'id':'B'},{'id':'C','references':['C']}]}
FEA={'model':'1d_axial_linear_elastic','units':{'length':'m','force':'N','modulus':'Pa','area':'m^2'},'nodes':[{'id':'n2','x':2},{'id':'n1','x':0}],'elements':[{'id':'e1','nodes':['n1','n2'],'E':10,'A':1}],'loads':[{'node':'n2','force':10}],'displacements':[{'node':'n1','value':0}]}
FLOW={'ports':[{'id':'i1','direction':'in','mass_flow_kg_per_s':6},{'id':'i2','direction':'in','mass_flow_kg_per_s':'4'},{'id':'o1','direction':'out','mass_flow_kg_per_s':'19/2'}],'closure_tolerance_percent':1}
PATHS={1510:'mechanical-design/1510/evaluate',1511:'cad-modeling/1511/evaluate',1512:'axial-fea/1512/solve',1513:'flow-balance/1513/evaluate'}

def check_mechan(r):
 assert r['verification_matrix']==[{'requirement_id':'R1','verification_method':None,'acceptance':'x','load_cases':[],'covered':False},{'requirement_id':'R2','verification_method':'test','acceptance':'<= 5 mm','load_cases':['L1'],'covered':True}]
 assert r['summary']=={'requirement_count':2,'covered_count':1,'uncovered_count':1,'uncovered_requirement_ids':['R1'],'declared_load_case_count':2,'referenced_load_case_ids':['L1'],'unreferenced_load_case_ids':['L2'],'requirements_complete':False}
 assert r['provenance']['input_sha256']=='0793ff0a6903a1f0010de680e6b106e36c0872e5129325d6b38567203a6cd1e7'
 assert r['provenance']['solver_or_cad_executed']is False and r['provenance']['physical_test_performed']is False
 assert r['human_review_required']is True

def check_cad(r):
 assert r['regeneration_order']==['F1','F2','F3']and r['regeneration_ready']is True and r['reference_errors']==[]
 assert r['summary']=={'feature_count':3,'error_count':0,'parameters_declared':['u','w'],'parameters_used':['w'],'parameters_unreferenced':['u']}
 assert r['provenance']['geometry_kernel_executed']is False and r['provenance']['regeneration_performed']is False and r['human_review_required']is True

def check_fea(r):
 assert [n['id']for n in r['nodes']]==['n1','n2']
 for n,displacement,reaction,restrained in zip(r['nodes'],[0.,2.],[-10.,0.],[True,False]):
  assert n['displacement']==pytest.approx(displacement)and n['reaction']==pytest.approx(reaction)and n['restrained']is restrained
 e=r['elements'][0];assert e['id']=='e1'and e['nodes']==['n1','n2']
 for key,val in [('length',2.),('strain',1.),('stress',10.),('axial_force',10.)]:assert e[key]==pytest.approx(val)
 for key,val in [('strain_energy',10.),('external_work_half',10.),('equilibrium_residual',0.),('force_balance_residual',0.)]:assert r[key]==pytest.approx(val)
 assert r['source_verified']is False and r['safety_certified']is False and r['requires_engineer_review']is True

def check_flow(r):
 assert r['totals']=={'mass_in_kg_per_s':'10','mass_out_kg_per_s':'9.5'}
 assert r['mass_imbalance_percent']=='5'and r['closure_tolerance_percent']=='1'and r['balanced_to_tolerance']is False
 assert r['port_rows']==[{'id':'i1','direction':'in','mass_flow_kg_per_s':'6','share_of_direction_percent':'60'},{'id':'i2','direction':'in','mass_flow_kg_per_s':'4','share_of_direction_percent':'40'},{'id':'o1','direction':'out','mass_flow_kg_per_s':'9.5','share_of_direction_percent':'100'}]
 assert r['largest_inflow']=={'id':'i1','share_percent':'60'}and r['largest_outflow']=={'id':'o1','share_percent':'100'}
 assert r['summary']=={'port_count':3,'inflow_count':2,'outflow_count':1}
 assert r['provenance']['input_sha256']=='941a4f21dec957c0701069b66063b87fb1e1f63819a552b13a94737104b304ef'
 assert r['provenance']['hash_scope']=='validated_fields'and r['provenance']['solver_run_claimed']is False
 assert r['boundary']['requires_engineer_review']is True

VECTORS=[(1510,MECHAN,evaluate_design_review,check_mechan),(1511,CAD,evaluate_feature_tree,check_cad),(1512,FEA,solve_axial_bar,check_fea),(1513,FLOW,evaluate_flow_balance,check_flow)]

@pytest.mark.parametrize('row,data,engine,check',VECTORS)
def test_live_engine_literal_vectors(row,data,engine,check):check(engine(copy.deepcopy(data)))

@pytest.fixture
def client_auth(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production')
 return TestClient(app,raise_server_exceptions=False),oidc_auth_headers('accept4','owner')

@pytest.mark.parametrize('row,data,engine,check',VECTORS)
def test_mounted_literal_acceptance(row,data,engine,check,client_auth):
 c,h=client_auth;path='/api/v1/api/modules/20/'+PATHS[row]
 assert c.post(path,json={'data':data}).status_code==401
 r=c.post(path,headers=h,json={'data':data});assert r.status_code==200,r.text
 check(r.json());assert r.json()['tenant_id']=='accept4'and r.json()['actor_id']=='owner'


def test_cad_forward_and_self_are_findings(client_auth):
 c,h=client_auth;r=c.post('/api/v1/api/modules/20/'+PATHS[1511],headers=h,json={'data':CAD_BAD_ORDER});assert r.status_code==200,r.text
 o=r.json();assert o['reference_errors']==[{'feature':'A','kind':'forward_reference','reference':'B'},{'feature':'C','kind':'self_reference','reference':'C'}]
 assert o['regeneration_order']is None and o['regeneration_ready']is False

ERRORS=[(1510,{},'MECHAN1510:invalid_input: requirements must be a list of 1..64 requirement objects'),(1510,{'extra':1},'MECHAN1510:unknown_key: unknown key at input'),(1511,{},'CADMOD1511:invalid_input: features must be a list of 1..64 feature objects'),(1511,{'extra':1},'CADMOD1511:unknown_key: unknown key at input'),(1512,{},'FEA1512_MODEL'),(1512,{'extra':1},'FEA1512_INPUT'),(1513,{},'COMPUT1513:invalid_input: ports must be a list of 1..64 port objects'),(1513,{'extra':1},'COMPUT1513:invalid_input: unknown key at input')]
@pytest.mark.parametrize('row,data,detail',ERRORS)
def test_exact_empty_unknown_engine_422(row,data,detail,client_auth):
 c,h=client_auth;r=c.post('/api/v1/api/modules/20/'+PATHS[row],headers=h,json={'data':data})
 assert r.status_code==422 and r.json()=={'detail':detail}
