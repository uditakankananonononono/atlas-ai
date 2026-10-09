# M24 slice5 verified inbox/lifecycle, INACTIVE candidate

Base merged main1c28cd3c68d0ab0bad391846b72e84bbfd483a75 independently spot-verified by executor108slice4+84luxury. Branchm24-slice5-verified-inbox-20261009. No push/deployment/activation/provider traffic/credential reads. Gate then executor reproduction required before landing. All code rebuilt for this unit; no Claire/memo3 integration.

## Ordering and trust

New verified identity namespace is account:test:eventID. WebhookAdmission verifies original raw bytes with existing HMAC timestamp verifier and checks event.object/id/type/shape, livemode=false, pinnedAPIversion, fixed endpoint account binding and Connect account match BEFORE admission. Own-account events must have account absent; Connect configuration is explicit. Readiness remains unconditional refusal; no default admission/inbox injected into production service. STRIPE_WEBHOOK_SECRET env alone no longer enables legacy signed lifecycle writes. Binding an endpoint secret to its real provider account and verifying TEST snapshot-version support remain operational prerequisites, not tested facts.

VerifiedEvent is trusted INTERNAL producer object, not cryptographic provenance in itself. No public API accepts that object or provider_account parameter. Internal forged objects/operator DB edits are outside claimed protection. Raw SHA256 and canonical payload digest detect accidental/local tampering, not provider signatures or adversarial-DB resilience. Secret/signature/raw request are not stored in quarantine; only bounded eventID/digest/reason/time. Verified payload snapshot is stored privately, bounded262144bytes; retention/export policy not yet implemented.

Admit commits pending first. Unique identity plus digest prevents conflicting redelivery silently succeeding. Raw-byte digest means even whitespace/reserialization differences for the same event hold as conflict, conservatively. Insert races accept only exact winner; a race conflict refuses but does not currently append a separate quarantine row on that IntegrityError branch. Same-ID unsigned diagnostics are separate quarantine and report processed=false; caller trusted_provider=True never grants lifecycle admission. No legacy events promoted/backfilled. Old nontransactional _apply_lifecycle_event disabled explicitly; provider path only through verified admission.

Apply serializes inbox row then provisioned resource ownership row, locks TenantBilling, validates exact account/environment/resource/customer/tenant/client reference and local mapping. Signed metadata alone cannot provision ownership. ResourceBindingRow has NO public setter/default production provisioning; fixture rows are not real provider-identity proof. Checkout uses subscription resource so subsequent subscription events share ordering cursor. Invoice own resource has its own cursor. Cancellation customer-fence remains independent and unchanged.

Lifecycle+resource cursor+applied marker in ONE transaction. db.flush precedes inside-apply kill hook, so that kill occurs after actual uncommitted lifecycle SQL, not only Python assignments. Apply failure rolls back all three, preserves pending row with bounded failure and allows exact signed redelivery/retry. Explicit apply(knownID) resumes durable pending without re-verifying an expired webhook signature; no provider I/O. No background polling/queue wiring yet, so pending requires redelivery or internal apply call. Applied readback no lifecycle replay. Unsupported/unbound events stay pending, not acknowledged as applied.

Per-resource provider created timestamp is the monotonic cursor. Older is ignored_stale. Equal timestamp/different digest is held, NEVER arrival-order overwrite. Same state/type repeated at same time is still conservative hold because digest includes eventID. No authoritative provider refresh/conflict resolution implemented. Cursor is not a global ordering/version guarantee; two different resource IDs for the same tenant can still affect shared state. Invoice and subscription cursors separate. No automatically provisioned new subscription/customer migration or checkout operation adoption.

Checkout activation requires payment_status=paid AND complete subscription session, exact succeeded durable checkout operation/account/version/tenant/approval/sessionID/plan/step/amount/currency, provisioned ownership and clientreference. unpaid/no_payment_required conservatively refuses, no free/subscription-trial entitlement autoactivation. Event.created must not exceed op.dispatch_not_after when recorded; that is a conservative upper bound (not proof of actual payment time) and may hold legitimate delayed completion. No automatic provider refresh or new deadline authority. Subscription updates validate explicit status/period/cancel flag; deleted requires canceled. Invoice paid validates paid status and amount_paid>=amount_due. No hosted provider URL trust; no refund/send/pay/compensation/provider lookup.

## RED receipts and GREEN controls

RED-legacy-four-gaps.log:4FAIL before product edits, using old Service flow: unsigned poisoning, apply-failure redelivery lost, unpaid checkout active, stale resource overwrite. Source legacy-red-probes.py preserved under audit, NOT collected acceptance tests. These are behavioral assertions on old flow, not provider effects.

New78nodes:76nonmigrationPASS2deselected45.87s (GREEN-restored-final76.log), plus2migrationPASS74deselected56.85s (GREEN-final-migration2.log; test bodies unchanged by last concurrent test addition). Python3.12.14, SQLite3.53.1, pgserver0.1.4 bundledPG16.2. No fullrepo/CI/production durability claim.

6 external SIGKILL nodes = pending-committed-before-apply, flushed-inside-apply-beforecommit, applied+markercommitted-beforeack xSQLite/PG. Fsynced PIDready, assert -SIGKILL, PIDdistinct resume, inspect pending/lifecycle/cursor jointly after kill, then exact applied readback. No model/provider mutation or receipt simulated here. This is child-process crash evidence, not PG server restart/WAL/powerloss/failover.

15 one-predicate mutations bite,2FAIL each (76deselected in final set), harness and raw RED retained: unsigned namespace, digest conflict, paid status, deadline, amount, tenant, customer, stale cursor, equal-time hold, TEST event, APIversion, endpoint account, applied marker, stored payload digest, commit split/rollback atomicity. Product bytes restored in finally; finalGREEN after restoration. rollback-atomic mutation intentionally commits lifecycle early, then injects failure and detects changed state; not merely error-classification bite. Initial tenant mutation SURVIVED due second per-field tenant check; first receipt/summary retained. Removed truly redundant aggregate tenant check, retained required metadata+perfield exact checks; perfield-removal now bites. No initial survivor silently erased.

Prior affected disjoint completed sets:
104slice4nonmigrationPASS4deselected67.16s;2cancelmigrationPASS66deselected24.40s;2reconciliationmigrationPASS38deselected43.26s;
76invoicenonmigrationPASS2deselected55.49s;2invoicemigrationPASS76deselected54.62s;
84checkoutnonmigrationPASS2deselected56.02s;2checkoutmigrationPASS84deselected54.70s;
293storage+otherM24+M00PASS74.92s;
6adjustedtest_billingPASS2deselected0.51s.
These573priorpasses +78new =649distinct completed passing nodes, NOTcombinedrun. Manifest651includes2known failing old billing fixtures. Some affected suites preceded final inbox-only digest/flush/concurrency changes; no claim full final-tip replay. Overlapping GREEN32/63/72/76 and mutation passes are NOT additive.

Affected-legacy-first.log:5FAIL9PASS. Three failures were expected changed legacy event contract, repaired explicitly in original tests: unsigned/notconfigured refuses and cannot alter lifecycle, rather than trusting callerboolean. Two unrelated old fixture failures remain: test_money_requires_proposal_and_approved_execution expects legacy direct checkout despite fail-closed readiness; test_cancel_and_invoice_are_separate_tenant_bound_approval_actions supplies Repo without tenant_billing. Exact landed base1c28cd3c separate worktree reproduced2FAIL6deselected0.56s (RED-exact-landed-base-existing-two.log), not merely new-code comparison. Neither silently fixed/deselected into a fullsuite success claim. The6-node adjusted run explicitly deselects them. Repository fullsuite remains RED/unknown, named receipts available.

One combined bash execution limit interrupted checkout run after83progress marks, no verdict: affected-checkout-interrupted.log retained. Complete separate84node rerun above; interrupted progress never counted as pass. Migration source new20261009_m24_verified_inbox on cancellation head, no renamed history. Populated legacy event survives without promotion; empty downgrade works; quarantine-populated downgrade refuses. Populated verified/cursor separately not migration-tested here, although implementation refuses any of three table counts. No live migration/interrupted migration.

## Exact peer run instructions

Use clean candidate clone and full[dev] install, own Python>=3.12/nonrootlocalPG/tempfiles. EXPORT PYTHONPATH=<absolute-repo-root>/backend IN ENVIRONMENT; pytest.ini alone cannot reach fresh SIGKILL child interpreters. Run sequentially:
PYTHONPATH=backend python -m pytest -q tests/modules/test_m24_verified_inbox.py -k 'not populated_inbox'
PYTHONPATH=backend python -m pytest -q tests/modules/test_m24_verified_inbox.py -k populated_inbox
PYTHONPATH=backend python audits/rebuild-20261009/m24-slice5/mutations.py
Mutations only in disposable clone, never commit/push/deploy changed product. Harness restores bytes even on assertion failure. No seeds beyond fixtures; no secrets/accounts/database/PIDs/tmp paths copied from builder. Real HMAC test secret whsec_fixture and acct_fixture are local fixtures only. Each DB/ownership row fresh under tmp_path. Tests may spawn local servers and kill own subprocess; no external Stripe requests. Timings above are observations, not tolerances; kill readiness/restart12s, wait5s, migration30s per subprocess, barrier5s.

## Remaining hard limits

INACTIVE only. No checked credential rotation/egress/runtime readiness/version verification/account secret binding/production resource provisioning; no defaultadapter/inbox config. No negative absence/retry or automatic paid spend. No thin-event fetch, list/search, general webhook support, source event expiry beyond signature admission, conflict review/release, multi-resource tenant cursor, backgroundpendingworker, historical inbox promotion/retention policy, signedinbox provider TEST coverage, generation budgets (slice6), Claire seam, fullsuite/CI/PGserverrestart/powerloss/failover/interruptedmigration. New snapshot-version reliance is a requirement, not TESTaccount proof.

Sources actually fetched this unit:
https://docs.stripe.com/webhooks (raw signature, duplicates/order/version destination behavior)
https://docs.stripe.com/api/events/object (account Connect-only, livemode/api_version/created)
https://docs.stripe.com/api/checkout/sessions/object (payment_status field)
No invented provider object links or live provider claims.

## Gate-requested guard additions after 5e330527

Original gate SCOPED PASS reproduced78nodes and confirmed2preexistingbillingfailures; landing still held for re-review+executor+parent decision. Tests/receipts/docs only, no product/migration/readiness/defaultadmission/worker changes.

18 added SQLite/PG nodes isolate futurecreated>now+300, localcustomer/local subscription mapping drift, checkoutoperationstate and exactreceiptID, invoicepaidstatus vs amountpaid independently, existinginvoiceforeignownership, deletedsubscriptionactive rather thancanceled. Each changes only named field and asserts pending/unchangedlifecycle+cursor where relevant.9mutations independently remove/weaken these guards and all returnpytest1 DID NOT RAISE,2FAIL each. checkout-state selector additionallyruns2passingresultIDcontrols, explicitly not mutation evidence. Restored bytes aftereach. GREENadditions18PASS78deselected7.98s; restored fullnonmigration94PASS2deselected49.83s. Original2migrationnodes unchanged/notrerunhere. Updatedacceptancemanifest96nodes. Initial78+18new=96distinctcontrols, NOT172fromoverlap. Updatedaffectedmanifest669includes2namedknownbillingfailures;649earlierdistinctpasses+18added=667distinctcompletedpasses across disjoint/overlappingruns, NOTfreshcombinedsuite.

Binding.provider_account check is redundant by construction in normal production rows: identity is fixedaccount:test:resource and no public provisioning exists. Retained defense-in-depth against malformedinternalprovisioning/DBrows, not independentlytested behavior. Do NOT count original tests as isolating this guard. Verified internal object/database trust limits unchanged.

Reproduce newmutations using PYTHONPATH=backend python audits/rebuild-20261009/m24-slice5/gate-addition-mutations.py in disposableclone; harnessexactselectors+rawRED-gate logs retained. Product restored. Fulloriginal15mutationrun not repeatedforthese test-only additions; originalreceipts remain. No activation/providertraffic/push.
