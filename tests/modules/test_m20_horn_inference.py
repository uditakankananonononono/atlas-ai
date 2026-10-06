import pytest
from app.modules.m20_general_cognitive_worker.horn_inference import forward


def test_multistep_conjunctive_closure_and_proof_links():
 r=forward({'facts':['a','b'],'rules':[{'id':'2','if':['c'],'then':'d'},{'id':'1','if':['a','b'],'then':'c'}],'query_atoms':['d','z']})
 assert r['facts']==['a','b','c','d']
 assert r['rule_trace']==[{'rule':'1','fact':'c'},{'rule':'2','fact':'d'}]
 assert r['proofs']['c']['premises']==['a','b'] and r['proofs']['d']['premises']==['c']
 assert r['queries'][0]['entailed'] and r['queries'][1]['not_entailed_does_not_mean_false']


def test_unsupported_cycle_has_no_self_created_evidence():
 r=forward({'facts':[],'rules':[{'if':['a'],'then':'b'},{'if':['b'],'then':'a'}],'query_atoms':['a']})
 assert r['facts']==[] and not r['queries'][0]['entailed']


def test_fact_change_really_changes_closure_and_empty_antecedent_rule():
 rules=[{'if':['a'],'then':'b'},{'if':[],'then':'axiom'}]
 assert forward({'facts':[],'rules':rules})['facts']==['axiom']
 assert forward({'facts':['a'],'rules':rules})['facts']==['a','axiom','b']

@pytest.mark.parametrize('rule',[{'then':None},{'if':'a','then':'b'},{'if':['a'],'unless':['c'],'then':'b'}])
def test_invalid_or_negated_rule_not_converted_to_string_fact(rule):
 with pytest.raises(ValueError):forward({'facts':['a'],'rules':[rule]})
