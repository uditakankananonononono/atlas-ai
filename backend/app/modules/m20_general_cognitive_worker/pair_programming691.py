"""Row 691 Pair Programming: bounded session-rotation and alignment checks.

Pair programming is two people collaborating on one task with rotating
driver/navigator roles. This engine takes a caller-supplied session record
(participants, timed driver rotations, switch handoff notes and shared
understanding checks) and computes the practice diagnostics: drive-time
balance, rotation alternation, handoff coverage and confirmed alignment.
It validates supplied records only; it neither observes collaboration nor
changes code.
"""
from .calibration_predictor import number, text
from .anchored_assessment import keys, rows

DOMINANT_SHARE = 0.75
MAX_ROTATION_MINUTES = 180


def collaborate(payload):
    session = text(payload.get('session_id'), 'session_id')
    task = text(payload.get('task'), 'task')
    participants = keys(payload.get('participants'), 'participants', minimum=2, maximum=2)
    rotations = []
    for row in rows(payload.get('rotations'), 'rotations', minimum=1, maximum=64):
        driver = text(row.get('driver_id'), 'rotation driver_id')
        if driver not in participants:
            raise ValueError('rotation driver_id must be one of the participants')
        minutes = number(row.get('duration_minutes'), 'duration_minutes')
        if not 0 < minutes <= MAX_ROTATION_MINUTES:
            raise ValueError('duration_minutes requires 0 < minutes <= 180')
        note = row.get('handoff_note')
        rotations.append({'driver_id': driver, 'duration_minutes': minutes,
                          'handoff_note': None if note is None else text(note, 'handoff_note')})
    checks = []
    for row in rows(payload.get('understanding_checks'), 'understanding_checks', minimum=1, maximum=16):
        item = text(row.get('item'), 'understanding item')
        confirmed = row.get('confirmed')
        if type(confirmed) is not bool:
            raise ValueError('confirmed requires a boolean')
        checks.append({'item': item, 'confirmed': confirmed})
    ordered = sorted(participants)
    drive = {name: 0 for name in ordered}
    for rotation in rotations:
        drive[rotation['driver_id']] += rotation['duration_minutes']
    total = sum(drive.values())
    share = {name: minutes / total for name, minutes in drive.items()}
    dominant = next((name for name in ordered if share[name] >= DOMINANT_SHARE), None)
    never = [name for name in ordered if drive[name] == 0]
    repeats = [i for i in range(1, len(rotations))
               if rotations[i]['driver_id'] == rotations[i - 1]['driver_id']]
    missing_notes = [i for i in range(1, len(rotations))
                     if rotations[i]['driver_id'] != rotations[i - 1]['driver_id']
                     and rotations[i]['handoff_note'] is None]
    unconfirmed = [c['item'] for c in checks if not c['confirmed']]
    gaps = []
    if dominant is not None:
        gaps.append('dominant_driver')
    if never:
        gaps.append('driver_never_rotated')
    if repeats:
        gaps.append('consecutive_driver_repeat')
    if missing_notes:
        gaps.append('missing_handoff_note')
    if unconfirmed:
        gaps.append('unconfirmed_understanding')
    return {'session_id': session, 'task': task, 'participants': ordered,
            'rotation_count': len(rotations), 'total_minutes': total,
            'drive_minutes': drive, 'drive_share': share,
            'dominant_driver': dominant, 'never_drove': never,
            'consecutive_repeat_indexes': repeats,
            'missing_handoff_indexes': missing_notes,
            'unconfirmed_understanding_items': unconfirmed,
            'balanced_rotation': dominant is None and not never,
            'shared_understanding_aligned': not unconfirmed,
            'gaps': gaps,
            'status': 'session_rotation_sound' if not gaps else 'session_rotation_gaps',
            'collaboration_observed': False, 'code_changes_made': False,
            'source_truth_verified': False,
            'boundary': 'Caller-supplied session records are checked for rotation balance, '
                        'alternation, switch handoff notes and confirmed shared understanding. '
                        'These are checks over supplied records only: no collaboration is '
                        'observed, no code is written or changed, and the records themselves '
                        'are not verified as true.'}
