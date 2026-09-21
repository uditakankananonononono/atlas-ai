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
