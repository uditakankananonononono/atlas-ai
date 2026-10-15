import itertools,math,random,re,unittest,importlib.util,builtins
from fractions import Fraction as F
from app.modules.instinct_doc import p235_concepts_batch357 as m
NAMES=('stoich_primitive_balance','stoich_balance_residual','stoich_limiting_reagents','stoich_reaction_extent','stoich_theoretical_product_yield','stoich_percent_yield','stoich_atom_economy','stoich_empirical_formula','stoich_formula_atom_counts','stoich_isotope_mass_distribution')
def pair(v):return(v.numerator,v.denominator)
def balance(a,split):
    # Meet-in-the-middle join atom totals for reactant/product coefficient assignments.
    n=len(a[0]);left={};out=[]
    for cs in itertools.product(range(1,7),repeat=split):
        key=tuple(sum(row[j]*cs[j] for j in range(split)) for row in a);left.setdefault(key,[]).append(cs)
    for cs in itertools.product(range(1,7),repeat=n-split):
        key=tuple(sum(row[j+split]*cs[j] for j in range(n-split)) for row in a)
        for ls in left.get(key,[]):
            if math.gcd(*(ls+cs))==1:out.append(ls+cs)
    return sorted(out)
def isotope(masses,n,a,b):
    hist={}
    for states in itertools.product((0,1),repeat=n):
        mass=sum(masses[s] for s in states);weight=F(1)
        for s in states:weight*=F(a if s==0 else b-a,b)
        hist[mass]=hist.get(mass,F(0))+weight
    return [(mass,pair(prob)) for mass,prob in sorted(hist.items()) if prob]
def formula_oracle(text):
    # Rewrite innermost groups to expanded letters, then count.
    def expand(s):
        return ''.join(letter*int(count or '1') for letter,count in re.findall(r'([ABC])([1-6]?)',s))
    while '(' in text:
        text=re.sub(r'\(([^()]*)\)([1-6]?)',lambda z:expand(z[1])*int(z[2] or '1'),text)
    text=expand(text);return tuple(text.count(c) for c in 'ABC')
class StoichTests(unittest.TestCase):
    def exact(self,a,b):
        self.assertIs(type(a),type(b))
        if type(b) in (tuple,list):
            self.assertEqual(len(a),len(b))
            for x,y in zip(a,b):self.exact(x,y)
        else:self.assertEqual(a,b)
    def test_exact_oracles(self):
        rng=random.Random(357)
        matrices=[([(a,b)],1) for a,b in itertools.product(range(1,5),repeat=2)]+[([(2,0,2),(0,2,1)],2)]
        for _ in range(80):
            cols=rng.randint(2,4);rows=[tuple(rng.randint(1,4) for j in range(cols)) for i in range(rng.randint(1,3))];matrices.append((rows,rng.randrange(1,cols)))
        for a,split in matrices:
            old=a.copy();self.exact(m.stoich_primitive_balance(a,split),balance(a,split));cs=[rng.randint(1,6) for j in a[0]]
            left=[sum(row[j]*cs[j] for j in range(split)) for row in a];right=[sum(row[j]*cs[j] for j in range(split,len(cs))) for row in a]
            self.exact(m.stoich_balance_residual(a,split,cs),tuple(x-y for x,y in zip(left,right)));self.assertEqual(a,old)
        menu=list(itertools.product((1,2,3),(0,1,3)))
        for length in (1,2,3):
            for rows in itertools.product(menu,repeat=length):
                rows=list(rows);candidates={F(a,c) for c,a in rows};extent=max(e for e in candidates if all(e*c<=a for c,a in rows));self.exact(m.stoich_reaction_extent(rows),pair(extent));self.exact(m.stoich_limiting_reagents(rows),[i for i,(c,a) in enumerate(rows) if c*extent==a])
        for rc,pc,rm,ra,pm in itertools.product((1,2),(1,3),(0,2,12),(1,3),(1,4)):
            moles=F(rm,ra);product_moles=moles*F(pc,rc);self.exact(m.stoich_theoretical_product_yield(rc,pc,rm,ra,pm),pair(product_moles*pm))
        for actual in range(13):
            for theoretical in range(1,13):self.exact(m.stoich_percent_yield(actual,theoretical),pair(100*F(actual,theoretical)))
        for _ in range(100):
            rows=[(rng.randint(1,6),rng.randint(1,12)) for i in range(rng.randint(1,3))];pc=rng.randint(1,6);pm=rng.randint(1,12);self.exact(m.stoich_atom_economy(rows,pc,pm),pair(F(pc*pm,sum(c*v for c,v in rows))*100))
            masses=[(rng.randint(1,12),rng.randint(1,12)) for i in range(rng.randint(1,3))];mol=[F(a,b) for a,b in masses];expected=next(tuple(int(v*k) for v in mol) for k in range(1,1729) if all((v*k).denominator==1 for v in mol));g=math.gcd(*expected);self.exact(m.stoich_empirical_formula(masses),tuple(v//g for v in expected))
        tokens=[c+str(k) for c in 'ABC' for k in range(1,7)]
        texts=['A','B','C','(AB)2C','((A2B)2C)3','(((A)))','A6B6C6']+[a+b for a,b in itertools.product(tokens,repeat=2)]
        for text in texts:self.exact(m.stoich_formula_atom_counts(text),formula_oracle(text))
        for masses in itertools.product(range(1,4),repeat=2):
            for n in range(4):
                for d in range(1,4):
                    for a in range(d+1):self.exact(m.stoich_isotope_mass_distribution(masses,n,a,d),isotope(masses,n,a,d))
        self.exact(m.stoich_isotope_mass_distribution((1,6),6,3,6),isotope((1,6),6,3,6))
    def refuses(self,name,args,code):
        with self.assertRaises(ValueError) as e:getattr(m,name)(*args)
        self.assertEqual(str(e.exception),'P235:'+name+':'+code)
    def test_validation(self):
        class I(int):pass
        class L(list):pass
        class T(tuple):pass
        class S(str):pass
        for name in NAMES[:2]:
            extra=[] if name==NAMES[0] else [[1,1]]
            for a,s,code in ((None,1,'bad_type:atoms'),(L([(1,1)]),1,'bad_type:atoms'),([],1,'bad_value:elements'),([None]*4,1,'bad_value:elements'),([[1,1]],1,'bad_type:row'),([T((1,1))],1,'bad_type:row'),([(1,)],1,'bad_value:shape'),([(1,1),(1,1,1)],1,'bad_value:shape'),([(True,1)],1,'bad_type:atom'),([(0,1)],1,'bad_value:empty_species'),([(5,1)],1,'bad_value:atom'),([(-1,1)],1,'bad_value:atom'),([(1,I(1))],1,'bad_type:atom'),([(1,1)],True,'bad_type:split'),([(1,1)],0,'bad_value:split'),([(1,1)],2,'too_many:split')):self.refuses(name,[a,s]+extra,code)
        for c,code in ((None,'bad_type:coefficients'),(L([1,1]),'bad_type:coefficients'),([1],'bad_type:coefficients'),([1,True],'bad_type:coefficient'),([1,0],'bad_value:coefficient'),([7,1],'bad_value:coefficient')):self.refuses(NAMES[1],[[(1,1)],1,c],code)
        for name in (NAMES[2],NAMES[3],NAMES[6],NAMES[7]):
            kind='reactants' if name in NAMES[2:4] else 'reactant_masses' if name==NAMES[6] else 'masses';extra=[1,1] if name==NAMES[6] else []
            for rows,code in ((None,'bad_type:'+kind),(L([(1,1)]),'bad_type:'+kind),([],'bad_value:length'),([None]*4,'bad_value:length'),([[1,1]],'bad_type:row'),([T((1,1))],'bad_type:row'),([(1,True)],'bad_type:entry'),([(I(1),1)],'bad_type:entry'),([(0,1)],'bad_value:entry'),([(13,1)],'bad_value:entry'),([(1,13)],'bad_value:entry'),([(1,1),(1,-1)],'bad_value:entry')):self.refuses(name,[rows]+extra,code)
        numeric=[(NAMES[4],[1,1,0,1,1],[(1,6),(1,6),(0,12),(1,12),(1,12)],['reactant_coefficient','product_coefficient','reactant_mass','reactant_molar_mass','product_molar_mass']),(NAMES[5],[0,1],[(0,12),(1,12)],['actual','theoretical'])]
        for name,args,bounds,labels in numeric:
            for pos,((lo,hi),label) in enumerate(zip(bounds,labels)):
                for bad,code in ((True,'bad_type:'),(I(1),'bad_type:'),(lo-1,'bad_value:'),(hi+1,'too_many:')):
                    values=args.copy();values[pos]=bad;self.refuses(name,values,code+label)
        for pos,label in ((1,'product_coefficient'),(2,'product_molar_mass')):
            for bad,code in ((None,'bad_type:'),(0,'bad_value:'),(13,'too_many:')):
                values=[[(1,1)],1,1];values[pos]=bad;self.refuses(NAMES[6],values,code+label)
        for text,code in ((None,'bad_type:formula'),(S('A'),'bad_type:formula'),('','bad_value:length'),('A'*33,'bad_value:length'),('()','bad_value:syntax'),('(A','bad_value:syntax'),('A)','bad_value:syntax'),('D','bad_value:syntax'),('A0','bad_value:syntax'),('A7','bad_value:syntax'),('A12','bad_value:syntax'),('2A','bad_value:syntax'),('Aé','bad_value:syntax'),('((((A))))','too_many:depth'),('(A6B6)6','too_many:atoms')):self.refuses(NAMES[8],[text],code)
        self.refuses(NAMES[9],[[1,2],1,1,2],'bad_type:masses')
        for pos,label,lo,hi in ((0,'mass0',1,6),(1,'mass1',1,6),(2,'atoms',0,6),(3,'probability_n',0,6),(4,'probability_d',1,6)):
            for bad,code in ((True,'bad_type:'),(I(1),'bad_type:'),(lo-1,'bad_value:'),(hi+1,'too_many:')):
                vals=[1,2,1,0,1];vals[pos]=bad;self.refuses(NAMES[9],[tuple(vals[:2])]+vals[2:],code+label)
        self.refuses(NAMES[9],[(1,2),1,2,1],'bad_value:probability')
        self.assertEqual(m.SCOPE,'PARTIAL exact bounded abstract stoichiometry,not verified chemistry or laboratory advice');self.assertEqual(m.NOT_CLAIMED,('AGI-like intelligence','chemical feasibility','unit consistency','laboratory safety','reaction mechanism','production readiness'))
    def test_boundaries_and_mixed_validation(self):
        self.exact(m.stoich_formula_atom_counts('A'*32),(32,0,0))
        self.exact(m.stoich_formula_atom_counts('(A5B5)6'),(30,30,0))
        self.refuses(NAMES[8],['(A5B5)6A'],'too_many:atoms')
        for name in NAMES[:2]:
            extra=[] if name==NAMES[0] else [[1,1]]
            self.refuses(name,[[(1,1),[1,1]],1]+extra,'bad_type:row')
            self.refuses(name,[[(1,1,1,1,1)],1]+extra,'bad_value:shape')
        for name in (NAMES[2],NAMES[3],NAMES[6],NAMES[7]):
            extra=[1,1] if name==NAMES[6] else []
            self.refuses(name,[[(1,1),[1,1]]]+extra,'bad_type:row')
            top=12 if name==NAMES[7] else 6
            second_low=0 if name in NAMES[2:4] else 1
            expected=[0] if name==NAMES[2] else pair(F(12,top)) if name==NAMES[3] else pair(F(100,top*12)) if name==NAMES[6] else (1,)
            self.exact(getattr(m,name)([(top,12)],*extra),expected)
            self.refuses(name,[[(top+1,1)]]+extra,'bad_value:entry')
            self.refuses(name,[[(1,second_low-1)]]+extra,'bad_value:entry')
        self.exact(m.stoich_theoretical_product_yield(6,6,12,12,12),(12,1))
        self.exact(m.stoich_atom_economy([(6,12)],6,12),(100,1))
        self.refuses(NAMES[6],[[(7,12)],1,1],'bad_value:entry')
        self.refuses(NAMES[6],[[(1,0)],1,1],'bad_value:entry')
        self.refuses(NAMES[6],[[(1,1)],7,1],'too_many:product_coefficient')
        self.exact(m.stoich_isotope_mass_distribution((6,6),6,6,6),[(36,(1,1))])
    def test_find_spec_guard(self):
        original=builtins.__import__;find=importlib.util.find_spec
        for absent,present in (('app.modules.instinct_doc.p235_concepts_registry',False),('app.modules.instinct_doc.p235_concepts_registry',True),('unrelated_dependency',False),('app',False)):
            def hook(name,*args,**kwargs):
                if name=='app.modules.instinct_doc.p235_concepts_registry':raise ModuleNotFoundError('missing',name=absent)
                return original(name,*args,**kwargs)
            builtins.__import__=hook;importlib.util.find_spec=lambda name:object() if present else None
            try:
                spec=importlib.util.spec_from_file_location('isolated357',m.__file__);module=importlib.util.module_from_spec(spec)
                if absent=='app.modules.instinct_doc.p235_concepts_registry' and not present:
                    spec.loader.exec_module(module)
                    with self.assertRaises(ValueError) as e:module.stoich_percent_yield(0,0)
                    self.assertEqual(str(e.exception),'P235:stoich_percent_yield:bad_value:theoretical')
                else:
                    with self.assertRaises(ModuleNotFoundError) as e:spec.loader.exec_module(module)
                    self.assertEqual(e.exception.name,absent)
            finally:builtins.__import__=original;importlib.util.find_spec=find
if __name__=='__main__':unittest.main()

class StoichFirstBadOrderTests(StoichTests):
    # First-bad pins: all type checks precede range checks across scalar slots;
    # row tuple-type precedes shape; atom range precedes empty_species; zero
    # element ROWS are valid (only all-zero species columns are refused).
    def test_types_before_ranges_across_slots(self):
        self.refuses(NAMES[4],[0,None,0,1,1],'bad_type:product_coefficient')
        self.refuses(NAMES[9],[(0,2),True,0,1],'bad_type:atoms')
    def test_row_type_before_shape(self):
        self.refuses(NAMES[0],[[[1]],1],'bad_type:row')
        self.refuses(NAMES[1],[[[1,1],[1,1,1]],1,[1,1]],'bad_type:row')
    def test_atom_range_before_empty_species(self):
        self.refuses(NAMES[0],[[(5,0)],1],'bad_value:atom')
        self.refuses(NAMES[1],[[(0,5)],1,[1,1]],'bad_value:atom')
    def test_zero_element_rows_valid(self):
        self.exact(m.stoich_primitive_balance([(0,0),(1,1)],1),[(1,1)])
        self.exact(m.stoich_balance_residual([(0,0),(1,1)],1,[2,3]),(0,-1))
