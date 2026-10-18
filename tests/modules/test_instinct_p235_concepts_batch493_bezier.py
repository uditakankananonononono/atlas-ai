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
from app.modules.instinct_doc import p235_concepts_batch493_bezier as m


def compare(fun,args,want):
    got=fun(*[x[:] if type(x) is list else x for x in args])
    assert type(got) is type(want) and got==want,(fun.__name__,args,got,want)


def refuse(fun,args,code):
    try:fun(*[x[:] if type(x) is list else x for x in args])
    except ValueError as e:assert str(e)=='P235:'+fun.__name__+':'+code,(str(e),code)
    else:raise AssertionError(('missing refusal',fun.__name__,args,code))


from fractions import Fraction as F
from math import comb
FUNS=[m.bezier_evaluate,m.bezier_subdivide,m.bezier_blossom,m.bezier_degree_elevate,m.bezier_elevate_n,m.bezier_derivative_control,m.bezier_second_derivative_control,m.bezier_derivative_evaluate,m.bezier_endpoints,m.bezier_is_collinear]
def bern(pts,t):
    n=len(pts)-1
    return [sum((comb(n,i)*(1-t)**(n-i)*t**i*p[d]for i,p in enumerate(pts)),F(0))for d in range(len(pts[0]))]
def split_oracle(pts,t):
    tri=[pts]
    while len(tri[-1])>1:
        layer=[[(1-t)*x+t*y for x,y in zip(a,b)]for a,b in zip(tri[-1],tri[-1][1:])]
        tri.append(layer)
    return[[row[0]for row in tri],[row[-1]for row in reversed(tri)]]
def elevate_oracle(pts):
    n=len(pts)
    return [pts[0]]+[[F(i,n)*a+F(n-i,n)*b for a,b in zip(pts[i-1],pts[i])]for i in range(1,n)]+[pts[-1]]
def check(pts,t):
    pts=[[F(x)for x in p]for p in pts];n=len(pts)-1
    compare(m.bezier_evaluate,[pts,t],bern(pts,t))
    left,right=split_oracle(pts,t)
    compare(m.bezier_subdivide,[pts,t],[left,right])
    assert bern(left,F(1))==bern(pts,t) and bern(right,F(0))==bern(pts,t)
    el=elevate_oracle(pts)
    compare(m.bezier_degree_elevate,[pts],el)
    cur=pts
    for r in range(5):
        compare(m.bezier_elevate_n,[pts,r],cur);cur=elevate_oracle(cur)
    if len(pts)<=4 and t in (F(0),F(1),F(1,2)) and all(type(x) is F and x.denominator==1 and abs(x.numerator)<=4 for p in pts for x in p):
        compare(m.bezier_evaluate,[el,t],bern(pts,t))
        for r in range(5):compare(m.bezier_evaluate,[m.bezier_elevate_n(pts,r),t],bern(pts,t))
        compare(m.bezier_endpoints,[left],[pts[0],bern(pts,t)])
        compare(m.bezier_endpoints,[right],[bern(pts,t),pts[-1]])
        compare(m.bezier_is_collinear,[el],m.bezier_is_collinear(pts))
    dc=[ [F(n)*(b-a)for a,b in zip(p,q)]for p,q in zip(pts,pts[1:])]
    compare(m.bezier_derivative_control,[pts],dc)
    compare(m.bezier_derivative_evaluate,[pts,t],bern(dc,t))
    if len(pts)>=3:
        d2=[[F(n-1)*(b-a)for a,b in zip(p,q)]for p,q in zip(dc,dc[1:])]
        compare(m.bezier_second_derivative_control,[pts],d2)
    else:refuse(m.bezier_second_derivative_control,[pts],'bad_value:degree')
    compare(m.bezier_endpoints,[pts],[pts[0],pts[-1]])
    compare(m.bezier_blossom,[pts,[t]*n],bern(pts,t))
def run():
    cases=[[[0],[1]],[[0,0],[1,0],[1,1]],[[0,0],[1,2],[2,2],[3,0]],[[0],[1],[2],[3],[4],[5],[6],[7],[8]],[[F(-4096),F(1,4096)],[F(4096),F(-1,4096)]]]
    ts=[F(0),F(1),F(1,2),F(-1),F(2),F(1,4096),F(-4096),F(4096)]
    for pts in cases:
        for t in ts:check(pts,t)
    rng=random.Random(493)
    for _ in range(30):
        dim=rng.randrange(1,5)
        pts=[[F(rng.randrange(-6,7),rng.randrange(1,9))for _ in range(dim)]for _ in range(rng.randrange(2,7))]
        check(pts,F(rng.randrange(-3,4),rng.randrange(1,7)))
    compare(m.bezier_is_collinear,[[[0,0],[1,1],[2,2]]],True)
    compare(m.bezier_is_collinear,[[[5,5],[5,5],[5,5]]],True)
    compare(m.bezier_is_collinear,[[[0,0],[1,2],[2,2]]],False)
    compare(m.bezier_is_collinear,[[[0,0,0],[1,1,0],[2,2,1]]],False)
    compare(m.bezier_is_collinear,[[[0,0,0],[1,1,0],[2,2,0]]],True)
    compare(m.bezier_is_collinear,[[[0,0],[1,1],[0,1]]],False)
    compare(m.bezier_is_collinear,[[[0,0],[1,1],[1,1],[0,1]]],False)
    compare(m.bezier_is_collinear,[[[0,0],[1,1],[2,0]]],False)
    compare(m.bezier_is_collinear,[[[0,1],[2,3],[1,3]]],False)
    compare(m.bezier_is_collinear,[[[0,1],[2,3],[1,0]]],False)
    compare(m.bezier_is_collinear,[[[1],[2],[4]]],True)
    compare(m.bezier_is_collinear,[[[0,0],[1,1],[0,1],[1,1]]],False)
    compare(m.bezier_is_collinear,[[[0,0],[1,1],[1,2],[0,1]]],False)
    compare(m.bezier_is_collinear,[[[1,0],[2,1],[3,2]]],True)
    compare(m.bezier_blossom,[[[0],[3],[5]],[F(1,3),F(2,3)]],[F(25,9)])
    compare(m.bezier_blossom,[[[0],[3],[5]],[F(1,2),F(1,2)]],[F(11,4)])
    refuse(m.bezier_blossom,[[[0],[1]],[]],'bad_value:args_size')
    refuse(m.bezier_blossom,[[[0],[1]],[F(0),F(0)]],'bad_value:args_size')
    refuse(m.bezier_blossom,[[[0],[1]],None],'bad_type:args')
    refuse(m.bezier_blossom,[[[0],[1]],[True]],'bad_type:arg')
    refuse(m.bezier_blossom,[[[0],[1]],[F(4097)]],'too_many:arg_numerator')
    badp=[(None,'bad_type:points'),([],'bad_value:points_size'),([[0]],'bad_value:points_size'),([[i]for i in range(10)],'too_many:points'),([None,[0]],'bad_type:point'),([[],[0]],'bad_value:dimension'),([[],[]],'bad_value:dimension'),([[[0]]*5,[0]]if False else [[0]*5,[0]*5],'too_many:dimension'),([[0],[0,0]],'bad_value:dimension'),([[True],[0]],'bad_type:component'),([[0.0],[0]],'bad_type:component'),([[4097],[0]],'too_many:numerator'),([[-4097],[0]],'too_many:numerator'),([[F(1,4097)],[0]],'too_many:denominator')]
    for fun in FUNS:
        for pts,code in badp:
            args=[pts]+[0]*(fun.__code__.co_argcount-1)
            refuse(fun,args,code)
    for fun in (m.bezier_evaluate,m.bezier_subdivide,m.bezier_derivative_evaluate):
        for t,code in [(True,'bad_type:t'),(0.0,'bad_type:t'),(F(4097),'too_many:t_numerator'),(F(-4097),'too_many:t_numerator'),(F(1,4097),'too_many:t_denominator')]:
            refuse(fun,[[[0],[1]],t],code)
    for r,code in [(True,'bad_type:r'),(0.0,'bad_type:r'),(-1,'bad_value:r'),(5,'too_many:r')]:refuse(m.bezier_elevate_n,[[[0],[1]],r],code)

class T(unittest.TestCase):
    def test_independent_oracles_and_refusals(self):run()
if __name__=='__main__':unittest.main()
