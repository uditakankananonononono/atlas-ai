# M12 opt-in bounded evidence boundary

Base: f64e0c37f3343b289f56583b7c63e5fa6ed5a4f9.
New module and tests only. No existing wiring is changed.

## Use

```python
from app.modules.m12_ai_research_lab.bounded_evidence import BoundedProvider, EvidenceLimits
from app.modules.m12_ai_research_lab.executor import ResearchExecutor
executor = ResearchExecutor(router, BoundedProvider(provider, EvidenceLimits()))
result = await executor.execute(request, prompt, context)
```

The boundary copies exact plain-data values without running custom conversion
methods. It rejects cycles, custom values, nonfinite numbers, invalid UTF-8,
oversized integers and excessive depth, item count or string byte count.
Repeated references are copied independently. Inputs are checked before dispatch;
invalid returned evidence raises ProviderOutcomeUnknown after one dispatch.
Valid provider exceptions and cancellation retain their existing behavior.
Missing confidence remains review-required through the existing executor.

Depth is the edge count from root; mapping keys count as items. Bytes count
UTF-8 string/key payload only, not serialized JSON syntax or numeric encoding.
Result fields share one result budget; input fields share one input budget.
The two budgets are separate, as are separate calls. Defaults are local choices,
not inferred owner requirements.

## Executed evidence

57 boundary tests and 253 existing focused collateral tests pass (310 total).
Base negative control: new test cannot import missing module, exit 2.
Two negative controls separately bypass detachment and result checking; each
kills three tests. Restoring code returns to passing. Providers in tests are
scripted test doubles. No real model inference is claimed.

## Limits

This is an opt-in composition, not a repair to the shipped HTTP service or all
existing entry points. No source authentication, calibrated confidence, actual
billing, aggregate spend authorization, provider timeout, durable replay,
rollback, prompt-injection resistance or real-provider acceptance is established.
Budgets bound copied data and traversal work, not provider generation, memory
already allocated upstream, network transport or concurrent mutation. There is
no hostile-concurrent-mutation or thread-safe snapshot claim. Exceptions raised
by an underlying provider are not reclassified or automatically retried here.

Executed on Python 3.10.12 in this local Linux environment. Project metadata
requires Python >=3.12; Python 3.12 execution and owner PC are not verified.
One existing Starlette/httpx deprecation warning remains in collateral tests.
