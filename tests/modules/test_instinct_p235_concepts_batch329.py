import itertools,unittest,random,copy
from fractions import Fraction
from app.modules.instinct_doc import p235_concepts_batch329 as m
NAMES=('flearn_shattered_coordinate_sets','flearn_vc_dimension_witnesses','flearn_littlestone_optimal_tree','flearn_minimum_teaching_sets','flearn_recursive_teaching_layers','flearn_optimal_membership_query_tree','flearn_star_number_witnesses','flearn_disagreement_coefficient','flearn_minimum_consistent_sample_errors','flearn_eluder_independent_sequences')
CASES=[(n,list(h)) for n in range(4) for k in range(1,min(6,1<<n)+1) for h in itertools.combinations(range(1<<n),k)];rng=random.Random(329);CASES +=[(4,sorted(rng.sample(range(16),rng.randrange(1,7)))) for _ in range(60)]+[(0,[0]),(4,[0,15]),(4,[0,1,2,4,8,15])]
def label(h,i):return (h//2**i)%2
def restrict(h,s):return tuple(label(h,i) for i in s)
def subsets(n):return [s for k in range(n+1) for s in itertools.combinations(range(n),k)]
def mask(s):return sum(2**i for i in s)
def teaching(n,h):
    out=[]
    for target in h:
        good=[s for s in subsets(n) if [x for x in h if restrict(x,s)==restrict(target,s)]==[target]];size=min(map(len,good));out.append((target,sorted(mask(s) for s in good if len(s)==size)))
    return out
class LearnTests(unittest.TestCase):
    def test_set_and_teaching_oracles(self):
        for n,h in CASES:
            shattered=[s for s in subsets(n) if set(restrict(x,s) for x in h)==set(itertools.product((0,1),repeat=len(s)))];self.assertEqual(m.flearn_shattered_coordinate_sets(n,h),sorted(mask(s) for s in shattered));d=max(map(len,shattered));cert=[]
            for s in sorted((s for s in shattered if len(s)==d),key=mask):
                p=mask(s);patterns=sorted({x&p for x in h});cert.append((p,[min(x for x in h if x&p==v) for v in patterns]))
            self.assertEqual(m.flearn_vc_dimension_witnesses(n,h),(d,cert));self.assertEqual(m.flearn_minimum_teaching_sets(n,h),teaching(n,h));left=h.copy();layers=[]
            while left:
                rows=teaching(n,left);dims={x:min(s.bit_count() for s in ss) for x,ss in rows};v=min(dims.values());removed=[x for x in left if dims[x]==v];layers.append((v,removed));left=[x for x in left if x not in removed]
            self.assertEqual(m.flearn_recursive_teaching_layers(n,h),layers)

    def test_tree_oracles(self):
        for n,h in CASES:
            # Enumerate depth-feasibility via sets of version spaces;complete
            # adversarial depth and worstcase identification depth DIFFERENT.
            allversions={tuple(x for x in h if restrict(x,s)==p) for s in subsets(n) for p in itertools.product((0,1),repeat=len(s))};allversions.discard(());ld={v:0 for v in allversions};qd={v:0 for v in allversions if len(v)==1}
            for version in sorted(allversions,key=len):
                splits=[(tuple(x for x in version if label(x,i)==0),tuple(x for x in version if label(x,i)==1)) for i in range(n)];splits=[(a,b) for a,b in splits if a and b];ld[version]=max((1+min(ld[a],ld[b]) for a,b in splits),default=0)
                if len(version)>1:qd[version]=min(1+max(qd[a],qd[b]) for a,b in splits)
            d,tree=m.flearn_littlestone_optimal_tree(n,h);self.assertEqual(d,ld[tuple(h)])
            def check_complete(tree,version,depth):
                if depth==0:self.assertIsNone(tree);self.assertTrue(version);return
                i,a,b=tree;choices=[j for j in range(n) if (v0:=tuple(x for x in version if label(x,j)==0)) and (v1:=tuple(x for x in version if label(x,j)==1)) and min(ld[v0],ld[v1])>=depth-1];self.assertEqual(i,min(choices));check_complete(a,tuple(x for x in version if label(x,i)==0),depth-1);check_complete(b,tuple(x for x in version if label(x,i)==1),depth-1)
            check_complete(tree,tuple(h),d)
            d,tree=m.flearn_optimal_membership_query_tree(n,h);self.assertEqual(d,qd[tuple(h)])
            def check_id(tree,version):
                if type(tree) is int:self.assertEqual(version,(tree,));return 0
                i,a,b=tree;v0=tuple(x for x in version if label(x,i)==0);v1=tuple(x for x in version if label(x,i)==1);self.assertTrue(v0 and v1);self.assertEqual(i,min(j for j in range(n) if (w0:=tuple(x for x in version if label(x,j)==0)) and (w1:=tuple(x for x in version if label(x,j)==1)) and 1+max(qd[w0],qd[w1])==qd[version]));return 1+max(check_id(a,v0),check_id(b,v1))
            self.assertEqual(check_id(tree,tuple(h)),d)

    def test_star_disagreement_sample_eluder(self):
        for n,h in CASES:
            rows=[]
            for center in h:
                for s in subsets(n):
                    target=restrict(center,s);spokes=[]
                    for j in range(len(s)):
                        changed=list(target);changed[j]=1-changed[j];choices=[x for x in h if restrict(x,s)==tuple(changed)]
                        if not choices:break
                        spokes.append(min(choices))
                    else:rows.append((center,mask(s),spokes))
            size=max(s.bit_count() for c,s,sp in rows);want=sorted((c,s,sp) for c,s,sp in rows if s.bit_count()==size);self.assertEqual(m.flearn_star_number_witnesses(n,h),(size,want))
            for center in h:
                entries=[]
                for r in range(1,n+1):
                    ball=[x for x in h if sum(label(x,i)!=label(center,i) for i in range(n))<=r];dis=[i for i in range(n) if len({label(x,i) for x in ball})==2];entries.append((Fraction(len(dis),r),r,mask(dis)))
                best=max([e[0] for e in entries],default=Fraction(0));self.assertEqual(m.flearn_disagreement_coefficient(n,h,center),(best,[(r,s) for v,r,s in entries if v==best]))
            sample=[[i,label(h[-1],i)] for i in range(n)]+([[0,0],[0,1]] if n else []);errors={x:sum(label(x,i)!=v for i,v in sample) for x in h};best=min(errors.values());self.assertEqual(m.flearn_minimum_consistent_sample_errors(n,h,sample),(best,[x for x in h if errors[x]==best]))
            # Independent-point feasible prefixes enumerated as a tree,state
            # tracks equivalence partition of hypotheses induced by observations.
            frontier=[([], [h])];valid=[[]]
            while frontier:
                new=[]
                for sequence,classes in frontier:
                    for i in range(n):
                        if i in sequence:continue
                        if any(len({label(x,i) for x in c})==2 for c in classes):
                            q=sequence+[i];split=[v for c in classes for b in (0,1) if (v:=[x for x in c if label(x,i)==b])];new.append((q,split))
                if not new:break
                valid=[q for q,c in new];frontier=new
            self.assertEqual(m.flearn_eluder_independent_sequences(n,h),sorted(valid))

    def test_boundaries_guard(self):
        self.assertEqual(m.flearn_minimum_consistent_sample_errors(1,[0,1],[[0,1]]*8),(0,[1]))
        with self.assertRaisesRegex(ValueError,'too_many:sample'):
            m.flearn_minimum_consistent_sample_errors(1,[0,1],[[0,1]]*9)
        with self.assertRaisesRegex(ValueError,'bad_value:sample_entry'):
            m.flearn_minimum_consistent_sample_errors(2,[0,1],[[-1,0]])
        import tempfile,pathlib,subprocess,sys,shutil
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);p=root/'app/modules/instinct_doc';p.mkdir(parents=True)
            for folder in (root/'app',root/'app/modules',p):(folder/'__init__.py').write_text('')
            shutil.copy(m.__file__,p/'p235_concepts_batch329.py')
            (p/'p235_concepts_registry.py').write_text("raise ModuleNotFoundError('initialization failure',name=__name__)\n")
            q=subprocess.run([sys.executable,'-c','from app.modules.instinct_doc import p235_concepts_batch329'],cwd=d,capture_output=True,text=True)
            self.assertNotEqual(q.returncode,0);self.assertIn('initialization failure',q.stderr)

    def test_refusals(self):
        args=[(2,[0,1,2])]*7+[(2,[0,1,2],0),(2,[0,1,2],[[0,1]]),(2,[0,1,2])]
        class I(int):pass
        class L(list):pass
        for name,a in zip(NAMES,args):
            f=getattr(m,name);before=copy.deepcopy(a);expected=copy.deepcopy(f(*a));got=f(*a)
            if type(got) is list:got.clear()
            self.assertEqual(f(*a),expected);self.assertEqual(a,before)
            for n,h,code in ((True,[0],'bad_type:n'),(I(1),[0],'bad_type:n'),(-1,[0],'bad_value:n'),(5,[0],'too_many:points'),(2,None,'bad_type:hypotheses'),(2,L([0]),'bad_type:hypotheses'),(2,[],'bad_value:empty_class'),(3,list(range(7)),'too_many:hypotheses'),(2,[True],'bad_type:hypothesis'),(2,[I(1)],'bad_type:hypothesis'),(2,['\x7f'],'bad_type:hypothesis'),(2,['\x1f'],'bad_type:hypothesis'),(2,[-1],'bad_value:hypothesis'),(2,[4],'bad_value:hypothesis'),(2,[1,0],'bad_value:canonical'),(2,[0,0],'bad_value:canonical')):
                with self.assertRaisesRegex(ValueError,'^P235:'+name+':'+code+'$'):f(n,h,*a[2:])
        for center in (True,None,4):
            with self.assertRaises(ValueError):m.flearn_disagreement_coefficient(2,[0,1],center)
        for sample in (None,[None]*9,[None],[[]],[[True,0]],[[-1,0]],[[2,0]],[[0,2]]):
            with self.assertRaises(ValueError):m.flearn_minimum_consistent_sample_errors(2,[0,1],sample)
if __name__=='__main__':unittest.main()
