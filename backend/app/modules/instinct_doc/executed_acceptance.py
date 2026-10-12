"""Execute source-line-bound scoped checks; do not certify semantic fulfillment."""
from pathlib import Path
from .repo_evidence import source_inventory, execute_tests, EvidenceError


def audit_selected_checks(root, source_path, checks):
    root = Path(root).resolve()
    source = source_inventory(root, source_path)
    lines = {row['id']: row['sha256'] for row in source['rows']}
    if type(checks) is not list or len(checks) > 1000:
        raise EvidenceError('checks must be a bounded list')
    seen, bindings = set(), {}
    for check in checks:
        if type(check) is not dict or set(check) != {'id', 'line_id', 'line_sha256', 'test_paths'}:
            raise EvidenceError('check fields must be exact')
        ident = check['id']
        if not isinstance(ident, str) or not ident.strip() or len(ident) > 128 or ident in seen:
            raise EvidenceError('invalid or duplicate check id')
        seen.add(ident)
        if not isinstance(check['line_id'], str) or lines.get(check['line_id']) != check['line_sha256']:
            raise EvidenceError('source line hash mismatch')
        run = execute_tests(root, check['test_paths'])
        bindings.setdefault(check['line_id'], []).append({'id': ident, 'run': run})
    rows = []
    for line_id, sha in lines.items():
        executions = bindings.get(line_id, [])
        passed = bool(executions) and all(item['run']['status'] == 'SCOPED_PASS' for item in executions)
        rows.append({'line_id': line_id, 'line_sha256': sha,
                     'check_status': 'SCOPED_PASS' if passed else 'UNVERIFIED',
                     'checks': executions, 'semantic_fulfillment_verified': False,
                     'reason': 'Selected tests pass; semantic acceptance not independently established' if passed else 'Missing or nonpassing selected check'})
    blockers = [{'line_id': row['line_id'], 'status': 'UNVERIFIED',
                 'reason': row['reason']} for row in rows]
    return {'lines': rows, 'blockers': blockers,
            'scoped_passing_lines': sum(row['check_status'] == 'SCOPED_PASS' for row in rows),
            'semantic_verified_lines': 0, 'dependency_scope_verified': False,
            'candy_gate': {'release': False, 'reason': 'Semantic line fulfillment and dependency scope remain unverified'},
            'boundary': 'Executed selected tests bound to current source hashes only; declared test/line correspondence is not semantic proof.'}
