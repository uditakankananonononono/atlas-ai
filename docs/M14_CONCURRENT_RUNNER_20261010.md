# M14 concurrent DAG runner candidate

Base: f37156c7fc7aec8cf7bec6ecbd0f8aa39ecb18fa. Additive library primitive;
no API binding, external executor, migration, shared dependency, or deployment.
Existing synchronous TaskRunner and schema behavior remain unchanged.

ConcurrentTaskRunner accepts an injected async executor and a TaskReservation
callback. max_parallel is explicitly 1..1000. ProjectPlan still caps tasks at500,
so this candidate can overlap at most500 tasks in a single validated plan.
The500-coroutine barrier test observes500 entered before any can leave. It is
not evidence of1000 deployed builders, throughput, remote capacity, or compute
quality. The1000-builder constitution requirement remains unmet.

Call count, maximum declared cost, and maximum declared aggregate runtime are
charged before dispatch, with no refunds. Budgets are conservative reservations,
not measured billing. The caller must truthfully bound executor effects and give
this runner exclusive ledger ownership. Executors cannot spend beyond declared
limits safely merely because their reported output is rejected afterward.
Independent effect/payment approval and external budget enforcement stay outside
this engine. No external effects are used by the tests.

Ready tasks run in bounded waves. Each task receives a deep copy. Dependents
unlock only after completed prerequisites; successes enter review by default.
Retries consume call/runtime/cost reservations again plus a retry iteration.
Failures do not erase successful siblings. Exhausted capacity stops new dispatch.
Unexpected exception text is not echoed into the report because it can contain
private data or credentials. A caller-owned executor must retain suitable private
failure evidence if diagnostic detail is required.

Timeouts/cancellation are cooperative asyncio cancellation, not subprocess-tree
kill or remote cancellation proof. Blocking or cancellation-suppressing code can
prevent prompt return. No universal timeout guarantee is claimed. Run-level
cancellation cancels and awaits the children, retains charged reservations, and
raises CancelledError rather than claiming completion. In-flight crash recovery,
durable leases, multi-tenant scheduling, distributed dispatch, exactly-once
external effects, API authorization wiring, and production capacity tests remain
future units. No existing H/followup/import6 gate is changed.
