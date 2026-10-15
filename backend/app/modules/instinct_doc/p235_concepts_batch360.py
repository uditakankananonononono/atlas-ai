"""P235 b360 strict finite matching markets, no prices or tie-breaking lotteries.
Indices0..n-1. Exact lists/ints only; argument order then row order validation.
Marriage n<=5, equal square permutation preference matrices. DA proposes left;
blocking pairs sorted(left,right); outcomes list right-index per left.
Lattice meet/join choose proposer-better/worse partners from two stable inputs.
Forced pairs are common to all stable outcomes. Attainable partners are sorted
per-proposer lists across all stable outcomes. Ranks are zero-based.
Hospitals: <=6 residents, <=4 hospitals, complete rectangular strict orders,
capacities0..resident-count; outcomes hospital index or -1 per resident.
Roommates: even n<=8; each row orders all others, outcomes sorted tuples of
partner indices for every stable perfect matching (empty market=[()]).
Housing n<=8, identity initial endowments; TTC assigns traded object per agent.
Serial dictatorship priority a permutation. Pareto cycles accept a permutation
allocation; output lex-sorted tuples of agents, starting smallest index,
length>=2, every agent strictly prefers next agent's object to its own.
No mutation, external data, prices, strategic or large-market guarantees.
"""
import importlib.util

def _absent(name):
    try:return importlib.util.find_spec(name) is None
    except (ImportError,ValueError):return True
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or not _absent(exc.name):raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:%s:%s' % (name,code))
        return fail
SCOPE='PARTIAL strict finite matching markets and housing allocation certificates'
NOT_CLAIMED=('large-market scalability','strategic guarantees','ties or incomplete preferences','global novelty','production readiness')

def _list(name,v,label,cap):
    if type(v) is not list:make_fail(name)('bad_type:'+label)
    if len(v)>cap:make_fail(name)('too_long:'+label)

def _int(name,v,label,lo,hi):
    if type(v) is not int:make_fail(name)('bad_type:'+label)
    if not lo<=v<=hi:make_fail(name)('bad_value:'+label)

def _order(name,row,label,universe):
    _list(name,row,label,len(universe))
    if len(row)!=len(universe):make_fail(name)('bad_length:'+label)
    for i,x in enumerate(row):
        if type(x) is not int:make_fail(name)('bad_type:'+label+'[%s]'%i)
        if x not in universe:make_fail(name)('bad_value:'+label+'[%s]'%i)
    if len(set(row))!=len(row):make_fail(name)('not_permutation:'+label)

def _prefs(name,prefs,label,cap=8,universe=None):
    _list(name,prefs,label,cap);n=len(prefs)
    allowed=range(n) if universe is None else universe
    for i,row in enumerate(prefs):_order(name,row,label+'[%s]'%i,allowed)
    return n

def _marriage(name,left,right):
    n=_prefs(name,left,'left',5);m=_prefs(name,right,'right',5)
    if m!=n:make_fail(name)('unequal_sides')
    return n

def _ranks(prefs):return [{x:i for i,x in enumerate(row)} for row in prefs]

def _blocks(left,right,matching):
    reverse={v:i for i,v in enumerate(matching)};lr=_ranks(left);rr=_ranks(right)
    return [(i,j) for i in range(len(left)) for j in range(len(right)) if lr[i][j]<lr[i][matching[i]] and rr[j][i]<rr[j][reverse[j]]]

def stable_marriage_deferred_acceptance(left,right):
    name='stable_marriage_deferred_acceptance';n=_marriage(name,left,right);ranks=_ranks(right);next_choice=[0]*n;partners=[-1]*n;free=list(range(n))
    while free:
        i=free.pop(0);j=left[i][next_choice[i]];next_choice[i]+=1;old=partners[j]
        if old==-1 or ranks[j][i]<ranks[j][old]:
            partners[j]=i
            if old!=-1:free.append(old)
        else:free.append(i)
    result=[-1]*n
    for j,i in enumerate(partners):result[i]=j
    return result

def marriage_blocking_pairs(left,right,matching):
    name='marriage_blocking_pairs';n=_marriage(name,left,right);_order(name,matching,'matching',range(n))
    return _blocks(left,right,matching)

def stable_marriage_lattice_meet_join(left,right,first,second):
    name='stable_marriage_lattice_meet_join';n=_marriage(name,left,right)
    _order(name,first,'first',range(n));_order(name,second,'second',range(n))
    if _blocks(left,right,first):make_fail(name)('unstable:first')
    if _blocks(left,right,second):make_fail(name)('unstable:second')
    ranks=_ranks(left)
    return [[min((first[i],second[i]),key=lambda j:ranks[i][j]) for i in range(n)],
            [max((first[i],second[i]),key=lambda j:ranks[i][j]) for i in range(n)]]

def stable_marriage_forced_pairs(left,right):
    _marriage('stable_marriage_forced_pairs',left,right)
    first=stable_marriage_deferred_acceptance(left,right)
    reverse=stable_marriage_deferred_acceptance(right,left);last=[0]*len(left)
    for j,i in enumerate(reverse):last[i]=j
    return [(i,j) for i,j in enumerate(first) if last[i]==j]

def stable_marriage_attainable_partners(left,right):
    name='stable_marriage_attainable_partners';n=_marriage(name,left,right);lr=_ranks(left);rr=_ranks(right);partners=[set() for _ in range(n)]
    # Build one edge at a time, reject blocking pairs whose two partners fixed.
    def visit(prefix,available):
        if not available:
            for i,j in enumerate(prefix):partners[i].add(j)
            return
        i=len(prefix)
        for j in available:
            if any((lr[k][j]<lr[k][v] and rr[j][k]<rr[j][i]) or (lr[i][v]<lr[i][j] and rr[v][i]<rr[v][k]) for k,v in enumerate(prefix)):continue
            visit(prefix+[j],available-{j})
    visit([],set(range(n)))
    return [sorted(values) for values in partners]

def hospital_resident_matching(residents,hospitals,capacities):
    name='hospital_resident_matching';_list(name,residents,'residents',6);_list(name,hospitals,'hospitals',4);r=len(residents);h=len(hospitals)
    for i,row in enumerate(residents):_order(name,row,'residents[%s]'%i,range(h))
    for i,row in enumerate(hospitals):_order(name,row,'hospitals[%s]'%i,range(r))
    _list(name,capacities,'capacities',4)
    if len(capacities)!=h:make_fail(name)('bad_length:capacities')
    for i,c in enumerate(capacities):_int(name,c,'capacities[%s]'%i,0,r)
    ranks=_ranks(hospitals);held=[[] for _ in range(h)];next_choice=[0]*r;free=list(range(r))
    while free:
        i=free.pop(0)
        if next_choice[i]==h:continue
        j=residents[i][next_choice[i]];next_choice[i]+=1;held[j].append(i);held[j].sort(key=lambda x:ranks[j][x])
        if len(held[j])>capacities[j]:free.append(held[j].pop())
    result=[-1]*r
    for j,group in enumerate(held):
        for i in group:result[i]=j
    return result

def stable_roommates_matchings(preferences):
    name='stable_roommates_matchings';_list(name,preferences,'preferences',8);n=len(preferences)
    if n%2:make_fail(name)('odd_population')
    for i,row in enumerate(preferences):_order(name,row,'preferences[%s]'%i,[j for j in range(n) if j!=i])
    rank=_ranks(preferences);out=[];partners=[-1]*n
    def visit(remaining):
        if not remaining:
            if not any(rank[i][j]<rank[i][partners[i]] and rank[j][i]<rank[j][partners[j]] for i in range(n) for j in range(i+1,n) if partners[i]!=j):out.append(tuple(partners))
            return
        i=remaining[0]
        for j in remaining[1:]:
            partners[i]=j;partners[j]=i;visit([x for x in remaining if x not in (i,j)]);partners[i]=partners[j]=-1
    visit(list(range(n)))
    return sorted(out)

def top_trading_cycles(preferences):
    name='top_trading_cycles';n=_prefs(name,preferences,'preferences');remaining=set(range(n));result=[-1]*n
    while remaining:
        pointers={i:next(j for j in preferences[i] if j in remaining) for i in remaining};path=[];i=min(remaining)
        while i not in path:path.append(i);i=pointers[i]
        cycle=path[path.index(i):]
        for j in cycle:result[j]=pointers[j]
        remaining.difference_update(cycle)
    return result

def serial_dictatorship_allocation(preferences,priority):
    name='serial_dictatorship_allocation';n=_prefs(name,preferences,'preferences');_order(name,priority,'priority',range(n));available=set(range(n));result=[-1]*n
    for i in priority:
        choice=next(j for j in preferences[i] if j in available);result[i]=choice;available.remove(choice)
    return result

def pareto_improving_cycles(preferences,allocation):
    name='pareto_improving_cycles';n=_prefs(name,preferences,'preferences');_order(name,allocation,'allocation',range(n));ranks=_ranks(preferences)
    edges=[[j for j in range(n) if ranks[i][allocation[j]]<ranks[i][allocation[i]]] for i in range(n)];out=[]
    def visit(path):
        for j in edges[path[-1]]:
            if j==path[0] and len(path)>=2:out.append(tuple(path))
            elif j>path[0] and j not in path:visit(path+[j])
    for i in range(n):visit([i])
    return sorted(out)
