"""Independent rotation-set,greedy-Lyndon-prefix,suffix-LCP,enumeration and DFS oracles."""
import importlib.abc,importlib.util,itertools,random,sys,types,unittest
from app.modules.instinct_doc import p235_concepts_batch302 as m
REG='app.modules.instinct_doc.p235_concepts_registry'
PATH=m.__file__
WORD=('cw_lyndon_factorization_exact','cw_is_lyndon_exact','cw_border_lengths_exact','cw_bwt_exact','cw_standard_factorization_exact','cw_distinct_squares_exact','cw_primitive_root_exact')
COUNT=('cw_necklace_count_exact','cw_lyndon_count_exact')
NAMES=WORD+COUNT+('cw_debruijn_exact',)
class I(int):pass
class S(str):pass
def words(lo,hi):return [''.join(t) for n in range(lo,hi+1) for t in itertools.product('ab',repeat=n)]
rng=random.Random(302)
WORDS=words(1,8)+[''.join(rng.choice('ab') for _ in range(rng.randint(9,12))) for _ in range(500)]+['a'*12,'b'*12,'ab'*6,'ba'*6,'aab'*4,'a'*11+'b','b'+'a'*11,'abaababaabaa']
def rotations(w):return [w[i:]+w[:i] for i in range(len(w))]
def lyndon(w):return all(w<r for r in rotations(w)[1:])
def greedy_factors(w):
    out=[]
    while w:
        k=max(j for j in range(1,len(w)+1) if lyndon(w[:j]));out.append(w[:k]);w=w[k:]
    return out
def lcp(x,y):
    k=0
    while k<min(len(x),len(y)) and x[k]==y[k]:k+=1
    return k
def distinct(w):
    suf=sorted(w[i:] for i in range(len(w)))
    return sum(len(s) for s in suf)-sum(lcp(suf[i],suf[i+1]) for i in range(len(suf)-1))
def inverse_bwt(last,idx):
    table=['']*len(last)
    for _ in range(len(last)):table=sorted(last[i]+table[i] for i in range(len(last)))
    return table[idx]
def squares(w):
    subs={w[i:j] for i in range(len(w)) for j in range(i+1,len(w)+1)}
    return len({x for x in subs if len(x)%2==0 and x[:len(x)//2]==x[len(x)//2:]})
def dfs_debruijn(n):
    """Lexicographic depth-first search over linear windows,closed cyclically."""
    total=1<<n
    def go(seq,used):
        if len(seq)==total:
            ext=seq+seq[:n-1]
            return seq if len({ext[i:i+n] for i in range(total)})==total else None
        for c in '01':
            t=seq+c
            if len(t)>=n:
                win=t[-n:]
                if win in used:continue
                used.add(win);r=go(t,used);used.discard(win)
            else:r=go(t,used)
            if r:return r
        return None
    return go('',set())
class WordTests(unittest.TestCase):
    def exact(self,a,b):
        self.assertIs(type(a),type(b))
        if type(b) is list:
            self.assertEqual(len(a),len(b))
            for x,y in zip(a,b):self.exact(x,y)
        else:self.assertEqual(a,b)
    def refuses(self,name,args,code):
        with self.assertRaises(ValueError) as e:getattr(m,name)(*args)
        self.assertEqual(str(e.exception),'P235:'+name+':'+code)
    def test_word_oracles(self):
        for w in WORDS:
            n=len(w);rots=rotations(w)
            self.exact(m.cw_lyndon_factorization_exact(w),greedy_factors(w))
            self.exact(m.cw_is_lyndon_exact(w),lyndon(w))
            self.exact(m.cw_border_lengths_exact(w),[k for k in range(1,n) if w[:k]==w[n-k:]])
            roots=[(w[:d],n//d) for d in range(1,n+1) if w[:d]*(n//d)==w and n%d==0]
            self.exact(m.cw_primitive_root_exact(w),[roots[0][0],roots[0][1]])
            last,idx=m.cw_bwt_exact(w)
            self.exact(last,''.join(r[-1] for r in sorted(rots)));self.exact(idx,sorted(rots).index(w))
            self.assertEqual(inverse_bwt(last,idx),w)
            self.assertEqual(sorted(last),sorted(w))
            self.exact(m.cw_distinct_squares_exact(w),squares(w))
            if lyndon(w) and n>=2:
                k=next(k for k in range(1,n) if lyndon(w[k:]))
                self.exact(m.cw_standard_factorization_exact(w),[w[:k],w[k:]])
                self.assertTrue(lyndon(w[:k]))
            elif not lyndon(w):self.refuses('cw_standard_factorization_exact',(w,),'bad_value:not_lyndon')
            else:self.refuses('cw_standard_factorization_exact',(w,),'bad_value:too_short')
    def test_count_oracles(self):
        for k in (1,2,3):
            for n in range(1,9):
                ws=[''.join(t) for t in itertools.product('abc'[:k],repeat=n)]
                self.exact(m.cw_necklace_count_exact(n,k),len({min(rotations(w)) for w in ws}))
                self.exact(m.cw_lyndon_count_exact(n,k),sum(1 for w in ws if lyndon(w)))
    def test_debruijn_oracle(self):
        for n in range(1,6):
            got=m.cw_debruijn_exact(n);self.exact(got,dfs_debruijn(n))
            self.assertEqual(len(got),2**n);ext=got+got[:n-1]
            self.assertEqual({ext[i:i+n] for i in range(2**n)},{''.join(t) for t in itertools.product('01',repeat=n)})
    def test_hand_values(self):
        self.exact(m.cw_lyndon_factorization_exact('babaab'),['b','ab','aab'])
        self.exact(m.cw_lyndon_factorization_exact('a'),['a'])
        self.exact(m.cw_lyndon_factorization_exact('aaaa'),['a','a','a','a'])
        self.exact(m.cw_lyndon_factorization_exact('aabab'),['aabab'])
        self.exact(m.cw_is_lyndon_exact('aab'),True)
        self.exact(m.cw_is_lyndon_exact('abab'),False)
        self.exact(m.cw_is_lyndon_exact('a'),True)
        self.exact(m.cw_is_lyndon_exact('ba'),False)
        self.exact(m.cw_border_lengths_exact('abaababaab'),[2,5])
        self.exact(m.cw_border_lengths_exact('a'),[])
        self.exact(m.cw_border_lengths_exact('aaaa'),[1,2,3])
        self.exact(m.cw_primitive_root_exact('ababab'),['ab',3])
        self.exact(m.cw_primitive_root_exact('aba'),['aba',1])
        self.exact(m.cw_primitive_root_exact('a'*12),['a',12])
        self.exact(m.cw_bwt_exact('ab'),['ba',0])
        self.exact(m.cw_bwt_exact('ba'),['ba',1])
        self.exact(m.cw_bwt_exact('a'),['a',0])
        self.exact(m.cw_bwt_exact('abab'),['bbaa',0])
        self.exact(m.cw_bwt_exact('baab'),['baba',2])
        self.exact(m.cw_standard_factorization_exact('aab'),['a','ab'])
        self.exact(m.cw_standard_factorization_exact('ab'),['a','b'])
        self.exact(m.cw_standard_factorization_exact('aabab'),['aab','ab'])
        self.exact(m.cw_standard_factorization_exact('aabb'),['a','abb'])
        self.refuses('cw_standard_factorization_exact',('a',),'bad_value:too_short')
        self.refuses('cw_standard_factorization_exact',('b',),'bad_value:too_short')
        self.refuses('cw_standard_factorization_exact',('ba',),'bad_value:not_lyndon')
        self.refuses('cw_standard_factorization_exact',('abab',),'bad_value:not_lyndon')
        self.exact(m.cw_distinct_squares_exact('aaaa'),2)
        self.exact(m.cw_distinct_squares_exact('abab'),1)
        self.exact(m.cw_distinct_squares_exact('ab'),0)
        self.exact(m.cw_distinct_squares_exact('aabaab'),2)
        self.exact(m.cw_necklace_count_exact(4,2),6)
        self.exact(m.cw_necklace_count_exact(8,3),834)
        self.exact(m.cw_necklace_count_exact(1,1),1)
        self.exact(m.cw_lyndon_count_exact(6,2),9)
        self.exact(m.cw_lyndon_count_exact(8,3),810)
        self.exact(m.cw_lyndon_count_exact(1,3),3)
        self.exact(m.cw_lyndon_count_exact(2,1),0)
        self.exact(m.cw_debruijn_exact(1),'01')
        self.exact(m.cw_debruijn_exact(2),'0011')
        self.exact(m.cw_debruijn_exact(3),'00010111')
        self.exact(m.cw_debruijn_exact(4),'0000100110101111')
    def test_word_codes_and_order(self):
        for name in WORD:
            for bad,code in ((None,'bad_type:word'),(b'ab','bad_type:word'),(['a'],'bad_type:word'),(S('ab'),'bad_type:word'),(1,'bad_type:word'),(('a',),'bad_type:word'),
                             ('','bad_value:empty'),('a'*13,'too_long:word'),('b'*100,'too_long:word'),('abababababab'+'c','too_long:word'),
                             ('c','bad_value:alphabet'),('A','bad_value:alphabet'),('ab ','bad_value:alphabet'),('ab\n','bad_value:alphabet'),('a\x00','bad_value:alphabet'),('a\u200b','bad_value:alphabet'),('a\ue000','bad_value:alphabet'),('a\ud800','bad_value:alphabet'),('a\u0378','bad_value:alphabet'),('a\x7f','bad_value:alphabet'),('a\x85','bad_value:alphabet'),
                             ('abc','bad_value:alphabet'),('cab','bad_value:alphabet'),('abcab','bad_value:alphabet'),('a\u0430','bad_value:alphabet'),('1','bad_value:alphabet')):
                self.refuses(name,(bad,),code)
            self.refuses(name,('c'*13,),'too_long:word')
            self.refuses(name,('',),'bad_value:empty')
            if name=='cw_standard_factorization_exact':getattr(m,name)('aab');getattr(m,name)('a'*11+'b')
            else:getattr(m,name)('a'*12);getattr(m,name)('b');getattr(m,name)('ab'*6)
    def test_count_codes_and_order(self):
        for name in COUNT:
            for args,code in (((None,1),'bad_type:n'),((True,1),'bad_type:n'),((I(2),1),'bad_type:n'),((2.0,1),'bad_type:n'),(('2',1),'bad_type:n'),
                              ((1,None),'bad_type:k'),((1,True),'bad_type:k'),((1,I(1)),'bad_type:k'),((1,1.0),'bad_type:k'),((1,'1'),'bad_type:k'),
                              ((0,1),'bad_value:n'),((9,1),'bad_value:n'),((-1,1),'bad_value:n'),((10**9,1),'bad_value:n'),
                              ((1,0),'bad_value:k'),((1,4),'bad_value:k'),((1,-1),'bad_value:k'),((8,10**9),'bad_value:k'),
                              ((None,None),'bad_type:n'),((99,None),'bad_type:k'),((None,99),'bad_type:n'),((0,0),'bad_value:n'),((9,4),'bad_value:n'),((1,True),'bad_type:k'),((True,99),'bad_type:n')):
                self.refuses(name,args,code)
            for n in (1,8):
                for k in (1,3):getattr(m,name)(n,k)
    def test_debruijn_codes(self):
        for bad,code in ((None,'bad_type:n'),(True,'bad_type:n'),(False,'bad_type:n'),(I(2),'bad_type:n'),(2.0,'bad_type:n'),('2','bad_type:n'),(0,'bad_value:n'),(6,'bad_value:n'),(-1,'bad_value:n'),(10**9,'bad_value:n')):
            self.refuses('cw_debruijn_exact',(bad,),code)
        m.cw_debruijn_exact(1);m.cw_debruijn_exact(5)
    def test_types_purity_and_contract(self):
        for w in ('abab','a','baab'):
            for name in WORD:
                if name=='cw_standard_factorization_exact':continue
                out=getattr(m,name)(w)
                if type(out) is list:
                    expected=list(out);out.clear();self.assertEqual(getattr(m,name)(w),expected)
        self.assertEqual(m.cw_border_lengths_exact('a'),[])
        for x in m.cw_lyndon_factorization_exact('babaab'):self.assertIs(type(x),str)
        for x in m.cw_border_lengths_exact('aaaa'):self.assertIs(type(x),int)
        r=m.cw_primitive_root_exact('abab');self.assertIs(type(r[0]),str);self.assertIs(type(r[1]),int);r[0]='z'
        self.assertEqual(m.cw_primitive_root_exact('abab'),['ab',2])
        r=m.cw_bwt_exact('abab');self.assertIs(type(r),list);self.assertIs(type(r[0]),str);self.assertIs(type(r[1]),int);r[0]='z'
        self.assertEqual(m.cw_bwt_exact('abab'),['bbaa',0])
        r=m.cw_standard_factorization_exact('aab');self.assertIs(type(r[0]),str);r[0]='z';self.assertEqual(m.cw_standard_factorization_exact('aab'),['a','ab'])
        for name,t in (('cw_is_lyndon_exact',bool),('cw_distinct_squares_exact',int)):self.assertIs(type(getattr(m,name)('ab')),t)
        self.assertIs(type(m.cw_necklace_count_exact(3,2)),int);self.assertIs(type(m.cw_lyndon_count_exact(3,2)),int);self.assertIs(type(m.cw_debruijn_exact(2)),str)
        self.assertEqual(m.SCOPE,'PARTIAL exact bounded binary word combinatorics,not string library or compression scheme')
        self.assertEqual(m.NOT_CLAIMED,('arbitrary alphabets','long words','global novelty','production readiness'))
        self.assertEqual(m.__doc__.splitlines()[0],'P235|L184 b302:exact combinatorics on binary words.')
        self.assertEqual([n for n in dir(m) if n.startswith('cw_')],sorted(NAMES))
    def test_fallback(self):
        saved=sys.modules.get(REG,'absent')
        class Boom(importlib.abc.Loader):
            def create_module(self,spec):return None
            def exec_module(self,module):raise ModuleNotFoundError('other missing',name='other.missing')
        class Finder(importlib.abc.MetaPathFinder):
            def find_spec(self,fullname,path,target=None):
                if fullname==REG:return importlib.util.spec_from_loader(fullname,Boom())
        def load():
            spec=importlib.util.spec_from_file_location('b302_copy',PATH);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
        try:
            sys.modules.pop(REG,None);f=Finder();sys.meta_path.insert(0,f)
            try:
                with self.assertRaises(ModuleNotFoundError) as e:load()
                self.assertEqual(e.exception.name,'other.missing')
            finally:sys.meta_path.remove(f)
            fake=types.ModuleType(REG)
            def make_fail(name):
                def fail(code):raise KeyError((name,code))
                return fail
            fake.make_fail=make_fail;sys.modules[REG]=fake
            mod=load()
            with self.assertRaises(KeyError) as e:mod.cw_is_lyndon_exact(None)
            self.assertEqual(e.exception.args[0],('cw_is_lyndon_exact','bad_type:word'))
            sys.modules[REG]=None
            mod=load()
            with self.assertRaises(ValueError) as e:mod.cw_is_lyndon_exact(None)
            self.assertEqual(str(e.exception),'P235:cw_is_lyndon_exact:bad_type:word')
        finally:
            if saved=='absent':sys.modules.pop(REG,None)
            else:sys.modules[REG]=saved
if __name__=='__main__':unittest.main()
