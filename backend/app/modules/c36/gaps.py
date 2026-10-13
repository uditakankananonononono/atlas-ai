"""S5.2 supplied occupation/task proposal coverage, never execution coverage.

No fetching, classification heuristic, worker dispatch, router or external effect.
References are supplied unverified provenance, not evidence of successful automation.
"""
from datetime import date
from app.modules.c30 import policy

PREFIX = 'VENT'
_FORBIDDEN = {'spend':'spend', 'purchase':'spend', 'send':'outreach',
              'submit':'outreach', 'outreach':'outreach', 'fake_accounts':'fakeacct',
              'autopost':'autopost', 'scrape':'scrape', 'trade':'trade'}


def _fail(reason):
    raise ValueError(PREFIX + '_REFUSED_' + reason)


def _record(value, fields, name):
    # Do not inspect arbitrary objects or iterate container subclasses.
    if type(value) is not dict:
        _fail('BAD_TYPE:' + name)
    if len(value) > 32:
        _fail('OVERSIZE:' + name)
    for key in value:
        policy.clean_text(key, PREFIX, 'key', 128)
        normalized = key.casefold().replace('-', '_')
        if normalized in _FORBIDDEN:
            policy.check(_FORBIDDEN[normalized], PREFIX)
    if set(value) - set(fields):
        _fail('UNKNOWN:' + name)
    for field in fields:
        if field not in value:
            _fail('MISSING:' + field)
    return value


def _list(value, limit, name, nonempty=False):
    if type(value) is not list:
        _fail('BAD_TYPE:' + name)
    if len(value) > limit:
        _fail('OVERSIZE:' + name)
    if nonempty and not value:
        _fail('EMPTY:' + name)
    return value


def _text(value, name, limit):
    return policy.clean_text(value, PREFIX, name, limit)


def _texts(value, limit, name):
    values = [_text(v, name, 500) for v in _list(value, limit, name, True)]
    if len(set(values)) != len(values):
        _fail('DUPLICATE:' + name)
    return sorted(values)


def run(request):
    """Map explicitly linked proposals to supplied taxonomy and expose gaps.

    A 'covered' task means it has a supplied proposal, not proven automation.
    Occupation coverage means at least one task has a proposal. Empty
    denominators produce None, not 100%. IDs match byte-exactly.
    """
    _record(request, ('as_of', 'taxonomy_source', 'occupations', 'opportunities'), 'request')
    as_of = _text(request['as_of'], 'as_of', 10)
    try:
        if len(as_of) != 10 or date.fromisoformat(as_of).isoformat() != as_of:
            _fail('BAD_DATE:as_of')
    except ValueError:
        _fail('BAD_DATE:as_of')
    source = _text(request['taxonomy_source'], 'taxonomy_source', 500)
    occupations = _list(request['occupations'], 2000, 'occupations')
    opportunities = _list(request['opportunities'], 10000, 'opportunities')
    taxonomy = {}
    for occupation in occupations:
        _record(occupation, ('id', 'title', 'tasks'), 'occupation')
        oid = _text(occupation['id'], 'occupation_id', 128)
        title = _text(occupation['title'], 'occupation_title', 500)
        if oid in taxonomy:
            _fail('DUPLICATE:occupation_id')
        tasks = {}
        for task in _list(occupation['tasks'], 200, 'tasks'):
            _record(task, ('id', 'text'), 'task')
            tid = _text(task['id'], 'task_id', 128)
            text = _text(task['text'], 'task_text', 2000)
            if tid in tasks:
                _fail('DUPLICATE:task_id')
            tasks[tid] = {'id': tid, 'text': text, 'opportunity_ids': []}
        taxonomy[oid] = {'occupation_id': oid, 'title': title, 'tasks': tasks,
                         'opportunity_ids': []}
    proposed = {}
    for opportunity in opportunities:
        _record(opportunity, ('id', 'occupation_id', 'task_ids', 'proposal', 'evidence_refs'), 'opportunity')
        pid = _text(opportunity['id'], 'opportunity_id', 128)
        oid = _text(opportunity['occupation_id'], 'occupation_id', 128)
        task_ids = _texts(opportunity['task_ids'], 200, 'task_ids')
        proposal = _text(opportunity['proposal'], 'proposal', 4000)
        evidence = _texts(opportunity['evidence_refs'], 20, 'evidence_refs')
        if pid in proposed:
            _fail('DUPLICATE:opportunity_id')
        if oid not in taxonomy:
            _fail('UNKNOWN_OCCUPATION')
        if any(tid not in taxonomy[oid]['tasks'] for tid in task_ids):
            _fail('UNKNOWN_TASK')
        proposed[pid] = {'id': pid, 'occupation_id': oid, 'task_ids': task_ids,
                         'proposal': proposal, 'evidence_refs': evidence,
                         'status': 'proposed_unverified'}
        taxonomy[oid]['opportunity_ids'].append(pid)
        for tid in task_ids:
            taxonomy[oid]['tasks'][tid]['opportunity_ids'].append(pid)
    mapped, gaps = [], []
    task_total = task_covered = occupation_covered = 0
    for oid in sorted(taxonomy):
        row = taxonomy[oid]
        row['opportunity_ids'].sort()
        tasks = [row['tasks'][tid] for tid in sorted(row['tasks'])]
        missing = []
        for task in tasks:
            task['opportunity_ids'].sort()
            task_total += 1
            if task['opportunity_ids']:
                task_covered += 1
            else:
                missing.append(task['id'])
        if row['opportunity_ids']:
            occupation_covered += 1
        if missing or not tasks:
            gaps.append({'occupation_id': oid, 'task_ids': missing})
        mapped.append({**row, 'tasks': tasks})
    occupation_total = len(taxonomy)
    return {'taxonomy_source': source, 'mapping': mapped, 'gaps': gaps,
            'opportunities': [proposed[pid] for pid in sorted(proposed)],
            'coverage': {'occupations_supplied': occupation_total,
                         'occupations_with_proposals': occupation_covered,
                         'occupation_percent': 100 * occupation_covered / occupation_total if occupation_total else None,
                         'tasks_supplied': task_total, 'tasks_with_proposals': task_covered,
                         'task_percent': 100 * task_covered / task_total if task_total else None},
            'coverage_basis': 'explicit supplied proposal links; occupation requires at least one linked task',
            'proposal_evidence': 'supplied_unverified', 'execution_coverage_verified': False,
            'scope': policy.scope(['explicit supplied occupation/task proposal mapping and gaps'],
                                  ['execution', 'feasibility verification', 'all jobs on earth',
                                   'taxonomy fetching', 'proposal discovery', 'routes'],
                                  'supplied taxonomy and proposals', as_of)}
