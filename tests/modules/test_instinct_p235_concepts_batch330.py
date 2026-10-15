"""Independent enumeration/optimization oracles for bounded statistics."""
import copy,itertools,random,math,unittest,builtins
from fractions import Fraction as F
from decimal import Decimal
from app.modules.instinct_doc import p235_concepts_batch330 as m


def compare(fn,args,want):
    before=copy.deepcopy(args);got=fn(*args)
    assert type(got)is type(want)and got==want,(fn.__name__,args,got,want)
    assert args==before


def refuse(fn,args,code):
    before=copy.deepcopy(args)
    try:fn(*args)
    except ValueError as exc:assert str(exc)=='P235:'+fn.__name__+':'+code,(fn.__name__,str(exc),code)
    else:raise AssertionError(('missing refusal',fn.__name__,args,code))
    assert args==before


def rank(x):
    order=sorted(range(len(x)),key=x.__getitem__);r=[None]*len(x)
    for i in order:r[i]=F(sum(j+1 for j,k in enumerate(order)if x[k]==x[i]),sum(x[k]==x[i]for k in order))
    return r


def med(x):
    # Median defined by min/max partition, not sorting middle-index helper.
    n=len(x);lo=next(v for v in set(x)if sum(y<v for y in x)<=((n-1)//2)<sum(y<=v for y in x));hi=next(v for v in set(x)if sum(y<v for y in x)<=(n//2)<sum(y<=v for y in x));return F(lo+hi,2)


def wilcox(d):
    nz=[x for x in d if x];r=rank(list(map(abs,nz)));totals=[sum((v for v,b in zip(r,bits)if b),F(0))for bits in itertools.product((0,1),repeat=len(nz))];return[sum((v for v,x in zip(r,nz)if x>0),F(0)),[[v,F(totals.count(v),len(totals))]for v in sorted(set(totals))]]


def ks(a,b):
    n=len(a);total=n+len(b)
    def d(sub):
        sub=set(sub);return max(abs(F(sum(i in sub for i in range(t)),n)-F(sum(i not in sub for i in range(t)),total-n))for t in range(total+1))
    pooled=sorted(a+b);observed=d([i for i,x in enumerate(pooled)if x in a]);hits=sum(d(sub)>=observed for sub in itertools.combinations(range(total),n));return[observed,F(hits,math.comb(total,n))]


def inversionlaw(n):
    counts=[0]*(n*(n-1)//2+1)
    for p in itertools.permutations(range(n)):counts[sum(a>b for i,a in enumerate(p)for b in p[i+1:])]+=1
    return[F(x,math.factorial(n))for x in counts]


def kw(groups):
    flat=sum(groups,[]);r=rank(flat);N=len(flat);offset=0;between=F(0)
    for row in groups:
        mean=sum(r[offset:offset+len(row)])/len(row);between+=len(row)*(mean-F(N+1,2))**2;offset+=len(row)
    dispersion=sum((v-F(N+1,2))**2 for v in r)
    return F(N-1)*between/dispersion if dispersion else None


def fried(rows):
    ranks=list(map(rank,rows));n=len(rows);k=len(rows[0]);deviation=sum((sum(row[j]-F(k+1,2)for row in ranks))**2 for j in range(k));dispersion=sum((v-F(k+1,2))**2 for row in ranks for v in row);return F(k-1)*deviation/dispersion if dispersion else None


def cochran(rows):
    k=len(rows[0]);columns=[sum(row[j]for row in rows)for j in range(k)];mean=F(sum(columns),k);num=(k-1)*sum((v-mean)**2 for v in columns);den=sum(sum(row)*(1-F(sum(row),k))for row in rows);return num/den if den else None


def isotonic(v,w):
    choices=[];n=len(v)
    for mask in range(1<<(n-1)):
        cuts=[0]+[i+1 for i in range(n-1)if mask>>i&1]+[n];fit=[]
        for a,b in zip(cuts,cuts[1:]):fit.extend([F(sum(v[i]*w[i]for i in range(a,b)),sum(w[a:b]))]*(b-a))
        if all(a<=b for a,b in zip(fit,fit[1:])):choices.append((sum(wi*(x-y)**2 for wi,x,y in zip(w,v,fit)),fit))
    return min(choices)[1]


def theil(points):
    slopes=[]
    for a,b in itertools.combinations(points,2):slopes.append(F(b[1]-a[1],b[0]-a[0]))
    slope=med(slopes);return[slope,med([y-slope*x for x,y in points])]


def huber(values,k):
    # Enumerate every clipping status below/linear/above; solve affine root,
    # verify clippedscore. Flat intervals handled by their lowest endpoint.
    roots=set()
    for states in itertools.product((-1,0,1),repeat=len(values)):
        active=[x for x,s in zip(values,states)if s==0];constant=k*sum(states)
        if active:candidate=F(sum(active)+constant,len(active))
        else:
            if constant:continue
            lower=[x+k for x,s in zip(values,states)if s==-1];upper=[x-k for x,s in zip(values,states)if s==1]
            if not lower or not upper or max(lower)>min(upper):continue
            candidate=F(max(lower))
        if all((x-candidate<=-k if s==-1 else x-candidate>=k if s==1 else -k<=x-candidate<=k)for x,s in zip(values,states)):roots.add(candidate)
    return min(roots)


def verify_code(code):
    import types
    target='app.modules.instinct_doc.p235_concepts_registry'
    for missing,present in((target,False),(target,True),('unrelated_registry_dependency',False)):
        def importer(name,*args,**kwargs):
            if name==target:raise ModuleNotFoundError('testmissing',name=missing)
            if name=='importlib.util':return types.SimpleNamespace(find_spec=lambda name:object()if present else None)
            return builtins.__import__(name,*args,**kwargs)
        env={'__name__':'isolated_import','__builtins__':dict(vars(builtins),__import__=importer)}
        try:exec(code,env)
        except ModuleNotFoundError as exc:assert (present or missing!=target)and exc.name==missing
        else:
            assert not present and missing==target
            try:env['kendall_inversion_null_law'](None)
            except ValueError as exc:assert str(exc)=='P235:kendall_inversion_null_law:bad_type:n'
            else:raise AssertionError('missingfallback')
            assert env['kendall_inversion_null_law'](2)==[F(1,2),F(1,2)]
    token=object()
    def importer(name,*args,**kwargs):
        if name==target:return types.SimpleNamespace(make_fail=lambda name:token)
        return builtins.__import__(name,*args,**kwargs)
    env={'__name__':'working_registry','__builtins__':dict(vars(builtins),__import__=importer)}
    exec(code,env);assert env['make_fail']('probe')is token


def run():
    from pathlib import Path
    verify_code(compile(Path(m.__file__).read_text(),m.__file__,'exec'));rng=random.Random(330)
    for n in range(9):compare(m.kendall_inversion_null_law,(n,),inversionlaw(n))
    for _ in range(70):
        n=rng.randrange(1,9);v=[rng.randrange(-16,17)for _ in range(n)];w=[rng.randrange(1,9)for _ in v];compare(m.wilcoxon_signed_rank_law,(v,),wilcox(v));compare(m.isotonic_l2_fit,(v,w),isotonic(v,w));pts=list(zip(rng.sample(range(-16,17),max(2,n)),[rng.randrange(-16,17)for _ in range(max(2,n))]));pts=list(map(list,pts));compare(m.theil_sen_fit,(pts,),theil(pts))
        n=rng.randrange(2,6);k=rng.randrange(2,6);rows=[[rng.randrange(-4,5)for _ in range(k)]for _ in range(n)];compare(m.page_ordered_alternative_statistic,(rows,),sum((sum(F(j+1)*x for j,x in enumerate(rank(row)))for row in rows),F(0)));want=fried(rows)
        if want is not None:compare(m.friedman_tie_statistic,(rows,),want)
        else:refuse(m.friedman_tie_statistic,(rows,),'bad_value:degenerate')
        binary=[[rng.randrange(2)for _ in range(k)]for _ in range(n)];want=cochran(binary)
        if want is not None:compare(m.cochran_q_statistic,(binary,),want)
        else:refuse(m.cochran_q_statistic,(binary,),'bad_value:degenerate')
        groups=[[rng.randrange(-4,5)for _ in range(rng.randrange(1,6))]for _ in range(rng.randrange(2,5))];want=kw(groups)
        if want is not None:compare(m.kruskal_wallis_tie_statistic,(groups,),want)
        else:refuse(m.kruskal_wallis_tie_statistic,(groups,),'bad_value:degenerate')
        v=[rng.randrange(-16,17)for _ in range(rng.randrange(1,6))];k=rng.randrange(1,9);compare(m.huber_location_exact,(v,k),huber(v,k))
    for _ in range(35):
        n=rng.randrange(1,7);k=rng.randrange(1,7);v=rng.sample(range(-16,17),n+k);a=v[:n];b=v[n:];compare(m.kolmogorov_smirnov_exact_tail,(a,b),ks(a,b))
    compare(m.huber_location_exact,([-16,16],1),F(-15));compare(m.isotonic_l2_fit,([1,1],[1,1]),[F(1),F(1)]);compare(m.wilcoxon_signed_rank_law,([0,0],),[F(0),[[F(0),F(1)]]])
    for fn in(m.kruskal_wallis_tie_statistic,m.friedman_tie_statistic,m.cochran_q_statistic):refuse(fn,([[0,0],[0,0]],),'bad_value:degenerate')
    rows=[[16,-16],[0,1]]
    compare(m.friedman_tie_statistic,(rows,),fried(rows));compare(m.page_ordered_alternative_statistic,(rows,),F(9))
    for a,b in(([i for i in range(8)],[-i-1 for i in range(8)]),([0],[1])):compare(m.kolmogorov_smirnov_exact_tail,(a,b),ks(a,b))
    compare(m.huber_location_exact,([0,0,0,2],1),F(1,3))
    refuse(m.isotonic_l2_fit,([0,1],[None]),'bad_value:length')
    refusals()


def refusals():
    bad=(None,True,1.0,F(1),Decimal(1),'1',[],{})
    for fn,tail in((m.wilcoxon_signed_rank_law,()),(m.huber_location_exact,(None,)),(m.isotonic_l2_fit,(None,)),(m.kolmogorov_smirnov_exact_tail,(None,))):
        label='values'if fn is m.isotonic_l2_fit else'first'if fn is m.kolmogorov_smirnov_exact_tail else'sample'
        for x in(None,(),{},''):refuse(fn,(x,*tail),'bad_type:'+label)
        refuse(fn,([None]*9,*tail),'too_many:'+label);refuse(fn,([],*tail),'bad_value:'+label)
        for x in bad:refuse(fn,([x],*tail),'bad_type:value')
        for x in(-17,17):refuse(fn,([x],*tail),'bad_value:value')
    for x in(None,(),{},''):refuse(m.kolmogorov_smirnov_exact_tail,([0],x),'bad_type:second');refuse(m.isotonic_l2_fit,([0],x),'bad_type:weights')
    refuse(m.kolmogorov_smirnov_exact_tail,([0],[None]*9),'too_many:second');refuse(m.kolmogorov_smirnov_exact_tail,([0],[]),'bad_value:second');refuse(m.kolmogorov_smirnov_exact_tail,([0],[0]),'bad_value:ties');refuse(m.isotonic_l2_fit,([0],[None]*9),'too_many:weights');refuse(m.isotonic_l2_fit,([0],[]),'bad_value:length')
    for x in bad:refuse(m.kolmogorov_smirnov_exact_tail,([0],[x]),'bad_type:value');refuse(m.isotonic_l2_fit,([0],[x]),'bad_type:weight');refuse(m.huber_location_exact,([0],x),'bad_type:threshold');refuse(m.kendall_inversion_null_law,(x,),'bad_type:n')
    for x in(-1,9):refuse(m.kendall_inversion_null_law,(x,),'bad_value:n')
    for x in(0,9):refuse(m.isotonic_l2_fit,([0],[x]),'bad_value:weight');refuse(m.huber_location_exact,([0],x),'bad_value:threshold')
    for x in(-17,17):refuse(m.kolmogorov_smirnov_exact_tail,([0],[x]),'bad_value:value')
    fn=m.kruskal_wallis_tie_statistic
    for x in(None,(),{},''):refuse(fn,(x,),'bad_type:groups');refuse(fn,([x,None],),'bad_type:group')
    refuse(fn,([None]*5,),'too_many:groups');refuse(fn,([None],),'bad_value:groups');refuse(fn,([[None]*6,None],),'too_many:group');refuse(fn,([[],None],),'bad_value:group')
    for x in bad:refuse(fn,([[x],None],),'bad_type:value')
    for x in(-17,17):refuse(fn,([[x],None],),'bad_value:value')
    for fn in(m.friedman_tie_statistic,m.cochran_q_statistic,m.page_ordered_alternative_statistic):
        binary=fn is m.cochran_q_statistic
        for x in(None,(),{},''):refuse(fn,(x,),'bad_type:rows');refuse(fn,([x,None],),'bad_type:row')
        refuse(fn,([None]*6,),'too_many:rows');refuse(fn,([None],),'bad_value:rows');refuse(fn,([[None]*6,None],),'too_many:row');refuse(fn,([[None],None],),'bad_value:row');refuse(fn,([[0,0],[0,0,0]],),'bad_value:rectangular');refuse(fn,([[0,0],[None,0,0]],),'bad_type:value')
        for x in bad:refuse(fn,([[x,0],None],),'bad_type:value')
        for x in((-1,2)if binary else(-17,17)):refuse(fn,([[x,0],None],),'bad_value:value')
    fn=m.theil_sen_fit
    for x in(None,(),{},''):refuse(fn,(x,),'bad_type:points');refuse(fn,([x,None],),'bad_type:point')
    refuse(fn,([None]*9,),'too_many:points');refuse(fn,([None],),'bad_value:points');refuse(fn,([[None]*3,None],),'too_many:point');refuse(fn,([[None],None],),'bad_value:point');refuse(fn,([[0,0],[0,1]],),'bad_value:duplicate_x')
    for x in bad:refuse(fn,([[x,0],None],),'bad_type:coordinate')
    for x in(-17,17):refuse(fn,([[x,0],None],),'bad_value:coordinate')
    for ch in map(chr,[*range(32,127),31,127]):
        refuse(m.wilcoxon_signed_rank_law,([ch],),'bad_type:value');refuse(m.kolmogorov_smirnov_exact_tail,([ch],None),'bad_type:value');refuse(m.kendall_inversion_null_law,(ch,),'bad_type:n');refuse(m.kruskal_wallis_tie_statistic,([[ch],None],),'bad_type:value')
        for fn in(m.friedman_tie_statistic,m.cochran_q_statistic,m.page_ordered_alternative_statistic):refuse(fn,([[ch,0],None],),'bad_type:value')
        refuse(m.isotonic_l2_fit,([ch],None),'bad_type:value');refuse(m.theil_sen_fit,([[ch,0],None],),'bad_type:coordinate');refuse(m.huber_location_exact,([ch],None),'bad_type:value')


class IndependentOracles(unittest.TestCase):
    def test_all(self):run()
if __name__=='__main__':run();print('b330 PASS')
