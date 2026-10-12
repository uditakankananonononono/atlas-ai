# Row 88 namespace worker mechanics

Exact selector: tests/troop/test_isolated_python_worker.py, --noconftest -q -rf,
Python 3.12, 45-second per-run timeout. Actual bubblewrap execution exercises
upstream inputs, wall timeout, dependent blocking, filesystem/network probes
and source/input/output receipt hashes. Five CAUGHT by FAILED tests: source
hash, input hash, receipt cap, detached receipt reads and output hash. SHA
restored per mutation. No skipped namespace tests counted as execution.

UNTESTED: actual named competitor comparisons, superiority, durable receipts,
escaped descendants, hostile kernel conditions and whole-repository regression.
Receipt hashes prove scoped bytes, not approval. Literal row remains PARTIAL.
