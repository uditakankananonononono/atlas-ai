from itertools import combinations
import random
import pytest
from app.modules.atlas_repair_frontier import Candidate,frontier,greedy,supported_points,replay

def independent_oracle(nodes,cap):
    # Independent combinations enumeration; no production masks/frontier used.
    answers=[]
    for count in range(len(nodes)+1):
        for group in combinations(nodes,count):
            chosen={n.key for n in group}
            if sum(n.cost for n in group)<=cap and all(n.executable and set(n.parents)<=chosen for n in group):
                answers.append(sum(n.value for n in group))
    return max(answers)

def graph(seed,n=9):
    r=random.Random(seed)
    return [Candidate(str(i),r.randint(1,9),r.randint(0,15),tuple(str(j) for j in range(i) if r.random()<.16),r.random()>.1) for i in range(n)]

def test_every_budget_against_independent_oracle():
    for seed in range(25):
        nodes=graph(seed);points=frontier(nodes)
        for cap in range(sum(n.cost for n in nodes)+1):
            assert max(p['value'] for p in points if p['cost']<=cap)==independent_oracle(nodes,cap)

def test_unsupported_cap_witness():
    nodes=[Candidate('a',2,2),Candidate('b',3,4)]
    points=frontier(nodes)
    assert [(p['cost'],p['value']) for p in points]==[(0,0),(2,2),(3,4),(5,6)]
    assert (2,2) not in [(p['cost'],p['value']) for p in supported_points(points)]
    assert independent_oracle(nodes,2)==2

def test_real_replay_and_withdrawal():
    nodes=[Candidate('a',1,0),Candidate('b',1,5,('a',)),Candidate('c',1,9,('b',))]
    for p in frontier(nodes):
        result=replay(nodes,p['keys'],evidence_version=2)
        # Full replay computed independently by topological evaluation.
        oracle={'a':2,'b':4,'c':6}
        assert result['outputs']=={k:oracle[k] for k in p['keys']}
        assert result==replay(nodes,p['keys'],evidence_version=2)
    with pytest.raises(ValueError):replay(nodes,['b'],evidence_version=2)
    assert replay(nodes,['a'],evidence_version=1)['receipt_sha256']!=replay(nodes,['a'],evidence_version=2)['receipt_sha256']

@pytest.mark.parametrize('nodes',[[Candidate('x',0,1)],[Candidate('x',True,1)],[Candidate('x',1,-1)],[Candidate('x',1,1,('x',))],[Candidate('x',1,1),Candidate('x',1,1)],[Candidate(str(i),1,1) for i in range(21)]])
def test_invalid_graphs(nodes):
    with pytest.raises(ValueError):frontier(nodes)

def test_greedy_never_overspends():
    for seed in range(10):
        nodes=graph(seed)
        for cap in range(20):
            p=greedy(nodes,cap);assert p['cost']<=cap
            replay(nodes,p['keys'],evidence_version=2)
            assert p['value']<=independent_oracle(nodes,cap)

def test_exact_twenty_boundary_and_empty():
    # Chain keeps this acceptance-boundary test linear rather than 2**20.
    nodes=[Candidate(str(i),1,1,(str(i-1),) if i else ()) for i in range(20)]
    assert frontier(nodes)[-1]=={'cost':20,'value':20,'keys':tuple(str(i) for i in range(20))}
    with pytest.raises(ValueError):frontier(nodes+[Candidate('20',1,1,('19',))])
    assert frontier([])==[{'cost':0,'value':0,'keys':()}]

@pytest.mark.parametrize('nodes',[
    None,{},[object()],[Candidate('',1,1)],[Candidate(1,1,1)],
    [Candidate('x',1,True)],[Candidate('x',1.0,1)],[Candidate('x',1,1.0)],
    [Candidate('x',1,1,[],True)],
    [Candidate('x',1,1),Candidate('y',1,1,('x','x'))],
    [Candidate('x',1,1,(1,))],
    [Candidate('x',1,1,(),1)],[Candidate('x',1,1,(),None)],
])
def test_validate_contract(nodes):
    from app.modules.atlas_repair_frontier.core import validate
    with pytest.raises(ValueError):validate(nodes)

@pytest.mark.parametrize('cap',[-1,True,1.0,None])
def test_invalid_greedy_caps(cap):
    with pytest.raises(ValueError):greedy([],cap)

def test_zero_cap():
    assert greedy([Candidate('x',1,0)],0)=={'cost':0,'value':0,'keys':()}

@pytest.mark.parametrize('version',[0,-1,True,1.0,None])
def test_invalid_evidence_versions(version):
    with pytest.raises(ValueError):replay([],[],evidence_version=version)

@pytest.mark.parametrize('selected',[None,{},set(),['a','a'],['unknown']])
def test_invalid_selection(selected):
    with pytest.raises(ValueError):replay([Candidate('a',1,1)],selected,evidence_version=1)

def test_nonexecutable_selection():
    with pytest.raises(ValueError):replay([Candidate('a',1,1,(),False)],['a'],evidence_version=1)

def test_receipt_wire_contract():
    import hashlib,json
    nodes=[Candidate('z',2,3),Candidate('a',1,4,('z',),True)]
    # Literal payload independent from the production payload construction.
    payload={'nodes':[{'key':'z','cost':2,'value':3,'parents':[],'executable':True},
                      {'key':'a','cost':1,'value':4,'parents':['z'],'executable':True}],
             'selected':['a','z'],'evidence_version':3,'outputs':{'z':3,'a':6}}
    expected=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert replay(nodes,['z','a'],evidence_version=3)=={'outputs':{'z':3,'a':6},'receipt_sha256':expected}
    assert replay(nodes,('a','z'),evidence_version=3)['receipt_sha256']==expected

def test_frontier_lexical_tiebreak_not_insertion_order():
    nodes=[Candidate('z',1,2),Candidate('a',1,2)]
    assert frontier(nodes)==[{'cost':0,'value':0,'keys':()},
                             {'cost':1,'value':2,'keys':('a',)},
                             {'cost':2,'value':4,'keys':('z','a')}]

def test_greedy_ties_ratio_then_value_then_key():
    # Equal ratio: larger marginal value wins, so b consumes the whole cap.
    nodes=[Candidate('z',1,2),Candidate('b',2,4)]
    assert greedy(nodes,2)=={'cost':2,'value':4,'keys':('b',)}
    # Equal ratio/value/cost: lexicographically largest key wins, regardless of order.
    assert greedy([Candidate('z',1,2),Candidate('a',1,2)],1)['keys']==('z',)
    assert greedy([Candidate('a',1,2),Candidate('z',1,2)],1)['keys']==('z',)
    # Zero value/ratio: lower cost wins before key (otherwise z would win).
    assert greedy([Candidate('a',1,0),Candidate('z',2,0)],2)['keys']==('a',)

def test_random_replay_against_memoised_recursive_oracle():
    from functools import lru_cache
    for seed in range(30):
        nodes=graph(seed);by={n.key:n for n in nodes}
        @lru_cache(None)
        def evaluate(key):
            return 7+sum(evaluate(parent) for parent in by[key].parents)
        for point in frontier(nodes):
            expected={key:evaluate(key) for key in point['keys']}
            assert replay(nodes,point['keys'],evidence_version=7)['outputs']==expected

def test_default_executable_and_supported_collinear_ties():
    assert Candidate('x',1,1).executable is True
    points=[{'cost':0,'value':0},{'cost':1,'value':1},{'cost':2,'value':2}]
    assert supported_points(points)==points
    points=[{'cost':0,'value':0},{'cost':2,'value':1},{'cost':3,'value':3},{'cost':6,'value':4}]
    assert supported_points(points)==[points[0],points[2],points[3]]

def test_supported_points_against_independent_fraction_sweep():
    from fractions import Fraction
    # Pairwise crossing coefficients and interior intervals cover every linear envelope.
    for seed in range(30):
        points=frontier(graph(seed))
        crossings={Fraction(0)}
        for p in points:
            for q in points:
                if p['cost']!=q['cost']:
                    x=Fraction(p['value']-q['value'],p['cost']-q['cost'])
                    if x>=0:crossings.add(x)
        ordered=sorted(crossings)
        probes=ordered+[(a+b)/2 for a,b in zip(ordered,ordered[1:])]+[ordered[-1]+1]
        expected=set()
        for x in probes:
            values=[p['value']-x*p['cost'] for p in points]
            expected.update(i for i,v in enumerate(values) if v==max(values))
        assert supported_points(points)==[p for i,p in enumerate(points) if i in expected]

def test_frontier_lexical_tie_in_ascending_insertion_order():
    assert frontier([Candidate('a',1,2),Candidate('z',1,2)])[1]['keys']==('a',)

def test_frontier_drops_zero_reward_and_dominated_points():
    assert frontier([Candidate('a',1,0)])==[{'cost':0,'value':0,'keys':()}]
    assert frontier([Candidate('a',1,5),Candidate('b',3,2)])==[
        {'cost':0,'value':0,'keys':()}, {'cost':1,'value':5,'keys':('a',)},
        {'cost':4,'value':7,'keys':('a','b')}]

@pytest.mark.parametrize('nodes',[[Candidate('a',0,2)],[Candidate('a',1,2),Candidate('a',2,3)]])
def test_greedy_validates_graph_first(nodes):
    with pytest.raises(ValueError):greedy(nodes,10)

def test_replay_validates_duplicate_keys():
    with pytest.raises(ValueError):replay([Candidate('a',1,1),Candidate('a',2,2)],['a'],evidence_version=1)

@pytest.mark.parametrize('names',[
    ('zeta','alpha','theta','beta','omega','gamma','delta','epsilon'),
    ('k11','k03','k91','k27','k55','k01','k09','k73'),
    ('violet','green','yellow','orange','blue','red','indigo'),
])
def test_receipt_large_sorted_selection(names):
    import hashlib,json
    nodes=[Candidate(k,1,2) for k in names]
    payload={'nodes':[{'key':k,'cost':1,'value':2,'parents':[],'executable':True} for k in names],
             'selected':sorted(names),'evidence_version':2,'outputs':{k:2 for k in names}}
    expected=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert replay(nodes,list(reversed(names)),evidence_version=2)['receipt_sha256']==expected

def test_candidate_immutable():
    from dataclasses import FrozenInstanceError
    n=Candidate('a',1,2)
    with pytest.raises(FrozenInstanceError):n.cost=3
