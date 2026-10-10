# ATLAS-4 M18 second-interpreter pending recovery canary

AUTHORED NOT RUN. Selected base: 94fba3f76ae55d02163577921b4fd85f82a548c5.
New test file only plus this scoped document. No product edits or weakened tests.

## Planned execution (peer-owned, not executed during prep)

From repository root, in the peer's existing Python >=3.12 dependency environment:

```sh
PYTHONPATH=backend python -m pytest -q tests/modules/test_m18_intent_process_restart_prep.py
PYTHONPATH=backend python -m pytest -q tests/modules/test_m18_dispatch_intent.py tests/modules/test_m18_durable_rate_limiter.py tests/modules/test_m18_intent_process_restart_prep.py
```

The first command collects 2 parametrized test functions, 4 cases total.
Each nominal case launches two actual sys.executable subprocesses; each mutation
case launches one. Six actual children per full file execution, no fake process.
A fixed aware clock, tenant, root and exact pending record cross JSON stdin; only
an explicit absolute backend PYTHONPATH and bytecode-disable flag form child env.
No parent environment/credentials copied. Product code imports happen only when
peer runs the tests. Existing package init/conftest and their dependencies remain
real; no bypass/stub of product modules. Unexpected child imports or stderr fail.

## Boundaries and assertions

Parent separately provisions WAL and pacing, creates pending-before-snapshot
via WAL.begin or pending-after-snapshot via real begin_request plus completion
refusal. The latter calls the actual snapshot writer before leaving pending.
No parent live limiter/WAL object is passed into a child. No concurrent parent
writer is active while children run. Fault is phase simulation, not power loss.

The second interpreter reconstructs IntentBoundHostRateLimiter from disk. It
attempts check, begin_request, record_request, record_failure, honor_retry_after
and record_success first on another host, then pending host. Every call must
raise StateRejected; raw pending WAL and pacing bytes must remain unchanged.
Parent verifies actual return code, JSON output, child PID and disk bytes.

Another fresh interpreter refuses a wrong exact intent, omitted inspected grant,
False and integer 1 grants without disk changes. The exact pending record with
operator_inspected=True clears pending and increments revision by one without
rewriting pacing. A new request on another host then succeeds. For the phase
chosen after snapshot, the old host's saved wait still applies; attempted spending
on that host returns the wait, not permission, with no write. Parent checks final
WAL revision/pending and unchanged original-host fields in the on-disk snapshot.

Mutation sensitivity uses a real child with an intentionally wrong guard bound
to DurableHostRateLimiter._guard, which ignores pending. The identical probe
must exit nonzero at the FIRST other-host check with the specific AssertionError.
The outer mutation case requires that failure, not an arbitrary import/error.
No product source is rewritten; peer can independently apply an equivalent source
mutation and run the nominal cases, which must fail. This is a defined mutant,
not proof against every possible mutation.

## Unresolved semantics / excluded claims

- Exact acknowledgment is trusted-caller asserted inspection, not authenticated
  operator authority. No real operator/effect inspection is automated here.
- No old-intent replay or external dispatch occurs. Only future pacing permission
  is checked, not network request success, global binding or exactly-once effects.
- Only the opt-in IntentBound class is covered. Plain DurableHostRateLimiter and
  legacy callers can ignore WAL; no global limiter binding claim.
- POSIX/private trusted directory, one active writer and filesystem semantics
  remain preconditions. No real power-loss, concurrent-writer or hostile rollback
  proof, no WAL for unseen Retry-After failures.
- Existing constructor may load snapshot while pending; denial is required at
  dispatch/mutation guard, not construction. These tests follow that actual API.
- The 2-second expected default wait is obtained from actual parent policy, not
  invented; clock remains fixed across all interpreters.
- No fixture engine/ORM usage is involved. Shared pytest conftest/package imports
  may require installed dependencies; child imports are intentionally real.

PREP checks are limited to static source reading, AST syntax validation (including
CHILD string separately), git diff checks, bundle verification and hashes. No
pytest, subprocess/test execution, product import, app startup or services in prep.
