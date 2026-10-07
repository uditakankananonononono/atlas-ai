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


def test_reverse_chain_uses_indexed_agenda_not_repeated_whole_program_scans():
 size=100
 rules=[{'id':str(i),'if':[str(i)],'then':str(i+1)} for i in reversed(range(size))]
 result=forward({'facts':['0'],'rules':rules,'query_atoms':['100']})
 assert result['queries'][0]['entailed']
 assert result['closure_metrics']['premise_notifications']==size
 assert result['closure_metrics']['rules_processed']==size
 assert result['rule_trace']==[{'rule':str(i),'fact':str(i+1)} for i in range(size)]


def test_indexed_horn_closure_keeps_ordered_sweep_first_proof_and_conjunction_semantics():
 rules=[{'id':'early','if':['b'],'then':'x'}, {'id':'make-b','if':['a'],'then':'b'},
        {'id':'late','if':['b'],'then':'x'},{'id':'join','if':['b','x'],'then':'done'},
        {'id':'cycle','if':['unsupported'],'then':'unsupported'}]
 result=forward({'facts':['a'],'rules':rules})
 assert result['rule_trace']==[{'rule':'make-b','fact':'b'},{'rule':'late','fact':'x'},{'rule':'join','fact':'done'}]
 assert result['closure_metrics']['rules_processed']<=4


def test_indexed_closure_matches_independent_ordered_sweep_on_100_random_programs():
 import random
 from app.modules.m20_general_cognitive_worker.defeasible_reasoning import closure,rules
 rng=random.Random(53);atoms=list('abcdef')
 for _ in range(100):
  program=rules([{'id':str(i),'if':rng.sample(atoms,rng.randrange(4)),'then':rng.choice(atoms)} for i in range(12)])
  facts=set(rng.sample(atoms,rng.randrange(4)));known=set(facts);trace=[];changed=True
  while changed:
   changed=False
   for rule in program:
    if rule['if']<=known and rule['then'] not in known:
     known.add(rule['then']);trace.append({'rule':rule['id'],'fact':rule['then']});changed=True
  actual,actual_trace=closure(facts,program)
  assert actual==known and actual_trace==trace


def test_horn_fact_revision_recomputes_alternative_support_not_blanket_descendant_retraction():
 result=forward({'facts':['a','b'],'removed_facts':['a'],
  'rules':[{'id':'via-a','if':['a'],'then':'x'},{'id':'via-b','if':['b'],'then':'x'},{'id':'next','if':['x'],'then':'y'}],
  'query_atoms':['y']})
 assert result['facts']==['b','x','y']
 assert result['before_facts']==['a','b','x','y']
 assert result['retracted_facts']==['a'] and result['new_facts']==[]
 assert result['proofs']['x']['rule_id']=='via-b'
 assert result['queries'][0]['proof_tree']['premise_proofs'][0]['rule_id']=='via-b'


def test_horn_revision_retracts_unsupported_cycle_and_adds_new_real_derivation():
 result=forward({'facts':['a'],'removed_facts':['a'],'added_facts':['b'],
  'rules':[{'id':'a-to-x','if':['a'],'then':'x'},{'id':'x-to-y','if':['x'],'then':'y'},
           {'id':'y-to-x','if':['y'],'then':'x'},{'id':'b-to-z','if':['b'],'then':'z'}]})
 assert result['facts']==['b','z']
 assert result['retracted_facts']==['a','x','y'] and result['new_facts']==['b','z']
 assert result['rule_trace']==[{'rule':'b-to-z','fact':'z'}]


def test_horn_revision_rejects_missing_removal_and_conflicting_add_remove():
 for update in [{'removed_facts':['missing']},{'added_facts':['a'],'removed_facts':['a']}]:
  with pytest.raises(ValueError):forward({'facts':['a'],'rules':[{'if':['a'],'then':'b'}],**update})
