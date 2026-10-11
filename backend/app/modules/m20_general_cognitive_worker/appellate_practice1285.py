"""Appellate Practice: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1285,prefix='APPELL1285:',vocabulary=('appealability', 'preservation', 'record_cites', 'review_standard', 'requested_relief'),limits=('as common scope line; never reaches a conclusion on appellate practice, never advises on it.',))
