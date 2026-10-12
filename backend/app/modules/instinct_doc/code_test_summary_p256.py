"""P256|L203 - "Output: Code and test summaries," (output-format section).

Pure stdlib, deterministic. Summaries are built from SUPPLIED stats only:
the module never reads a filesystem, runs tests, measures coverage or invents
numbers. A coverage claim with no supplied source refs is marked UNVERIFIED;
refs are recorded, never authenticated, and never verify anything.
"""

MAX_PROJECTS = 256
MAX_REFS = 16
ID_LIMIT = 128
REF_LIMIT = 256
COUNT_LIMIT = 10000000

FIELDS = ("id", "code_files", "code_lines", "test_files", "test_lines",
          "test_cases", "coverage_percent", "source_refs")
COUNT_FIELDS = ("code_files", "code_lines", "test_files", "test_lines", "test_cases")
STATUSES = ("NO_CLAIM", "UNVERIFIED", "EVIDENCE_DECLARED")


def _err(msg):
    return ValueError("P256:" + msg)


def _text(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise _err(f"{name}: expected nonblank string of length 1..{limit}")
    return value


def _count(value, name):
    if type(value) is not int or value < 0 or value > COUNT_LIMIT:
        raise _err(f"{name}: expected integer 0..{COUNT_LIMIT}")
    return value


def _percent(value):
    if value is None:
        return None
    if type(value) not in (int, float) or not 0 <= value <= 100:
        raise _err("coverage_percent: expected null or number 0..100")
    return value


def summarize_projects(projects):
    """Return a canonical summary of supplied per-project code/test stats.

    The input list and records are never mutated. Output ordering is
    canonical: projects sort by case-sensitive Unicode id, source refs sort
    the same way, and totals are exact integer sums.
    """
    if type(projects) is not list or len(projects) > MAX_PROJECTS:
        raise _err(f"projects: expected list of at most {MAX_PROJECTS} records")
    seen = set()
    rows = []
    for project in projects:
        if type(project) is not dict or set(project) != set(FIELDS):
            raise _err("project: exactly " + ",".join(FIELDS) + " required")
        ident = _text(project["id"], "id", ID_LIMIT)
        if ident in seen:
            raise _err(f"duplicate project id: {ident}")
        seen.add(ident)
        counts = {name: _count(project[name], name) for name in COUNT_FIELDS}
        percent = _percent(project["coverage_percent"])
        refs = project["source_refs"]
        if type(refs) is not list or len(refs) > MAX_REFS:
            raise _err(f"source_refs: expected list of at most {MAX_REFS} references")
        checked = []
        for ref in refs:
            ref = _text(ref, "source_ref", REF_LIMIT)
            if ref in checked:
                raise _err(f"duplicate source_ref: {ref}")
            checked.append(ref)
        if percent is None:
            status = "NO_CLAIM"
        elif not checked:
            status = "UNVERIFIED"
        else:
            status = "EVIDENCE_DECLARED"
        rows.append(dict(id=ident, **counts,
                         coverage=dict(percent=percent, status=status,
                                       source_refs=sorted(checked),
                                       caller_declared=True),
                         stats_are_caller_supplied=True))
    rows.sort(key=lambda r: r["id"])
    totals = {name: sum(r[name] for r in rows) for name in COUNT_FIELDS}
    return dict(
        projects=rows,
        totals=totals,
        coverage_counts={s: sum(1 for r in rows if r["coverage"]["status"] == s)
                         for s in STATUSES},
        unverified_coverage_project_ids=[r["id"] for r in rows
                                         if r["coverage"]["status"] == "UNVERIFIED"],
        status="supplied_stats_summary_only",
        stats_measured=False,
        coverage_measured=False,
        evidence_verified=False,
        completeness_verified=False,
        boundary=("Only supplied stats are summarized. Nothing is measured: no "
                  "code is read, no tests are run and no coverage is computed. "
                  "Coverage claims are caller declarations marked UNVERIFIED "
                  "without supplied source refs; refs are recorded, never "
                  "authenticated, and never verify a claim. An empty summary "
                  "does not prove the absence of projects."),
    )


def inspect_projects(root, projects, *, execute=False):
    """Compute selected project file counts and optional test-run observations.

    Project/path mappings are operator scope. This does not authenticate the
    mapping, discover all program projects or certify whole-project fulfillment.
    """
    from pathlib import Path
    from .repo_evidence import safe_file, snapshot, execute_tests, EvidenceError
    if type(execute) is not bool:
        raise _err('execute must be boolean')
    if type(projects) is not list or len(projects) > MAX_PROJECTS:
        raise _err('projects must be a bounded list')
    root = Path(root).resolve()
    snap = snapshot(root)
    rows, seen = [], set()
    for item in projects:
        if type(item) is not dict or set(item) != {'id', 'code_paths', 'test_paths'}:
            raise _err('project fields must be exact')
        ident = _text(item['id'], 'id', ID_LIMIT)
        if ident in seen:
            raise _err('duplicate project id')
        seen.add(ident)
        files, errors = {}, []
        for field in ('code_paths', 'test_paths'):
            paths = item[field]
            if type(paths) is not list or len(paths) > 1000 or not all(isinstance(p, str) for p in paths) or len(set(paths)) != len(paths):
                raise _err('paths must be unique bounded lists')
            for path in paths:
                try:
                    if path not in snap['files']:
                        raise EvidenceError('path is not tracked')
                    data = safe_file(root, path).read_bytes()
                    files[path] = {'lines': len(data.splitlines()), 'sha256': snap['files'][path]['sha256'], 'kind': field}
                except (EvidenceError, OSError, ValueError) as exc:
                    errors.append({'path': path, 'reason': str(exc)[:200]})
        if set(item['code_paths']) & set(item['test_paths']):
            raise _err('code and test paths must not overlap')
        run = None
        if execute and item['test_paths'] and not errors:
            run = execute_tests(root, item['test_paths'])
        rows.append({'id': ident, 'files': files, 'errors': errors,
                     'code_files': sum(v['kind'] == 'code_paths' for v in files.values()),
                     'code_lines': sum(v['lines'] for v in files.values() if v['kind'] == 'code_paths'),
                     'test_files': sum(v['kind'] == 'test_paths' for v in files.values()),
                     'test_lines': sum(v['lines'] for v in files.values() if v['kind'] == 'test_paths'),
                     'execution': run, 'coverage_percent': None,
                     'status': 'SCOPED_PASS' if run and run['status'] == 'SCOPED_PASS' else 'UNVERIFIED',
                     'completion_verified': False,
                     'scope_declared': True})
    return {'projects': rows, 'head': snap['head'], 'tree_digest': snap['tree_digest'], 'dirty': snap['dirty'],
            'boundary': 'Selected tracked source counts and opt-in test execution only; no exhaustive project scope, empirical coverage or whole-project completion.'}
