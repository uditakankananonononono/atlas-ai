# Row 93 supplied category inventory

Exact selector: tests/modules/test_group93_corpus_coverage.py, --noconftest -q
-rf, Python 3.12. Per-run timeout 40 seconds. row93.json names five mutations:
exact text hash, duplicate-id refusal, URL-credential refusal, empty-category
status and false completeness. Five CAUGHT by FAILED tests, source SHA restored
per mutation. Run via scoped_mutations.py; external logs/receipt retain results.

UNTESTED: real source verification, platform collection, category-wide coverage,
engagement truth, accounts and publishing. Source URL is caller-supplied, not
fetched. No runtime change; literal row remains PARTIAL.
