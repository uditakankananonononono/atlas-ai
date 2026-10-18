"""Independent bounded oracles; local missing-registry stub, not dispatch proof."""
import importlib,math,random,sys,types,unittest
try:importlib.import_module('app.modules.instinct_doc.p235_concepts_registry')
except ModuleNotFoundError as exc:
    if exc.name!='app.modules.instinct_doc.p235_concepts_registry':raise
    stub=types.ModuleType(exc.name)
    def make_fail(name):
        def fail(code):raise ValueError('P235:'+name+':'+code)
        return fail
    stub.make_fail=make_fail;sys.modules[stub.__name__]=stub
from app.modules.instinct_doc import p235_concepts_batch487_cfg as m


def compare(fun,args,want):
    got=fun(*[x[:] if type(x) is list else x for x in args])
    assert type(got) is type(want) and got==want,(fun.__name__,args,got,want)


def refuse(fun,args,code):
    try:fun(*[x[:] if type(x) is list else x for x in args])
    except ValueError as e:assert str(e)=='P235:'+fun.__name__+':'+code,(str(e),code)
    else:raise AssertionError(('missing refusal',fun.__name__,args,code))


from functools import lru_cache
FUNS=[m.cfg_inside_chart,m.cfg_outside_chart,m.cfg_root_splits,m.cfg_terminal_usage,m.cfg_binary_usage,m.cfg_symbol_usage,m.cfg_active_spans]
def oracle(n,s,T,B,w):
    L=len(w)
    @lru_cache(None)
    def count(a,i,j):
        if j-i==1:return int([a,w[i]]in T)
        return sum(count(b,i,k)*count(c,k,j)for aa,b,c in B if aa==a for k in range(i+1,j))
    def derivative(mark):
        @lru_cache(None)
        def rec(a,i,j):
            v=count(a,i,j);dv=0
            if j-i==1:
                if [a,w[i]]in T and mark==('t',T.index([a,w[i]])):dv=1
            else:
                for r,(aa,b,c)in enumerate(B):
                    if aa!=a:continue
                    for k in range(i+1,j):
                        x,dx=rec(b,i,k);y,dy=rec(c,k,j)
                        dv+=dx*y+x*dy+int(mark==('b',r))*x*y
            if mark==('s',a):dv+=v
            if mark==('c',a,i,j):dv+=1
            return v,dv
        return rec(s,0,L)[1]if L else 0
    cells=[(a,i,j)for a in range(n)for i in range(L)for j in range(i+1,L+1)]
    d={c:count(*c)for c in cells};o={c:derivative(('c',)+c)for c in cells}
    v=count(s,0,L)if L else 0
    return [[[*c,d[c]]for c in cells if d[c]],[[*c,o[c]]for c in cells if o[c]],
      [sum(count(b,0,k)*count(c,k,L)for a,b,c in B if a==s)for k in range(1,L)],
      [derivative(('t',r))for r in range(len(T))],[derivative(('b',r))for r in range(len(B))],
      [derivative(('s',a))for a in range(n)],[[*c]for c in cells if d[c]and o[c]]]
def check(n,s,T,B,w):
    out=oracle(n,s,T,B,w)
    for f,v in zip(FUNS,out):compare(f,[n,s,T,B,w],v)
def run():
    check(1,0,[[0,0]],[[0,0,0]],[])
    for L in range(1,6):check(1,0,[[0,0]],[[0,0,0]],[0]*L)
    check(3,0,[[1,0],[2,1]],[[0,1,2]],[0,1])
    check(3,0,[[1,0],[2,1]],[[0,1,2]],[1,0])
    check(3,0,[[1,0],[2,0]],[[0,1,2],[0,2,1]],[0,0])
    compare(m.cfg_binary_usage,[1,0,[[0,7]],[[0,0,0]],[7]*10],[43758])
    compare(m.cfg_terminal_usage,[1,0,[[0,7]],[[0,0,0]],[7]*10],[48620])
    compare(m.cfg_symbol_usage,[1,0,[[0,7]],[[0,0,0]],[7]*10],[92378])
    compare(m.cfg_root_splits,[1,0,[[0,7]],[[0,0,0]],[7]*10],[1430,429,264,210,196,210,264,429,1430])
    T=[[a,t]for a in range(3)for t in range(8)]
    B=[[a,b,c]for a in range(4)for b in range(4)for c in range(4)]
    compare(m.cfg_symbol_usage,[6,5,T,B,[7]],[0]*6)
    compare(m.cfg_active_spans,[6,2,T,B,[7]],[[2,0,1]])
    rng=random.Random(487)
    for _ in range(55):
        n=rng.randrange(1,4);s=rng.randrange(n)
        T=[[a,t]for a in range(n)for t in range(2)if rng.randrange(2)]
        B=[[a,b,c]for a in range(n)for b in range(n)for c in range(n)if rng.randrange(4)==0]
        w=[rng.randrange(2)for _ in range(rng.randrange(5))]
        check(n,s,T,B,w)
    cases=[([True,None,None,None,None],'bad_type:n'),([1.0,0,[],[],[]],'bad_type:n'),([0,0,[],[],[]],'bad_value:n'),([7,0,[],[],[]],'too_many:n'),
      ([1,True,[],[],[]],'bad_type:start'),([1,0.0,[],[],[]],'bad_type:start'),([1,-1,[],[],[]],'bad_value:start'),([1,1,[],[],[]],'bad_value:start'),
      ([1,0,None,None,None],'bad_type:terminals'),([1,0,[[0,0]]*25,None,None],'too_many:terminals'),([1,0,[None],[],[]],'bad_type:rule'),([1,0,[[0]],[],[]],'bad_value:rule_size'),
      ([1,0,[[True,0]],[],[]],'bad_type:symbol'),([1,0,[[0,0.5]],[],[]],'bad_type:symbol'),([1,0,[[1,0]],[],[]],'bad_value:symbol'),([1,0,[[0,8]],[],[]],'bad_value:symbol'),([1,0,[[0,-1]],[],[]],'bad_value:symbol'),
      ([1,0,[[0,0],[0,0]],[],[]],'bad_value:duplicate_rule'),([1,0,[],None,[]],'bad_type:binaries'),([1,0,[],[[0,0,0]]*65,[]],'too_many:binaries'),
      ([1,0,[],[None],[]],'bad_type:rule'),([1,0,[],[[0,0]],[]],'bad_value:rule_size'),([1,0,[],[[0,1,0]],[]],'bad_value:symbol'),([1,0,[],[[0,0,True]],[]],'bad_type:symbol'),
      ([1,0,[],[[0,0,0],[0,0,0]],[]],'bad_value:duplicate_rule'),([1,0,[],[],None],'bad_type:word'),([1,0,[],[],[0]*11],'too_many:word'),
      ([1,0,[],[],[True]],'bad_type:token'),([1,0,[],[],[0.0]],'bad_type:token'),([1,0,[],[],[-1]],'bad_value:token'),([1,0,[],[],[8]],'bad_value:token')]
    for f in FUNS:
        for args,code in cases:refuse(f,args,code)

class T(unittest.TestCase):
    def test_independent_oracles_and_refusals(self):run()
if __name__=='__main__':unittest.main()
