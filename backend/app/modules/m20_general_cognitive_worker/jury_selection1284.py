"""Jury Selection: supplied reference declarations only."""
from .legal_a3_engine import run_bound as _run_bound

def run(request):
 return _run_bound(request,row=1284,prefix='JURYSE1284:',vocabulary=('case_neutral_topics', 'cause_grounds', 'equal_protection_review'),limits=('as common scope line; topics are case-neutral by caller declaration only; no juror profiling by protected class, no scoring or ranking of persons.',))
