"""Legal Ethics: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1290,prefix='LEGALE1290:',vocabulary=('actor', 'role', 'duty', 'rule_source', 'facts', 'ethics_review'),limits=('as common scope line; never issues an ethics opinion.',))
