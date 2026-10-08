# Shipped executor boundary

Continuation of 81abf0f7 on original base f64e0c37. ResearchExecutor now applies
bounded plain-data copies to input context and each provider input, then bounds
and deeply detaches returned evidence before success, fallback or review.
Service inherits this path and build_service uses it. No main edit or push.

Existing envelope/text/usage/logprob guards and unavailable-confidence review
semantics remain. The executor first sanitizes unavailable confidence/logprobs
on its copy, then subjects retained result data to the stricter plain-data
contract. This preserves the established review boundary instead of treating
all invalid confidence as provider-unknown. Result subclass reconstruction still
uses existing copy semantics and may invoke subclass post-init before rejection;
the no-custom-conversion guarantee belongs to plain-data traversal, not that
pre-existing envelope step.

10 new wiring tests: before 9 fail, 1 pass; after all pass. These include the
real build_service construction and mounted HTTP route with unknown/409 and
retry_allowed=false after exactly one scripted provider dispatch. The entire
M12 test selection passes: 1334 tests, one existing Starlette/httpx warning,
Python 3.12.14. Initial broad candidate had 25 failures with 1308 pass; its
placement was corrected, and that failed candidate is not shipped as success.

The test providers are explicit doubles. No external model inference, billing,
source authentication, confidence calibration or owner-PC acceptance is claimed.
Plain-data budgets do not bound provider allocation/transport or concurrent
mutation, and are not aggregate spending limits. Existing local confidence
fallback remains governed by the existing policy, not by authorization added by
this boundary. Default budgets are local engineering choices. No durable replay,
rollback, injection-resistance or hostile snapshot guarantee is added.

Reproduce: python -m pytest tests/modules/test_m12_*.py -q
