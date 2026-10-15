from itertools import product,permutations,combinations
from copy import deepcopy
import random,pytest,runpy,sys,types,builtins,importlib.util,importlib.machinery
from app.modules.instinct_doc import p235_concepts_batch360 as m
NAMES=('stable_marriage_deferred_acceptance','marriage_blocking_pairs','stable_marriage_lattice_meet_join','stable_marriage_forced_pairs','stable_marriage_attainable_partners','hospital_resident_matching','stable_roommates_matchings','top_trading_cycles','serial_dictatorship_allocation','pareto_improving_cycles')

def exact(a,b):
    assert type(a) is type(b)
    if type(b) in (list,tuple):
        assert len(a)==len(b)
        for x,y in zip(a,b):exact(x,y)
    else:assert a==b

def call(name,*args):
    old=deepcopy(args);out=getattr(m,name)(*args);assert args==old;return out

def blocks(left,right,matching):
    out=[]
    for i,j in product(range(len(left)),repeat=2):
        other=matching.index(j)
        if left[i].index(j)<left[i].index(matching[i]) and right[j].index(i)<right[j].index(other):out.append((i,j))
    return out

def stable(left,right):return [p for p in permutations(range(len(left))) if not blocks(left,right,p)]

def check_marriage(left,right):
    n=len(left);outcomes=stable(left,right)
    best=next(p for p in outcomes if all(all(left[i].index(p[i])<=left[i].index(q[i]) for i in range(n)) for q in outcomes))
    exact(call(NAMES[0],left,right),list(best))
    exact(call(NAMES[3],left,right),[(i,best[i]) for i in range(n) if all(p[i]==best[i] for p in outcomes)])
    exact(call(NAMES[4],left,right),[sorted({p[i] for p in outcomes}) for i in range(n)])
    for p in permutations(range(n)):exact(call(NAMES[1],left,right,list(p)),blocks(left,right,p))
    for p,q in product(outcomes,repeat=2):
        # Lattice greatest lower/least upper bound in proposer-rank order.
        lower=[r for r in outcomes if all(left[i].index(r[i])<=min(left[i].index(p[i]),left[i].index(q[i])) for i in range(n))]
        upper=[r for r in outcomes if all(left[i].index(r[i])>=max(left[i].index(p[i]),left[i].index(q[i])) for i in range(n))]
        meet=next(r for r in lower if all(all(left[i].index(r[i])>=left[i].index(t[i]) for i in range(n)) for t in lower))
        join=next(r for r in upper if all(all(left[i].index(r[i])<=left[i].index(t[i]) for i in range(n)) for t in upper))
        exact(call(NAMES[2],left,right,list(p),list(q)),[list(meet),list(join)])

def test_marriage_complete_small_and_sample_large():
    for n in range(3):
        orders=list(permutations(range(n)))
        for allrows in product(orders,repeat=2*n):check_marriage([list(p) for p in allrows[:n]],[list(p) for p in allrows[n:]])
    rng=random.Random(360)
    for n in (3,4,5):
        for _ in range(60):
            left=[rng.sample(range(n),n) for i in range(n)];right=[rng.sample(range(n),n) for i in range(n)];check_marriage(left,right)
    left=[[0,1],[1,0]];right=[[1,0],[0,1]]
    exact(call(NAMES[3],left,right),[]);exact(call(NAMES[4],left,right),[[0,1],[0,1]])
    exact(call(NAMES[2],left,right,[0,1],[1,0]),[[0,1],[1,0]])

def hospital_outcomes(residents,hospitals,caps):
    r=len(residents);h=len(hospitals);out=[]
    for allocation in product(range(-1,h),repeat=r):
        if any(allocation.count(j)>caps[j] for j in range(h)):continue
        blocked=False
        for i in range(r):
            for j in residents[i]:
                if allocation[i]!=-1 and residents[i].index(allocation[i])<=residents[i].index(j):continue
                group=[k for k,x in enumerate(allocation) if x==j]
                if len(group)<caps[j] or any(hospitals[j].index(i)<hospitals[j].index(k) for k in group):blocked=True
        if not blocked:out.append(allocation)
    return out

def test_hospital_and_roommates_different_route():
    rng=random.Random(361)
    for r,h in ((0,0),(0,4),(6,0),(1,1),(3,2),(4,3),(6,4)):
        for _ in range(8):
            residents=[rng.sample(range(h),h) for i in range(r)];hospitals=[rng.sample(range(r),r) for i in range(h)];caps=[rng.randrange(r+1) for i in range(h)];out=hospital_outcomes(residents,hospitals,caps)
            rank=lambda i,j:h if j==-1 else residents[i].index(j)
            best=next(p for p in out if all(all(rank(i,p[i])<=rank(i,q[i]) for i in range(r)) for q in out));exact(call(NAMES[5],residents,hospitals,caps),list(best))
    for n in (0,2,4,6,8):
        for _ in range(8):
            prefs=[rng.sample([j for j in range(n) if i!=j],n-1) for i in range(n)]
            outcomes=[]
            for p in permutations(range(n)):
                if any(p[i]==i or p[p[i]]!=i for i in range(n)):continue
                if not any(p[i]!=j and prefs[i].index(j)<prefs[i].index(p[i]) and prefs[j].index(i)<prefs[j].index(p[j]) for i,j in combinations(range(n),2)):outcomes.append(p)
            exact(call(NAMES[6],prefs),outcomes)

def core_allocations(prefs):
    n=len(prefs);out=[]
    for allocation in permutations(range(n)):
        blocked=False
        for size in range(1,n+1):
            for coalition in combinations(range(n),size):
                for trade in permutations(coalition):
                    gains=[prefs[i].index(allocation[i])-prefs[i].index(j) for i,j in zip(coalition,trade)]
                    if min(gains)>=0 and max(gains)>0:blocked=True;break
                if blocked:break
            if blocked:break
        if not blocked:out.append(allocation)
    return out

def improving_cycles(prefs,allocation):
    n=len(prefs);out=[]
    for size in range(2,n+1):
        for p in permutations(range(n),size):
            if p[0]!=min(p):continue
            if all(prefs[i].index(allocation[j])<prefs[i].index(allocation[i]) for i,j in zip(p,p[1:]+p[:1])):out.append(p)
    return sorted(out)

def test_housing_core_and_cycle_oracles():
    rng=random.Random(362)
    for n in range(5):
        for _ in range(15):
            prefs=[rng.sample(range(n),n) for i in range(n)];core=core_allocations(prefs);assert len(core)==1;exact(call(NAMES[7],prefs),list(core[0]))
            priority=rng.sample(range(n),n)
            # Uniqueallocationwhereeachpriorityagenthasnobetterobjectownedbylateragent.
            serial=next(p for p in permutations(range(n)) if all(all(prefs[i].index(p[i])<prefs[i].index(p[j]) for j in priority[k+1:]) for k,i in enumerate(priority)))
            exact(call(NAMES[8],prefs,priority),list(serial));allocation=rng.sample(range(n),n);exact(call(NAMES[9],prefs,allocation),improving_cycles(prefs,allocation))
    prefs=[[j for j in range(8)] for i in range(8)];exact(call(NAMES[7],prefs),list(range(8)));exact(call(NAMES[8],prefs,list(range(7,-1,-1))),list(range(7,-1,-1)));exact(call(NAMES[9],prefs,list(range(8))),[])
    # Copyisolationallcollectionreturns.
    inputs=[([[0]],[[0]]),([[0]],[[0]],[0]),([[0]],[[0]],[0],[0]),([[0]],[[0]]),([[0]],[[0]]),([[0]],[[0]],[1]),([[] ,[]],),([[0]],),([[0]],[0]),([[0]],[0])]
    inputs[6]=([[1],[0]],)
    for name,args in zip(NAMES,inputs):
        out=call(name,*args);expected=deepcopy(out);out.clear();exact(call(name,*args),expected)

class I(int):pass
class L(list):pass

def fail(name,args,code):
    before=deepcopy(args)
    with pytest.raises(ValueError) as e:getattr(m,name)(*args)
    assert str(e.value)=='P235:'+name+':'+code;assert args==before

def test_all_validation_and_boundaries():
    # Everytop-levelargument, row, numeric-slot type, range, length, permutation.
    specs={
    NAMES[0]:([[0]],[[0]]),NAMES[1]:([[0]],[[0]],[0]),NAMES[2]:([[0]],[[0]],[0],[0]),NAMES[3]:([[0]],[[0]]),NAMES[4]:([[0]],[[0]]),NAMES[5]:([[0]],[[0]],[1]),NAMES[6]:([[1],[0]],),NAMES[7]:([[0]],),NAMES[8]:([[0]],[0]),NAMES[9]:([[0]],[0])}
    labels={name:('left','right')+('matching',) if name==NAMES[1] else ('left','right','first','second') if name==NAMES[2] else ('left','right') for name in NAMES[:5]}
    labels.update({NAMES[5]:('residents','hospitals','capacities'),NAMES[6]:('preferences',),NAMES[7]:('preferences',),NAMES[8]:('preferences','priority'),NAMES[9]:('preferences','allocation')})
    for name,args in specs.items():
        for slot,label in enumerate(labels[name]):
            for bad in (None,(),L()):
                values=deepcopy(list(args));values[slot]=bad
                for k in range(slot+1,len(values)):values[k]=None
                fail(name,values,'bad_type:'+label)
            cap=5 if name in NAMES[:5] and slot<2 else 6 if name==NAMES[5] and slot==0 else 4 if name==NAMES[5] else 8
            if (name in NAMES[:5] and slot>=2) or (name in (NAMES[8],NAMES[9]) and slot==1):cap=len(args[0])
            values=deepcopy(list(args));values[slot]=[None]*(cap+1);fail(name,values,'too_long:'+label)
            matrix=(name in NAMES[:5] and slot<2) or (name==NAMES[5] and slot<2) or (name in NAMES[6:] and slot==0)
            if matrix:
                #Roommatesneed2rows;othersone.
                valid=deepcopy(list(args))
                for bad in (None,(),L()):
                    values=deepcopy(valid);values[slot][0]=bad;fail(name,values,'bad_type:'+label+'[0]')
                for bad,kind in ((None,'bad_type:'),(False,'bad_type:'),(I(0),'bad_type:'),(0.0,'bad_type:'),(-1,'bad_value:'),(9,'bad_value:')):
                    values=deepcopy(valid);values[slot][0][0]=bad;fail(name,values,kind+label+'[0][0]')
                values=deepcopy(valid);values[slot][0]=[];fail(name,values,'bad_length:'+label+'[0]')
            else:
                for bad,kind in ((None,'bad_type:'),(False,'bad_type:'),(I(0),'bad_type:'),(0.0,'bad_type:'),(-1,'bad_value:'),(9,'bad_value:')):
                    values=deepcopy(list(args));values[slot][0]=bad;fail(name,values,kind+label+'[0]')
    for name in NAMES[:5]:
        args=[[[0,1],[0,1]],[[0,1],[0,1]]]+([[0,1]] if name==NAMES[1] else [[0,1],[0,1]] if name==NAMES[2] else [])
        for slot,label in ((0,'left'),(1,'right')):
            values=deepcopy(args);values[slot][0]=[0,0];fail(name,values,'not_permutation:'+label+'[0]')
        fail(name,[[[0]],[]]+args[2:],'unequal_sides')
    fail(NAMES[2],[[[0,1],[0,1]],[[0,1],[0,1]],[1,0],[0,1]],'unstable:first')
    fail(NAMES[2],[[[0,1],[0,1]],[[0,1],[0,1]],[0,1],[1,0]],'unstable:second')
    fail(NAMES[6],[[[]]],'odd_population')
    fail(NAMES[5],[[[0]],[[0]],[]],'bad_length:capacities')
    for name in (NAMES[8],NAMES[9]):fail(name,[[[0,1],[0,1]],[0,0]],'not_permutation:'+('priority' if name==NAMES[8] else 'allocation'))
    assert m.SCOPE=='PARTIAL strict finite matching markets and housing allocation certificates'
    assert m.NOT_CLAIMED==('large-market scalability','strategic guarantees','ties or incomplete preferences','global novelty','production readiness')

def test_find_spec_registry_routes(monkeypatch):
    key='app.modules.instinct_doc.p235_concepts_registry';original=builtins.__import__;fake=types.ModuleType(key);sentinel=object();fake.make_fail=lambda name:sentinel
    with monkeypatch.context() as p:
        p.setitem(sys.modules,key,fake);assert runpy.run_path(m.__file__)['make_fail']('x') is sentinel
    def broken_with(missing):
        def broken(name,*a,**k):
            if name==key:raise ModuleNotFoundError('missing',name=missing)
            return original(name,*a,**k)
        return broken
    for missing,spec,raises in ((key,None,False),(key,importlib.machinery.ModuleSpec(key,loader=None),True),('other_dependency',None,True)):
        with monkeypatch.context() as p:
            p.setattr(builtins,'__import__',broken_with(missing));p.setattr(importlib.util,'find_spec',lambda name:spec)
            if raises:
                with pytest.raises(ModuleNotFoundError) as e:runpy.run_path(m.__file__)
                assert e.value.name==missing
            else:
                ns=runpy.run_path(m.__file__)
                with pytest.raises(ValueError,match='P235:x:y'):ns['make_fail']('x')('y')
    for error in (ImportError,ValueError):
        with monkeypatch.context() as p:
            p.setattr(builtins,'__import__',broken_with(key))
            def bad(name):raise error('missing')
            p.setattr(importlib.util,'find_spec',bad);assert runpy.run_path(m.__file__)['stable_marriage_deferred_acceptance']([],[])==[]

def test_row_caps_duplicates_numeric_caps_firstbad():
    for name in NAMES[:5]:
        left=[[0,1],[0,1]];right=[[0,1],[0,1]]
        args=[left,right]+([[0,1]] if name==NAMES[1] else [[0,1],[0,1]] if name==NAMES[2] else [])
        for slot,label in ((0,'left'),(1,'right')):
            values=deepcopy(args);values[slot][0]=[None]*3;fail(name,values,'too_long:'+label+'[0]')
        for slot,label in ((2,'matching'),) if name==NAMES[1] else ((2,'first'),(3,'second')) if name==NAMES[2] else ():
            values=deepcopy(args);values[slot]=[0,0];fail(name,values,'not_permutation:'+label)
            values=deepcopy(args);values[slot]=[];fail(name,values,'bad_length:'+label)
    for name in NAMES[7:]:fail(name,[[[None,None]]]+([[0]] if name in NAMES[8:] else []),'too_long:preferences[0]')
    fail(NAMES[6],[[[1,1],[0]]],'too_long:preferences[0]')
    fail(NAMES[6],[[[0],[0]]],'bad_value:preferences[0][0]')
    fail(NAMES[5],[[[None,None]],[[0]],[1]],'too_long:residents[0]')
    fail(NAMES[5],[[[0]],[[None,None]],[1]],'too_long:hospitals[0]')
    fail(NAMES[5],[[[0]],[[0]],[2]],'bad_value:capacities[0]')
    r=[list(range(4)) for i in range(6)];h=[list(range(6)) for i in range(4)]
    exact(call(NAMES[5],r,h,[6]*4),[0]*6)
    exact(call(NAMES[5],r,h,[0]*4),[-1]*6)
    for name,label in ((NAMES[8],'priority'),(NAMES[9],'allocation')):fail(name,[[[0]],[]],'bad_length:'+label)

class TestMatchingFirstBadOrder:
    # Docstring: "argument order then row order validation" - element type/range
    # precedes permutation check; length precedes element checks; argument-level
    # refusals (odd population, unstable inputs) precede later-argument checks.
    def test_elements_before_permutation(self):
        fail(NAMES[0],[[[None,None],[0,1]],[[0,1],[0,1]]],'bad_type:left[0][0]')
        fail(NAMES[7],[[[None,None],[0,1]]],'bad_type:preferences[0][0]')
        fail(NAMES[8],[[[0,1],[1,0]],[None,None]],'bad_type:priority[0]')
    def test_length_before_elements(self):
        fail(NAMES[0],[[[None],[0,1]],[[0,1],[0,1]]],'bad_length:left[0]')
        fail(NAMES[1],[[[0,1],[1,0]],[[0,1],[1,0]],[None]],'bad_length:matching')
    def test_odd_population_before_rows(self):
        fail(NAMES[6],[[[None]]],'odd_population')
        fail(NAMES[6],[[[],[],[]]],'odd_population')
    def test_unstable_first_before_second(self):
        fail(NAMES[2],[[[0,1],[0,1]],[[0,1],[0,1]],[1,0],[1,0]],'unstable:first')
    def test_hospital_rows_before_capacities(self):
        fail(NAMES[5],[[[None]],[[0]],None],'bad_type:residents[0][0]')
        fail(NAMES[5],[[[0]],[[None]],[0,0,0,0,0]],'bad_type:hospitals[0][0]')
