# Row 94 offline namespace graph

Exact selector: tests/modules/test_group94_isolated_workforce.py, --noconftest
-q -rf, Python 3.12, per-run timeout 45 seconds. Actual namespace graph
execution. Five core mutations: dependency ordering, receipt return, timeout
forwarding, unknown edge-role refusal and missing source refusal. Initial
3-second-for-1-second timeout mutation SURVIVED because both timed out; added
observed duration <2.5s assertion on receipts. All five rerun CAUGHT by FAILED
tests. Both receipt generations retained; source SHA restores checked.

UNTESTED: external company operations, industry-wide scale, thousands of workers,
durable runtime, escaped descendants and whole-repository regression. Timing
assertion is a local sensitivity check, not production latency guarantee.
Literal row remains PARTIAL; no runtime edits.
