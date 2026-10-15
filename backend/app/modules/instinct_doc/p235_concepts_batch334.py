"""P235 b334: bounded exact total binary deterministic finite automata.
Automaton exact tuple(transitions,start,finals): transitions exact tuple1..4
rows exact tuple2 exact state-index ints;start exact index;finals exact tuple
0..n unique exact indices,order immaterial. Validate automaton shape,table
outer,rows shape/cell types/ranges,start,finals outer/length/types/ranges/
duplicates. Word exact tuple0..8 binary ints;length exact int0..8. Functions
validate first automaton fully before second/word/length. Outputs fresh,
canonical reachable states indexed BFS symbol0then1. Products may have up to
16states (output not necessarily accepted as capped input). Minimization
returns [canonical_DFA,old_state_to_new_or_None_list]. Distinguishers list
(i,j,shortest_lex_word_or_None)for i<j including unreachable states. Empty
word=(). Equivalence witness shortest lex distinguishing word or None.
No regex parsing,unbounded scalability,global novelty/production claim.
"""
from collections import deque
from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:%s:%s'%(name,code))
        return fail
SCOPE='PARTIAL: exact bounded total binary DFA language algebra and canonical minimization'
NOT_CLAIMED=('regex parsing','unbounded scalability','global novelty','production readiness')


def _dfa(name,a,tag='a'):
    fail=make_fail(name)
    if type(a) is not tuple or len(a)!=3:fail('bad_type:automaton_'+tag)
    transitions,start,finals=a
    if type(transitions) is not tuple:fail('bad_type:transitions_'+tag)
    if not 1<=len(transitions)<=4:fail('bad_value:size_'+tag)
    n=len(transitions)
    for row in transitions:
        if type(row) is not tuple or len(row)!=2:fail('bad_type:row_'+tag)
        if any(type(v) is not int for v in row):fail('bad_type:target_'+tag)
        if any(not 0<=v<n for v in row):fail('bad_value:target_'+tag)
    if type(start) is not int:fail('bad_type:start_'+tag)
    if not 0<=start<n:fail('bad_value:start_'+tag)
    if type(finals) is not tuple:fail('bad_type:finals_'+tag)
    if len(finals)>n:fail('bad_value:finals_length_'+tag)
    if any(type(v) is not int for v in finals):fail('bad_type:final_'+tag)
    if any(not 0<=v<n for v in finals):fail('bad_value:final_'+tag)
    if len(set(finals))!=len(finals):fail('bad_value:finals_unique_'+tag)
    return fail


def _witness(a,b,sa=None,sb=None):
    ta,ia,fa=a;tb,ib,fb=b;start=(ia if sa is None else sa,ib if sb is None else sb);seen={start};queue=deque([(start,())])
    while queue:
        (i,j),word=queue.popleft()
        if (i in fa)!=(j in fb):return word
        for symbol in (0,1):
            pair=(ta[i][symbol],tb[j][symbol])
            if pair not in seen:seen.add(pair);queue.append((pair,word+(symbol,)))
    return None


def _trim(a):
    table,start,finals=a;order=[start];index={start:0}
    for state in order:
        for target in table[state]:
            if target not in index:index[target]=len(order);order.append(target)
    return (tuple(tuple(index[t] for t in table[s]) for s in order),0,tuple(index[s] for s in order if s in finals)),order


def dfa_accept_word(a,word):
    fail=_dfa('dfa_accept_word',a)
    if type(word) is not tuple:fail('bad_type:word')
    if len(word)>8:fail('bad_value:word_length')
    if any(type(v) is not int for v in word):fail('bad_type:symbol')
    if any(v not in (0,1) for v in word):fail('bad_value:symbol')
    table,state,finals=a
    for symbol in word:state=table[state][symbol]
    return state in finals


def dfa_language_count(a,length):
    fail=_dfa('dfa_language_count',a)
    if type(length) is not int:fail('bad_type:length')
    if not 0<=length<=8:fail('bad_value:length')
    table,start,finals=a;counts=[0]*len(table);counts[start]=1
    for _ in range(length):
        new=[0]*len(table)
        for i,row in enumerate(table):
            for target in row:new[target]+=counts[i]
        counts=new
    return sum(counts[i] for i in finals)


def dfa_shortest_accepted_word(a):
    _dfa('dfa_shortest_accepted_word',a)
    table,start,finals=a;queue=deque([(start,())]);seen={start}
    while queue:
        state,word=queue.popleft()
        if state in finals:return word
        for symbol,target in enumerate(table[state]):
            if target not in seen:seen.add(target);queue.append((target,word+(symbol,)))
    return None


def dfa_equivalence_witness(a,b):
    _dfa('dfa_equivalence_witness',a);_dfa('dfa_equivalence_witness',b,'b')
    return _witness(a,b)


def dfa_reachable_trim(a):
    _dfa('dfa_reachable_trim',a)
    return _trim(a)[0]


def dfa_complement(a):
    _dfa('dfa_complement',a)
    table,start,finals=a
    return (table,start,tuple(i for i in range(len(table)) if i not in finals))


def _product(a,b,union):
    ta,ia,fa=a;tb,ib,fb=b;states=[(ia,ib)];index={states[0]:0};table=[];finals=[]
    for i,j in states:
        if ((i in fa) or (j in fb)) if union else ((i in fa) and (j in fb)):finals.append(index[i,j])
        row=[]
        for s in (0,1):
            pair=(ta[i][s],tb[j][s])
            if pair not in index:index[pair]=len(states);states.append(pair)
            row.append(index[pair])
        table.append(tuple(row))
    return tuple(table),0,tuple(finals)


def dfa_intersection(a,b):
    _dfa('dfa_intersection',a);_dfa('dfa_intersection',b,'b')
    return _product(a,b,False)


def dfa_union(a,b):
    _dfa('dfa_union',a);_dfa('dfa_union',b,'b')
    return _product(a,b,True)


def dfa_state_distinguishers(a):
    _dfa('dfa_state_distinguishers',a)
    return [(i,j,_witness(a,a,i,j)) for i in range(len(a[0])) for j in range(i+1,len(a[0]))]


def dfa_minimize_exact(a):
    _dfa('dfa_minimize_exact',a);trimmed,order=_trim(a);table,start,finals=trimmed;groups=[];mapping={}
    for state in range(len(table)):
        group=next((i for i,B in enumerate(groups) if _witness(trimmed,trimmed,state,B[0]) is None),None)
        if group is None:group=len(groups);groups.append([])
        groups[group].append(state);mapping[state]=group
    quotient=(tuple(tuple(mapping[t] for t in table[B[0]]) for B in groups),mapping[start],tuple(i for i,B in enumerate(groups) if B[0] in finals))
    canonical,qorder=_trim(quotient);qindex={s:i for i,s in enumerate(qorder)};old=[None]*len(a[0])
    for newstate,original in enumerate(order):old[original]=qindex[mapping[newstate]]
    return [canonical,old]
