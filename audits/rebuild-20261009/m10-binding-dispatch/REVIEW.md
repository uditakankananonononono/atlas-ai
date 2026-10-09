# Isolated memo 1 + 2 branch review

Base: a1fbe5970471e50dad1df2bb511e47a15506723a. No main merge or publication authorized. Only probe authority/baseline and dispatch-boundary design work implemented; memo 3-8 remain open.

## Runtime contract

M10 send_email_reply gets a frozen context from persisted approval ID/owner/module/action/payload digest. Its trusted SendReplyProbe receives that context rather than payload-selected authority. Tenant mismatch refuses before token/data reads. Message/account/draft selection is tenant-scoped; draft must link to message, account and actual approval. Payload account/Gmail target/thread/recipient/subject/body must match linked storage. Missing draft, non-pending draft, missing/trashed reply target or owner already replying refuse. Returned thread identity must match. Other generic probes keep the existing payload-only contract.

M10 capture refuses arbitrary explicit state and non-M10 callable substitution. Snapshot embeds exact approval binding; approval decision and direct permit consumption refuse missing/explicit/foreign snapshots. Historical unbound approvals require trusted fresh capture while pending and fresh review; already-approved unbound approvals refuse rather than silently migrating. Denial remains available without a snapshot. Failed capture cannot approve until a successful fresh bound capture. Preview without a snapshot never claims safe_to_consume for M10.

At worker dispatch, M10 requires a conditional adapter registered through the separate conditional registry. No production M10 conditional adapter is installed: default behavior is refuse before consuming a permit. There is NO automatic risk-accept path. Gmail conditional/version support remains unverified. The fixture adapter compares the condition and effects within its local lock; it is not a live-provider implementation. Registration of a callable interface does not prove a provider capability: any future adapter needs independent capability/operation acceptance before production registration.

Worker gives adapter exact approval binding and observation state hash; the adapter's dispatch_if_current must enforce that condition in the actual effect operation. Preflight checks alone do not guarantee atomicity. Tests force observed-world changes before read, after read/before permit, after permit/before dispatch and at dispatch and assert no fixture effect. A provider without a dispatch-enforced equivalent is refused, not labeled atomic. This is dispatch containment plus a reviewed adapter seam, not Gmail atomic sending.

Permit-once still does NOT imply execute-once. If a condition refuses after permit issue, consumed accounting can exist without an effect; durable outcome/retry ledger is memo 3, not implemented. Local fencing cannot stop stale external effects without adapter-enforced fencing/idempotency, and lease expiry cannot authorize an unknown retry. Direct SDK consume remains permit accounting, not an executor.

## Tests and fixture changes

New tests: tests/modules/test_m10_binding_dispatch.py. Exact names enumerate owner-isolated preview/capture/consume, zero external reads, each resource/content mismatch, each stored-draft link mismatch, baseline missing/trashed/sent/missing-draft, explicit marker bypass, legacy approved snapshot absence, failed/recovered capture, snapshot replay across approvals, denial, immutable context, disconnected account, untrusted named probe and conditional dispatch boundaries/default refusal.

Existing M10 drift fixture now includes account_id and links the draft to the durable approval before capture. Unknown-message test now uses the authorized capture entry instead of invoking a raw payload-only M10 probe. Existing drift/path assertions retained. Branch targeted selection initially315PASS, then six additional acceptance cases added with no runtime changes: final M10/new binding selection46PASS. No production send occurred.

## Full-suite gate and resource provenance

Initial collected scope11179unique nodes. Serial receipt selection covers the identical set exactly once:11147PASS/31SKIP/1retainedFAIL/0ERROR. Not an all-green suite. The one retained failure is M13 Chromium Page.captureScreenshot unable to capture screenshot; narrow branch4PASS and exact published-base runtime4PASS in the same environment did not reproduce it. All three logs retained. This is nondeterministic environmental/test behavior, not erased and not proven branch regression.

Original whole-suite attempt timed out exit124 at approximately9%. Batches11-14 failed/aborted on PostgreSQL initdb no-space errors. Smaller identical-node reruns after cleanup completed clean; original failure logs retained. Some batches timed out and were split without changing node scope. Aggregate verifies node set/cardinality, but separate pytest processes do not prove global single-process order independence.

After the full11179scope, six additional new acceptance nodes passed in46-test targeted run. The final repository therefore has11185nodes in the ordinary suite, with the extra six checked separately. The diagnostic concurrency harness is outside test collection, at audits/rebuild-20261009/m10-binding-dispatch/concurrency_harness.py, and must be run explicitly. It deliberately preserves the invalid executor-barrier assumption for reproduction; it is not an automatic green acceptance test.

Disk audit:29GBvolume; current venv7GB retained; older local acceptance3.6GB retained; prior frontend862MB retained; duplicate browser cache657MB removed from /tmp/atlas-ci-no-browsers only. Live ~/.cache/ms-playwright657MB retained. Serial disposable pytest cleanup freed space. No source/receipts/local acceptance data deleted. Available space about970MB after cleanup.

## Concurrency receipts, separate from binding acceptance

Historical builder original-barrier1FAIL/12, reviewer3FAIL/12 (trials0,3,9), each preserved separately. New branch standalone barrierFAIL plus repeated trial5FAIL/12: diagnostic harness16PASS/2FAIL. All failures include BrokenBarrierError + pre-executor used-effect conflict. New branch no-barrier12/12 duplicate; profiles0ms19dup/1conflict,1ms19/1,10ms20/0. Deterministic winner-after-approval-lookup/before-effect-lookup passes. Profile-bound duplicate behavior remains, no memo3 execution-ledger repair inferred. The barrier itself assumes two arrivals despite a legitimate conflict; retain failure provenance and use outcome-measuring controls for meaningful acceptance.

## Limits and review questions

- No main changes/push, no live Gmail/provider/broker acceptance, no production readiness or M00 completion claim.
- Baseline policy and stricter binding intentionally reduce M10 availability. No implicit fallback for legacy/unbound requests.
- Snapshot trusted provenance here relies on application capture and private database integrity, not cryptographic attestation against a database writer.
- Conditional adapter interface alone is not external atomicity. Review whether default refusal plus the adapter seam closes memo2 at containment scope; provider implementation remains unavailable.
- Typed errors/wire metadata/audit widths/PK/outbox/outcome ledger are not broadly repaired here. Returned-thread identity checking is required resource binding, not the whole memo7 taxonomy.
- Handle retained Chromium nondeterminism explicitly in review; never call the aggregate all-green.

## Final collection verification

Fresh pytest collection reports11185tests. Set reconciliation against the original11179IDs confirms zero removed and exactly six added. All six added nodes are included in the46PASS targeted receipt. acceptance-manifest.json enumerates every new binding test parameter, all existing M10 drift nodes, and the exact six-node delta. Diagnostic harness relocation removes no node from the original full aggregate; it was never in that scope. No whole-final-suite all-green claim follows.
