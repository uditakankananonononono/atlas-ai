# Draft invoice second-step failure

The invoice workflow first creates an invoice item, then creates a draft invoice.
An HTTP or JSON-decode failure in the second step now raises RuntimeError with a
partial-effect warning: the invoice item was accepted, the draft invoice outcome
is unknown, and provider reconciliation is needed before retry. Existing billing
execution routes map RuntimeError to HTTP 409. No automatic retry or compensation
was added; the separate stable approval-bound idempotency keys remain.

Tests use a real localhost HTTP server returning a first-step 200 and then either
a second-step 500 or invalid JSON. They inspect request paths and idempotency keys.
No Stripe account is contacted. A first-step 200 is treated as provider acceptance;
it is not proof of a valid persisted Stripe item. This warning is not a durable
execution journal. Approval replay, save-after-provider failure, first-step unknown
outcome, cancellation, webhook transactional gaps and concurrency are unchanged.
The process may still be interrupted between the two steps. No full M24 closure,
production billing or live-provider acceptance is claimed.
