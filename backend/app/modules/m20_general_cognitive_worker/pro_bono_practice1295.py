"""Pro Bono Practice: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1295,prefix='PROBON1295:',vocabulary=('scope', 'eligibility_source', 'competence', 'capacity', 'engagement_approval'),limits=('as common scope line; never determines eligibility or accepts an engagement.',))
