# M19 free-local default and execution-state repair candidate

Baseline: 313309be. Local branch: repair/m19-local-state. No remote push.

## Reproduced acceptance

`python -m pytest tests/modules/test_m19* tests/test_technical_spec_166_198.py tests/modules/test_technical_spec_round8_199_229.py tests/test_m19_spec_truth.py -q`

Result after provider-boundary repair: 287 passed, 1 dependency deprecation warning on CPython 3.12.14.
See tests.txt and environment.txt. The tests include existing ledger/domain tests,
20 new run-state/provider/migration tests, and 5 new spec-truth tests. Tests
reproduce file-backed SQL persistence, a fresh subprocess restart, four-process
idempotent intake reservation, parallel thread claims, version conflict rollback,
cross-tenant isolation, verified production OIDC identity, failure persistence,
lease expiry, preview duplicate suppression/uncertain-store failure, package
replay/evidence persistence, and rejection of invented prototype URLs.

Model success tests use controlled test JSON and HTTP MockTransport, explicitly
not real model inference. A real loopback connection-refused test verifies the
unavailable path. No live installed Ollama model or owner-PC RAM claim is made.
Migration upgrade/downgrade was executed against SQLite. PostgreSQL was not tested.

## Corrected statements

- Default Service provider was `openai`. Mounted M19 now uses local-only generation,
  explicit installed-model configuration, no hosted fallback, and visible 503 errors.
- Generated intake used `state="queued", stage=LANDSCAPE` without any executor.
  Successful draft intake now stays INTAKE, awaiting_evidence, not_executed, with
  unavailable_stages and a non-proceeding gate. No full workflow completion is claimed.
- Preview formerly changed stage to PREVIEW merely on an approval request. Now
  stage stays INTAKE and request payload says executor_available=false. Approval
  replay is durable; uncertain cross-store submission needs reconciliation.
- Package is unverified JSON with caller-supplied evidence persisted, not rendered PDF.
- Technical row 168's file list and `tests_included=True` is now explicitly a plan,
  files_written=false, tests_included=false, tests_run=false.
- Row 169 remains proposal, now also not_executed and executor_available=false.
- Row 170's `patch_proposed=True` per failure is now failure_recorded, no patch
  proposed/applied, no repair executor, no pretend retry stop. A bounded/truncated
  list is not an execution loop.
- Row 171's `render_status=ready` is now not_rendered, planned, pdf_created=false.
- Row 204's `status=implemented, parallel=True, acceptance_test=True` for planned
  streams is now planned, parallel=false, executed=false, end_to_end_verified=false.

## Scope and remaining gaps

This repairs default configuration and observable state, not downstream stage
execution, source verification, deployed previews, code production, PDFs, paid
provider access or external effects. Existing ledger files were not edited. New
SQL observations are append-only through this repository API; privileged raw SQL
can alter them, so tamper-proof storage is not claimed. Model text and supplied
references remain unverified. No user-visible UI change required pixel verification.

Before integration, independent audit must rerun the acceptance command and review
permissions/state semantics. M20 estimate candidate 98c87076 was not merged. This
candidate touches two shared cross-module spec files only for row corrections:
backend/app/runtime/technical_spec_166_198.py and
backend/app/modules/m20_general_cognitive_worker/technical_spec_round8_199_229.py.
Preserve those row-level corrections when combining other lanes. Run migration
20261003_m19_runs; reconcile it with other new Alembic heads if needed. Set local
model configuration; the repair does not install, train or download a model.

## Independent review follow-up

Independent review of 59a4fea returned PARTIAL for malformed local URL/port errors
escaping normalization and valid-JSON 302 responses being accepted. Four mounted
regression tests failed before the fix (provider-boundary-red.txt), then the full
287-test acceptance passed after URL parsing/port validation was placed within
the configuration error boundary and non-2xx responses were rejected.

Configuration and ordinary transport failures now become ProviderError and are
persisted as unavailable with no canvas and no operation lease. Intake returns a
specific error with run_id and HTTP 503. No automatic fallback was introduced.
The allowed hostnames are a host allowlist, not DNS-pinned local guarantees:
localhost/ollama resolution depends on the operating system/container network.
No claim of immutable local address resolution or actual successful inference is
made. Existing cross-store uncertainty/manual reconciliation, no PDF/executor,
and untested PostgreSQL limitations remain unchanged.
