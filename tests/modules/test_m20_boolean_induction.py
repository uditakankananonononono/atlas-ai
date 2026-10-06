import pytest
from app.modules.m20_general_cognitive_worker.boolean_induction import induce

def obs(id,a,b,label):return {'evidence_id':id,'features':{'a':a,'b':b},'label':label}
def run(rows,**kw):return induce({'features':['a','b'],'induction_observations':rows,**kw})

def test_induces_actual_boolean_rule_not_supplied_pattern():
 r=run([obs('1',True,True,True),obs('2',True,False,True),obs('3',False,True,False),obs('4',False,False,False)],pattern='b',strength=1)
 assert r['consistent_hypothesis_count']==1 and r['simplest_consistent_rules']==[{'a':True}]
 assert r['hypotheses_evaluated']==9 and r['minimum_training_errors']==0


def test_unseen_case_preserves_version_space_disagreement():
 r=run([obs('1',True,True,True)],induction_targets=[{'id':'x','features':{'a':False,'b':True}}])
 assert r['consistent_hypothesis_count']==4
 assert r['predictions'][0]['label'] is None and r['predictions'][0]['possible_labels']==[False,True]


def test_conflicting_observations_do_not_produce_fictional_rule():
 r=run([obs('1',True,True,True),obs('2',True,True,False)])
 assert r['status']=='no_consistent_conjunction' and r['minimum_training_errors']==1
 assert r['simplest_consistent_rules']==[]


def test_negated_literal_and_target_prediction():
 r=run([obs('1',False,True,True),obs('2',False,False,True),obs('3',True,True,False)],induction_targets=[{'id':'x','features':{'a':True,'b':False}}])
 assert r['simplest_consistent_rules']==[{'a':False}]
 assert r['predictions'][0]['label'] is False


def test_missing_duplicate_or_nonboolean_evidence_rejected():
 with pytest.raises(ValueError):run([obs('1',True,True,True),obs('1',False,False,False)])
 with pytest.raises(ValueError):run([obs('1',1,True,True)])
