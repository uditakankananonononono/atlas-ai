"""Execute source-line-bound scoped checks; do not certify semantic fulfillment."""
from pathlib import Path
from .repo_evidence import source_inventory, execute_tests, EvidenceError, snapshot, safe_file


def audit_selected_checks(root, source_path, checks):
    root = Path(root).resolve()
    source = source_inventory(root, source_path)
    lines = {row['id']: row['sha256'] for row in source['rows']}
    if type(checks) is not list or len(checks) > 1000:
        raise EvidenceError('checks must be a bounded list')
    snap = snapshot(root)
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
        paths = check['test_paths']
        if type(paths) is not list or not 1 <= len(paths) <= 100 or not all(isinstance(path, str) for path in paths):
            raise EvidenceError('test paths must be bounded nonempty lists')
        for path in paths:
            file = safe_file(root, path)
            if path not in snap['files'] or not path.startswith('tests/') or not file.name.startswith('test_') or file.suffix != '.py':
                raise EvidenceError('selected tests must be tracked test files')
    for check in checks:
        ident = check['id']
        try:
            run = execute_tests(root, check['test_paths'])
        except Exception as exc:
            run = {'status': 'UNVERIFIED', 'head': None, 'tree_digest': None, 'error': type(exc).__name__}
        bindings.setdefault(check['line_id'], []).append({'id': ident, 'run': run})
    after = source_inventory(root, source_path)
    source_stable = after['sha256'] == source['sha256'] and after['rows'] == source['rows']
    rows = []
    for line_id, sha in lines.items():
        executions = bindings.get(line_id, [])
        passed = bool(executions) and source_stable and all(item['run']['status'] == 'SCOPED_PASS' and item['run'].get('head') == snap['head'] and item['run'].get('tree_digest') == snap['tree_digest'] for item in executions)
        rows.append({'line_id': line_id, 'line_sha256': sha,
                     'check_status': 'SCOPED_PASS' if passed else 'UNVERIFIED',
                     'checks': executions, 'semantic_fulfillment_verified': False, 'test_line_pairing_verified': False,
                     'reason': 'Scoped execution observed; semantic acceptance remains a separate blocker' if passed else 'Missing or nonpassing selected check'})
    blockers = [{'line_id': row['line_id'], 'status': 'UNVERIFIED',
                 'reason': row['reason']} for row in rows]
    return {'source_path': source_path, 'source_sha256': source['sha256'],
            'head': snap['head'], 'tree_digest': snap['tree_digest'], 'dirty': snap['dirty'],
            'source_stable_after_runs': source_stable,
            'aggregate_budget_enforced': False, 'execution_is_sandboxed': False,
            'execution_scope': 'Trusted checkout; at most 1000 per-run bounded calls, no aggregate time/disk budget.',
            'lines': rows, 'blockers': blockers,
            'scoped_passing_lines': sum(row['check_status'] == 'SCOPED_PASS' for row in rows),
            'semantic_verified_lines': 0, 'dependency_scope_verified': False,
            'candy_gate': {'release': False, 'reason': 'Release is intentionally disabled: this API has no authenticated semantic evidence channel; passing declared check mappings cannot enable it'},
            'boundary': 'Executed selected tests bound to current source hashes only; declared test/line correspondence is not semantic proof.'}
