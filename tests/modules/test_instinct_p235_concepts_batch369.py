from itertools import product
from copy import deepcopy
import pytest,runpy,sys,types,builtins,importlib.util,importlib.machinery
from app.modules.instinct_doc import p235_concepts_batch369 as m
NAMES=('eca_ring_step','eca_ring_preimages','eca_ring_preimage_count','eca_ring_attractor_cycles','eca_rule_symmetry_orbit','eca_ring_garden_of_eden_states','eca_ring_transient_length_profile','eca_ring_reversible_rules','eca_ring_damage_profile','eca_space_time_cone')

def exact(a,b):
    assert type(a) is type(b)
    if type(b) in (list,tuple):
        assert len(a)==len(b)
        for x,y in zip(a,b):exact(x,y)
    else:assert a==b

def call(name,*args):
    old=deepcopy(args);out=getattr(m,name)(*args);assert args==old;return out

def truth(rule):return [int(x) for x in format(rule,'08b')[::-1]]

def step(rule,s):
    table=truth(rule);n=len(s)
    return tuple(table[int(str(s[(i-1)%n])+str(s[i])+str(s[(i+1)%n]),2)] for i in range(n))

def dynamics(rule,n):
    states=list(product((0,1),repeat=n));cycles=set();profile=[]
    for s in states:
        path=[]
        while s not in path:path.append(s);s=step(rule,s)
        entry=path.index(s);profile.append(entry);cycle=path[entry:];rotations=[tuple(cycle[k:]+cycle[:k]) for k in range(len(cycle))];cycles.add(min(rotations))
    return [list(c) for c in sorted(cycles)],profile

def check(rule,n):
    states=list(product((0,1),repeat=n));images={s:step(rule,s) for s in states};preimages={}
    for s,t in images.items():preimages.setdefault(t,[]).append(list(s))
    for t in states:
        exact(call(NAMES[0],rule,list(t)),list(images[t]));exact(call(NAMES[1],rule,list(t)),preimages.get(t,[]));exact(call(NAMES[2],rule,list(t)),len(preimages.get(t,[])))
        damage=[]
        for i in range(n):
            changed=list(t);changed[i]=1-changed[i];nxt=step(rule,changed);damage.append([int(a!=b) for a,b in zip(images[t],nxt)])
        exact(call(NAMES[8],rule,list(t)),damage)
    cycles,profile=dynamics(rule,n);exact(call(NAMES[3],rule,n),cycles);exact(call(NAMES[6],rule,n),profile);exact(call(NAMES[5],rule,n),[list(s) for s in states if s not in preimages])

def test_all_rules_smallrings_and_large_boundary():
    for rule in range(256):
        for n in (1,2,3):check(rule,n)
    for rule in (0,1,18,30,54,90,110,150,170,204,255):
        for n in (4,5,6,7,8):check(rule,n)
    for n in range(1,9):
        states=list(product((0,1),repeat=n));expected=[]
        for rule in range(256):
            counts={s:0 for s in states}
            for s in states:counts[step(rule,s)]+=1
            if all(c==1 for c in counts.values()):expected.append(rule)
        exact(call(NAMES[7],n),expected)
    assert m.eca_ring_step(90,[0,1,0])==[1,0,1]
    assert m.eca_ring_preimage_count(0,[0])==2
    assert m.eca_ring_garden_of_eden_states(0,1)==[[1]]
    assert m.eca_ring_transient_length_profile(0,1)==[0,1]

def symmetry(rule):
    # Orbitclosureunderseparatepermutationoperations,notfourcaseformula.
    def reflected(r):
        table=truth(r);out=[table[int(format(i,'03b')[::-1],2)] for i in range(8)]
        return sum(x*2**i for i,x in enumerate(out))
    def complemented(r):return sum((1-truth(r)[7-i])*2**i for i in range(8))
    seen={rule};todo=[rule]
    for r in todo:
        for s in (reflected(r),complemented(r)):
            if s not in seen:seen.add(s);todo.append(s)
    return sorted(seen)

def cone(rule,bits,time):
    # Infinitebackgroundrepresentedbylargefixedwindowwithmargin>lightcone.
    margin=2*time+2;width=len(bits)+2*margin;row=[0]*margin+bits+[0]*margin;out=[bits[:]]
    for t in range(1,time+1):
        table=truth(rule);nxt=[table[0]]*width
        for i in range(1,width-1):nxt[i]=table[row[i-1]*4+row[i]*2+row[i+1]]
        row=nxt;out.append(row[margin-t:margin+len(bits)+t])
    return out

def test_symmetry_and_lightcones():
    for rule in range(256):
        exact(call(NAMES[4],rule),symmetry(rule))
        for bits in ([0],[1],[0,1,0],[1]*8):
            for t in range(5):exact(call(NAMES[9],rule,bits,t),cone(rule,bits,t))
    for name,args in ((NAMES[0],(90,[0,1])),(NAMES[1],(90,[0,1])),(NAMES[3],(90,2)),(NAMES[4],(90,)),(NAMES[5],(90,2)),(NAMES[6],(90,2)),(NAMES[7],(2,)),(NAMES[8],(90,[0,1])),(NAMES[9],(90,[0,1],2))):
        out=call(name,*args);expected=deepcopy(out);out.clear();exact(call(name,*args),expected)
class I(int):pass
class L(list):pass

def fail(name,args,code):
    old=deepcopy(args)
    with pytest.raises(ValueError) as e:getattr(m,name)(*args)
    assert str(e.value)=='P235:'+name+':'+code;assert args==old

def test_validation_caps_firstbad_scope():
    for name in NAMES:
        args=[1] if name==NAMES[7] else [0] if name==NAMES[4] else [0,1] if name in (NAMES[3],NAMES[5],NAMES[6]) else [0,[0],0] if name==NAMES[9] else [0,[0]]
        label='length' if name==NAMES[7] else 'rule';lo=1 if name==NAMES[7] else 0;hi=8 if name==NAMES[7] else 255
        for v,kind in ((None,'bad_type:'),(True,'bad_type:'),(I(lo),'bad_type:'),(float(lo),'bad_type:'),(lo-1,'bad_value:'),(hi+1,'bad_value:')):fail(name,[v]+[None]*(len(args)-1),kind+label)
        values=deepcopy(args);values[0]=hi;call(name,*values)
        if name in (NAMES[3],NAMES[5],NAMES[6]):
            for v,kind in ((None,'bad_type:'),(True,'bad_type:'),(I(1),'bad_type:'),(1.0,'bad_type:'),(0,'bad_value:'),(9,'bad_value:')):fail(name,[0,v],kind+'length')
        elif name not in (NAMES[4],NAMES[7]):
            label='target' if name in (NAMES[1],NAMES[2]) else 'bits'
            for v in (None,(),L()):fail(name,[0,v]+([None] if name==NAMES[9] else []),'bad_type:'+label)
            for v in ([],[None]*9):fail(name,[0,v]+([None] if name==NAMES[9] else []),'bad_length:'+label)
            for v,kind in ((None,'bad_type:'),(False,'bad_type:'),(I(0),'bad_type:'),(0.0,'bad_type:'),(-1,'bad_value:'),(2,'bad_value:')):fail(name,[0,[v]]+([None] if name==NAMES[9] else []),kind+label+'[0]')
        if name==NAMES[9]:
            for v,kind in ((None,'bad_type:'),(True,'bad_type:'),(I(0),'bad_type:'),(0.0,'bad_type:'),(-1,'bad_value:'),(5,'bad_value:')):fail(name,[0,[0],v],kind+'time')
    assert m.SCOPE=='PARTIAL bounded elementary cellular automata and exact finite-ring dynamics certificates'
    assert m.NOT_CLAIMED==('continuous physics','large-ring scalability','unbounded dynamics classification','global novelty','production readiness')

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
            p.setattr(importlib.util,'find_spec',bad);assert runpy.run_path(m.__file__)['eca_ring_step'](0,[0])==[0]
