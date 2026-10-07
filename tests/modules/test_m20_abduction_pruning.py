from app.modules.m20_general_cognitive_worker import defeasible_reasoning as reasoning


def test_abduction_skips_supersets_of_proven_minimal_explanations(monkeypatch):
    original=reasoning.closure;calls=[]
    def counted(facts,program):
        calls.append(set(facts));return original(facts,program)
    monkeypatch.setattr(reasoning,'closure',counted)
    result=reasoning.abductive_search({'facts':[],'observations':['observed'],
        'hypotheses':[{'atom':f'h{i}','cost':i} for i in range(8)],
        'rules':[{'id':f'r{i}','if':[f'h{i}'],'then':'observed'} for i in range(8)]})
    assert result['explanation_count']==8
    assert len(calls)==9
    assert result['best_explanations'][0]['hypotheses']==['h0']


def test_pruned_abduction_preserves_pair_alternatives_forbidden_and_empty_solution():
    result=reasoning.abductive_search({'facts':[],'observations':['o'],'forbidden':['bad'],
        'hypotheses':[{'atom':'a','cost':1},{'atom':'b','cost':1},{'atom':'c','cost':2}],
        'rules':[{'if':['a','b'],'then':'o'},{'if':['c'],'then':'o'},{'if':['a','c'],'then':'bad'}]})
    assert {tuple(r['hypotheses']) for r in result['explanations']}=={('a','b'),('c',)}
    assert len(result['best_explanations'])==2
    result=reasoning.abductive_search({'facts':['o'],'observations':['o'],
        'hypotheses':[{'atom':'a','cost':1}], 'rules':[{'if':['a'],'then':'other'}]})
    assert result['explanations'][0]['hypotheses']==[]
    assert result['subsets_evaluated']==1


def test_pruned_search_matches_exhaustive_oracle_on_small_programs():
    import itertools,random
    rng=random.Random(37)
    for _ in range(30):
        atoms=['a','b','c','d'];raw=[]
        for i in range(5):
            raw.append({'id':str(i),'if':rng.sample(atoms,rng.randint(1,3)),
                        'then':rng.choice(['o','bad'])})
        program=reasoning.rules(raw);valid=[]
        for size in range(5):
            for subset in itertools.combinations(atoms,size):
                known,_=reasoning.closure(set(subset),program)
                if 'o' in known and 'bad' not in known:valid.append(set(subset))
        minimal={tuple(sorted(s)) for s in valid if not any(other<s for other in valid)}
        result=reasoning.abductive_search({'facts':[],'observations':['o'],'forbidden':['bad'],
            'hypotheses':[{'atom':atom,'cost':1} for atom in atoms],'rules':raw})
        assert {tuple(sorted(r['hypotheses'])) for r in result['explanations']}==minimal


def test_abduction_computes_discriminating_probe_from_actual_explanation_closures():
 result=reasoning.abductive_search({'observations':['wet'],
  'hypotheses':[{'atom':'rain','cost':1},{'atom':'sprinkler','cost':2}],
  'rules':[{'if':['rain'],'then':'wet'},{'if':['sprinkler'],'then':'wet'},{'if':['rain'],'then':'cloudy'}],
  'probe_atoms':['wet','cloudy','unknown']})
 assert result['next_probe']['atom']=='cloudy'
 assert result['next_probe']['entailed_explanation_count']==1
 assert result['next_probe']['not_entailed_explanation_count']==1
 assert result['next_probe']['worst_case_remaining_explanations']==1
 assert result['next_probe']['not_entailed_is_not_predicted_false']
 assert result['probe_results'][1]['atom']=='unknown' # sorted deterministic order
 assert result['probe_results'][1]['entailed_explanation_count']==0


def test_abduction_probe_split_counts_all_minimal_alternatives_not_just_cheapest():
 result=reasoning.abductive_search({'observations':['o'],
  'hypotheses':[{'atom':'a','cost':1},{'atom':'b','cost':5},{'atom':'c','cost':10}],
  'rules':[{'if':[atom],'then':'o'} for atom in 'abc']+[{'if':['a'],'then':'probe'},{'if':['b'],'then':'probe'}],
  'probe_atoms':['probe']})
 assert result['explanation_count']==3 and len(result['best_explanations'])==1
 assert result['next_probe']['entailed_explanation_count']==2
 assert result['next_probe']['not_entailed_explanation_count']==1
 assert result['next_probe']['worst_case_remaining_explanations']==2


def test_abduction_no_explanation_or_no_disagreement_does_not_invent_probe():
 for hypothesis,status in [('rain','no_discriminating_probe'),('sun','no_explanations')]:
  result=reasoning.abductive_search({'observations':['wet'],'hypotheses':[{'atom':hypothesis,'cost':1}],
   'rules':[{'if':['rain'],'then':'wet'}],'probe_atoms':['wet']})
  assert result['next_probe'] is None and result['probe_status']==status
