"""Reconcile an existing roadmap with supplied dated completion evidence.

Does not verify that the work happened. Avoids repeating completed steps;
rejects future evidence and completion without prerequisite evidence.
"""
from copy import deepcopy
from datetime import date
from urllib.parse import urlsplit


def reconcile(roadmap: dict, curriculum: dict, evidence: list, *, today: date, reflow: bool = False) -> dict:
    if type(today) is not date or type(evidence) is not list or len(evidence) > 10000:
        raise ValueError('dated bounded evidence required')
    from .polymath_roadmap import _check_curriculum
    _, steps = _check_curriculum(curriculum)
    by_id = {s['id']: s for s in steps}
    completed = {}
    for item in evidence:
        if type(item) is not dict or set(item) != {'step_id', 'completed_at', 'artifact_url'}:
            raise ValueError('completion requires step, date and artifact URL')
        sid = item['step_id']
        if type(sid) is not str or sid not in by_id or sid in completed:
            raise ValueError('unknown or duplicate completed step')
        if type(item['completed_at']) is not str:
            raise ValueError('ISO date required')
        day = date.fromisoformat(item['completed_at'])
        if day.isoformat() != item['completed_at']:
            raise ValueError('canonical ISO date required')
        if day > today:
            raise ValueError('future completion refused')
        if type(item['artifact_url']) is not str:
            raise ValueError('HTTPS artifact required')
        parsed = urlsplit(item['artifact_url'])
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('HTTPS artifact required')
        completed[sid] = dict(item)
    for sid, item in completed.items():
        for dep in by_id[sid]['after']:
            if dep not in completed or completed[dep]['completed_at'] > item['completed_at']:
                raise ValueError('completion missing earlier prerequisite evidence')
    if type(reflow) is not bool:
        raise ValueError("boolean reflow required")
    result = deepcopy(roadmap)
    schedule = result.get('schedule')
    if type(schedule) is not dict or type(schedule.get('steps')) is not list:
        raise ValueError('roadmap schedule required')
    if any(type(s) is not dict or s.get('id') not in by_id for s in schedule['steps']):
        raise ValueError('roadmap steps must match curriculum')
    pending = []
    for step in schedule['steps']:
        if step['id'] in completed:
            continue
        step['ready'] = all(dep in completed for dep in by_id[step['id']]['after'])
        pending.append(step)
    if reflow:
        from .polymath_roadmap import _schedule
        weekly, horizon = schedule.get('weekly_hours'), schedule.get('horizon_weeks')
        import math
        if type(weekly) not in (int,float) or not math.isfinite(weekly) or not 0 < weekly <= 168 or type(horizon) is not int or not 1 <= horizon <= 520:
            raise ValueError('bounded weekly hours and horizon required for reflow')
        # Include steps previously beyond horizon, so completing prerequisites
        # can move them into the fresh remaining horizon. Keep original selection.
        selected = {s['id'] for s in pending}
        for item in schedule.get('unscheduled', []):
            if type(item) is not dict or item.get('id') not in by_id:
                raise ValueError('unscheduled steps must match curriculum')
            if item['id'] not in completed: selected.add(item['id'])
        todo = [dict(s,after=[d for d in s['after'] if d not in completed]) for s in steps if s['id'] in selected]
        if any(dep not in selected for s in todo for dep in s['after']):
            raise ValueError('pending curriculum missing prerequisite')
        domains = list(dict.fromkeys(s['domain'] for s in todo))
        new_schedule = _schedule(todo, domains, domains, weekly, horizon)
        new_schedule['remaining_hours'] = new_schedule.pop('total_hours')
        new_schedule['week_basis'] = 'relative to supplied reconciliation date'
        pending = new_schedule['steps']
        for step in pending:step['ready'] = all(d in completed for d in by_id[step['id']]['after'])
        schedule['original_total_hours'] = schedule.pop('total_hours', None)
        schedule.update(new_schedule)
    schedule['steps'] = pending
    result['completion_evidence'] = list(completed.values())
    result['completion_basis'] = 'caller-supplied artifacts, not independently verified'
    result['next_ready'] = [s['id'] for s in pending if s['ready']]
    return result
