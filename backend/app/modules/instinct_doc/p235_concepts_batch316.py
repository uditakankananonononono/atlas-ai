"""b316 finite weighted population descriptives, exact arithmetic only.
rows exact list1..6 exacttuples(value,count); all shape checks then all exact
int checks then all values-4..4 then all counts1..4. Duplicate values allowed.
Counts are frequencies, not probability masses or independent sample evidence.
Moments use total frequency denominator,not unbiased sample corrections.
"""
from fractions import Fraction as F
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry':
        raise
    def make_fail(name):
        def fail(code):
            raise ValueError("P235:%s:%s" % (name, code))
        return fail
SCOPE='PARTIAL exact bounded supplied frequency descriptives,not population inference'
NOT_CLAIMED=('AGI-like intelligence','sampling validity','population inference','forecasting','production readiness')

def _data(name,rows):
    fail=make_fail(name)
    if type(rows) is not list:fail('bad_type:rows')
    if not rows:fail('bad_value:empty')
    if len(rows)>6:fail('too_many:rows')
    if any(type(r) is not tuple or len(r)!=2 for r in rows):fail('bad_type:row')
    if any(type(x) is not int for r in rows for x in r):fail('bad_type:entry')
    if any(not -4<=v<=4 for v,c in rows):fail('bad_value:value')
    if any(not 1<=c<=4 for v,c in rows):fail('bad_value:count')
    total=sum(c for v,c in rows);mean=F(sum(v*c for v,c in rows),total)
    return total,mean

def _pair(x):return(x.numerator,x.denominator)
def _moment(rows,total,mean,degree):return sum((c*(v-mean)**degree for v,c in rows),F(0))/total

def weighted_mean(rows):
    """Frequency-weighted mean, reduced pair."""
    total,mean=_data('weighted_mean',rows);return _pair(mean)
def weighted_variance(rows):
    """Population central moment2, denominator total frequency."""
    total,mean=_data('weighted_variance',rows);return _pair(_moment(rows,total,mean,2))
def weighted_third_central_moment(rows):
    """Signed central moment3."""
    total,mean=_data('weighted_third_central_moment',rows);return _pair(_moment(rows,total,mean,3))
def weighted_fourth_central_moment(rows):
    """Central moment4."""
    total,mean=_data('weighted_fourth_central_moment',rows);return _pair(_moment(rows,total,mean,4))
def weighted_squared_skewness(rows):
    """mu3 squared / mu2 cubed;None if mu2 zero; sign intentionally discarded."""
    total,mean=_data('weighted_squared_skewness',rows);v=_moment(rows,total,mean,2)
    return _pair(_moment(rows,total,mean,3)**2/v**3) if v else None
def weighted_excess_kurtosis(rows):
    """mu4/mu2 squared minus3;None for constant data,no finite-sample correction."""
    total,mean=_data('weighted_excess_kurtosis',rows);v=_moment(rows,total,mean,2)
    return _pair(_moment(rows,total,mean,4)/v**2-3) if v else None
def weighted_mean_absolute_deviation(rows):
    """Mean absolute distance from weighted mean(not median absolute deviation)."""
    total,mean=_data('weighted_mean_absolute_deviation',rows);return _pair(sum((c*abs(v-mean) for v,c in rows),F(0))/total)
def weighted_gini_mean_difference(rows):
    """E[abs(X-Y)] for independent frequency draws with replacement,including self-pairs."""
    total,mean=_data('weighted_gini_mean_difference',rows);return _pair(F(sum(c*d*abs(v-w) for v,c in rows for w,d in rows),total**2))
def weighted_lower_semivariance(rows):
    """E[min(X-mean,0)^2],denominator total frequency, not lower-tail count."""
    total,mean=_data('weighted_lower_semivariance',rows);return _pair(sum((c*min(v-mean,0)**2 for v,c in rows),F(0))/total)
def weighted_three_quarter_expectile(rows):
    """Unique e solving3*sum c max(v-e,0)=sum c max(e-v,0).
    Exact asymmetric quadratic loss minimizer;tied observations weight1 at e.
    """
    total,mean=_data('weighted_three_quarter_expectile',rows)
    values=sorted({v for v,c in rows})
    for cut in range(len(values)+1):
        lower=set(values[:cut]);den=sum(c*(1 if v in lower else 3) for v,c in rows);num=sum(v*c*(1 if v in lower else 3) for v,c in rows);e=F(num,den)
        if all((v<=e if v in lower else v>=e) for v in values):return _pair(e)
    raise AssertionError('unreachable expectile')
