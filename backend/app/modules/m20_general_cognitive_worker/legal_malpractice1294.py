"""Legal Malpractice: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1294,prefix='LEGALM1294:',vocabulary=('duty', 'standard_evidence', 'breach_allegation', 'causation', 'damages_assertions'),limits=('as common scope line; never concludes malpractice, breach, causation or damages.',))
