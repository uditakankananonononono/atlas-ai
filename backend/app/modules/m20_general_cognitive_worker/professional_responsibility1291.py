"""Professional Responsibility: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1291,prefix='PROFES1291:',vocabulary=('competence', 'diligence', 'candor', 'supervision', 'communication'),limits=("as common scope line; never assesses a lawyer's compliance.",))
