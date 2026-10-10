# Restart-safe knowledge service factory candidate

Base7628c745. Exact HTTP behavior changes for ALL six existing endpoints:
POST ingest, POST search, GET export, DELETE sources/{source_id}, GET contradictions,
POST claims/substantiate. All require explicit ATLAS_M25_DURABLE_ROOT, existing
private nonvolatile root and matching registry+workspace. Former implicit /tmp
creation removed. Missing/lost/unprovisioned/corrupt/profile drift/consent failure
returns identical503 detail "knowledge service unavailable". Owner mismatch403
"knowledge owner access required". Existing request.actor check retained. Audio
HTTP ingest503 because original offline transcriber unavailable; no guess. Owner
routes otherwise preserve payloads/results. No existing M25 test invokes these
routes/get_service; existing library tests remain unchanged, new15factory tests
exercise changed dependency and actual productionOIDC routes.

Administrative provision requires explicit known_new=True, owneractor/profile;
refuses any prior registry/workspace, including legacy. Not a public endpoint.
Factory never provisions, only reads. Root absolute/existing/private permissions,
symlink components refused, /tmp /var/tmp /dev/shm forbidden except explicit
non-HTTP test constructor. A nonvolatile-looking path is NOT proof of mount
durability: operator must provision a persistent filesystem. Crash during admin
provision leaves denied residue; operator reconciles, no automatic reset.

One owneractor per tenant, registry pinned offline profile exactly
"deterministic-embedder-v1+unavailable-transcriber-v1". Deployment provision is
explicit adapter attestation, not inference. Built-in adapters only, no plugins.
No collaborator access or migration/adoption of oldstores. Default determinisic
embedder implementation must revise profile on any behavior change; profile label
is trusted deployment data, not cryptographic code verification. Claimed consent
not authenticated; checked again on warm requests. Audio restore fails if original
adapter needed. No training/network/model downloads. Metadata/time known versus
legacy unknown inherited, no authenticity/TOCTOU/hostileadmin/aggregateCPU proof.

One factory/process per root, no multiprocess lease. Cache keyed tenant, no eager
setdefault, publication AFTER full verified restore. Thread Lock serializes all
endpoint operations; dependency yield can acquire/release on differentworkerthreads.
Registry/workspace existence/profile/owner rechecked every request. Warm cache
is NOT full bytes-integrity revalidation; external disk changes inside existing
workspace may remain invisible until restart or ingest validation. Mixing legacy
factory bypasses policy; caller deployment must use this factory throughout.
Expiry checked on warmrequests. Root permission/topology changes after factory
creation remain filesystem/operator risk. No background monitoring or deletion.

ATLAS_M25_DURABLE_ROOT must be the CANONICAL absolute path: factory normalizes
it, but warm route compares normalized root to raw env string, so a valid alias
can pass first request and return503 next request. Fail-closed, not alias support.
Independent PASS-WITH-NOTES: original156/base141,15canaries/7mutationkills;
normalized-root repair adds1canary, builder157PASS. All sixendpointnarrowings
probed independently. No productionmount/crash/distributedacceptance implied.
