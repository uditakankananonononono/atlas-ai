"""P235|L184 b329:finite conceptclass learning certificates,notBoolean analysis.
Unstructuredpoints0..n-1,n exactint0..4;hypotheses exactlist<=6sorted distinct
exactint bitmasks0..2**n-1,nonempty. NoIO/text/inputmutation. ValueErrorP235.
"""
from itertools import combinations,permutations,product
from fractions import Fraction
from functools import lru_cache
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    from importlib.util import find_spec
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec(exc.name) is not None:raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:%s:%s' % (name,code))
        return fail
SCOPE='PARTIAL finite learning-class certificates,not AGI or statistical generalization guarantees'
NOT_CLAIMED=('AGI-like intelligence','statistical generalization guarantees','unbounded scalability','production readiness')


def _class(name,n,hypotheses):
    fail=make_fail(name)
    if type(n) is not int:fail('bad_type:n')
    if n<0:fail('bad_value:n')
    if n>4:fail('too_many:points')
    if type(hypotheses) is not list:fail('bad_type:hypotheses')
    if not hypotheses:fail('bad_value:empty_class')
    if len(hypotheses)>6:fail('too_many:hypotheses')
    if any(type(h) is not int for h in hypotheses):fail('bad_type:hypothesis')
    if any(h<0 or h>=1<<n for h in hypotheses):fail('bad_value:hypothesis')
    if hypotheses!=sorted(set(hypotheses)):fail('bad_value:canonical')
    return fail,tuple(hypotheses)


def _shattered(h,mask):return len({x&mask for x in h})==1<<mask.bit_count()


def flearn_shattered_coordinate_sets(n,hypotheses):
    """All pointsetmasks shattered byH,ascending,includemask0. Labels0/1."""
    _,h=_class('flearn_shattered_coordinate_sets',n,hypotheses)
    return [s for s in range(1<<n) if _shattered(h,s)]


def flearn_vc_dimension_witnesses(n,hypotheses):
    """(VCdimension,[(mask,representatives)])allmaximumshatteredsets.
    Representatives=minhypothesis perlabelpattern sortedmaskedpattern.
    """
    _,h=_class('flearn_vc_dimension_witnesses',n,hypotheses);sets=[s for s in range(1<<n) if _shattered(h,s)];d=max(s.bit_count() for s in sets);out=[]
    for s in sets:
        if s.bit_count()!=d:continue
        patterns=sorted({x&s for x in h});out.append((s,[min(x for x in h if x&s==p) for p in patterns]))
    return d,out


def flearn_littlestone_optimal_tree(n,hypotheses):
    """(Littlestonedimension,completeadversarialtree). TreeleafNone,node
    (point,zerochild,onechild),lexleastroot/ties. Maximizecompletebinarydepth,
    bothbranchesnonempty. Leavestruncatewhen nofurthercompletelevelpossible.
    """
    _,h=_class('flearn_littlestone_optimal_tree',n,hypotheses)
    @lru_cache(None)
    def depth(h):
        candidates=[1+min(depth(tuple(x for x in h if not(x>>i&1))),depth(tuple(x for x in h if x>>i&1))) for i in range(n) if any(x>>i&1 for x in h) and any(not(x>>i&1) for x in h)]
        return max(candidates,default=0)
    def tree(h,d):
        if d==0:return None
        i=next(i for i in range(n) if len(a:=tuple(x for x in h if not(x>>i&1)))>0 and len(b:=tuple(x for x in h if x>>i&1))>0 and min(depth(a),depth(b))>=d-1)
        return i,tree(tuple(x for x in h if not(x>>i&1)),d-1),tree(tuple(x for x in h if x>>i&1),d-1)
    d=depth(h)
    return d,tree(h,d)


def flearn_minimum_teaching_sets(n,hypotheses):
    """Perhypothesis rows(target,minimumteachingpointsetmasks). Teachlabels
    comefromtarget;emptysetteaches singletonclass. Allminimizersascending.
    """
    _,h=_class('flearn_minimum_teaching_sets',n,hypotheses);out=[]
    for target in h:
        good=[s for s in range(1<<n) if all(x==target or (x^target)&s for x in h)];size=min(s.bit_count() for s in good);out.append((target,[s for s in good if s.bit_count()==size]))
    return out


def flearn_recursive_teaching_layers(n,hypotheses):
    """Rows(minteachingdimension,removedhypotheses)iteratively removeallcurrent
    minimumTDhypotheses,thenrecomputewithremainingclass. NotonetimeTDsort.
    """
    _,h=_class('flearn_recursive_teaching_layers',n,hypotheses);h=list(h);out=[]
    while h:
        dims={target:min(s.bit_count() for s in range(1<<n) if all(x==target or (x^target)&s for x in h)) for target in h};d=min(dims.values());removed=[x for x in h if dims[x]==d];out.append((d,removed));h=[x for x in h if x not in removed]
    return out


def flearn_optimal_membership_query_tree(n,hypotheses):
    """(minimumworstcasequeries,identificationtree),leafhypothesisint,
    node(point,zerochild,onechild). Lowestpointtie,allhypothesesidentified.
    OppositeobjectivefromLittlestone:MINmaxbranchdepth,notMAXminbranchdepth.
    """
    _,h=_class('flearn_optimal_membership_query_tree',n,hypotheses)
    @lru_cache(None)
    def solve(h):
        if len(h)==1:return 0,h[0]
        choices=[]
        for i in range(n):
            a=tuple(x for x in h if not(x>>i&1));b=tuple(x for x in h if x>>i&1)
            if not a or not b:continue
            da,ta=solve(a);db,tb=solve(b);choices.append((1+max(da,db),i,ta,tb))
        d,i,a,b=min(choices,key=lambda row:(row[0],row[1]));return d,(i,a,b)
    return solve(h)


def flearn_star_number_witnesses(n,hypotheses):
    """(maxsize,[(center,pointmask,spokes)])allmaximumstars. For eachpointof
    mask,spokeagreewithcenteronallotherselectedpointsanddisagreesthere;
    canonicalleasthypothesisperspoke,pointorderascending. Outsidefree.
    """
    _,h=_class('flearn_star_number_witnesses',n,hypotheses);rows=[]
    for center in h:
        for s in range(1<<n):
            spokes=[]
            for i in range(n):
                if not(s>>i&1):continue
                matching=[x for x in h if (x^center)&s==1<<i]
                if not matching:break
                spokes.append(min(matching))
            else:rows.append((center,s,spokes))
    size=max(s.bit_count() for c,s,v in rows)
    return size,[row for row in rows if row[1].bit_count()==size]


def flearn_disagreement_coefficient(n,hypotheses,center):
    """(maxratio,[(integerHammingradius,DISpointmask)])overr1..n. Ballincludes
    hammingdistance<=rfromcenter inclass. Ratio|DIS(ball)|/r=uniformmeasure
    normalizationcancelled. n0->(0,[]). Allmaxradii,notPACbound.
    """
    fail,h=_class('flearn_disagreement_coefficient',n,hypotheses)
    if type(center) is not int:fail('bad_type:center')
    if center not in h:fail('bad_value:center')
    rows=[]
    for radius in range(1,n+1):
        ball=[x for x in h if (x^center).bit_count()<=radius];mask=0
        for x in ball:mask|=x^center
        rows.append((Fraction(mask.bit_count(),radius),radius,mask))
    best=max((ratio for ratio,r,s in rows),default=Fraction(0))
    return best,[(r,s) for ratio,r,s in rows if ratio==best]


def flearn_minimum_consistent_sample_errors(n,hypotheses,sample):
    """(minimumerrors,allminimizinghypotheses)exact empiricalrisk. Sample
    exactlist<=8 exactlist[point,label],duplicates/contradictionsallowed.
    Countsoccurrences,notlabelset. Pointint0..n-1,labelint0/1.
    """
    fail,h=_class('flearn_minimum_consistent_sample_errors',n,hypotheses)
    if type(sample) is not list:fail('bad_type:sample')
    if len(sample)>8:fail('too_many:sample')
    if any(type(r) is not list for r in sample):fail('bad_type:row')
    if any(len(r)!=2 for r in sample):fail('bad_value:row')
    if any(type(x) is not int for r in sample for x in r):fail('bad_type:sample_entry')
    if any(not 0<=i<n or label not in (0,1) for i,label in sample):fail('bad_value:sample_entry')
    costs={x:sum((x>>i&1)!=label for i,label in sample) for x in h};best=min(costs.values())
    return best,[x for x in h if costs[x]==best]


def flearn_eluder_independent_sequences(n,hypotheses):
    """Alllongestorderedpointsequenceswhereateachnewpointtwoclassmembers
    agreeonALLearlierpointsbutdisagreeonthenewpoint(epsilon0). Atmostn,
    sortedlex,finitesequenceindependence,notlinearalgebra/binarywordkernel.
    """
    _,h=_class('flearn_eluder_independent_sequences',n,hypotheses)
    for size in range(n,-1,-1):
        rows=[]
        for sequence in permutations(range(n),size):
            mask=0
            for i in sequence:
                if not any((a^b)&mask==0 and (a^b)>>i&1 for a,b in combinations(h,2)):break
                mask|=1<<i
            else:rows.append(list(sequence))
        if rows:return rows
