"""P235 b330 bounded nonparametric statistics and robust fits. Exact rational
synthetic calculations, no clinical conclusions, significance decisions or
asymptotic accuracy claims. Ranking/median primitives shared, not extra credits.
"""
from fractions import Fraction as F
from math import comb,factorial
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    from importlib.util import find_spec
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec(exc.name) is not None:
        raise
    def make_fail(name):
        def fail(code):raise ValueError('P235:'+name+':'+code)
        return fail

SCOPE = 'Bounded exact rank null laws, rank dispersion statistics, binary repeated responses and robust fits.'
NOT_CLAIMED = 'No Mann-Whitney U, standalone rank/median credit, asymptotic p-values, clinical inference or live registry integration.'


def _int(f,x,label,lo,hi):
    if type(x)is not int:f('bad_type:'+label)
    if not lo<=x<=hi:f('bad_value:'+label)


def _list(f,x,label,cap):
    if type(x)is not list:f('bad_type:'+label)
    if len(x)>cap:f('too_many:'+label)


def _sample(f,x,label='sample',cap=8):
    _list(f,x,label,cap)
    if not x:f('bad_value:'+label)
    for v in x:_int(f,v,'value',-16,16)


def _rows(f,rows,binary=False):
    _list(f,rows,'rows',5)
    if len(rows)<2:f('bad_value:rows')
    width=None
    for row in rows:
        _list(f,row,'row',5)
        if len(row)<2:f('bad_value:row')
        for x in row:_int(f,x,'value',0 if binary else -16,1 if binary else 16)
        if width is None:width=len(row)
        if len(row)!=width:f('bad_value:rectangular')


def _ranks(x):
    return[F(1+sum(y<v for y in x))+F(sum(y==v for y in x)-1,2)for v in x]


def _median(x):
    x=sorted(x);n=len(x);return F(x[(n-1)//2]+x[n//2],2)


def wilcoxon_signed_rank_law(differences):
    """1..8 int differences-16..16,discardzeros; rankabsvalues with mean ties.
    Return[observedWplus,[[Wplus,mass],...]] for independent equiprobable signs
    of all NONZERO observations. Ties retain multiplicities; allzero law0point.
    Not normalapproximation,Prattzeros or two-sided p-value.
    """
    f=make_fail('wilcoxon_signed_rank_law');_sample(f,differences);nonzero=[x for x in differences if x];ranks=_ranks(list(map(abs,nonzero)));law={F(0):1}
    for r in ranks:
        new=dict(law)
        for k,v in law.items():new[k+r]=new.get(k+r,0)+v
        law=new
    observed=sum((r for r,d in zip(ranks,nonzero)if d>0),F(0));return[observed,[[k,F(v,1<<len(nonzero))]for k,v in sorted(law.items())]]


def kolmogorov_smirnov_exact_tail(first,second):
    """Each1..8 int observations-16..16,NO pooledties. Two-sidedD exact and
    P(Dnull>=Dobserved),conditional exchangeability of labels. Strict-interior
    latticepaths count complement; no continuous/asymptotic approximation.
    Return[D,tail]. Ties refused rather than silently approximate.
    """
    f=make_fail('kolmogorov_smirnov_exact_tail');_sample(f,first,'first');_sample(f,second,'second')
    if len(set(first+second))!=len(first)+len(second):f('bad_value:ties')
    n=len(first);m=len(second);d=max(abs(F(sum(x<=v for x in first),n)-F(sum(x<=v for x in second),m))for v in first+second);ways={(0,0):1}
    for i in range(n+1):
        for j in range(m+1):
            if i==j==0:continue
            ways[i,j]=0 if abs(F(i,n)-F(j,m))>=d else ways.get((i-1,j),0)+ways.get((i,j-1),0)
    return[d,1-F(ways[n,m],comb(n+m,n))]


def kendall_inversion_null_law(n):
    """n0..8. Exact law of inversioncount of uniform random permutation.
    Mahonian insertion convolution,return masses at0..n(n-1)/2. Not Kendall
    correlation withties, permutation rank/order/list, or asymptotic p-value.
    """
    f=make_fail('kendall_inversion_null_law');_int(f,n,'n',0,8);counts=[1]
    for k in range(1,n+1):
        new=[0]*(len(counts)+k-1)
        for i,v in enumerate(counts):
            for j in range(k):new[i+j]+=v
        counts=new
    return[F(x,factorial(n))for x in counts]


def kruskal_wallis_tie_statistic(groups):
    """2..4 nonempty independentgroups,each<=5 intvalues-16..16. Return exact
    pooledrank H corrected for ties. Allidentical pooledvalues refused (zero
    tiecorrection). Statistic only,no chi-square p-value or Mann-Whitney U.
    """
    f=make_fail('kruskal_wallis_tie_statistic');_list(f,groups,'groups',4)
    if len(groups)<2:f('bad_value:groups')
    for row in groups:_sample(f,row,'group',5)
    flat=[x for row in groups for x in row];n=len(flat);r=_ranks(flat);offset=0;total=F(0)
    for row in groups:total+=sum(r[offset:offset+len(row)])**2/len(row);offset+=len(row)
    correction=1-F(sum(flat.count(x)**3-flat.count(x)for x in set(flat)),n**3-n)
    if correction==0:f('bad_value:degenerate')
    return(F(12,n*(n+1))*total-3*(n+1))/correction


def friedman_tie_statistic(rows):
    """2..5blocks x2..5treatments intvalues-16..16. Withinblockmeanranks,
    exact FriedmanQ with standardwithinblocktie correction. Allblocks tied
    refused. No missingblocks, replication or chi-square p-value.
    """
    f=make_fail('friedman_tie_statistic');_rows(f,rows);n=len(rows);k=len(rows[0]);r=[_ranks(row)for row in rows];sums=[sum(row[j]for row in r)for j in range(k)];q=F(12,n*k*(k+1))*sum(x*x for x in sums)-3*n*(k+1);correction=1-F(sum(row.count(x)**3-row.count(x)for row in rows for x in set(row)),n*(k**3-k))
    if correction==0:f('bad_value:degenerate')
    return q/correction


def cochran_q_statistic(rows):
    """2..5subjects x2..5treatments binaryints. Exact CochranQ for repeated
    binaryresponse withsubject effects. Denominatorzero refused. Statistic
    only,no independence claim, chi-square p-value or McNemar two-sidedtest.
    """
    f=make_fail('cochran_q_statistic');_rows(f,rows,True);k=len(rows[0]);columns=[sum(row[j]for row in rows)for j in range(k)];total=sum(columns);den=k*total-sum(sum(row)**2 for row in rows)
    if den==0:f('bad_value:degenerate')
    return F((k-1)*(k*sum(x*x for x in columns)-total**2),den)


def page_ordered_alternative_statistic(rows):
    """2..5blocks x2..5ORDEREDtreatments intvalues-16..16. Return PageL
    sum_j(j+1)*withinblockranksum_j,meanrankties. Increasingtreatment scores
    support largeL. Statistic only,no nullprobability or tiecorrection claim.
    """
    f=make_fail('page_ordered_alternative_statistic');_rows(f,rows);return sum((F(j+1)*v for row in rows for j,v in enumerate(_ranks(row))),F(0))


def isotonic_l2_fit(values,weights):
    """1..8 valuesint-16..16,positiveintweights1..8 same length. Weighted
    leastsquares nondecreasing projection via PAVA. Return exact fittedvector.
    Adjacent equalblockmeans mayremainseparate but fittedvalues identical.
    """
    f=make_fail('isotonic_l2_fit');_sample(f,values,'values');_list(f,weights,'weights',8)
    if len(weights)!=len(values):f('bad_value:length')
    for x in weights:_int(f,x,'weight',1,8)
    blocks=[]
    for i,(v,w)in enumerate(zip(values,weights)):
        blocks.append([i,i+1,v*w,w])
        while len(blocks)>1 and F(blocks[-2][2],blocks[-2][3])>F(blocks[-1][2],blocks[-1][3]):
            b=blocks.pop();a=blocks.pop();blocks.append([a[0],b[1],a[2]+b[2],a[3]+b[3]])
    return[F(total,w)for start,end,total,w in blocks for _ in range(start,end)]


def theil_sen_fit(points):
    """2..8 points[x,y] integer-16..16,DISTINCTx. Slope=median allpairslopes;
    intercept=median(y-slope*x),jointmedian residual convention. Return[slope,
    intercept]. Evenmedians average middlepair. Not Siegel repeatedmedian or OLS.
    """
    f=make_fail('theil_sen_fit');_list(f,points,'points',8)
    if len(points)<2:f('bad_value:points')
    for row in points:
        _list(f,row,'point',2)
        if len(row)!=2:f('bad_value:point')
        for x in row:_int(f,x,'coordinate',-16,16)
    if len({row[0]for row in points})!=len(points):f('bad_value:duplicate_x')
    slope=_median([F(y-v,x-u)for i,(x,y)in enumerate(points)for u,v in points[:i]]);return[slope,_median([F(y)-slope*x for x,y in points])]


def huber_location_exact(values,threshold):
    """1..8 intvalues-16..16,thresholdinteger1..8,fixedscale1. Minimize sum
    Huber losses,return LOWESTroot of sumclip(value-location,-threshold,+threshold)
    =0. Exactpiecewise-affine solver,not IRLS,toleranceestimate or scalelearning.
    """
    f=make_fail('huber_location_exact');_sample(f,values);_int(f,threshold,'threshold',1,8);breaks=sorted({F(x+s*threshold)for x in values for s in(-1,1)})
    def score(t):return sum(max(-threshold,min(threshold,x-t))for x in values)
    for i,a in enumerate(breaks):
        left=score(a)
        if left==0:return a
        if i+1<len(breaks):
            b=breaks[i+1];right=score(b)
            if left>0 and right<0:return a+(b-a)*left/(left-right)
    raise AssertionError('convex score root')
