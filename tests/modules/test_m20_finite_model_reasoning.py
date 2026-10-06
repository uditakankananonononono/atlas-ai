import pytest
from app.modules.m20_general_cognitive_worker.finite_model_reasoning import models

def c(left,op,right):return {'left':left,'operator':op,'right':{'variable':right}}
def run(constraints,queries=[]):return models({'model_domains':{'a':[0,1,2],'b':[0,1,2],'c':[0,1,2]},'model_constraints':constraints,'model_queries':queries})

def test_model_constraints_compute_predictions_with_transitive_entailment():
 r=run([c('a','lt','b'),c('b','lt','c')],[c('a','lt','c')])
 assert r['assignments_evaluated']==27 and r['feasible_model_count']==1
 assert r['example_model']=={'a':0,'b':1,'c':2}
 assert r['queries'][0]['entailed'] and r['queries'][0]['possible']


def test_countermodel_preserves_possible_but_not_guaranteed_prediction():
 r=run([c('a','lt','b')],[c('b','lt','c')]);q=r['queries'][0]
 assert not q['entailed'] and q['possible']
 assert not q['countermodel']['b']<q['countermodel']['c']
 assert q['supporting_model']['b']<q['supporting_model']['c']


def test_inconsistent_model_does_not_claim_vacuous_real_world_truth():
 r=run([c('a','lt','b'),c('b','lt','a')],[c('a','lt','c')])
 assert r['status']=='inconsistent' and r['feasible_model_count']==0
 assert r['queries'][0]['entailed'] is None and r['example_model'] is None


def test_literal_constraint_is_not_confused_with_named_variable():
 r=models({'model_domains':{'name':['name','other']},'model_constraints':[{'left':'name','operator':'eq','right':{'value':'name'}}]})
 assert r['example_model']=={'name':'name'} and r['feasible_model_count']==1


def test_bad_domain_constraint_or_search_size_rejected():
 with pytest.raises(ValueError):models({'model_domains':{'a':list(range(20)),'b':list(range(20)),'c':list(range(20)),'d':list(range(20))},'model_constraints':[]})
 with pytest.raises(ValueError):run([c('a','lt','missing')])
