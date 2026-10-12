"""Connect durable merged Claire jobs to implemented private computations.

No eval, generated source, browser, tools, payment or message adapter. Any
exception from a computation is recorded as a failed computation result, not a hidden
retry. If the result cannot be stored (lease expired, stale version, result not
serializable), the outcome is returned with status result_not_persisted instead of raised.
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
    except Exception as exc:
        outcome=_failure(exc)
    try:
        queue.finish(row['id'],worker,row['version'],outcome)
    except Exception as store_exc:
        fallback=_failure(store_exc,'result could not be stored: ')
        try:queue.finish(row['id'],worker,row['version'],fallback);outcome=fallback
        except Exception:
            return {'id':row['id'],'status':'result_not_persisted','outcome':outcome,'persist_error_type':type(store_exc).__name__,'persist_error':str(store_exc),'external_effects':[]}
    return queue.get(row['id'])


def _failure(exc,prefix=''):
    return {'status':'computation_failed','error_type':type(exc).__name__,'error':prefix+str(exc),'external_effects':[]}
