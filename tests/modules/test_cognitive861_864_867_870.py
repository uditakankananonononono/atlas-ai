import pytest
from app.modules.m20_general_cognitive_worker.cognitive_learning_860_909 import execute,CognitiveLearningError
from app.modules.m20_general_cognitive_worker.concept_induction870 import induce


def packet(inputs):
    return {'tenant_id':'t','actor_id':'a','sources':[{'source_id':'s','observed_at':'2026-10-13'}],'inputs':inputs}


def test_real_argument_entailment_countermodel_and_vacuity():
    good=execute(861,packet({'formulas':['p',{'implies':['p','q']}],'conclusion':'q'}))['result']['formal_argument_analysis']
    assert good['validity'] and good['premises_satisfiable'] and good['soundness']is None
    bad=execute(861,packet({'formulas':[{'implies':['p','q']},'q'],'conclusion':'p'}))['result']['formal_argument_analysis']
    assert not bad['validity'] and bad['countermodel']=={'p':False,'q':True}
    contradiction=execute(861,packet({'formulas':['p',{'not':'p'}],'conclusion':'q'}))['result']['formal_argument_analysis']
    assert contradiction['validity'] and not contradiction['premises_satisfiable']


def test_actual_concept_induction_negative_and_boundary_cases():
    out=induce({'examples':[{'id':'p1','attributes':['red','round']},{'id':'p2','attributes':['red','round','small']}],
                'non_examples':[{'id':'n1','attributes':['red']},{'id':'n2','attributes':['round']}],
                'boundary_cases':[{'id':'q1','attributes':['red','round']},{'id':'q2','attributes':['round']}]})
    assert out['hypotheses']==[['red','round']]
    assert [q['classification']for q in out['boundary_cases']]==[True,False]
    assert not out['general_concept_learning']


def test_contradictions_and_hypothesis_disagreement_not_hidden():
    p={'examples':[{'id':'p','attributes':['red','round']}],
       'non_examples':[{'id':'n','attributes':[]}],'boundary_cases':[{'id':'q','attributes':['red']}]}
    out=induce(p);assert out['hypotheses']==[['red'],['round']] and out['boundary_cases'][0]['classification']is None
    p['non_examples'][0]['attributes']=['red','round']
    assert induce(p)['status']=='no_consistent_conjunction'


def test_object_ideas_and_deterministic_reframing():
    ideas=[{'text':'a','category':'x'},{'text':'a','category':'x'},{'text':'b','category':'y'}]
    out=execute(864,packet({'ideas':ideas}))['result']
    assert out['fluency']==2 and out['flexibility']==2
    out=execute(867,packet({'current_frame':'cost','alternative_frame':'investment','new_implications':['z','b','a'],'old_implications':['b']}))['result']
    assert out['implication_delta']==['a','z']


def test_induction_complexity_and_duplicate_ids_refused():
    p={'examples':[{'id':'p','attributes':[str(i)for i in range(17)]}],'non_examples':[]}
    with pytest.raises(ValueError,match='16'):induce(p)
    with pytest.raises(CognitiveLearningError):execute(870,packet({'concept_induction':True,'examples':[{'id':'p','attributes':['a']}],'non_examples':[{'id':'p','attributes':[]}]}))
