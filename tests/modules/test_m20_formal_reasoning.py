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


def test_deduction_returns_source_indexed_entailing_support_and_drops_irrelevant_premise():
 r=argument_validity({'formulas':['P',{'implies':['P','Q']},'R'],'conclusion':'Q'})
 support=r['premise_support']
 assert support['premise_indices']==[0,1]
 assert support['kind']=='entailing_premise_subset' and support['irreducible']
 assert support['verified_entailment'] and not support['minimum_cardinality']
 for i in support['premise_indices']:
  keep=[j for j in support['premise_indices'] if j!=i]
  reduced=argument_validity({'formulas':[['P',{'implies':['P','Q']},'R'][j] for j in keep],'conclusion':'Q'})
  assert not reduced['validity']


def test_vacuous_entailment_support_is_named_inconsistent_not_sound_proof():
 r=argument_validity({'formulas':['P',{'not':'P'},'R'],'conclusion':'Q'})
 assert r['premise_support']['premise_indices']==[0,1]
 assert r['premise_support']['kind']=='inconsistent_premise_subset'
 assert not r['premise_support']['premises_satisfiable']
 assert r['soundness'] is None


def test_tautology_can_have_empty_support_and_invalid_argument_has_no_support():
 r=argument_validity({'formulas':['P'],'conclusion':{'or':['Q',{'not':'Q'}]}})
 assert r['premise_support']['premise_indices']==[] and r['premise_support']['irreducible']
 r=argument_validity({'formulas':['Q'],'conclusion':'P'})
 assert r['premise_support'] is None and r['countermodel']=={'P':False,'Q':True}


def test_propositional_support_budget_exhaustion_is_not_claimed_irreducible():
 r=argument_validity({'formulas':['P',{'implies':['P','Q']},'R'],'conclusion':'Q','support_max_checks':1})
 assert r['premise_support']['premise_indices']==[0,1,2]
 assert not r['premise_support']['irreducible'] and r['premise_support']['stopped_by']=='check_budget'


def test_returned_propositional_support_matches_independent_assignment_oracle():
 import itertools
 premises=['P',{'implies':['P','Q']},{'implies':['Q','R']},'S']
 r=argument_validity({'formulas':premises,'conclusion':'R'})
 indices=r['premise_support']['premise_indices']
 def valid(selected):
  for P,Q,R,S in itertools.product((False,True),repeat=4):
   values=[P,not P or Q,not Q or R,S]
   if all(values[i] for i in selected) and not R:return False
  return True
 assert indices==[0,1,2] and valid(indices)
 assert all(not valid(indices[:i]+indices[i+1:]) for i in range(len(indices)))
