import pytest
from app.modules.m20_general_cognitive_worker.fuzzy_inference import infer
R=[{'id':'high','if':{'and':['warm',{'not':'wet'}]},'consequent':10},
   {'id':'low','if':{'or':['wet','cold']},'consequent':2,'weight':.5}]
def run(m,**kw):return infer({'memberships':m,'fuzzy_rules':R,**kw})

def test_actual_nested_antecedents_and_weighted_consequents():
 r=run({'warm':.8,'wet':.2,'cold':.1})
 assert [x['firing_strength'] for x in r['rules']]==pytest.approx([.8,.1])
 assert r['output']==pytest.approx(8.2/.9)
 assert run({'warm':.1,'wet':.9,'cold':.1})['output']<r['output']


def test_no_firing_rule_does_not_fabricate_default_output():
 r=infer({'memberships':{'a':0},'fuzzy_rules':[{'id':'1','if':'a','consequent':5}]})
 assert r['output'] is None and r['status']=='no_firing_rule'


def test_consequent_and_rule_weight_change_actual_output():
 r=infer({'memberships':{'a':1},'fuzzy_rules':[{'id':'1','if':'a','consequent':2},{'id':'2','if':'a','consequent':10,'weight':0}]})
 assert r['output']==2 and r['total_firing_strength']==1

@pytest.mark.parametrize('m',[{'warm':2,'wet':.2,'cold':.1},{'warm':True,'wet':.2,'cold':.1},{'warm':float('nan'),'wet':.2,'cold':.1}])
def test_invalid_memberships_rejected(m):
 with pytest.raises(ValueError):run(m)


def test_unknown_atoms_and_duplicate_rule_ids_rejected():
 with pytest.raises(ValueError):run({'warm':.2})
 with pytest.raises(ValueError):infer({'memberships':{'a':1},'fuzzy_rules':[{'id':'1','if':'a','consequent':1}]*2})
