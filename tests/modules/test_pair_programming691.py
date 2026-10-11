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


# --- repair pins (second-audit survivors; tests only, runtime frozen) ---

def exact_refusal(p, message):
    with pytest.raises(ValueError) as e:
        collaborate(p)
    assert str(e.value) == message

def test_session_id_refusal_exact_text():
    p = payload(); del p['session_id']
    exact_refusal(p, 'session_id requires bounded nonempty string')

def test_unknown_driver_refusal_exact_text():
    p = payload(); p['rotations'][0]['driver_id'] = 'caro'
    exact_refusal(p, 'rotation driver_id must be one of the participants')

def test_duration_refusal_exact_text():
    p = payload(); p['rotations'][0]['duration_minutes'] = 181
    exact_refusal(p, 'duration_minutes requires 0 < minutes <= 180')

def test_confirmed_refusal_exact_text():
    p = payload(); p['understanding_checks'][0]['confirmed'] = 'yes'
    exact_refusal(p, 'confirmed requires a boolean')

def test_rotation_list_cap_accepts_64_refuses_65():
    rotations = [{'driver_id': 'asha' if i % 2 == 0 else 'biren',
                  'duration_minutes': 1, 'handoff_note': 'n'} for i in range(64)]
    p = payload(); p['rotations'] = rotations
    assert collaborate(p)['rotation_count'] == 64
    p = payload(); p['rotations'] = rotations + [
        {'driver_id': 'biren', 'duration_minutes': 1, 'handoff_note': 'n'}]
    exact_refusal(p, 'rotations requires bounded object list')

def test_understanding_checks_cap_accepts_16_refuses_17():
    checks = [{'item': 'item %d' % i, 'confirmed': True} for i in range(16)]
    p = payload(); p['understanding_checks'] = checks
    assert collaborate(p)['shared_understanding_aligned'] is True
    p = payload(); p['understanding_checks'] = checks + [{'item': 'item 16', 'confirmed': True}]
    exact_refusal(p, 'understanding_checks requires bounded object list')

def test_single_rotation_and_single_check_accepted():
    p = payload()
    p['rotations'] = [{'driver_id': 'asha', 'duration_minutes': 45}]
    p['understanding_checks'] = [{'item': 'goal clear', 'confirmed': True}]
    r = collaborate(p)
    assert r['rotation_count'] == 1 and r['total_minutes'] == 45
    assert r['drive_minutes'] == {'asha': 45, 'biren': 0}
    assert r['status'] == 'session_rotation_gaps'

def test_dominance_just_below_three_quarters_is_balanced():
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 107},
        {'driver_id': 'biren', 'duration_minutes': 36, 'handoff_note': 'x'}]
    r = collaborate(p)
    assert r['drive_share'] == {'asha': 107 / 143, 'biren': 36 / 143}
    assert 0.74 < r['drive_share']['asha'] < 0.75
    assert r['dominant_driver'] is None and r['balanced_rotation'] is True

def test_final_rotation_switch_without_note_flagged():
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 30},
        {'driver_id': 'biren', 'duration_minutes': 30, 'handoff_note': 'x'},
        {'driver_id': 'asha', 'duration_minutes': 30}]
    r = collaborate(p)
    assert r['missing_handoff_indexes'] == [2]
    assert 'missing_handoff_note' in r['gaps']

def test_final_rotation_repeat_flagged():
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 30},
        {'driver_id': 'biren', 'duration_minutes': 30, 'handoff_note': 'x'},
        {'driver_id': 'biren', 'duration_minutes': 30}]
    r = collaborate(p)
    assert r['consecutive_repeat_indexes'] == [2]
    assert 'consecutive_driver_repeat' in r['gaps']

def test_participants_sorted_not_input_order():
    p = payload(); p['participants'] = ['biren', 'asha']
    r = collaborate(p)
    assert r['participants'] == ['asha', 'biren']
    assert list(r['drive_minutes']) == ['asha', 'biren']
    assert list(r['drive_share']) == ['asha', 'biren']

def test_same_driver_without_note_is_not_switch_gap():
    # missing-note condition: first half FALSE (no switch), second half TRUE (note absent)
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 30},
        {'driver_id': 'asha', 'duration_minutes': 30}]
    r = collaborate(p)
    assert r['missing_handoff_indexes'] == []
    assert 'missing_handoff_note' not in r['gaps']

def test_switch_with_note_is_not_switch_gap():
    # missing-note condition: second half FALSE (note present), first half TRUE (a switch)
    p = payload()
    assert collaborate(p)['missing_handoff_indexes'] == []

def test_envelope_keys_exact():
    r = collaborate(payload())
    assert set(r) == {'session_id', 'task', 'participants', 'rotation_count',
                      'total_minutes', 'drive_minutes', 'drive_share',
                      'dominant_driver', 'never_drove', 'consecutive_repeat_indexes',
                      'missing_handoff_indexes', 'unconfirmed_understanding_items',
                      'balanced_rotation', 'shared_understanding_aligned', 'gaps',
                      'status', 'collaboration_observed', 'code_changes_made',
                      'source_truth_verified', 'boundary'}


# --- second-audit pins round 2 (peer-corrected mapping; tests only, runtime frozen) ---

def test_task_refusal_exact_text():
    p = payload(); del p['task']
    exact_refusal(p, 'task requires bounded nonempty string')

def test_rotations_refusal_exact_text():
    p = payload(); del p['rotations']
    exact_refusal(p, 'rotations requires bounded object list')

def test_handoff_note_type_refusal_exact_text():
    p = payload(); p['rotations'][1]['handoff_note'] = 123
    exact_refusal(p, 'handoff_note requires bounded nonempty string')

def test_balanced_rotation_dominant_set_never_empty_is_unbalanced():
    # AND half 1 FALSE: dominant driver set, nobody idle -> not balanced
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 45},
        {'driver_id': 'biren', 'duration_minutes': 15, 'handoff_note': 'x'}]
    r = collaborate(p)
    assert r['dominant_driver'] == 'asha' and r['never_drove'] == []
    assert r['balanced_rotation'] is False

def test_balanced_rotation_no_dominant_but_never_drove_is_unbalanced(monkeypatch):
    # AND half 2 FALSE: no dominant driver, but a participant never drove.
    # Unreachable with the 0.75 threshold and exactly 2 participants, so the
    # threshold constant is raised to pin the half deterministically.
    import app.modules.m20_general_cognitive_worker.pair_programming691 as pp691
    monkeypatch.setattr(pp691, 'DOMINANT_SHARE', 1.1)
    p = payload(); p['rotations'] = [
        {'driver_id': 'asha', 'duration_minutes': 30},
        {'driver_id': 'asha', 'duration_minutes': 30}]
    r = collaborate(p)
    assert r['dominant_driver'] is None and r['never_drove'] == ['biren']
    assert r['balanced_rotation'] is False
    assert 'driver_never_rotated' in r['gaps']

def test_participants_sorted_contract_seed_independent(monkeypatch):
    # Patch the module's own keys() binding (imported at module line 12 from
    # .anchored_assessment) to return a deterministic unsorted LIST, so the
    # sorted() output contract is checked without set-hash involvement.
    import app.modules.m20_general_cognitive_worker.pair_programming691 as pp691
    monkeypatch.setattr(pp691, 'keys', lambda *a, **kw: ['zed', 'amy'])
    p = payload(); p['participants'] = ['zed', 'amy']
    p['rotations'] = [
        {'driver_id': 'zed', 'duration_minutes': 30},
        {'driver_id': 'amy', 'duration_minutes': 30, 'handoff_note': 'x'}]
    r = collaborate(p)
    assert r['participants'] == ['amy', 'zed']
    assert list(r['drive_minutes']) == ['amy', 'zed']
    assert list(r['drive_share']) == ['amy', 'zed']
