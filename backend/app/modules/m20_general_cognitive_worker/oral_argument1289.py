"""Oral Argument: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1289,prefix='ORALAR1289:',vocabulary=('likely_questions', 'record_cites', 'authorities', 'concessions', 'unknowns'),limits=('as common scope line; never predicts a bench, an outcome or a ruling.',))
