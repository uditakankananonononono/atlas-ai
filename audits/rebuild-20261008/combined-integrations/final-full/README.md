# Combined full regression

573 files / 58 batches: 10,783 passed, 0 failed, 14 skipped, 0 errors. 206 subtests separately passed, not added to ordinary test total.

Initial source c99ab5ce5; after batch25, 617146775 changed only two historical-forward test upgrade targets and append-only audit records. No product drift. Original failing logs and corrected receipts are retained. Batch5 harness correction: initialize isolated test DB. Batch11 harness correction: do not propagate auto-schema into Alembic subprocesses. Batch25 test semantics correction: historical identity-forward test targets its specific revision, not later graph head.

Separate affected backend/dashboard frontend and SQLite cycle receipts remain scoped. No production, external provider, broad feature-completion or combined PostgreSQL cycle claim. Later queued feature changes require separate receipts and review.
