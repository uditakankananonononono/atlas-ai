import pytest
from tests.modules.test_m00_impact_preview import service,PAYLOAD
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalConflictError


def test_concurrent_same_permit_workers_both_execute_local_effect(service, monkeypatch):
    import concurrent.futures
    import threading
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    monkeypatch.setattr(action_registry, '_EXECUTORS', {})
    monkeypatch.setattr('app.modules.m00_approval_center.service.default_service', lambda: service)
    view = service.submit(module_id=5, action_type='fixture_concurrent_worker', payload={}, user_id='udita')
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    barrier = threading.Barrier(2)
    calls = []
    lock = threading.Lock()
    def local_executor(payload):
        barrier.wait(timeout=5)
        with lock:
            calls.append(1)
            return {'calls': len(calls)}
    action_registry.register_executor(5, 'fixture_concurrent_worker', local_executor)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(execute_approved_action.run, view['id'], 'concurrent-effect') for _ in range(2)]
        results, errors = [], []
        for job in jobs:
            try:
                results.append(job.result(timeout=10))
            except Exception as error:
                errors.append((type(error).__name__, str(error)))
        assert not errors, errors
    assert len(calls) == 2 and {result['result']['calls'] for result in results} == {1, 2}
    assert [event['event'] for event in service.audit(view['id'])].count('effect_consumed') == 1


@pytest.mark.parametrize('trial', range(12))
def test_own_repeat_original_worker_barrier(service, monkeypatch, trial):
    test_concurrent_same_permit_workers_both_execute_local_effect(service, monkeypatch)


def test_own_forced_winner_between_approval_and_effect_lookup(service):
    from sqlalchemy import event
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    engine = service._sessions.kw['bind']
    fired = []
    def interleave(conn, cursor, statement, parameters, context, executemany):
        if not fired and 'FROM m00_approval_effects' in statement and 'WHERE m00_approval_effects.effect_id =' in statement:
            fired.append(True)
            service.consume_effect(view['id'], module_id=5, action_type='send_email', payload=PAYLOAD,
                                   user_id='udita', effect_id='forced-winner', actor='winner')
    event.listen(engine, 'before_cursor_execute', interleave)
    try:
        with pytest.raises(ApprovalConflictError, match='effect id'):
            service.consume_effect(view['id'], module_id=5, action_type='send_email', payload=PAYLOAD,
                                   user_id='udita', effect_id='forced-winner', actor='loser')
    finally:
        event.remove(engine, 'before_cursor_execute', interleave)
    assert fired == [True]
    assert [e['event'] for e in service.audit(view['id'])].count('effect_consumed') == 1
    assert service.consume_effect(view['id'], module_id=5, action_type='send_email', payload=PAYLOAD,
                                  user_id='udita', effect_id='forced-winner', actor='replay')['allowed']


def test_concurrent_same_permit_race_rate_distribution(service, monkeypatch, capsys):
    """Measure, don't assert away, the concurrent duplicate-execution race."""
    import concurrent.futures
    import threading
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    outcomes = {'both_executed': 0, 'one_conflicted': 0, 'other': 0}
    for trial in range(12):
        monkeypatch.setattr(action_registry, '_EXECUTORS', {})
        monkeypatch.setattr('app.modules.m00_approval_center.service.default_service', lambda: service)
        view = service.submit(module_id=5, action_type=f'race_trial_{trial}', payload={}, user_id='udita')
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
        calls = []
        lock = threading.Lock()
        def local_executor(payload):
            with lock:
                calls.append(1)
            return {'ok': True}
        action_registry.register_executor(5, f'race_trial_{trial}', local_executor)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(execute_approved_action.run, view['id'], f'race-effect-{trial}') for _ in range(2)]
            errors = [job.exception(timeout=10) for job in jobs]
        if len(calls) == 2:
            outcomes['both_executed'] += 1
        elif len(calls) == 1 and any(isinstance(e, ApprovalConflictError) for e in errors):
            outcomes['one_conflicted'] += 1
        else:
            outcomes['other'] += 1
    print(f'RACE_DISTRIBUTION={outcomes}')
    assert outcomes['other'] == 0, outcomes
    assert outcomes['both_executed'] >= 1, f'replay duplicate-execution path unreachable in 12 trials: {outcomes}'


@pytest.mark.parametrize('delay', [0, 0.001, 0.01])
def test_own_worker_start_profiles(service, monkeypatch, delay):
    import concurrent.futures
    import threading
    import time
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    monkeypatch.setattr(action_registry, '_EXECUTORS', {})
    monkeypatch.setattr('app.modules.m00_approval_center.service.default_service', lambda: service)
    outcomes = {'both': 0, 'one_conflicted': 0, 'other': 0}
    for trial in range(20):
        name=f'own_profile_{trial}';view=service.submit(module_id=5, action_type=name, payload={}, user_id='udita')
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
        calls=[];lock=threading.Lock()
        def execute(payload):
            with lock:calls.append(1)
            return {'ok': True}
        action_registry.register_executor(5,name,execute)
        def run(sleep):
            time.sleep(sleep)
            return execute_approved_action.run(view['id'],f'own-profile-effect-{trial}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(run,0),pool.submit(run,delay)];errors=[j.exception(timeout=10) for j in jobs]
        if len(calls)==2 and not any(errors):outcomes['both']+=1
        elif len(calls)==1 and sum(isinstance(e,ApprovalConflictError) for e in errors)==1:outcomes['one_conflicted']+=1
        else:outcomes['other']+=1
    print('OWN_PROFILE',delay,outcomes)
    assert outcomes['other']==0
