# Discovery promotion authority and retries

`promote_candidate(tenant_id, candidate_id)` no longer accepts an
`approval_authority` argument. It resolves the native Module 0 verifier inside
server composition. Deployment administrators configure the current owner
principal per tenant using `ATLAS_PROMOTION_OWNERS_JSON`, a JSON object mapping
tenant ids to authenticated owner ids. An absent directory fails closed.
Never populate this variable from request payloads. Owner ids must match the
principal recorded by the authenticated Module 0 decision transport.

This boundary protects against request-level caller-supplied authority objects,
not a malicious process owner, arbitrary Python code execution, or someone who
can rewrite the approval database or deployment environment. A type check is
only a sanity check. `_PromotionService` is a private trusted composition/test
seam, not a public authority API.

Every review attempt has an immutable approval id, candidate id, version,
tenant, source destination and canonical scope hash. Requests and bindings are
written in the same transaction, so failed creation leaves no orphan approval.
Duplicate requests for a live attempt return its original id. A denied, expired
or revoked attempt can receive a fresh owner review under the same candidate.
Promotion always reads the latest attempt; an old approved decision cannot
stand in for the new pending review. Consumption is an immutable one-shot
receipt written in the same transaction as the source and candidate changes.
Duplicate promotion is denied, even though duplicate review requests are
idempotent. Consumed candidates do not get new permits.

New sources use stable per-account keys derived from platform and account key.
Distinct accounts on the same platform can both be reviewed and promoted.
Updating an existing source requires an explicit `target_source_id` in the
review request. The tenant, prior configuration, enabled flag, source id and
all reviewed collection settings are bound into the approval. No platform-wide
source is selected implicitly, and no changed source is silently overwritten.
Concurrent updates to the same reviewed source cannot both win after drift.

`Service.revoke(approval_id, tenant_id=..., revoked_by=...)` is the service-level
revocation writer. The authenticated transport must supply the actual caller
principal, not a request-selected actor label. The service checks the current
server-owned owner directory, takes the approval row lock, and adds a revoked
event. Repeated revocation is idempotent. Revocation before consumption blocks
promotion; revocation after consumption is rejected rather than claiming to
undo the action. SQLite uses an immediate write transaction; PostgreSQL uses
row locks and transaction-scoped advisory locks for candidate and source keys.

The migration preserves existing bindings and receipts as history. Old review
scope hashes do not contain the new attempt fields and therefore cannot
promote under the new verifier. Revoke a still-active legacy review through the
service and request a new owner review. Already consumed sources are retained.
Downgrading versioned history is intentionally refused to avoid audit loss;
restore an audited pre-upgrade backup instead.

# Preference dataset compatibility

`preference_dataset` intentionally rejects an explicit `context=None` with
`ValueError`. Previously, treating null context as empty risked conflating
unknown/missing context with a reviewed empty context. Callers must supply an
explicit text context (including an empty string where intended)
or omit the context field to use its documented default. This is an intentional
compatibility change, not an accidental coercion. Dataset permutation and
conflict tests remain in place; no fixed scores or model substitutes are used.
