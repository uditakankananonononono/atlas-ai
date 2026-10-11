"""Brief Writing: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1288,prefix='BRIEFW1288:',vocabulary=('record_proposition', 'authority', 'counterauthority', 'analysis', 'requested_relief'),limits=('as common scope line; never reaches a conclusion on brief writing, never advises on it.',))
