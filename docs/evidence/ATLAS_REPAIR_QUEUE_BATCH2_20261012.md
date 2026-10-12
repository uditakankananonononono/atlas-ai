# Atlas repair queue batch 2

Base: `78ef85579f738497387e5b6ec84f9c1c3d94a402`, after batch 1 and its positive-route fixture reconciliation. Local only. No push. No live publication or spending.

## Test evidence

Before code changes: four publication cases failed (wrong-audience effect ran, retired provider key was accepted, no configured preflight/registry contract); two M18 cases failed (generic spend placeholder got an approval, fabricated succeeded receipt accepted). Saved red logs accompany the patch.

Focused mounted/service selection after changes: 25 passed, one warning on Python 3.12.14. This includes original publication route, persisted acceptance, receipt verification, key lifecycle, all new safety regressions, durable M18 runs and official runner tests. Three additional negative cases were added after the first red pass: restored budget approval, unverified unknown receipt, caller-provided key map not establishing mounted-route trust.

Broader M17/M18/M19 selection before those final three additional cases: 1213 passed, 8 skipped, 19 deselected, two warnings. Selection:

```
python -m pytest tests/modules/test_m17*.py tests/modules/test_m18*.py tests/modules/test_m19*.py tests/modules/test_repair_*.py -k 'not test_actual_second_process_factory_pending_and_tenant_isolation and not test_m19_immutable_snapshots' -q
```

The immutable-snapshot tests require unavailable pgserver and account for 18 deselections. The second-process factory case fails its Python subprocess setup on the base too, independently reproduced on the unpatched base; this is the remaining deselection. A prior unfiltered run had 17 pgserver setup errors, 8 skips, and the subprocess failure. These are not presented as passing tests. Full repository suite was not run.

## Per-card disposition

| Card | Status | Change and limit |
|---|---|---|
| ATLAS-m17n.A04 | NARROW SAFETY FIX; TRUSTED ADAPTER BOUNDARY | Publication gate requires side-effect-free signed preflight, resolves active tenant/provider/key trust from configured registry before publish, verifies exact essay/hash/audience, and authenticates returned receipt after publish. Mounted receipt verification ignores caller trust bytes. Wrong audience and retired key both stop before publish. |
| ATLAS-m18.A05 | FAIL-CLOSED SAFETY FIX; RUNTIME OPEN | Request and authorization refuse generic budget/spend placeholders, including restored old approvals. No spend adapter, actual spend ledger, currency/merchant/total/undo-term checkout validation or real cap accounting is implemented. Cannot close original runtime with this short patch. |
| ATLAS-m18.A06 | FAIL-CLOSED DEFAULT; PROVIDER ADAPTER OPEN | Succeeded receipt requires injected trusted-host verifier returning exactly True. Callback receives copies of receipt/action/artifact. Default mounted service does not configure a verifier and refuses succeeded records. Failed/unknown are unverified caller observations. Provider integration and cryptographic/provider exact-payload verification remain host-adapter obligations; a callback accepting only an ID is a unit fixture, not production proof. |
| ATLAS-m19.A01 | CANNOT CLOSE WITH SHORT PATCH | Core Service.intake only emits the intake gate and sets LANDSCAPE. No seven-stage execution runtime. Requires a designed stage executor and evidence-backed gates, not labels. |
| ATLAS-m19.A04 | CANNOT CLOSE WITH SHORT PATCH | ResearchAnalysisService._compute has computations for 115/120/121/134; the other 21 required-input methods return copied sections/caveats. Method-specific computations and validation remain absent. |
| ATLAS-m19.A05 | CANNOT CLOSE WITH SHORT PATCH | Core routes do not mount the lane ledger. Wiring it without reconciling duplicate schema/state/tenant/ownership contracts is not a safe short fix. |
| ATLAS-m19.A06 | CANNOT CLOSE WITH SHORT PATCH | Core flow lacks durable Postgres stage runs, queue/retry/repair, sandbox/deployment, scans, kill switch and PDF rendering. INTEGRATION.md is an imperative implementation plan, not evidence these systems execute. No completion claim. |

## Trust and compatibility bounds

The publication adapter contract intentionally changes from publish-only to prepare+publish. Existing unsigned fixtures are updated to active configured signatures. Registry lifecycle and signing trust are configured by the host; the existing tenant key-registration route is not upgraded here into administrative provider enrollment. A provider's signature authenticates its assertion, not actual published bytes. An arbitrary adapter can violate side-effect-free prepare or publish a different object; the gate does not sandbox arbitrary code. Final receipt failure cannot undo an already-run effect. This is a fail-closed trusted-adapter interface, not arbitrary-adapter confinement or atomic provider publication. Registry revocation between prepare and effect remains a distributed-state race.

M18 verifier injection is code configuration, not caller request data. Outcomes are still explicitly observed inputs, not independently verified. Unknown/failed receipts and historical stored snapshots are not retroactively authenticated. The patch does not supply a live provider verifier.

M13-M16 are outside this patch scope and are untouched.

## Reviewed-binding snapshot regression

An additional red case reproduced request mutation inside prepare: the prior acceptance check passed for hash a, then the effect published hash c. The gate now revalidates and freezes a private scalar request snapshot and copies acceptance before any adapter callback. Preflight verification, effect arguments, final verification and returned metadata all use that frozen snapshot. Changed signed preflight bindings are refused before publish. Mutating the caller request during prepare or publish cannot change the approved effect or returned metadata.
