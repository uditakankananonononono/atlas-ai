from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m04_research_scientist.quant_methods_185_234 import *
S=[{'source_id':'dataset-1','observed_at':datetime.now(timezone.utc).isoformat()}]
def data(i):
 b={'sources':S}
 if i==185:return {**b,'x':[1,2,3,4],'y':[2,4.1,5.9,8.1]}
 if i==186:return {**b,'series':{'a':[1,2,3,4],'b':[2,2.5,3,4]}}
 if i in (187,188):return {**b,'observations':[1,2,3],'process_variance':.1,'measurement_variance':1}
 if i==189:return {**b,'observations':['0','1'],'states':['L','H'],'start':{'L':.5,'H':.5},'transition':{'L':{'L':.8,'H':.2},'H':{'L':.2,'H':.8}},'emission':{'L':{'0':.9,'1':.1},'H':{'0':.1,'1':.9}}}
 if 190<=i<=194:
  x={**b,'records':[{'time':1,'event':True,'cause':'a','x':1,'cluster':'c'},{'time':2,'event':False,'x':2,'cluster':'c'},{'time':3,'event':True,'cause':'b','x':3,'cluster':'d'}]}
  if i==191:x['covariate']='x'
  return x
 if 195<=i<=199:
  x={**b,'points':[{'x':0,'y':0,'value':1},{'x':1,'y':0,'value':2},{'x':0,'y':1,'value':3}]}
  if i==196:x|={'target':{'x':.2,'y':.2},'bandwidth':1}
  if i==197:x['weights']=[[0,1,1],[1,0,1],[1,1,0]]
  if i==198:x['target']={'x':.2,'y':.2}
  if i==199:x['area']=2
  return x
 if 200<=i<=204:return {**b,'nodes':['a','b','c','d'],'edges':[['a','b'],['b','c'],['c','a']]}
 if i in (205,206):return {**b,'population':1000,'initial_infected':10,'beta':.3,'gamma':.1,'steps':4}
 if i==207:return {**b,'agents':[{'id':'a','state':'S','transition_probability':1}],'transition':{'S':'I'},'steps':1,'seed':2}
 if i==208:return {**b,'initial_stock':10,'inflow':3,'outflow':2,'steps':3}
 if i==209:return {**b,'events':[{'time':2,'id':'b'},{'time':1,'id':'a'}]}
 if i==210:return {**b,'actions':['a','b'],'rewards':{'a':[1],'b':[2]},'rollouts':4,'seed':1}
 x={**b,'bounds':[[-2,2],[-2,2]],'objective':'sphere','iterations':10,'seed':1,'candidates':[[1,1],[0,0],[-1,2]]}
 if i in (218,219):x['objective_vectors']=[{'id':'a','values':[1,2]},{'id':'b','values':[2,1]},{'id':'c','values':[3,3]}]
 if i==223:x|={'stages':[{'transitions':{'s':[{'next':'a','cost':2},{'next':'b','cost':1}]}},{'transitions':{'a':[{'next':'z','cost':1}],'b':[{'next':'z','cost':4}]}}],'initial_state':'s'}
 if i==222:x['integer_indices']=[0]
 if i==224:x['scenarios']=[{'probability':.25,'coefficients':[1,2]},{'probability':.75,'coefficients':[2,1]}]
 if i==225:x|={'coefficients':[1,2],'coefficient_uncertainty':[.1,.2]}
 return x
@pytest.mark.parametrize('i',range(185,235))
def test_each_exact_row_executes_with_provenance_and_no_side_effect(i):
 o=run(i,data(i));assert o['row_id']==i and o['method']==ROWS[i] and o['sources']==S and o['side_effects']==[] and o['status'].startswith('reference')
def test_cointegration_does_not_overclaim():assert not run(185,data(185))['result']['cointegration_claimed']
def test_var_exposes_equations_and_diagnostics():assert run(186,data(186))['result']['stability_diagnostics_required']
def test_kalman_uncertainty_shrinks():
 s=run(188,data(188))['result']['filtered_states'];assert s[-1]['variance']<1
def test_hmm_viterbi_path_length():assert len(run(189,data(189))['result']['viterbi_path'])==2
def test_kaplan_meier_monotone():
 c=run(192,data(192))['result']['kaplan_meier'];assert all(c[i]['survival']>=c[i+1]['survival'] for i in range(len(c)-1))
def test_competing_risks_keeps_causes():assert set(run(193,data(193))['result']['cause_counts'])=={'a','b'}
def test_morans_i_requires_weights():
 d=data(197);del d['weights']
 with pytest.raises(QuantError,match='weights'):run(197,d)
def test_link_prediction_never_creates_links():assert not run(203,data(203))['result']['links_created']
def test_sir_mass_conserved():
 for p in run(206,data(206))['result']['curve']:assert round(p['susceptible']+p['infected']+p['recovered'],8)==1000
def test_simulation_reproducible():assert run(207,data(207))==run(207,data(207))
def test_mcts_selects_best_reward():assert run(210,data(210))['result']['selected_action']=='b'
def test_pareto_removes_dominated():assert {x['id'] for x in run(219,data(219))['result']['pareto_frontier']}=={'a','b'}
def test_integer_program_rounds_candidates():assert all(float(x).is_integer() for x in run(221,data(221))['result']['best_point'])
def test_dynamic_programming_recurrence():assert run(223,data(223))['result']['terminal_costs']['z']==3
def test_no_feasible_candidates_negative_path():
 d=data(220);d['constraints']=[{'coefficients':[1,1],'rhs':-10}]
 with pytest.raises(QuantError,match='no feasible'):run(220,d)
def test_bad_gini_like_input_not_relevant_but_bad_bounds_candidates_rejected():
 d=data(228);d['candidates']=[[9,9]]
 with pytest.raises(QuantError,match='no feasible'):run(228,d)
def test_source_required():
 d=data(185);d['sources']=[]
 with pytest.raises(QuantError,match='provenance'):run(185,d)
def test_exact_range_titles():assert set(ROWS)==set(range(185,235)) and ROWS[185]=='Cointegration Analysis' and ROWS[234]=='Interior Point Methods'
def test_mounted_route():
 c=TestClient(app);r=c.post('/api/v1/research-scientist/quant-methods-185-234/210',json=data(210));assert r.status_code==200 and r.json()['method']=='Monte Carlo Tree Search'
def test_route_negative_path():assert TestClient(app).post('/api/v1/research-scientist/quant-methods-185-234/184',json={}).status_code==422
def test_catalog_route_lists_50():assert len(TestClient(app).get('/api/v1/research-scientist/quant-methods-185-234').json())==50

@pytest.mark.parametrize('row,algorithm',[(211,'tournament'),(212,None),(213,None),(214,None),(215,None),(216,None)])
def test_seeded_global_optimizers_have_distinct_diagnostics_and_converge(row,algorithm):
 d=data(row);d.pop('candidates',None);d['iterations']=60;d['population_size']=24
 r=run(row,d)['result']
 assert r['best_value']<.08 and r['seed']==1 and r==run(row,d)['result']
 assert r['evaluations']>1 and len(r['objective_history'])>1
 signatures={211:'selection',212:'inertia',213:'temperature_schedule',214:'pheromone_model',215:'strategy',216:'acquisition'}
 assert signatures[row] in r

def test_gaussian_process_known_function_and_uncertainty():
 d=data(217);d|={'training_x':[[-1.],[0.],[1.]],'training_y':[1.,0.,1.],'query_points':[[0.],[.5]],'bounds':[[-2,2]]}
 r=run(217,d)['result'];assert abs(r['predictions'][0]['mean'])<1e-4 and r['predictions'][0]['variance']<1e-5 and r['kernel']=='RBF'

def test_linear_program_finds_known_vertex_and_certifies():
 d=data(220);d|={'objective':'linear','coefficients':[-3,-2],'bounds':[[0,4],[0,4]],'constraints':[{'coefficients':[1,1],'rhs':4}]}
 r=run(220,d)['result'];assert r['best_point']==pytest.approx([4,0]) and r['best_value']==pytest.approx(-12) and 'certificate' in ' '.join(r)

def test_stochastic_program_uses_probabilities_and_rejects_bad_distribution():
 d=data(224);r=run(224,d)['result'];assert r['algorithm']=='finite_scenario_expected_value' and len(r['scenario_values'])==2
 d['scenarios'][0]['probability']=.5
 with pytest.raises(QuantError,match='sum to one'):run(224,d)

def test_robust_solution_reports_worst_case_and_validates_radii():
 d=data(225);r=run(225,d)['result'];assert r['worst_case_value']==r['best_value'] and r['algorithm'].startswith('box_uncertainty')
 d['coefficient_uncertainty'][0]=-1
 with pytest.raises(QuantError,match='nonnegative'):run(225,d)

@pytest.mark.parametrize('row,key,value_limit',[(226,'projected_gradient',1e-8),(228,'gradient_descent_armijo',1e-8),(229,'random_coordinate_stochastic_gradient',1e-5),(230,'adam',2e-3),(231,'damped_newton',1e-8),(232,'BFGS',1e-8),(233,'trust_region_Cauchy',1e-8)])
def test_distinct_derivative_optimizer_known_answer(row,key,value_limit):
 d=data(row);d.pop('candidates',None);d|={'initial_point':[1.5,-1.25],'iterations':300,'tolerance':1e-9}
 r=run(row,d)['result'];assert r['algorithm']==key and r['best_value']<value_limit and r['gradient_norm']<.1

def test_newton_rejects_non_positive_hessian():
 d=data(231);d|={'objective':'double_well','initial_point':[0.,0.]}
 with pytest.raises(QuantError,match='Hessian is not positive definite'):run(231,d)

def test_nonconvex_multistart_finds_double_well_and_reproducible():
 d=data(227);d|={'objective':'double_well','iterations':150,'restarts':12};d.pop('candidates',None)
 r=run(227,d)['result'];assert r['best_value']<1e-8 and r['algorithm']=='seeded_multistart_local_search' and r==run(227,d)['result']

def test_interior_point_stays_strictly_feasible_and_rejects_boundary_start():
 d=data(234);d|={'objective':'linear','coefficients':[-1,-1],'bounds':[[0,2],[0,2]],'constraints':[{'coefficients':[1,1],'rhs':3}],'initial_point':[.5,.5]}
 r=run(234,d)['result'];assert r['strict_feasibility_maintained'] and sum(r['best_point'])<3.000001 and r['duality_gap_bound']<.01
 d['initial_point']=[2,1]
 with pytest.raises(QuantError,match='strictly feasible'):run(234,d)

def test_optimizer_shape_and_bound_failures():
 d=data(228);d['bounds']=[[1,1]]
 with pytest.raises(QuantError,match='lower < upper'):run(228,d)
 d=data(220);d['constraints']=[{'coefficients':[1],'rhs':0}]
 with pytest.raises(QuantError,match='dimension mismatch'):run(220,d)
