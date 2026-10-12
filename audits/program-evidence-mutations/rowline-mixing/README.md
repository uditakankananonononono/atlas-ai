# Acceptance case: line-mixing

Five named source operators, not exhaustive or necessarily distinct faults.
Classification: rc1 plus FAILED test IDs only, including product crash failures such as KeyError/RuntimeError;
ERROR/timeout/collection failures are INVALID, not credited.
Mixed FAILED plus SKIP is not rejected; counts are failure sensitivity. Local subprocess
execution and offline Git/file checks coexist with explicitly controlled injected
receipt/drift tests. No authenticated external source or semantic completion.
The retained local runs report SHA-matching source restores and passing
restored baselines. These are recorded outcomes for the receipt-bound version,
not a universal guarantee, independent reproduction or rerun-current claim.

Initial outcomes preserved: line-mixing5caught; single-drift2caught/3survived;
receipt-visibility4caught/1survived. After controlled sensitivity additions,
final5caught each. Initial survivors are not rewritten as original catches.
Run python audits/program-evidence-mutations/runner.py audits/program-evidence-mutations/line-mixing.json
Literal rows remain PARTIAL; snapshots non-atomic, no aggregate sandbox/budget.
