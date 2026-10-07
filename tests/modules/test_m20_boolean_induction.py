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


def test_exact_next_query_splits_remaining_version_space_without_reasking_observed_case():
 r=run([obs('1',True,True,True)])
 query=r['next_query']
 assert query['features']=={'a':False,'b':True}
 assert query['label_hypothesis_counts']=={'false':2,'true':2}
 assert query['worst_case_remaining_hypotheses']==2
 assert query['guaranteed_eliminated_hypotheses']==2
 assert r['query_selection_status']=='discriminating_query_available'


def test_ambiguous_prediction_has_concrete_disagreeing_rules_not_probability():
 r=run([obs('1',True,True,True)],induction_targets=[{'id':'x','features':{'a':False,'b':True}}])
 prediction=r['predictions'][0]
 assert prediction['label_hypothesis_counts']=={'false':2,'true':2}
 for label in (False,True):
  rule=prediction['disagreement_witnesses'][str(label).lower()]
  assert all(value is True for value in rule.values())
  actual=all(prediction_value=={'a':False,'b':True}[feature] for feature,prediction_value in rule.items())
  assert actual is label


@pytest.mark.parametrize('rows,status',[
 ([obs('1',True,True,True),obs('2',True,False,True),obs('3',False,True,False),obs('4',False,False,False)],'no_discriminating_query'),
 ([obs('1',True,True,True),obs('2',True,True,False)],'inconsistent_evidence')])
def test_resolved_or_inconsistent_space_does_not_invent_next_query(rows,status):
 r=run(rows)
 assert r['next_query'] is None and r['query_selection_status']==status


def test_next_query_matches_independent_three_feature_oracle_and_label_update():
 import itertools
 names=['a','b','c']; vectors=list(itertools.product((False,True),repeat=3))
 records=[{'evidence_id':'yes','features':dict(zip(names,(True,True,True))),'label':True},
          {'evidence_id':'no','features':dict(zip(names,(False,False,False))),'label':False}]
 def predict(rule,vector):return all(bit is None or bit==actual for bit,actual in zip(rule,vector))
 hypotheses=[rule for rule in itertools.product((None,False,True),repeat=3)
             if predict(rule,(True,True,True)) and not predict(rule,(False,False,False))]
 candidates=[]
 for vector in vectors:
  if vector in [(True,True,True),(False,False,False)]:continue
  yes=sum(predict(rule,vector) for rule in hypotheses)
  candidates.append((max(yes,len(hypotheses)-yes),vector))
 worst,vector=min(candidates)
 result=induce({'features':names,'induction_observations':records})
 assert result['next_query']['features']==dict(zip(names,vector))
 assert result['next_query']['worst_case_remaining_hypotheses']==worst
 for label in (False,True):
  updated=induce({'features':names,'induction_observations':records+[{'evidence_id':'answer','features':dict(zip(names,vector)),'label':label}]})
  assert updated['consistent_hypothesis_count']==sum(predict(rule,vector)==label for rule in hypotheses)
  assert updated['consistent_hypothesis_count']<=worst
