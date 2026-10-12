"""Repeated selected-test timings, not field-leading benchmark certification."""
from pathlib import Path
from statistics import median
from .repo_evidence import execute_tests, EvidenceError, safe_file, snapshot
import math


def compare_selected_tests(root, subjects, repeats=3):
    """Run each explicit test selection repeatedly and retain returned bounded receipts.

    No caller-supplied scores or comparator victories. Timings are local and
    workload-dependent. Passing different tests is not comparable task quality.
    """
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise EvidenceError('repeats must be 1..5')
    if type(subjects) is not list or not 2 <= len(subjects) <= 10:
        raise EvidenceError('select 2..10 subjects')
    root = Path(root).resolve()
    snap = snapshot(root)
    seen, rows = set(), []
    for subject in subjects:
        if type(subject) is not dict or set(subject) != {'id', 'test_paths'}:
            raise EvidenceError('subject fields must be exact')
        ident = subject['id']
        if not isinstance(ident, str) or not ident.strip() or len(ident) > 128 or ident in seen:
            raise EvidenceError('invalid or duplicate subject id')
        seen.add(ident)
        paths = subject['test_paths']
        if type(paths) is not list or not 1 <= len(paths) <= 100 or not all(isinstance(p, str) for p in paths):
            raise EvidenceError('subject test paths must be a bounded nonempty list')
        for path in paths:
            p = safe_file(root, path)
            if path not in snap['files'] or not path.startswith('tests/') or not p.name.startswith('test_') or p.suffix != '.py':
                raise EvidenceError('subject tests must be tracked tests/test_*.py files')
    for subject in subjects:
        ident = subject['id']
        runs = []
        for _ in range(repeats):
            try:
                receipt = execute_tests(root, subject['test_paths'])
                if type(receipt) is not dict or not all(isinstance(receipt.get(key), str) for key in ('head', 'tree_digest', 'status')) or type(receipt.get('duration_seconds')) not in (int, float):
                    raise EvidenceError('malformed execution receipt')
                duration = float(receipt['duration_seconds'])
                if not math.isfinite(duration) or duration < 0:
                    raise EvidenceError('invalid duration')
                receipt['duration_seconds'] = duration
                runs.append(receipt)
            except Exception as exc:
                runs.append({'status': 'UNVERIFIED', 'head': None, 'tree_digest': None,
                             'duration_seconds': None, 'error': type(exc).__name__})
        coherent = len({(run['head'], run['tree_digest']) for run in runs}) == 1
        passed = coherent and all(run['status'] == 'SCOPED_PASS' and type(run['duration_seconds']) in (int, float) and math.isfinite(run['duration_seconds']) and run['duration_seconds'] >= 0 for run in runs)
        rows.append({'id': ident, 'runs': runs, 'status': 'SCOPED_PASS' if passed else 'UNVERIFIED',
                     'median_seconds': sorted(run['duration_seconds'] for run in runs)[len(runs)//2] if passed else None,
                     'semantic_workload_equivalence_verified': False, 'field_leader_verified': False})
    snapshots = {(run['head'], run['tree_digest']) for row in rows for run in row['runs']}
    try:
        final = snapshot(root)
        final_stable = final['head'] == snap['head'] and final['tree_digest'] == snap['tree_digest'] and final['status_digest'] == snap['status_digest']
    except Exception:
        final_stable = False
    cross_coherent = final_stable and len(snapshots) == 1 and next(iter(snapshots)) == (snap['head'], snap['tree_digest'])
    if not cross_coherent:
        for row in rows:
            row['status'], row['median_seconds'] = 'UNVERIFIED', None
    return {'final_snapshot_stable': final_stable, 'cross_subject_coherent': cross_coherent,
            'aggregate_budget_enforced': False, 'execution_is_sandboxed': False,
            'rehash_boundary': 'Before/after snapshots are not atomic and cannot prove absence of transient restored changes.',
            'duration_summary': 'Upper middle observed duration; avoids averaging overflow for even repeats',
            'execution_scope': 'Trusted checkout only. At most 50 per-run bounded calls; no aggregate time/disk budget. Test code can have effects. Returned output may be truncated.',
            'subjects': rows, 'repeats': repeats, 'winner': None,
            'benchmark_victory_verified': False,
            'boundary': 'Executed local test timing observations only; different selections are not equivalent workloads or leading-product benchmarks.'}
