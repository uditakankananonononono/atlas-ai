"""Legal Writing: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1286,prefix='LEGALW1286:',vocabulary=('question', 'short_answer_alternatives', 'facts', 'sourced_rules', 'analysis_gaps'),limits=('as common scope line; never reaches a conclusion on legal writing, never advises on it.',))
