import pytest
from app.modules.m20_general_cognitive_worker.defeasible_reasoning import default_inference,abductive_search


def test_default_conclusion_retracts_when_exception_arrives_and_restores_after_removal():
 defaults=[{'id':'bird','if':['bird'],'unless':['penguin'],'then':'flies'}]
 r=default_inference({'facts':['bird'],'defaults':defaults,'added_facts':['penguin']})
 assert r['before']['cautious_conclusions']==['bird','flies']
 assert r['cautious_conclusions']==['bird','penguin'] and r['retracted_conclusions']==['flies']
 s=default_inference({'facts':['bird','penguin'],'defaults':defaults,'removed_facts':['penguin']})
 assert s['new_conclusions']==['flies']


def test_mutually_defeasible_conclusions_keep_alternative_models_not_arbitrary_winner():
 r=default_inference({'defaults':[{'unless':['b'],'then':'a'},{'unless':['a'],'then':'b'}]})
 assert r['model_count']==2 and r['cautious_conclusions']==[]
 assert r['ambiguous_conclusions']==['a','b']


def test_negation_cycle_no_stable_model_is_explicit():
 r=default_inference({'defaults':[{'unless':['a'],'then':'a'}]})
 assert not r['consistent'] and r['stable_models']==[]


def test_abduction_searches_combinations_and_returns_actual_proof_trace():
 p={'observations':['alarm'],'rules':[{'id':'r','if':['smoke','power'],'then':'alarm'}],
    'hypotheses':[{'atom':'smoke','cost':2},{'atom':'power','cost':1},{'atom':'alarm','cost':9}]}
 r=abductive_search(p)
 assert r['best_explanations'][0]['hypotheses']==['smoke','power']
 assert r['best_explanations'][0]['cost']==3
 assert r['best_explanations'][0]['proof_trace']==[{'rule':'r','fact':'alarm'}]
 assert r['explanation_count']==2


def test_abduction_forbidden_consequence_removes_inconsistent_explanation():
 p={'observations':['wet'],'forbidden':['danger'],'rules':[{'if':['rain'],'then':'wet'},{'if':['sprinkler'],'then':'wet'},{'if':['rain'],'then':'danger'}],
    'hypotheses':[{'atom':'rain','cost':1},{'atom':'sprinkler','cost':2}]}
 r=abductive_search(p)
 assert r['best_explanations'][0]['hypotheses']==['sprinkler'] and r['explanation_count']==1


def test_unexplained_observations_do_not_generate_plausible_text():
 r=abductive_search({'observations':['wet'],'rules':[{'if':['rain'],'then':'wet'}],'hypotheses':[{'atom':'sun','cost':1}]})
 assert r['explanations']==[] and r['best_explanations']==[]


def test_duplicate_hypotheses_and_unsupported_rule_negation_rejected():
 p={'observations':['wet'],'rules':[{'if':['rain'],'then':'wet'}],'hypotheses':[{'atom':'rain','cost':1}]*2}
 with pytest.raises(ValueError):abductive_search(p)
 with pytest.raises(ValueError):abductive_search({**p,'hypotheses':[{'atom':'rain','cost':1}],'rules':[{'unless':['sun'],'then':'wet'}]})
