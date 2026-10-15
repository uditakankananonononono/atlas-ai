"""b357 bounded abstract stoichiometry,not verified real chemical reactions.
Exact supplied atom/mass/amount arithmetic;units assumed mutually consistent.
Output rational pairs reduced,sorted where specified. No IO/mutation.
Every public function refuses bool/subclasses;errors P235:function:code.
"""
from fractions import Fraction as F
from math import gcd,lcm,comb
from itertools import product
import importlib.util

def _absent(name):
    try:return importlib.util.find_spec(name) is None
    except (ImportError,ValueError):return True
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or not _absent(exc.name):raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:'+name+':'+code)
        return fail
SCOPE='PARTIAL exact bounded abstract stoichiometry,not verified chemistry or laboratory advice'
NOT_CLAIMED=('AGI-like intelligence','chemical feasibility','unit consistency','laboratory safety','reaction mechanism','production readiness')

def _ints(name,items):
    fail=make_fail(name)
    for label,value,lo,hi in items:
        if type(value) is not int:fail('bad_type:'+label)
    for label,value,lo,hi in items:
        if value<lo:fail('bad_value:'+label)
        if value>hi:fail('too_many:'+label)
def _pair(v):return(v.numerator,v.denominator)
def _atoms(name,a,split):
    fail=make_fail(name)
    if type(a) is not list:fail('bad_type:atoms')
    if not 1<=len(a)<=3:fail('bad_value:elements')
    if any(type(r) is not tuple for r in a):fail('bad_type:row')
    n=len(a[0])
    if not 2<=n<=4 or any(len(r)!=n for r in a):fail('bad_value:shape')
    if any(type(v) is not int for r in a for v in r):fail('bad_type:atom')
    if any(not 0<=v<=4 for r in a for v in r):fail('bad_value:atom')
    if any(all(r[j]==0 for r in a) for j in range(n)):fail('bad_value:empty_species')
    _ints(name,[('split',split,1,n-1)])
    return n

def _residual(a,split,c):return tuple(sum(row[j]*c[j]*(1 if j<split else -1) for j in range(len(c))) for row in a)
def stoich_primitive_balance(atoms,split):
    """Rows elements,columns species;columns<split reactants,others products.
    ALL positive coefficients1..6 with gcd1 and conservation,lex sortedtuples.
    Empty list means no balance within bound,not chemically impossible.
    """
    name='stoich_primitive_balance';n=_atoms(name,atoms,split);out=[]
    for c in product(range(1,7),repeat=n):
        if gcd(*c)==1 and not any(_residual(atoms,split,c)):out.append(c)
    return out

def stoich_balance_residual(atoms,split,coefficients):
    """Signed per-element reactant-minus-product atom residual for supplied coefficients."""
    name='stoich_balance_residual';n=_atoms(name,atoms,split);fail=make_fail(name)
    if type(coefficients) is not list or len(coefficients)!=n:fail('bad_type:coefficients')
    if any(type(c) is not int for c in coefficients):fail('bad_type:coefficient')
    if any(not 1<=c<=6 for c in coefficients):fail('bad_value:coefficient')
    return _residual(atoms,split,coefficients)
def _pairs(name,rows,kind,lo1,hi1,lo2,hi2):
    fail=make_fail(name)
    if type(rows) is not list:fail('bad_type:'+kind)
    if not 1<=len(rows)<=3:fail('bad_value:length')
    if any(type(r) is not tuple or len(r)!=2 for r in rows):fail('bad_type:row')
    if any(type(v) is not int for r in rows for v in r):fail('bad_type:entry')
    if any(not lo1<=a<=hi1 or not lo2<=b<=hi2 for a,b in rows):fail('bad_value:entry')
    return rows

def stoich_limiting_reagents(reactants):
    """Reactant tuples(coefficient1..6,availablemoles0..12);all limiting indices,
    including all tied zero-availability reactants. Does not verify balance.
    """
    rows=_pairs('stoich_limiting_reagents',reactants,'reactants',1,6,0,12);ratios=[F(a,c) for c,a in rows];bound=min(ratios);return [i for i,v in enumerate(ratios) if v==bound]
def stoich_reaction_extent(reactants):
    """Maximum nonnegative forward extent min(availablemoles/coefficient), reduced pair."""
    rows=_pairs('stoich_reaction_extent',reactants,'reactants',1,6,0,12);return _pair(min(F(a,c) for c,a in rows))
def stoich_theoretical_product_yield(reactant_coefficient,product_coefficient,reactant_mass,reactant_molar_mass,product_molar_mass):
    """Single supplied limiting-reactant mass converted to product mass;
    reactant_mass0..12,otherargs1..12(coefficients<=6),not a predicted actual yield.
    """
    name='stoich_theoretical_product_yield';_ints(name,[('reactant_coefficient',reactant_coefficient,1,6),('product_coefficient',product_coefficient,1,6),('reactant_mass',reactant_mass,0,12),('reactant_molar_mass',reactant_molar_mass,1,12),('product_molar_mass',product_molar_mass,1,12)])
    return _pair(F(reactant_mass*product_coefficient*product_molar_mass,reactant_coefficient*reactant_molar_mass))
def stoich_percent_yield(actual,theoretical):
    """100*actual/theoretical;actual0..12,theoretical1..12,may exceed100.
    Inputs abstract consistent mass units,not authenticated experimental data.
    """
    _ints('stoich_percent_yield',[('actual',actual,0,12),('theoretical',theoretical,1,12)]);return _pair(F(100*actual,theoretical))
def stoich_atom_economy(reactant_masses,product_coefficient,product_molar_mass):
    """100*desired-product coeff*molar mass /sumreactant coeff*molar mass.
    Reactant1..3tuples(coeff1..6,molarmass1..12),productargs same bounds.
    No chemical balance verification;ratios over100 possible with supplied terms.
    """
    name='stoich_atom_economy';rows=_pairs(name,reactant_masses,'reactant_masses',1,6,1,12);_ints(name,[('product_coefficient',product_coefficient,1,6),('product_molar_mass',product_molar_mass,1,12)]);return _pair(F(100*product_coefficient*product_molar_mass,sum(c*v for c,v in rows)))
def stoich_empirical_formula(masses):
    """Exact positive tuples(elementmass1..12,atomicmass1..12),1..3elements.
    Return primitive positive integer mole ratio in input order,not formula name.
    """
    rows=_pairs('stoich_empirical_formula',masses,'masses',1,12,1,12);ratios=[F(a,b) for a,b in rows];den=lcm(*(v.denominator for v in ratios));nums=[int(v*den) for v in ratios];g=gcd(*nums);return tuple(v//g for v in nums)
def stoich_formula_atom_counts(formula):
    """Symbolic grammar A/B/C or nonempty(parenthesizedsequence),optional
    multiplier1..6(single digit);nesting<=3,text1..32,totalatoms<=60.
    Return(Acount,Bcount,Ccount). No real element-name parser.
    """
    name='stoich_formula_atom_counts';fail=make_fail(name)
    if type(formula) is not str:fail('bad_type:formula')
    if not 1<=len(formula)<=32:fail('bad_value:length')
    index=0
    def parse(depth):
        nonlocal index
        out=[0,0,0];terms=0
        while index<len(formula) and formula[index]!=')':
            ch=formula[index];index+=1
            if ch in 'ABC':part=[int(ch==v) for v in 'ABC']
            elif ch=='(':
                if depth>=3:fail('too_many:depth')
                part=parse(depth+1)
                if index==len(formula) or formula[index]!=')':fail('bad_value:syntax')
                index+=1
            else:fail('bad_value:syntax')
            multiplier=1
            if index<len(formula) and formula[index] in '123456':multiplier=int(formula[index]);index+=1
            out=[a+b*multiplier for a,b in zip(out,part)];terms+=1
            if sum(out)>60:fail('too_many:atoms')
        if not terms:fail('bad_value:syntax')
        return out
    counts=parse(0)
    if index!=len(formula):fail('bad_value:syntax')
    return tuple(counts)
def stoich_isotope_mass_distribution(masses,atoms,probability_n,probability_d):
    """masses exacttuple2exactints1..6,atoms0..6,probabilityn0..d,d1..6.
    Each independent abstract atom takes masses[0] with probabilityn/d,
    else masses[1]. Sorted[(integer totalmass,reducedprobabilitypair)],zeros omitted.
    """
    name='stoich_isotope_mass_distribution';fail=make_fail(name)
    if type(masses) is not tuple or len(masses)!=2:fail('bad_type:masses')
    _ints(name,[('mass0',masses[0],1,6),('mass1',masses[1],1,6),('atoms',atoms,0,6),('probability_n',probability_n,0,6),('probability_d',probability_d,1,6)])
    if probability_n>probability_d:fail('bad_value:probability')
    p=F(probability_n,probability_d);hist={}
    for k in range(atoms+1):
        mass=k*masses[0]+(atoms-k)*masses[1];prob=comb(atoms,k)*p**k*(1-p)**(atoms-k);hist[mass]=hist.get(mass,F(0))+prob
    return [(mass,_pair(prob)) for mass,prob in sorted(hist.items()) if prob]
