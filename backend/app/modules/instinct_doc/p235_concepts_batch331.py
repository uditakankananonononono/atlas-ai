"""P235 b331: bounded exact finite labelled-urn sampling distributions.
Counts exact tuple1..3 of exact int1..3,total<=8. Draws exact int0..total
(for replacement also this cap). Validate counts outer,length,allcell types,
allcell ranges,total,then draws type/range,then color if supplied (exact int
0..number colors-1). Without replacement uniform labelled-item samples;
replacement independent draws weighted by supplied color counts.
Multivariate laws return sorted (count_tuple,Fraction) lists. Other laws
return sorted(integer,Fraction)lists. First/last hit use0 for no selected
color occurrence and1-based draw positions otherwise. Empty draw has0runs,
0collision pairs,0distinct;all colors missing. Missing law returns the
actual missing-color bitmask,not merely a relabelled distinct-count law.
Full coverage probability=allcolors represented. All outputs fresh,exact.
No observed data,inference,unbounded sampling,global novelty/production claim.
"""
from fractions import Fraction as F
from math import comb,factorial
import itertools as it
from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:%s:%s'%(name,code))
        return fail
SCOPE='PARTIAL: exact bounded labelled-urn finite sampling and color occupancy distributions'
NOT_CLAIMED=('observed data validity','statistical inference','unbounded sampling','global novelty','production readiness')


def _check(name,counts,draws,color=None,needs_color=False):
    fail=make_fail(name)
    if type(counts) is not tuple:fail('bad_type:counts')
    if not 1<=len(counts)<=3:fail('bad_value:length_counts')
    if any(type(v) is not int for v in counts):fail('bad_type:cell_counts')
    if any(not 1<=v<=3 for v in counts):fail('bad_value:cell_counts')
    if sum(counts)>8:fail('bad_value:total_counts')
    if type(draws) is not int:fail('bad_type:draws')
    if not 0<=draws<=sum(counts):fail('bad_value:draws')
    if needs_color:
        if type(color) is not int:fail('bad_type:color')
        if not 0<=color<len(counts):fail('bad_value:color')


def _law(counts,draws,replacement=False):
    result=[];total=sum(counts)
    for vector in it.product(range(draws+1),repeat=len(counts)):
        if sum(vector)!=draws:continue
        if replacement:
            ways=factorial(draws)
            for v in vector:ways//=factorial(v)
            mass=F(ways,total**draws)
            for c,v in zip(counts,vector):mass*=c**v
        else:
            if any(v>c for c,v in zip(counts,vector)):continue
            mass=F(1,comb(total,draws))
            for c,v in zip(counts,vector):mass*=comb(c,v)
        result.append((vector,mass))
    return result


def _aggregate(law,key):
    bins={}
    for vector,mass in law:
        value=key(vector);bins[value]=bins.get(value,F(0))+mass
    return sorted(bins.items())


def urn_multivariate_without_replacement(counts,draws):
    _check('urn_multivariate_without_replacement',counts,draws)
    return _law(counts,draws)


def urn_multivariate_with_replacement(counts,draws):
    _check('urn_multivariate_with_replacement',counts,draws)
    return _law(counts,draws,True)


def urn_distinct_colors_without_replacement(counts,draws):
    _check('urn_distinct_colors_without_replacement',counts,draws)
    return _aggregate(_law(counts,draws),lambda v:sum(x>0 for x in v))


def urn_distinct_colors_with_replacement(counts,draws):
    _check('urn_distinct_colors_with_replacement',counts,draws)
    return _aggregate(_law(counts,draws,True),lambda v:sum(x>0 for x in v))


def urn_first_color_hit(counts,draws,color):
    _check('urn_first_color_hit',counts,draws,color,True);total=sum(counts);good=counts[color];bad=total-good;result=[]
    none=F(comb(bad,draws),comb(total,draws)) if draws<=bad else F(0)
    if none:result.append((0,none))
    for k in range(1,draws+1):
        if k-1>bad:break
        probability=F(comb(bad,k-1),comb(total,k-1))*F(good,total-k+1)
        if probability:result.append((k,probability))
    return result


def urn_last_color_hit(counts,draws,color):
    _check('urn_last_color_hit',counts,draws,color,True)
    # Reversal preserves uniform sampling law;last=k iff first=draws+1-k.
    return sorted((0 if k==0 else draws+1-k,p) for k,p in urn_first_color_hit(counts,draws,color))


def urn_full_coverage_probability(counts,draws):
    _check('urn_full_coverage_probability',counts,draws)
    return sum((p for v,p in _law(counts,draws) if all(v)),F(0))


def urn_missing_colors_distribution(counts,draws):
    _check('urn_missing_colors_distribution',counts,draws)
    return _aggregate(_law(counts,draws),lambda v:sum(1<<i for i,x in enumerate(v) if x==0))


def urn_collision_pairs_distribution(counts,draws):
    _check('urn_collision_pairs_distribution',counts,draws)
    return _aggregate(_law(counts,draws),lambda v:sum(x*(x-1)//2 for x in v))


def urn_runs_without_replacement(counts,draws):
    _check('urn_runs_without_replacement',counts,draws);states={(counts,-1,0):F(1)}
    for _ in range(draws):
        next_states={}
        for (remaining,last,runs),mass in states.items():
            for color,count in enumerate(remaining):
                if not count:continue
                new=list(remaining);new[color]-=1;key=(tuple(new),color,runs+int(color!=last))
                next_states[key]=next_states.get(key,F(0))+mass*F(count,sum(remaining))
        states=next_states
    result={}
    for (remaining,last,runs),mass in states.items():result[runs]=result.get(runs,F(0))+mass
    return sorted(result.items())
