# Acceptance case: line-mixing

Five named source operators, not exhaustive or necessarily distinct faults.
Classification: rc1 plus FAILED test IDs only, including product crash failures;
ERROR/timeout/collection failures are INVALID, not credited. Local subprocess
execution and offline Git/file checks coexist with explicitly controlled injected
receipt/drift tests. No authenticated external source or semantic completion.
Every applied mutation is SHA-restored and restored baseline passes.

Initial outcomes preserved: line-mixing5caught; single-drift2caught/3survived;
receipt-visibility4caught/1survived. After controlled sensitivity additions,
final5caught each. Initial survivors are not rewritten as original catches.
Run python audits/program-evidence-mutations/runner.py audits/program-evidence-mutations/line-mixing.json
Literal rows remain PARTIAL; snapshots non-atomic, no aggregate sandbox/budget.
