# M08 landing runtime: scoped local acceptance

Base: 7eb17975d020d2fb83c56e0ab939da51d5db6ca1

Repaired a mounted landing archive defect: package.json, layout, TS configuration,
and CSS build configuration were absent. User product/hero/features text is now
JSON data rendered by React instead of interpolated TSX source. The HTTP router
uses a subclass; unchanged documentation/deck/approval methods are inherited.
Existing direct imports of service.Service retain the old generator. This narrow
integration must be considered if there are callers outside the mounted router.

Verified with Python 3.12.14, Node 22.23.3, Next 16.4.0, TypeScript 5.9.3:
- Complete M08 test selection: 36 passed, one Starlette deprecation warning.
- Regression test fails on base: four required runtime files are absent.
- Generated archive from actual SQLite-backed runtime service: npm install,
  production Next build and tsc typecheck passed.
- Production next start HTTP: invalid form/email 400, missing storage config 503.
- Chromium: product/hero/features exact text, no script injection/dialogs/errors.
- Desktop 1280 and mobile 390 pixels inspected: readable, complete, no overflow.
- Mounted route tests use real RS256 production-mode verification and SQLite:
  anonymous denied, archive stored/hash matches, other tenant cannot retrieve.

Reproduce:
PYTHONPATH=backend python scripts/m08_verify_landing_runtime.py --output /tmp/m08-evidence
pytest -q tests/modules/test_m08*.py

Limits:
- No live Supabase success/upsert/duplicate acceptance, remote deployment, or
  account access. Missing config is honestly 503, never simulated success.
- No rate limiting, email verification, consent policy or spam prevention.
- Existing-table migration not implemented; SQL IF NOT EXISTS needs review.
- Direct service.Service generator is unchanged; router now uses runtime_service.
- Static docs extraction and synthetic-200 OpenAPI limitation remain unchanged.
- Brand dictionary not applied. No whole-M08 acceptance or audit-row completion.
- Python 3.10 all-M08 attempt failed collection on existing StrEnum usage; Python
  3.12 resolved environment. Initial new HTTP test trusted dev-bypass identity
  and failed; corrected test explicitly selects production auth. Both receipts
  retained, not represented as successful product runs.
- Generated package pins direct versions; npm lockfile receipt locks transitive
  dependencies for this run. Generator does not embed that receipt's lockfile.
- No push/main edits. Branch package requires independent integration review.
