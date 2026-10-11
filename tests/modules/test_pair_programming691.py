"""Row 691 Pair Programming: bounded session-rotation and alignment diagnostics."""
import pytest
from app.modules.m20_general_cognitive_worker.pair_programming691 import collaborate

def payload():
    return {'session_id': 's1', 'task': 'implement rate limiter',
            'participants': ['asha', 'biren'],
            'rotations': [
                {'driver_id': 'asha', 'duration_minutes': 30},
                {'driver_id': 'biren', 'duration_minutes': 30, 'handoff_note': 'tests red on burst'},
                {'driver_id': 'asha', 'duration_minutes': 30, 'handoff_note': 'limiter skeleton up'},
                {'driver_id': 'biren', 'duration_minutes': 30, 'handoff_note': 'edge case list'}],
            'understanding_checks': [
                {'item': 'both can state the goal', 'confirmed': True},
                {'item': 'both agree on next step', 'confirmed': True}]}

def test_sound_session_exact_envelope():
    r = collaborate(payload())
    assert r == {'session_id': 's1', 'task': 'implement rate limiter',
        'participants': ['asha', 'biren'], 'rotation_count': 4, 'total_minutes': 120,
        'drive_minutes': {'asha': 60, 'biren': 60}, 'drive_share': {'asha': 0.5, 'biren': 0.5},
        'dominant_driver': None, 'never_drove': [], 'consecutive_repeat_indexes': [],
        'missing_handoff_indexes': [], 'unconfirmed_understanding_items': [],
        'balanced_rotation': True, 'shared_understanding_aligned': True, 'gaps': [],
        'status': 'session_rotation_sound', 'collaboration_observed': False,
        'code_changes_made': False, 'source_truth_verified': False,
        'boundary': 'Caller-supplied session records are checked for rotation balance, '
        'alternation, switch handoff notes and confirmed shared understanding. These are '
        'checks over supplied records only: no collaboration is observed, no code is '
        'written or changed, and the records themselves are not verified as true.'}

def test_dominant_driver_at_three_quarter_share():
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 45},
        {'driver_id': 'biren', 'duration_minutes': 15, 'handoff_note': 'x'}]
    r = collaborate(p)
    assert r['drive_share'] == {'asha': 0.75, 'biren': 0.25}
    assert r['dominant_driver'] == 'asha' and r['balanced_rotation'] is False
    assert 'dominant_driver' in r['gaps'] and r['status'] == 'session_rotation_gaps'

def test_below_three_quarter_share_is_balanced():
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 44},
        {'driver_id': 'biren', 'duration_minutes': 16, 'handoff_note': 'x'}]
    r = collaborate(p)
    assert r['dominant_driver'] is None and r['balanced_rotation'] is True

def test_consecutive_driver_repeat_flagged():
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 30},
        {'driver_id': 'asha', 'duration_minutes': 30, 'handoff_note': 'x'},
        {'driver_id': 'biren', 'duration_minutes': 60, 'handoff_note': 'y'}]
    r = collaborate(p)
    assert r['consecutive_repeat_indexes'] == [1]
    assert 'consecutive_driver_repeat' in r['gaps']

def test_switch_without_handoff_note_flagged():
    p = payload(); del p['rotations'][1]['handoff_note']
    r = collaborate(p)
    assert r['missing_handoff_indexes'] == [1]
    assert 'missing_handoff_note' in r['gaps']

def test_participant_who_never_drives_flagged():
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 20},
        {'driver_id': 'asha', 'duration_minutes': 20, 'handoff_note': 'x'}]
    r = collaborate(p)
    assert r['never_drove'] == ['biren'] and r['drive_minutes']['biren'] == 0
    assert 'driver_never_rotated' in r['gaps'] and r['balanced_rotation'] is False

def test_unconfirmed_understanding_listed():
    p = payload(); p['understanding_checks'][1]['confirmed'] = False
    r = collaborate(p)
    assert r['unconfirmed_understanding_items'] == ['both agree on next step']
    assert r['shared_understanding_aligned'] is False
    assert 'unconfirmed_understanding' in r['gaps']

def test_duration_bounds_accept_180():
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 180},
        {'driver_id': 'biren', 'duration_minutes': 180, 'handoff_note': 'x'}]
    assert collaborate(p)['total_minutes'] == 360

def error(p, fragment):
    with pytest.raises(ValueError) as e:
        collaborate(p)
    assert fragment in str(e.value)

def test_refusals():
    error({'task': 'x', 'participants': ['a', 'b'], 'rotations': [{'driver_id': 'a', 'duration_minutes': 5}],
           'understanding_checks': [{'item': 'i', 'confirmed': True}]}, 'session_id')
    p = payload(); p['participants'] = ['asha']; error(p, 'participants')
    p = payload(); p['participants'] = ['asha', 'biren', 'caro']; error(p, 'participants')
    p = payload(); p['participants'] = ['asha', 'asha']; error(p, 'unique')
    p = payload(); p['rotations'] = []; error(p, 'rotations')
    p = payload(); p['rotations'][0]['driver_id'] = 'caro'; error(p, 'participant')
    p = payload(); p['rotations'][0]['duration_minutes'] = 0; error(p, 'duration_minutes')
    p = payload(); p['rotations'][0]['duration_minutes'] = 181; error(p, 'duration_minutes')
    p = payload(); p['rotations'][0]['duration_minutes'] = '30'; error(p, 'duration_minutes')
    p = payload(); p['understanding_checks'] = []; error(p, 'understanding_checks')
    p = payload(); p['understanding_checks'][0]['confirmed'] = 'yes'; error(p, 'confirmed')
    p = payload(); p['understanding_checks'][0]['item'] = ''; error(p, 'item')
