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
