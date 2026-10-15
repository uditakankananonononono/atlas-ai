import copy,itertools,random,unittest,builtins,importlib.util
from fractions import Fraction as F
from app.modules.instinct_doc import p235_concepts_batch316 as m
NAMES=('weighted_mean','weighted_variance','weighted_third_central_moment','weighted_fourth_central_moment','weighted_squared_skewness','weighted_excess_kurtosis','weighted_mean_absolute_deviation','weighted_gini_mean_difference','weighted_lower_semivariance','weighted_three_quarter_expectile')
def pair(x):return(x.numerator,x.denominator)
def oracle(rows):
    xs=[v for v,c in rows for i in range(c)];N=len(xs);mean=F(sum(xs),N)
    # binomial expansion of central moments from raw moments
    import math
    raw=[F(sum(x**j for x in xs),N) for j in range(5)]
    moments={k:sum((math.comb(k,j)*(-mean)**(k-j)*raw[j] for j in range(k+1)),F(0)) for k in (2,3,4)}
    # enumerate rational candidate solutions independent of data cut indexing
    values=sorted(set(xs));candidates={F(sum(x*weights[values.index(x)] for x in xs),sum(weights[values.index(x)] for x in xs)) for weights in itertools.product((1,3),repeat=len(values))}
    expectile=next(e for e in candidates if sum(3*max(F(x)-e,0)-max(e-F(x),0) for x in xs)==0)
    v=moments[2]
    return [pair(mean),pair(v),pair(moments[3]),pair(moments[4]),pair(moments[3]**2/v**3) if v else None,pair(moments[4]/v**2-3) if v else None,pair(F(sum(abs(F(x)-mean) for x in xs),N)),pair(F(sum(abs(x-y) for x in xs for y in xs),N*N)),pair(F(sum((F(x)-mean)**2 for x in xs if x<mean),N)),pair(expectile)]
class WeightedTests(unittest.TestCase):
    def exact(self,a,b):
        self.assertIs(type(a),type(b))
        if type(b) in (tuple,list):
            self.assertEqual(len(a),len(b))
            for x,y in zip(a,b):self.exact(x,y)
        else:self.assertEqual(a,b)
    def check(self,rows):
        old=copy.deepcopy(rows)
        for name,e in zip(NAMES,oracle(rows)):self.exact(getattr(m,name)(rows),e)
        self.assertEqual(rows,old)
    def test_small_exhaustive_caps(self):
        menu=list(itertools.product((-1,0,1),(1,2)))
        for n in (1,2,3):
            for rows in itertools.product(menu,repeat=n):self.check(list(rows))
        rng=random.Random(316)
        for _ in range(30):self.check([(rng.randint(-4,4),rng.randint(1,4)) for i in range(rng.randint(1,6))])
        self.check([(-4,4),(4,4)]*3);self.check([(4,4)]*6)
    def test_validation(self):
        class I(int):pass
        class L(list):pass
        class T(tuple):pass
        cases=[(None,'bad_type:rows'),(L([(1,1)]),'bad_type:rows'),([],'bad_value:empty'),([None]*7,'too_many:rows'),([None],'bad_type:row'),([[1,1]],'bad_type:row'),([T((1,1))],'bad_type:row'),([(1,)],'bad_type:row'),([(1,1,1)],'bad_type:row'),([(True,1)],'bad_type:entry'),([(1,I(1))],'bad_type:entry'),([(1,None)],'bad_type:entry'),([(-5,1)],'bad_value:value'),([(5,1)],'bad_value:value'),([(0,0)],'bad_value:count'),([(0,5)],'bad_value:count'),([(5,0),(0,None)],'bad_type:entry'),([(0,0),(5,1)],'bad_value:value'),([(0,None),None],'bad_type:row'),([(0,1),(0,5)],'bad_value:count')]
        for name in NAMES:
            for rows,code in cases:
                with self.assertRaises(ValueError) as e:getattr(m,name)(rows)
                self.assertEqual(str(e.exception),'P235:'+name+':'+code)
            for pos in range(6):
                rows=[(0,1)]*6;rows[pos]=(I(0),1)
                with self.assertRaises(ValueError) as e:getattr(m,name)(rows)
                self.assertEqual(str(e.exception),'P235:'+name+':bad_type:entry')
        self.assertEqual(m.SCOPE,'PARTIAL exact bounded supplied frequency descriptives,not population inference')
        self.assertEqual(m.NOT_CLAIMED,('AGI-like intelligence','sampling validity','population inference','forecasting','production readiness'))
    def test_guard(self):
        original=builtins.__import__
        for absent in ('app.modules.instinct_doc.p235_concepts_registry','app','unrelated_dependency'):
            def hook(name,*args,**kwargs):
                if name=='app.modules.instinct_doc.p235_concepts_registry':raise ModuleNotFoundError('missing',name=absent)
                return original(name,*args,**kwargs)
            builtins.__import__=hook
            try:
                spec=importlib.util.spec_from_file_location('isolated316',m.__file__);module=importlib.util.module_from_spec(spec)
                if absent=='app.modules.instinct_doc.p235_concepts_registry':
                    spec.loader.exec_module(module)
                    with self.assertRaises(ValueError) as e:module.weighted_mean([])
                    self.assertEqual(str(e.exception),'P235:weighted_mean:bad_value:empty')
                else:
                    with self.assertRaises(ModuleNotFoundError) as e:spec.loader.exec_module(module)
                    self.assertEqual(e.exception.name,absent)
            finally:builtins.__import__=original
if __name__=='__main__':unittest.main()
