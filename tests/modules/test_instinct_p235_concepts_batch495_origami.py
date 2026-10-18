"""Independent bounded oracles; local missing-registry stub, not dispatch proof."""
import importlib,sys,types,unittest
try:importlib.import_module('app.modules.instinct_doc.p235_concepts_registry')
except ModuleNotFoundError as exc:
    if exc.name!='app.modules.instinct_doc.p235_concepts_registry':raise
    stub=types.ModuleType(exc.name)
    def make_fail(name):
        def fail(code):raise ValueError('P235:'+name+':'+code)
        return fail
    stub.make_fail=make_fail;sys.modules[stub.__name__]=stub
from app.modules.instinct_doc import p235_concepts_batch495_origami as m


def compare(fun,args,want):
    got=fun(*[x[:] if type(x) is list else x for x in args])
    assert type(got) is type(want) and got==want,(fun.__name__,args,got,want)


def refuse(fun,args,code):
    try:fun(*[x[:] if type(x) is list else x for x in args])
    except ValueError as e:assert str(e)=='P235:'+fun.__name__+':'+code,(str(e),code)
    else:raise AssertionError(('missing refusal',fun.__name__,args,code))


from math import comb
def alt_oracle(a):return [sum(a[::2]),sum(a[1::2])]
def kaw_oracle(a):return len(a)%2==0 and alt_oracle(a)[0]==alt_oracle(a)[1]
def signings_oracle(a):
    n=len(a);out=[]
    for mask in range(1<<n):
        s=[(mask>>i)&1 for i in range(n)]
        if abs(2*sum(s)-n)==2:out.append(s)
    return sorted(out)

VALID=[[90,90,90,90],[60,120,60,120],[45,135,45,135],[30,90,60,60,90,30],[120,120,120],[180,180],[1,359],[120,30,120,90],[30]*12,[10,170,10,170],[200,160],[36,72,36,72,72,72],[100,260],[72]*5,[90,180,90],[60,90,60,90,60]]

def check(a):
    n=len(a)
    compare(m.origami_kawasaki,[a],kaw_oracle(a))
    compare(m.origami_alternating_sums,[a],alt_oracle(a))
    compare(m.origami_angle_sum,[a],360)
    compare(m.origami_min_angle_positions,[a],[i for i in range(n)if a[i]<a[(i-1)%n]and a[i]<a[(i+1)%n]])
    for s in ([0]*n,[1]*n,[i%2 for i in range(n)],[1]+[0]*(n-1)):
        compare(m.origami_sign_imbalance,[a,s],2*sum(s)-n)
        compare(m.origami_maekawa,[a,s],abs(2*sum(s)-n)==2)
        compare(m.origami_flat_foldable,[a,s],kaw_oracle(a) and abs(2*sum(s)-n)==2)
    if kaw_oracle(a):
        compare(m.origami_valid_signings,[a],signings_oracle(a))
        compare(m.origami_signing_count,[a],len(signings_oracle(a)))
        if n%2==0:compare(m.origami_signing_count,[a],comb(n,n//2+1)+comb(n,n//2-1))
        compare(m.origami_signing_count,[a],len(m.origami_valid_signings(a)))
    else:
        refuse(m.origami_valid_signings,[a],'bad_value:not_kawasaki')
        refuse(m.origami_signing_count,[a],'bad_value:not_kawasaki')

def run():
    for a in VALID:check(a)
    compare(m.origami_kawasaki,[[90,90,90,90]],True)
    compare(m.origami_kawasaki,[[80,100,100,80]],True)
    compare(m.origami_kawasaki,[[120,120,120]],False)
    compare(m.origami_kawasaki,[[10,170,10,170]],False)
    compare(m.origami_alternating_sums,[[60,120,60,120]],[120,240])
    compare(m.origami_alternating_sums,[[1,359]],[1,359])
    compare(m.origami_sign_imbalance,[[90,90,90,90],[1,1,0,0]],0)
    compare(m.origami_sign_imbalance,[[90,90,90,90],[1,1,1,0]],2)
    compare(m.origami_sign_imbalance,[[90,90,90,90],[0,0,0,0]],-4)
    compare(m.origami_maekawa,[[90,90,90,90],[1,1,1,0]],True)
    compare(m.origami_maekawa,[[90,90,90,90],[1,1,0,0]],False)
    compare(m.origami_maekawa,[[90,90,90,90],[0,0,0,1]],True)
    compare(m.origami_maekawa,[[90,90,90,90],[0,0,1,1]],False)
    compare(m.origami_flat_foldable,[[90,90,90,90],[1,1,1,0]],True)
    compare(m.origami_flat_foldable,[[90,90,90,90],[1,1,0,0]],False)
    compare(m.origami_flat_foldable,[[80,100,100,80],[0,1,1,1]],True)
    compare(m.origami_flat_foldable,[[60,120,60,120],[0,1,1,1]],False)
    compare(m.origami_flat_foldable,[[120,120,120],[1,1,0]],False)
    compare(m.origami_valid_signings,[[180,180]],[[0,0],[1,1]])
    compare(m.origami_signing_count,[[180,180]],2)
    compare(m.origami_signing_count,[[90,90,90,90]],8)
    compare(m.origami_signing_count,[[30,90,60,60,90,30]],30)
    compare(m.origami_signing_count,[[30]*12],1584)
    compare(m.origami_valid_signings,[[90,90,90,90]],[[0,0,0,1],[0,0,1,0],[0,1,0,0],[0,1,1,1],[1,0,0,0],[1,0,1,1],[1,1,0,1],[1,1,1,0]])
    compare(m.origami_min_angle_positions,[[120,30,120,90]],[1,3])
    compare(m.origami_min_angle_positions,[[90,90,90,90]],[])
    compare(m.origami_min_angle_positions,[[100,260]],[0])
    compare(m.origami_min_angle_positions,[[30,90,60,60,90,30]],[])
    compare(m.origami_cyclic_equivalent,[[60,120,60,120],[120,60,120,60]],True)
    compare(m.origami_cyclic_equivalent,[[60,120,60,120],[60,60,120,120]],False)
    compare(m.origami_cyclic_equivalent,[[90,90,90,90],[90,90,90,90]],True)
    compare(m.origami_cyclic_equivalent,[[180,180],[90,90,90,90]],False)
    compare(m.origami_cyclic_equivalent,[[30,90,60,60,90,30],[60,90,30,30,90,60]],True)
    compare(m.origami_angle_sum,[[1,359]],360)

def run2():
    bad=[('x','bad_type:angles'),(None,'bad_type:angles'),(True,'bad_type:angles'),([],'bad_value:angles_size'),([180],'bad_value:angles_size'),([30]*13,'too_many:angles'),([True,359],'bad_type:angle'),([1.0,359],'bad_type:angle'),(['90',270],'bad_type:angle'),([0,360],'bad_value:angle'),([-5,365],'bad_value:angle'),([90,360],'too_many:angle'),([90,90,90,91],'bad_value:angle_sum'),([90,90,90,89],'bad_value:angle_sum')]
    one=[m.origami_kawasaki,m.origami_alternating_sums,m.origami_valid_signings,m.origami_signing_count,m.origami_min_angle_positions,m.origami_angle_sum]
    two=[m.origami_maekawa,m.origami_sign_imbalance,m.origami_flat_foldable]
    for fun in one:
        for a,code in bad:refuse(fun,[a],code)
    for fun in two:
        for a,code in bad:refuse(fun,[a,[0,0,0,0]],code)
        refuse(fun,[[90,90,90,90],'x'],'bad_type:signs')
        refuse(fun,[[90,90,90,90],True],'bad_type:signs')
        refuse(fun,[[90,90,90,90],[0,0]],'bad_value:signs_size')
        refuse(fun,[[90,90,90,90],[0,0,0,0,0]],'bad_value:signs_size')
        refuse(fun,[[90,90,90,90],[0,0,0,True]],'bad_type:sign')
        refuse(fun,[[90,90,90,90],[0,0,0,1.0]],'bad_type:sign')
        refuse(fun,[[90,90,90,90],[0,0,0,2]],'bad_value:sign')
        refuse(fun,[[90,90,90,90],[0,0,0,-1]],'bad_value:sign')
    for a,code in bad:
        refuse(m.origami_cyclic_equivalent,[a,[90,90,90,90]],code)
        refuse(m.origami_cyclic_equivalent,[[90,90,90,90],a],code)
    refuse(m.origami_maekawa,['x','y'],'bad_type:angles')
    refuse(m.origami_maekawa,[[90,90,90,91],[0]],'bad_value:angle_sum')
    refuse(m.origami_flat_foldable,[[90,90,90,91],'x'],'bad_value:angle_sum')
    refuse(m.origami_valid_signings,[[90,90,90,91]],'bad_value:angle_sum')
    refuse(m.origami_signing_count,[[30]*13],'too_many:angles')
    refuse(m.origami_cyclic_equivalent,[[0,360],[30]*13],'bad_value:angle')

class T(unittest.TestCase):
    def test_independent_oracles(self):run()
    def test_refusal_order_and_caps(self):run2()
if __name__=='__main__':unittest.main()
