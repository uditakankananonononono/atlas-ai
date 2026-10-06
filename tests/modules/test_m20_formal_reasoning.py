import pytest
from app.modules.m20_general_cognitive_worker.formal_reasoning import argument_validity,causal_effect,counterfactual


def test_deduction_proves_modus_ponens_and_returns_countermodel_for_affirming_consequent():
 good=argument_validity({'formulas':['P',{'implies':['P','Q']}],'conclusion':'Q'})
 bad=argument_validity({'formulas':['Q',{'implies':['P','Q']}],'conclusion':'P','validity':True})
 assert good['validity'] and good['soundness'] is None
 assert not bad['validity'] and bad['countermodel']=={'P':False,'Q':True}


def test_inconsistent_premises_explicitly_flag_vacuous_entailment():
 r=argument_validity({'formulas':['P',{'not':'P'}],'conclusion':'Q'})
 assert r['validity'] and not r['premises_satisfiable'] and r['premise_model_count']==0


def test_deduction_requires_formulas_not_caller_truth_labels():
 with pytest.raises(ValueError):argument_validity({'validity':True,'premises_true':True})


def test_do_intervention_propagates_mediated_effect_not_confounding_association():
 equations={'U':{},'X':{'parents':{'U':2}},'M':{'parents':{'X':3}},'Y':{'parents':{'M':4,'U':10}}}
 r=causal_effect({'equations':equations,'exposure':'X','outcome':'Y','intervention_values':[1,2],'exogenous':{'U':5}})
 assert r['effect']==12 and r['effect_per_unit']==12
 assert r['interventions'][0]['U']==r['interventions'][1]['U']==5
 assert r['interventions'][0]['Y']==62 and r['interventions'][1]['Y']==74


def test_counterfactual_abducts_actual_unit_noise_then_holds_it_constant():
 equations={'U':{},'X':{'parents':{'U':2}},'Y':{'parents':{'X':3,'U':4}}}
 r=counterfactual({'equations':equations,'factual':{'U':1,'X':3,'Y':15},'intervention':{'X':5}})
 assert r['abduced_noise']=={'U':1.,'X':1.,'Y':2.}
 assert r['result']=={'U':1.,'X':5.,'Y':21.}
 assert r['differences']['Y']==6 and r['held_constant']==r['abduced_noise']


def test_intervening_on_mediator_cuts_original_parent_edge():
 r=causal_effect({'equations':{'X':{},'M':{'parents':{'X':3}},'Y':{'parents':{'M':4}}},'exposure':'M','outcome':'Y','intervention_values':[1,2],'exogenous':{'X':100}})
 assert r['effect']==4


def test_cyclic_model_and_missing_factual_data_rejected():
 with pytest.raises(ValueError,match='acyclic'):causal_effect({'equations':{'X':{'parents':{'Y':1}},'Y':{'parents':{'X':1}}}})
 with pytest.raises(ValueError,match='complete'):counterfactual({'equations':{'X':{},'Y':{}},'factual':{'X':1},'intervention':{'X':2}})


def test_biconditional_rejects_or_truth_assignment_and_accepts_equal_values():
 # Iff(P,Q) entails equal truth values. Or(P,Q) does not entail P.
 r=argument_validity({'formulas':[{'iff':['P','Q']},'Q'],'conclusion':'P'})
 assert r['validity'] and r['premise_model_count']==1
 r=argument_validity({'formulas':[{'iff':['P','Q']},{'not':'P'}],'conclusion':{'not':'Q'}})
 assert r['validity'] and r['premise_model_count']==1
 r=argument_validity({'formulas':[{'iff':['P','Q']}],'conclusion':'P'})
 assert not r['validity'] and r['countermodel']=={'P':False,'Q':False}
