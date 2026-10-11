"""Attorney-Client Privilege: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1293,prefix='ATTORN1293:',vocabulary=('communication', 'participants', 'purpose', 'confidentiality', 'waiver', 'exceptions'),limits=('as common scope line; never determines that privilege applies, is waived or is preserved.',))
