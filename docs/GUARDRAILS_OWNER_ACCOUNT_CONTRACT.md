# Owner-Account Identity Gate - Contract (group 139, line 1)

Bounded mechanism: `backend/app/runtime/guardrails/owner_account_gate.py`.
An enforced runtime check over every external-service call. This document
scopes the mechanism only.

## Rule

A (service, account_identity) pair is usable only when the gate's ledger
carries a binding that is `binding_registered` then `binding_verified` and
not `binding_revoked`. `call(ledger, call_id, service, account_identity,
effect=..., now=...)` is the choke point:

- state verified -> the effect runs; the admitted call is ledgered (and a
  failed effect ledgers its error type);
- state unregistered / registered-unverified / revoked ->
  `GuardrailRefusal("ACCTGATE:refused:<state>")`; the refused call is
  ledgered first; the effect is never invoked.

Registration order is enforced on the chain: verify/revoke require a live
registration; re-registration is allowed only after revocation.

## Limits (named, none hidden)

- Verification is CALLER-ATTESTED: the gate records who verified, when, and
  under what evidence reference, and enforces that only currently verified
  owner accounts are usable. It cannot authenticate the account; wire live
  probes through `app.integrations.acceptance` for that.
- The gate binds (service, account_identity) pairs only; permissions inside
  the account are out of scope.
- The ledger is an unkeyed hash chain: tamper-evident, not tamper-proof. A rehashed edit is not detectable; safe storage of the serialized ledger is the caller's job.
- Admission/spend records are committed write-ahead via the `on_commit` hook BEFORE the effect runs and are retained on ANY exception the effect raises; an effect that fails after admission reconciles as spent-pending-review, never silently re-usable. Without a wired `on_commit`/persist sink the ledger lives in memory only.
- `reviewer` / `granted_by` / `verified_by` labels are caller-supplied DECLARATIONS, not authentication. A record carrying `authority_ref` (an approval-store reference) Fail-closed coverage, exactly as coded: (a) a verification carrying
  `authority_ref` with NO hook configured fails; (b) when a hook IS configured, verification
  requires a validated `authority_ref`; (c) the hook receives (authority_ref, binding digest) where the
  digest binds the exact (service, account_identity) pair, and accepts only with a strict True or a
  verified-permit object. With no hook configured, verifications without `authority_ref` remain
  unvalidated declarations.
