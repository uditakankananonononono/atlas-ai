"""Execute baseline/candidate evaluators over a declared immutable task suite.

Callables must be host-owned adapters, never source strings from a request.
An error, missing coverage, zero baseline, or regressed module cannot produce
an improvement claim. Metrics measure this suite, not whole-product quality.
"""
import copy
import hashlib
import json
import math
from collections import defaultdict


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def compare(tasks,baseline,candidate):
    if type(tasks) is not list or not 1 <= len(tasks) <= 10000:
        raise ValueError('1..10000 benchmark tasks required')
    ids=set()
    for task in tasks:
        ident=task.get('id');module=task.get('module')
        if type(ident) is not str or not ident.strip() or ident in ids or type(module) is not str or not module.strip():
            raise ValueError('unique task id and module required')
        if 'input' not in task or 'expected' not in task:raise ValueError('input and expected required')
        ids.add(ident)
    pinned=copy.deepcopy(tasks);fingerprint=_digest(pinned)
    rows=[]
    for task in pinned:
        row={'id':task['id'],'module':task['module']}
        for name,adapter in [('baseline',baseline),('candidate',candidate)]:
            try:
                output=adapter(copy.deepcopy(task['input']))
                digest=_digest(output)
                correct=output==task['expected']
                row[name]={'correct':correct,'output_sha256':digest,'error':None}
            except Exception as exc:
                row[name]={'correct':False,'output_sha256':None,'error':type(exc).__name__}
        rows.append(row)
    modules={}
    for module in sorted({t['module'] for t in pinned}):
        selected=[r for r in rows if r['module']==module]
        b=sum(r['baseline']['correct'] for r in selected)/len(selected)
        c=sum(r['candidate']['correct'] for r in selected)/len(selected)
        modules[module]={'cases':len(selected),'baseline_accuracy':b,'candidate_accuracy':c,'delta':c-b,
                         'accuracy_ratio':c/b if b else None,'regressed':c<b}
    failed=any(r[n]['error'] for r in rows for n in ('baseline','candidate'))
    regressed=any(m['regressed'] for m in modules.values())
    improved=any(m['delta']>0 for m in modules.values())
    return {'suite_sha256':fingerprint,'executed_cases':len(rows),'by_module':modules,'cases':rows,
            'scoped_acceptance':not failed and not regressed and improved,
            'any_execution_error':failed,'any_module_regressed':regressed,
            'million_fold_improvement_established':False,'world_class_established':False,
            'scope':'Exact-match quality on caller-declared suite only. No independent benchmark or whole-product certification.'}
