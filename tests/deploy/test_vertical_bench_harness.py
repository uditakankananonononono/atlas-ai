"""ATLAS-U-1223 / X14 vertical Celery-worker scaling benchmark - hermetic behavior tests.

AUTHORED-NOT-RUN (PREP-NORUN): the builder authored these tests but ran none
of them, imported nothing, and started no broker or worker. They are for the
main side to run. The builder's only local check was py_compile syntax
compilation of the harness and this file, disclosed in the unit report.

These tests invoke the ACTUAL harness: they import
deploy/local/vertical_bench.py and drive its real Celery application, its
real `vertical_bench.echo` task and its real apply_async enqueue path.
Hermetic basis (no broker, no network, no docker, no worker processes):
Celery eager execution (task_always_eager) plus the in-memory cache result
backend (cache+memory://), both Celery built-ins. They assert behavior only:

* enqueue: apply_async assigns and tracks the given task id and passes the
  message through Celery's real producer JSON serialization round-trip;
* execution: the task body really runs and computes its payload;
* retry: a retrying task on the harness's app completes only after real
  retry round-trips, and retry exhaustion ends in FAILURE with
  MaxRetriesExceededError;
* result state: task ids move PENDING -> SUCCESS through the result backend,
  and payloads are retrievable through AsyncResult.

No throughput, latency or performance level is asserted anywhere; measured
numbers are produced only when the main side runs the benchmark itself.
"""
import importlib.util
import os
import time
import uuid
from pathlib import Path

import pytest
from celery.exceptions import MaxRetriesExceededError
from celery.result import AsyncResult, EagerResult

HARNESS = Path('deploy/local/vertical_bench.py')
DOCS = Path('docs/deployment/VERTICAL_BENCH.md')
GAP = 'Proof of horizontal (multi-machine) scaling'


@pytest.fixture(scope='module')
def harness():
    """Load the real harness module and pin it to hermetic eager execution.

    Import only: Celery connects lazily, so importing the harness contacts
    no broker. Eager execution plus the in-memory backend keep every
    assertion below in-process with no external service.
    """
    spec = importlib.util.spec_from_file_location('vertical_bench', HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.celery_app.conf.update(
        broker_url='memory://',
        result_backend='cache+memory://',
        task_always_eager=True,
        task_eager_propagates=False,
        task_store_eager_result=True,
    )
    module.echo.store_eager_result = True
    return module


def test_named_gap_verbatim_in_module_docstring_and_docs(harness):
    docstring = harness.__doc__ or ''
    assert GAP in docstring, 'named gap must be stated verbatim in the harness module docstring'
    assert GAP in DOCS.read_text(), 'named gap must be stated verbatim in the docs'


def test_enqueue_assigns_tracks_and_serializes_through_celery(harness):
    """Enqueue: the real apply_async path honors the given task id and routes
    the message through the producer's real JSON serializer - a tuple
    argument can only arrive at the task body as a list."""
    task_id = str(uuid.uuid4())
    result = harness.echo.apply_async(args=[(7, 8), time.time()], queue=harness.QUEUE, task_id=task_id)
    assert isinstance(result, EagerResult), 'eager enqueue must return the eager result handle'
    assert result.id == task_id, 'the id given at enqueue must be the id under execution'
    payload = result.get(timeout=5)
    assert isinstance(payload['i'], list), 'args must arrive through JSON serialization, not a direct call'
    assert payload['i'] == [7, 8]


def test_execution_returns_payload_computed_by_task_body(harness):
    """Execution: the task body really runs and computes its payload."""
    sent = time.time()
    result = harness.echo.apply_async(args=[3, sent], queue=harness.QUEUE)
    assert result.state == 'SUCCESS'
    payload = result.get(timeout=5)
    assert payload['i'] == 3
    assert payload['worker_pid'] == os.getpid(), 'eager execution happens in the calling process'
    assert isinstance(payload['latency'], float) and payload['latency'] >= 0.0


def test_result_state_tracked_through_backend(harness):
    """Result state: the enqueued id moves PENDING -> SUCCESS in the result
    backend and its payload is retrievable through AsyncResult."""
    app = harness.celery_app
    task_id = str(uuid.uuid4())
    assert AsyncResult(task_id, app=app).state == 'PENDING', 'an id with no stored result must be PENDING'
    harness.echo.apply_async(args=[9, time.time()], queue=harness.QUEUE, task_id=task_id)
    tracked = AsyncResult(task_id, app=app)
    assert tracked.state == 'SUCCESS', 'the result backend must record the executed state'
    assert tracked.get(timeout=5)['i'] == 9


def test_retry_round_trips_until_success(harness):
    """Retry: a task that fails twice completes only after two real retry
    round-trips, with Celery itself advancing the request retry counter."""
    app = harness.celery_app
    attempts = {'n': 0}

    @app.task(bind=True, name='vertical_bench.test_retry_probe', max_retries=3)
    def retry_probe(self, fail_times):
        attempts['n'] += 1
        if attempts['n'] <= fail_times:
            raise self.retry(countdown=0)
        return {'attempts': attempts['n'], 'request_retries': self.request.retries}

    retry_probe.store_eager_result = True
    result = retry_probe.apply_async(args=[2])
    assert result.state == 'SUCCESS', 'retry round-trips must end in the success state'
    payload = result.get(timeout=5)
    assert payload['attempts'] == 3, 'the task body must run once per attempt, not once total'
    assert payload['request_retries'] == 2, 'Celery must advance the request retry counter per round-trip'


def test_retry_exhaustion_ends_in_failure_state(harness):
    """Retry exhaustion: exceeding max_retries records the FAILURE state with
    MaxRetriesExceededError as the result."""
    app = harness.celery_app

    @app.task(bind=True, name='vertical_bench.test_exhaustion_probe', max_retries=1)
    def exhaustion_probe(self):
        raise self.retry(countdown=0)

    exhaustion_probe.store_eager_result = True
    result = exhaustion_probe.apply_async()
    assert result.state == 'FAILURE', 'retry exhaustion must record the failure state'
    assert isinstance(result.result, MaxRetriesExceededError), 'exhaustion must surface MaxRetriesExceededError'


def test_percentile_returns_the_correct_ranked_element(harness):
    """Percentile pins: exact ranked elements (kills the index-0 survivor)."""
    values = [10, 20, 30, 40, 50]
    assert harness.percentile(values, 0.50) == 30
    assert harness.percentile(values, 0.95) == 50
    assert harness.percentile(values, 0.0) == 10
    assert harness.percentile([], 0.5) is None


def test_argument_validation_rejects_nonpositive_counts(harness, capsys, monkeypatch):
    """Argument validation: nonpositive workers/concurrency/tasks must exit 1
    naming the 'args' check, before any broker or worker is touched."""
    for flag in ('--workers', '--concurrency', '--tasks'):
        monkeypatch.setattr('sys.argv', ['vertical_bench.py', flag, '0'])
        with pytest.raises(SystemExit) as excinfo:
            harness.main()
        assert excinfo.value.code == 1, f'{flag} 0 must exit 1'
        assert '"check": "args"' in capsys.readouterr().out, f'{flag} 0 must fail the args check'


def test_task_queue_equals_worker_queue_exactly(harness):
    """Queue pin: the bench task is enqueued on exactly the queue the spawned
    workers consume (kills the queue->'celery' survivor)."""
    assert harness.QUEUE == 'vertical-bench'
    cmd = harness.worker_command(0, 2)
    assert cmd[cmd.index('-Q') + 1] == harness.QUEUE, 'workers must consume exactly the bench queue'
    recorded = []
    real_apply_async = harness.echo.apply_async

    def spy(*args, **kwargs):
        recorded.append(kwargs)
        return real_apply_async(*args, **kwargs)

    harness.echo.apply_async = spy
    try:
        results = harness.enqueue_batch(2)
    finally:
        harness.echo.apply_async = real_apply_async
    assert len(recorded) == 2, 'the harness must enqueue one message per requested task'
    assert all(r.get('queue') == harness.QUEUE for r in recorded), 'enqueue queue must equal the worker queue'
    assert sorted(res.get(timeout=5)['i'] for res in results) == [0, 1]


def test_latency_is_computed_from_the_sent_time(harness):
    """Latency pin: the returned latency is the real elapsed time since the
    sent timestamp the caller passed (kills the latency->0.0 survivor)."""
    sent = time.time() - 5.0
    result = harness.echo.apply_async(args=[11, sent], queue=harness.QUEUE)
    payload = result.get(timeout=5)
    now = time.time()
    assert 5.0 <= payload['latency'], 'latency must reflect the sent time, not a constant'
    assert payload['latency'] <= now - sent, 'latency cannot exceed the real elapsed time since sent'
