# M12 opt-in bounded evidence boundary

Adapted base: 3eef2c0ab2344abfcc2de912e154a1b28f43d087.
See WIRING.md for actual shipped path and evidence on this base.

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

See WIRING.md and delivered receipts. Old-base counts are retained in the
separate historical package, not acceptance of this adaptation.

## Limits

BoundedProvider is also usable as an opt-in composition; this adaptation wires
it into ResearchExecutor and the single-run HTTP service, not all entry points. No source authentication, calibrated confidence, actual
billing, aggregate spend authorization, provider timeout, durable replay,
rollback, prompt-injection resistance or real-provider acceptance is established.
Budgets bound copied data and traversal work, not provider generation, memory
already allocated upstream, network transport or concurrent mutation. There is
no hostile-concurrent-mutation or thread-safe snapshot claim. Exceptions raised
by an underlying provider are not reclassified or automatically retried here.

Executed on Python 3.12.14 in this local Linux environment. Owner PC is not verified.
One existing Starlette/httpx deprecation warning remains in collateral tests.
