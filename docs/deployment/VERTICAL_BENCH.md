# X14 vertical Celery-worker scaling benchmark (local substitute)

## What this substitute honestly cannot cover

Proof of horizontal (multi-machine) scaling.

Everything here runs on ONE host. This harness produces single-host
(vertical) evidence only and makes no claim about horizontal scaling.

## What it does

`deploy/local/vertical_bench.py` spawns N real local `celery worker`
processes against a real broker (the same `ATLAS_REDIS_URL` wiring the
application uses), enqueues real tasks through the broker on the dedicated
`vertical-bench` queue, and reports only numbers measured at run time:

- wall seconds and derived throughput for the enqueued batch;
- per-task broker round-trip latency percentiles computed from timings the
  worker processes return themselves;
- the count of distinct worker process ids observed in returned results
  (distribution evidence, not a guarantee of even spread).

It is a measurement harness, not a performance claim. This repository
records no measured numbers; every number is produced when the harness is
actually run.

## Hermetic behavior tests (authored, not yet run anywhere)

`tests/deploy/test_vertical_bench_harness.py` exercises the real harness
module with no broker, no network, no docker and no worker processes, using
Celery eager execution (`task_always_eager`) plus the in-memory
`cache+memory://` result backend, both Celery built-ins. It imports
`deploy/local/vertical_bench.py` and drives its real Celery app, its real
`vertical_bench.echo` task and its real `apply_async` path. Authored
coverage, for the main side to run:

- enqueue: the given task id is the id under execution and message
  arguments arrive through Celery's real JSON serialization round-trip;
- execution: the task body really runs and computes its payload;
- retry: a retrying task on the harness's app completes only after real
  retry round-trips, and retry exhaustion records `FAILURE` with
  `MaxRetriesExceededError`;
- result state: task ids move `PENDING` to `SUCCESS` through the result
  backend and payloads are retrievable via `AsyncResult`;
- percentile: exact ranked elements (`p50`/`p95`/`p0`), not index 0;
- argument validation: nonpositive `--workers`/`--concurrency`/`--tasks`
  exit 1 naming the `args` check, before any broker or worker is touched;
- queue: the bench task is enqueued on exactly the queue the spawned
  workers consume (`vertical-bench`), via the harness's own
  `worker_command` and `enqueue_batch` helpers;
- latency: the returned latency is the real elapsed time since the caller's
  sent timestamp, not a constant.

These tests are AUTHORED-NOT-RUN: their outcomes are unverified until the
main side runs them. Worker spawn, control ping, real broker round-trips,
the 200-task measured run and process cleanup are main-side runtime
acceptance, also not yet run. Run the hermetic tests with:

    pytest tests/deploy/test_vertical_bench_harness.py

## Requirements

Free/local only: a reachable Redis broker (for example the `redis` service
from `deploy/local/docker-compose.yml`) and the project dependencies
installed. No paid account, no cloud service, no 32GB hardware assumption.

## Usage

    # broker on localhost (for example: docker compose -f deploy/local/docker-compose.yml up redis)
    export ATLAS_REDIS_URL=redis://localhost:6379/0
    python deploy/local/vertical_bench.py --workers 4 --concurrency 2 --tasks 200
    # or point at any local broker and capture the JSON report:
    python deploy/local/vertical_bench.py --broker redis://localhost:6379/0 \
        --workers 2 --concurrency 2 --tasks 200 --output /tmp/vertical-bench.json

Run it once per worker count (for example 1, 2, 4, 8) and compare the
measured-at-run-time reports side by side for a vertical scaling curve.

## Behavior on failure

Every failure names its check and exits non-zero: unreachable broker
(`broker`), a worker process that dies or never answers the control ping
(`worker_start`), a task deadline overrun or task error (`tasks`), invalid
arguments (`args`). Worker processes are always terminated when the harness
exits.

## Honesty notes

- Throughput and latency figures exist only in the JSON the harness prints
  at run time. None are recorded here or asserted anywhere.
- `distinct_worker_pids` reports how many real worker processes actually
  executed tasks; it does not assert balanced distribution.
- The harness asserts no performance level: exit 0 means the run completed
  truthfully, not that it was fast.
- No test in this repository has been run by the author; every test outcome
  is the main side's to observe.
- Scaling the worker count beyond one host's cores measures contention, not
  horizontal capacity; that is exactly the boundary of this substitute.
