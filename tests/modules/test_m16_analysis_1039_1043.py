"""Concept-level tests for doc rows 1039-1043."""
import pytest
from app.modules.m16_executive_dashboard import analysis

def test_row_1039_linear_chain_crf_global_decoding_and_partition():
 data={'tokens':['A','B'],'labels':['X','Y'],'emission_scores':[{'X':2,'Y':0},{'X':0,'Y':2}],'start_scores':{'X':0,'Y':0},'transition_scores':{'X':{'X':0,'Y':1},'Y':{'X':0,'Y':0}}}
 o=analysis.run('conditional_random_field',data)['output']
 assert o['labels']==['X','Y'] and o['path_score']==5
 assert o['log_partition']>o['path_score']

def test_row_1040_graphical_model_detects_cycles_and_components():
 dag=analysis.run('graphical_model',{'nodes':['a','b','c'],'edges':[['a','b'],['b','c']]})['output']
 assert dag['is_dag'] and dag['topological_order']==['a','b','c'] and dag['components']==[['a','b','c']]
 cyc=analysis.run('graphical_model',{'nodes':['a','b'],'edges':[['a','b'],['b','a']]})['output']
 assert not cyc['is_dag'] and cyc['topological_order'] is None

def test_row_1041_bayesian_network_exact_conditioning():
 data={'variables':['Rain','Sprinkler','Wet'],'parents':{'Rain':[],'Sprinkler':['Rain'],'Wet':['Rain','Sprinkler']},'cpts':{'Rain':{'':.2},'Sprinkler':{'0':.4,'1':.01},'Wet':{'00':.0,'01':.9,'10':.8,'11':.99}},'query':'Rain','evidence':{'Wet':True}}
 o=analysis.run('bayesian_network',data)['output']
 assert 0<o['probability_true']<1 and o['probability_true']>.2
 assert o['probability_true']+o['probability_false']==pytest.approx(1)

def test_row_1042_mrf_normalizes_potentials_and_returns_map():
 data={'variables':['a','b'],'edges':[['a','b']],'unary_log_potentials':{'a':{'0':0,'1':.2},'b':{'0':0,'1':.2}},'pairwise_log_potentials':{'a|b':{'00':1,'01':0,'10':0,'11':1}}}
 o=analysis.run('markov_random_field',data)['output']
 assert o['partition_function']>0 and o['map_assignment']=={'a':True,'b':True}
 assert all(0<=p<=1 for p in o['marginal_true'].values())

def test_row_1043_factor_graph_exact_product_inference():
 data={'variables':['a','b'],'factors':[{'scope':['a'],'table':{'0':.2,'1':.8}},{'scope':['a','b'],'table':{'00':3,'01':1,'10':1,'11':3}}]}
 o=analysis.run('factor_graph',data)['output']
 assert o['marginal_true']['a']==pytest.approx(.8)
 assert o['map_assignment']=={'a':True,'b':True} and 0<o['map_probability']<1

def test_graphical_algorithms_reject_malformed_models():
 with pytest.raises(ValueError):analysis.run('bayesian_network',{'variables':['b','a'],'parents':{'b':['a'],'a':[]},'cpts':{'a':1,'b':1},'query':'a'})
 with pytest.raises(ValueError):analysis.run('factor_graph',{'variables':['a'],'factors':[{'scope':['a'],'table':{'0':1}}]})
