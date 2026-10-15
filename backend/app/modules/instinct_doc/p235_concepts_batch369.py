"""P235 b369 elementary cellular automata, binary periodic rings1..8.
Rule exactint0..255, outputbit=(rule>>(4*left+2*center+right))&1.
Exact listbits0/1, ringlength1..8, no bool/subclasses. Time exactint0..4.
Preimages sortedlex; count trace of 4-state localtransferproduct. Attractors
are cycles of tuplebitstates rotatedlexminimum, allcyclessortedlex.
Symmetry orbit sortedrules underleft/rightreflection and statecomplement.
GardenofEden states lexsortedbitswithoutanypreimage. Transientprofile indexed
lexbinaryinputstates givesstepsuntilearliestcycleentry, cyclememberszero.
Reversible rules permute allstates of specifiedringlength. Damage matrix
rowinputflips, coloutputchanges, 0/1. Cone embeds given patterninzeroinfinite
background, returns time+1 rows; at t row spans original interval expanded
by t eachside; backgroundevolves underhomogeneousrule,notclampedzero.
No IO/mutation, no continuous-space/physical/scalability claim.
"""
import importlib.util
from itertools import product

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
SCOPE='PARTIAL bounded elementary cellular automata and exact finite-ring dynamics certificates'
NOT_CLAIMED=('continuous physics','large-ring scalability','unbounded dynamics classification','global novelty','production readiness')

def _int(name,v,label,lo,hi):
    if type(v) is not int:make_fail(name)('bad_type:'+label)
    if not lo<=v<=hi:make_fail(name)('bad_value:'+label)

def _rule(name,rule):_int(name,rule,'rule',0,255)

def _bits(name,bits,label='bits'):
    if type(bits) is not list:make_fail(name)('bad_type:'+label)
    if not 1<=len(bits)<=8:make_fail(name)('bad_length:'+label)
    for i,x in enumerate(bits):_int(name,x,label+'[%s]'%i,0,1)

def _f(rule,a,b,c):return rule>>(4*a+2*b+c)&1

def _step(rule,bits):return tuple(_f(rule,bits[i-1],b,bits[(i+1)%len(bits)]) for i,b in enumerate(bits))

def eca_ring_step(rule,bits):
    name='eca_ring_step';_rule(name,rule);_bits(name,bits)
    return list(_step(rule,bits))

def eca_ring_preimages(rule,target):
    name='eca_ring_preimages';_rule(name,rule);_bits(name,target,'target');n=len(target);out=set()
    for a,b in product((0,1),repeat=2):
        def walk(pair,position,word):
            if position==n:
                if pair==(a,b):out.add(tuple(word))
                return
            x,y=pair
            for z in (0,1):
                if _f(rule,x,y,z)==target[position]:walk((y,z),position+1,word+[y])
        walk((a,b),0,[])
    return [list(w) for w in sorted(out)]

def eca_ring_preimage_count(rule,target):
    name='eca_ring_preimage_count';_rule(name,rule);_bits(name,target,'target');matrix=[[int(i==j) for j in range(4)] for i in range(4)]
    for bit in target:
        transfer=[[int((u&1)==(v>>1) and _f(rule,u>>1,u&1,v&1)==bit) for v in range(4)] for u in range(4)]
        matrix=[[sum(matrix[i][k]*transfer[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
    return sum(matrix[i][i] for i in range(4))

def eca_ring_attractor_cycles(rule,length):
    name='eca_ring_attractor_cycles';_rule(name,rule);_int(name,length,'length',1,8);done=set();cycles=[]
    for start in product((0,1),repeat=length):
        path=[];positions={};state=start
        while state not in done and state not in positions:positions[state]=len(path);path.append(state);state=_step(rule,state)
        if state in positions:
            cycle=path[positions[state]:];k=cycle.index(min(cycle));cycles.append(cycle[k:]+cycle[:k])
        done.update(path)
    return sorted(cycles)

def eca_rule_symmetry_orbit(rule):
    _rule('eca_rule_symmetry_orbit',rule);out=set()
    for reflect,complement in product((0,1),repeat=2):
        value=0
        for a,b,c in product((0,1),repeat=3):
            x,y,z=(c,b,a) if reflect else (a,b,c)
            bit=_f(rule,x^complement,y^complement,z^complement)^complement;value|=bit<<(4*a+2*b+c)
        out.add(value)
    return sorted(out)

def eca_ring_garden_of_eden_states(rule,length):
    name='eca_ring_garden_of_eden_states';_rule(name,rule);_int(name,length,'length',1,8);states=list(product((0,1),repeat=length));image={_step(rule,s) for s in states}
    return [list(s) for s in states if s not in image]

def eca_ring_transient_length_profile(rule,length):
    name='eca_ring_transient_length_profile';_rule(name,rule);_int(name,length,'length',1,8);states=list(product((0,1),repeat=length));index={s:i for i,s in enumerate(states)};successor=[index[_step(rule,s)] for s in states];indegree=[0]*len(states)
    for j in successor:indegree[j]+=1
    queue=[i for i,d in enumerate(indegree) if not d];removed=[]
    for i in queue:
        removed.append(i);j=successor[i];indegree[j]-=1
        if not indegree[j]:queue.append(j)
    lengths=[0]*len(states)
    for i in reversed(removed):lengths[i]=lengths[successor[i]]+1
    return lengths

def eca_ring_reversible_rules(length):
    _int('eca_ring_reversible_rules',length,'length',1,8);states=list(product((0,1),repeat=length));out=[]
    for rule in range(256):
        seen=set()
        for state in states:
            nxt=_step(rule,state)
            if nxt in seen:break
            seen.add(nxt)
        else:out.append(rule)
    return out

def eca_ring_damage_profile(rule,bits):
    name='eca_ring_damage_profile';_rule(name,rule);_bits(name,bits);original=_step(rule,bits);out=[]
    for i in range(len(bits)):
        changed=bits[:];changed[i]^=1;nxt=_step(rule,changed);out.append([a^b for a,b in zip(original,nxt)])
    return out

def eca_space_time_cone(rule,bits,time):
    name='eca_space_time_cone';_rule(name,rule);_bits(name,bits);_int(name,time,'time',0,4);row=bits[:];out=[row];background=0
    for _ in range(time):
        padded=[background]*2+row+[background]*2
        row=[_f(rule,padded[i],padded[i+1],padded[i+2]) for i in range(len(padded)-2)];background=_f(rule,background,background,background);out.append(row)
    return out
