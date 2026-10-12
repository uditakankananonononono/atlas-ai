"""Connect durable merged Claire jobs to implemented private computations.

No eval, generated source, browser, tools, payment or message adapter. Runtime
exceptions are recorded as failed computation results, not hidden retries.
"""
from .exact_math import analyze
from .robust_strategy import optimize
from .enclosure import generate
from .patent_preparation import prepare
from .admissions_training import fit


def execute_one(queue,worker):
    row=queue.claim(worker)
    if row is None:return None
    try:
        handlers={'polynomial':analyze,'strategy':optimize,'enclosure':generate,'patent_prepare':prepare}
        if row['task']=='admissions_topic_train':
            if row['payload'].get('owner_consented') is not True:raise PermissionError('explicit owner consent required')
            result=fit(row['payload']['corpus'],row['payload']['sources'])
        else:result=handlers[row['task']](row['payload'])
        outcome={'status':'computed','result':result,'external_effects':[]}
    except (ValueError,TypeError,KeyError,PermissionError,AttributeError) as exc:
        outcome={'status':'computation_failed','error_type':type(exc).__name__,'error':str(exc),'external_effects':[]}
    queue.finish(row['id'],worker,row['version'],outcome)
    return queue.get(row['id'])
