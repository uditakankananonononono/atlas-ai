# BILL1305: bounded draft-invoice preparation for ledger row 1305

Candidate SCOPED additive unit for ledger row 1305 (Legal Billing; the
ledger row description is empty, so this unit is a bounded mechanism only).
Implementation:
backend/app/modules/m20_general_cognitive_worker/legal_billing1305.py
Tests: tests/modules/test_m20_legal_billing1305.py

## Existing mechanisms cited

- backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py
  dispatches row 1305 to a `billing_review_map` template: it organizes
  supplied authorities, facts and analysis items for counsel review and
  echoes `row_inputs`; it performs no billing computation and self-labels
  `supplied_legal_review_template_only`.
- backend/app/modules/m12_ai_research_lab/legal_support.py (OPS category)
  sums float `amount` fields per matter against a budget for a variance row;
  it does not validate time/fee records or produce invoices.

## Delta of this unit

Neither existing surface carries time/fee as validated decimal strings or
prepares invoices. This unit adds: caller hours and hourly rate as rational decimal
strings (validated, finite, ranged, not digit-capped), one draft invoice per matter; entry products and invoice totals are
computed under a 64-significant-digit decimal context (totals may round
beyond 64 significant digits), and batch-level total_hours and grand_total
are re-summed and normalized outside that context at the default 28
significant digits (they may round beyond 28 significant digits), duplicate entry-id refusal, and row-prefixed
(BILL1305:) exact refusal messages.

## Mechanism

`prepare_invoices(payload)` takes `batch_id` text and 1..256 entry records
(entry_id, matter_id, optional timekeeper/narrative text, hours and rate as
rational decimal strings). Hours must satisfy 0 < hours <= 24, rate must
satisfy 0 <= rate <= 100000 (zero rate is a pro bono entry). Entry ids must
be unique across the batch. Missing, mistyped, duplicated, non-finite or
out-of-range inputs refuse with ValueError; nothing is mutated or
defaulted. Output: one invoice per matter (sorted by matter id, entries in
input order) with entry ids, entry count, total hours, subtotal, status
`prepared_draft`, approval_granted=False, plus batch totals and honesty
labels payment_executed=False, posted_to_ledger=False,
trust_accounting_performed=False, records_verified_as_true=False.

## LIMITS

Not legal advice and not a legal conclusion. No payment is executed, no
ledger is posted, no trust accounting is performed, no tax or currency
handling, no client outreach. Supplied records are computed over, not
verified as true. Drafts require approval by licensed counsel or the
responsible human before any use. Mounted router wiring, auth and tenant
behaviour are not part of this package.
