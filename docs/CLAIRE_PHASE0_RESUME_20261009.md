# Claire / Meemee Phase-0 resume decisions

Date: 2026-10-09. Baselines inspected:
- Meemee main: 653bc158207d2e4ae4612bc3d3dc679d7d75ae61.
- Atlas claire-runtime-m1: 3f7321be32816dc27e8015d9f49d01b1554a8fb5.
- Vendored shared-models: 4cd3944, per backend/instinct_models/VENDORED.md.

These are design choices, not assertions about unknown deployment state.

## Decisions and rationale

1. Preserve legacy Meemee data, accounts, SDK/client contracts, jobs, webhooks and
browser sessions. Do not infer an empty deployment from absence of local files.
No deletion, archive or live cutover in this slice. Import requires a verified
inventory, owner mapping, snapshot/restore and reconciliation of pending effects.
Rationale: irreversible loss and duplicated external effects outweigh quick cleanup.

2. SQLite remains the single-host development target. PostgreSQL is the multi-host
release target. Both need independent execution evidence; SQLite tests do not prove
PostgreSQL locking, schema migration or lease fencing. Rationale: retain a cheap
local setup while avoiding a false distributed-runtime claim.

3. Preserve channel/companion protocol interfaces; do not claim live-provider parity
without actual canaries. Do not send email or switch real delivery processes here.
Rationale: interface compatibility does not establish authentication, delivery,
receipt reconciliation or a safe device binding.

4. Training, learned personalization, desktop parity and AGI claims remain separately
tracked acceptance gates. The runtime import does not supply learned reasoning.
No synthetic transport server may be labeled a real selected-model canary.
Rationale: infrastructure and a language model connection are necessary, not sufficient.

5. Use one explicitly selected loopback shared-model provider for the next seam.
No router fallback, hosted provider or automatic billing. Unavailable means blocked.
Rationale: make the model identity and privacy boundary testable; the existing Router
catches arbitrary exceptions and records diagnostic text, which is not appropriate
for this engine boundary. The vendored model layer is unchanged.

6. Independently review bounded slices before publication/integration. Existing
milestone remains: partial read-only runtime seam with plan acceptance A NOT met.
Rationale: protocol tests cannot substitute for the merge plan's mounted truth,
isolation, authority, recovery and release gates.

## Known evidence and unresolved inventory

Prior builder's slice-16 publication is corroborated by the live branch head.
Its earlier partial Phase-0 record and later audit history were recovered for leads;
reported historical suite counts are not rerun evidence in this checkout.

Live deployed accounts, data, clients, active jobs, webhooks and browser sessions
were not queried. There is no deployment-management connection in this slice.
This is an unresolved release gate, not a request for another design permission.
Meemee LICENSE names Udita Phookan and reserves rights. Third-party dependency,
model-weight and training-data licenses still need an explicit release review.

## Next bounded slice: local model protocol adapter

Add LocalSharedModel as an async ModelPort for a selected local shared Provider.
Parse exactly one JSON action; reject duplicate keys, NaN, extra fields, deep input,
oversize input and native tool-call responses to the JSON-only protocol. Declared
provider errors become model_unavailable; malformed decisions become
model_invalid_output. Unlisted programming errors remain loud.

The sync provider runs in a thread with a transcript snapshot. Cancellation stops
waiting, not that thread. This is not provider-process isolation or production worker
wiring. No credentials or inherited hosted fallback are used by select().

Tests exercise protocol controls and a real HTTP exchange to a synthetic loopback
server. They prove transport, not model reasoning, production auth or acceptance A.

## Seven-day checkpoints, not unsupported completion promises

Day 1: baseline/inventory and local model seam.
Day 2: mounted worker/configuration and real selected-model canary.
Day 3: PostgreSQL migration/isolation and restart/two-worker fencing.
Day 4: write-tool integration, payment/comms review and unknown-effect recovery.
Day 5: retrieval/correction/deletion and browser/device/channel canaries.
Day 6: independent regression/repair and migration rehearsal.
Day 7: reviewed integration/cutover only if all gates pass; name gaps otherwise.

Training and AGI behavior are separate evidence gates; this schedule does not turn
them into delivered functionality. Other builders own the wider Atlas and Sugarcode
lanes. No x1M performance claim is supported by this adapter slice.
