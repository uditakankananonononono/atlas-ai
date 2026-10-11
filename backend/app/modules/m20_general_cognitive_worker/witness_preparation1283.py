"""Witness Preparation: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1283,prefix='WITNES1283:',vocabulary=('firsthand_recollection', 'documents', 'uncertainty', 'prohibited_coaching'),limits=('as common scope line; never scripts, rehearses or shapes testimony; prohibited_coaching is a declared element, not a coaching function.',))
