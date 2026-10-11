"""Conflicts of Interest: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1292,prefix='CONFLI1292:',vocabulary=('clients', 'former_clients', 'adverse_parties', 'matters', 'consent_questions'),limits=('as common scope line; never clears or declares a conflict or its absence.',))
