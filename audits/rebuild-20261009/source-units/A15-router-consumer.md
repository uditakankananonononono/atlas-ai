# A15 actual local HTTP router consumer

The actual GCWRuntime novel-goal path now has evidence through the A14 LangChain
planner, unchanged free-first router, real providers.generate/_post and loopback
HTTP protocol fixtures. Tests do not monkeypatch generate, _post or HTTP transport.
One fixture speaks Ollama chat, one OpenAI-compatible chat on the same controlled
local server. Request path, model, schema and private goal are inspected; SQL
proposed plan/method survive engine close/reopen and remain review-held.

Private routing skips hosted-free and hosted-paid canary routes even with the
paid feature flag enabled in the test. The next local route is selected only
after a preflight-open circuit (no first-route POST). An invoked 503 or malformed
JSON is one POST, holds unknown durably, does not try the backup and stays held
without another call after restart. No provider keys, hosted requests or spending
are involved. Production defaults, routing, privacy and spend policy are unchanged.

Four new acceptance controls pass; focused router/adapter/private/unknown/schema
suite: 56 passed, zero failures. This is protocol-fixture transport and product
router-consumer evidence, not actual Ollama inference, hosted-provider acceptance,
model quality or full A15 closure. Spec model versions differ from current defaults;
exact-version, missing-key, hosted-model and live-cognition acceptance remain OPEN.
The fixture catalog entry exists only during tests and makes no model availability
claim. Existing passing paths gain evidence; no base product defect is asserted.
