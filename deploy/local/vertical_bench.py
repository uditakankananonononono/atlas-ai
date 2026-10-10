#!/usr/bin/env python3
"""X14 local substitute: vertical (single-host) Celery-worker scaling benchmark.

What this substitute honestly cannot cover: Proof of horizontal (multi-machine) scaling.

This harness spawns N real local `celery worker` processes against a real
broker (the same ATLAS_REDIS_URL wiring the application uses), drives real
tasks through the broker on a dedicated queue, and reports only numbers
measured at run time: wall seconds, throughput, per-task latency percentiles
computed from worker-returned timings, and the distinct worker process ids
observed. It is a measurement harness, not a performance claim: it invents
no numbers and asserts no performance level. Free/local only: no paid
account, no cloud service, no 32GB hardware assumption. See
docs/deployment/VERTICAL_BENCH.md.

Exit 0 only when the broker is reachable, every spawned worker answers a real
control ping, and every enqueued task returns a well-formed result before the
deadline; every failure names its check and exits 1. Worker processes are
always terminated on exit.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent          # deploy/local
ROOT = HERE.parents[1]                          # repository root
BACKEND = ROOT / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

QUEUE = 'vertical-bench'
TASK_NAME = 'vertical_bench.echo'

from app.workers.celery_app import celery_app  # noqa: E402


@celery_app.task(name=TASK_NAME)
def echo(i, sent):
    """Benchmark task: returns the broker round-trip latency and the executing worker pid."""
    return {'i': i, 'latency': time.time() - sent, 'worker_pid': os.getpid()}


def worker_node_name(index, host):
    """Deterministic node name for the control-ping readiness handshake."""
    return f'vertical-bench-{index}@{host}'


def worker_command(index, concurrency):
    """The exact celery worker command: consumes ONLY the bench queue."""
    return [sys.executable, '-m', 'celery',
            '-A', 'app.workers.celery_app:celery_app',
            'worker', '-Q', QUEUE, '-I', 'vertical_bench',
            '--concurrency', str(concurrency),
            '--loglevel', 'WARNING', '-n', f'vertical-bench-{index}@%h',
            '--without-gossip', '--without-mingle', '--without-heartbeat']


def enqueue_batch(count):
    """Enqueue count real bench tasks through the broker on the bench queue."""
    return [echo.apply_async(args=[i, time.time()], queue=QUEUE) for i in range(count)]


def fail(check, detail):
    print(json.dumps({'check': check, 'ok': False, 'detail': str(detail)[:1000]}))
    sys.exit(1)


def percentile(sorted_values, fraction):
    if not sorted_values:
        return None
    return sorted_values[min(len(sorted_values) - 1, int(fraction * len(sorted_values)))]


def main():
    parser = argparse.ArgumentParser(description='Vertical single-host Celery-worker scaling benchmark (X14 substitute).')
    parser.add_argument('--workers', type=int, default=2, help='number of real worker processes to spawn')
    parser.add_argument('--concurrency', type=int, default=2, help='celery --concurrency per worker process')
    parser.add_argument('--tasks', type=int, default=200, help='number of real tasks to drive through the broker')
    parser.add_argument('--broker', default=os.environ.get('ATLAS_REDIS_URL', 'redis://localhost:6379/0'),
                        help='broker and result backend URL (default: ATLAS_REDIS_URL)')
    parser.add_argument('--timeout', type=float, default=300.0, help='overall task deadline in seconds')
    parser.add_argument('--start-timeout', type=float, default=120.0, help='worker readiness deadline in seconds')
    parser.add_argument('--output', default=None, help='optional path to write the JSON report')
    args = parser.parse_args()
    if args.workers < 1 or args.concurrency < 1 or args.tasks < 1:
        fail('args', 'workers, concurrency and tasks must all be >= 1')

    # Same wiring as the application: one broker URL for driver and workers.
    celery_app.conf.broker_url = args.broker
    celery_app.conf.result_backend = args.broker

    # Broker preflight: fail loudly before spawning anything.
    try:
        with celery_app.connection() as connection:
            connection.ensure_connection(max_retries=3, interval_start=0.2)
    except Exception as exc:
        fail('broker', f'{type(exc).__name__}: {exc}')

    env = dict(os.environ)
    env['ATLAS_REDIS_URL'] = args.broker
    env['PYTHONPATH'] = os.pathsep.join([str(BACKEND), str(HERE), env.get('PYTHONPATH', '')])
    host = socket.gethostname()
    node_names = [worker_node_name(i, host) for i in range(args.workers)]
    procs = []
    try:
        for i in range(args.workers):
            cmd = worker_command(i, args.concurrency)
            procs.append(subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))

        # Readiness: a real control handshake - every worker answers ping.
        ready = set()
        deadline = time.monotonic() + args.start_timeout
        while time.monotonic() < deadline and len(ready) < args.workers:
            for proc in procs:
                if proc.poll() is not None:
                    detail = proc.stderr.read().decode(errors='replace') if proc.stderr else ''
                    fail('worker_start', f'worker exited with {proc.returncode}: {detail}')
            replies = celery_app.control.inspect(destination=node_names, timeout=2).ping() or {}
            ready = {name for name, reply in replies.items() if reply.get('ok') == 'pong'}
            if len(ready) < args.workers:
                time.sleep(1)
        if len(ready) < args.workers:
            fail('worker_start', f'only {len(ready)}/{args.workers} workers answered ping')

        # Drive real tasks through the broker and measure.
        start = time.perf_counter()
        results = enqueue_batch(args.tasks)
        latencies, pids, completed = [], set(), 0
        for res in results:
            remaining = start + args.timeout - time.perf_counter()
            if remaining <= 0:
                fail('tasks', f'deadline exceeded with {completed}/{args.tasks} tasks complete')
            try:
                out = res.get(timeout=remaining)
            except Exception as exc:
                fail('tasks', f'{type(exc).__name__}: {exc}')
            latencies.append(float(out['latency']))
            pids.add(int(out['worker_pid']))
            completed += 1
        elapsed = time.perf_counter() - start

        lat = sorted(latencies)
        report = {
            'check': 'vertical_bench',
            'ok': True,
            'workers_spawned': args.workers,
            'concurrency_per_worker': args.concurrency,
            'tasks': args.tasks,
            'tasks_completed': completed,
            'distinct_worker_pids': len(pids),
            'seconds': elapsed,
            'throughput_tasks_per_second': completed / elapsed if elapsed > 0 else None,
            'latency_seconds': {'p50': percentile(lat, 0.50), 'p95': percentile(lat, 0.95),
                                'max': lat[-1] if lat else None},
            'horizontal_scaling': 'not covered: single host only',
        }
        print(json.dumps(report))
        if args.output:
            Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
        return 0
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == '__main__':
    sys.exit(main())
