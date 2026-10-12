"""Repeated selected-test timings, not field-leading benchmark certification."""
from pathlib import Path
from statistics import median
from .repo_evidence import execute_tests, EvidenceError


def compare_selected_tests(root, subjects, repeats=3):
    """Run each explicit test selection repeatedly and retain complete receipts.

    No caller-supplied scores or comparator victories. Timings are local and
    workload-dependent. Passing different tests is not comparable task quality.
    """
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise EvidenceError('repeats must be 1..5')
    if type(subjects) is not list or not 2 <= len(subjects) <= 10:
        raise EvidenceError('select 2..10 subjects')
    seen, rows = set(), []
    for subject in subjects:
        if type(subject) is not dict or set(subject) != {'id', 'test_paths'}:
            raise EvidenceError('subject fields must be exact')
        ident = subject['id']
        if not isinstance(ident, str) or not ident.strip() or len(ident) > 128 or ident in seen:
            raise EvidenceError('invalid or duplicate subject id')
        seen.add(ident)
        runs = [execute_tests(Path(root), subject['test_paths']) for _ in range(repeats)]
        coherent = len({(run['head'], run['tree_digest']) for run in runs}) == 1
        passed = coherent and all(run['status'] == 'SCOPED_PASS' for run in runs)
        rows.append({'id': ident, 'runs': runs, 'status': 'SCOPED_PASS' if passed else 'UNVERIFIED',
                     'median_seconds': median(run['duration_seconds'] for run in runs) if passed else None,
                     'semantic_workload_equivalence_verified': False, 'field_leader_verified': False})
    return {'subjects': rows, 'repeats': repeats, 'winner': None,
            'benchmark_victory_verified': False,
            'boundary': 'Executed local test timing observations only; different selections are not equivalent workloads or leading-product benchmarks.'}
