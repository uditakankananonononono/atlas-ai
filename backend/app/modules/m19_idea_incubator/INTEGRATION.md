# Module 19 integration and limits

The existing ledger routes remain unchanged. The autonomous `/ideas` routes now
use authenticated tenant context and SQL run snapshots plus append-only run
observations. SQLite tables are created for local use; production needs migration
`20261003_m19_runs`. Existing pre-repair in-memory runs cannot be recovered.

## Free local model configuration

Install and run Ollama separately on the owner's PC. Set `ATLAS_M19_MODEL` to an
already installed model identifier. No model is selected or downloaded here.
`ATLAS_M19_OLLAMA_URL` defaults to `http://127.0.0.1:11434`; a local Docker Compose
setup can use `http://ollama:11434`. Loopback or the compose `ollama` hostname is
required. This is a hostname allowlist, not DNS-pinned address enforcement;
resolution depends on the operating system/container network. No hosted provider, paid fallback, proxy environment or redirect is used.
This does not prove any model fits the owner's RAM or is installed on her PC.

Missing configuration, an unavailable server, and malformed output fail visibly.
The persisted failed run has no invented canvas. HTTP intake failures return 503
with run_id for inspection. A request may be replayed with the `Idempotency-Key`
header: exact duplicates reuse one run, different input under the same key is 409.
A failed or interrupted request is not silently retried; a deliberate new intake
uses a new key. Keys are scoped by tenant. Local headers are development identity
only; production uses the existing OIDC verifier, ignoring spoofed tenant headers.

Canvas generation is synchronous, then `awaiting_evidence` at `intake`. It is
not a queued landscape job. No landscape, validation, wireframe, scaffold, test,
viability or preview stage executor has been added. Gates do not announce readiness
for those stages. Snapshots use version compare-and-swap; observations record model
identity and caller-supplied evidence, without pretending it was externally verified.
GET `/ideas/{id}/events` returns tenant-scoped observations. Expired three-minute
operation leases become interrupted on read; no background resumer is claimed.

Package output is draft, unverified JSON, not a PDF. Supplied evidence/artifact
references are persisted as caller-supplied and unverified. Invented preview URLs
or new prototype references are rejected. Exact replay returns saved package JSON;
a changed request for that run is 409. This is not fact-checking of every model claim.

Preview only submits a tenant-scoped Module 0 approval, with executor availability
explicitly false. It does not deploy even after approval. The SQL compare-and-swap
reservation prevents concurrent duplicate submissions. If approval submission or a
crash leaves commit status uncertain, the run requires reconciliation instead of
resubmitting: no distributed transaction with Module 0 is claimed. The run stage
stays intake and execution_status stays not_executed. No cloud effects, purchases,
accounts, publishing, or production deployment are enabled by this repair.

Future work needs real source collection, sandboxed code execution and artifacts,
PDF rendering, an approved preview consumer, independent fact verification and
explicit retry/reconciliation endpoints. Do not mark those implemented from these
contracts. PostgreSQL multi-process acceptance still needs a real test deployment;
this candidate's persistence acceptance uses file-backed SQLite.
