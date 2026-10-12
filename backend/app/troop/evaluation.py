"""Execute the same frozen cases against actual runner objects.

Scores are recomputed, never accepted from supplied score labels. A result
only compares these cases and these adapters, not products as a whole.
Run only trusted registered adapters: this is not a code sandbox.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from time import perf_counter


def evaluate(runners: dict, cases: list) -> dict:
    if type(runners) is not dict or not 2 <= len(runners) <= 16:
        raise ValueError("two to sixteen registered runners required")
    if any(type(name) is not str or not name.strip() or len(name) > 128
           or not callable(getattr(runner, 'run', None)) for name, runner in runners.items()):
        raise ValueError("named executable runners required")
    if type(cases) is not list or not 1 <= len(cases) <= 1000:
        raise ValueError("one to 1000 frozen cases required")
    for case in cases:
        if type(case) is not dict or set(case) != {'task', 'expected'}:
            raise ValueError("case requires task and expected outputs")
        if type(case['task']) is not dict or not case['task'].get('id'):
            raise ValueError("case task id required")
        if type(case['expected']) is not dict or not case['expected']:
            raise ValueError("nonempty expected outputs required")
    ids = [c['task']['id'] for c in cases]
    if any(type(i) is not str for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("unique string case ids required")
    raw = json.dumps(cases, sort_keys=True, allow_nan=False, separators=(',', ':'))
    frozen = json.loads(raw)
    rows = []
    for name, runner in sorted(runners.items()):
        trials = []
        for case in frozen:
            start = perf_counter()
            try:
                result = runner.run(deepcopy(case['task']))
                # JSON canonicalization handles equivalent tuple/list outputs.
                checks = {key: key in result.outputs and
                          json.loads(json.dumps(result.outputs[key], allow_nan=False)) == expected
                          for key, expected in case['expected'].items()}
                passed = result.status == 'completed' and all(checks.values())
                trial = {'case_id': case['task']['id'], 'passed': passed,
                         'checks': checks, 'run_status': result.status,
                         'attempts': dict(result.attempts)}
            except Exception as exc:
                trial = {'case_id': case['task']['id'], 'passed': False,
                         'error_type': type(exc).__name__}
            trial['seconds'] = perf_counter() - start
            trials.append(trial)
        passed = sum(t['passed'] for t in trials)
        rows.append({'runner': name, 'passed': passed, 'total': len(trials),
                     'pass_rate': passed / len(trials), 'trials': trials})
    return {'cases_sha256': hashlib.sha256(raw.encode()).hexdigest(), 'results': rows,
            'scope': 'Executed registered runners on supplied frozen cases only. '
                     'No Cellcog, Strawberry or YC product superiority claim.'}
