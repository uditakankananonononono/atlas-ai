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


def test_default_queries_preserve_concrete_support_and_countermodel_for_ambiguity():
 p={'defaults':[{'id':'a-if-not-b','unless':['b'],'then':'a'},{'id':'b-if-not-a','unless':['a'],'then':'b'}], 'query_atoms':['a','unknown']}
 r=default_inference(p)
 query=next(q for q in r['queries'] if q['atom']=='a')
 assert query['status']=='ambiguous' and query['possible'] and not query['cautious']
 assert query['supporting_model']==['a'] and query['countermodel']==['b']
 proofs={tuple(w['model']):w for w in r['model_witnesses']}
 assert proofs[('a',)]['derived_trace']==[{'rule':'a-if-not-b','fact':'a'}]
 assert proofs[('a',)]['defeated_rules']==[{'rule_id':'b-if-not-a','blocking_atoms':['a']}]
 unknown=next(q for q in r['queries'] if q['atom']=='unknown')
 assert unknown['status']=='not_entailed' and not unknown['possible']
 assert unknown['not_entailed_does_not_mean_false']


def test_default_no_models_does_not_report_query_false_or_vacuously_cautious():
 r=default_inference({'defaults':[{'unless':['a'],'then':'a'}],'query_atoms':['a']})
 q=r['queries'][0]
 assert q['status']=='inconsistent_program' and q['possible'] is None and q['cautious'] is None
 assert q['supporting_model'] is None and q['countermodel'] is None
 assert r['model_witnesses']==[]


def test_default_query_witness_uses_revised_facts_and_actual_reduct_derivation():
 r=default_inference({'facts':['bird','penguin'],'removed_facts':['penguin'], 'defaults':[{'id':'fly','if':['bird'],'unless':['penguin'],'then':'flies'}],'query_atoms':['flies']})
 q=r['queries'][0]
 assert q['status']=='cautiously_entailed' and q['countermodel'] is None
 assert q['supporting_model']==['bird','flies']
 assert r['model_witnesses'][0]['supplied_facts']==['bird']
 assert r['model_witnesses'][0]['derived_trace']==[{'rule':'fly','fact':'flies'}]
