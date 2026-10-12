# Reviewed-execution gate for APP-PLANNER drafts

## Design rationale

The landed per-site application planner (`site_application_planner.py`) stops at a
draft descriptor whose handoff says proposal-only and requires exact review; its own
contract states the descriptor is not authorization and that a reviewed integration is
separate work. This module is that separate, local gate: an explicit human-review step
must exist, recorded and auditable, before any execution-side step may draw on a draft.
It performs no execution itself.

## What it does

`open_review(plan, ...)` accepts only a plan with status `draft_ready_for_review`,
`submission_enabled`/`browser_action_performed` exactly false, and a handoff that
requires exact review with hashes matching the plan. The draft digest is recomputed
from `draft_values` (sha256 of the JSON with sorted keys) and a mismatch is refused,
so a tampered draft cannot ride on a stale self-declared hash. `snapshot_sha256` is
taken on trust: the HTML is not available here to re-hash. The review binds the exact
`site_url`, the trusted `snapshot_sha256` and the recomputed `draft_sha256` of that
one draft.

`record_decision(ledger, ...)` appends one final human decision (`approved` or
`rejected`, with reviewer label and rationale). One decision per review, never amended.

`issue_permit(ledger, plan, ...)` refuses unless the review exists, is approved, is
inside its caller-declared validity window (measured from `opened_at`), the presented
plan still matches the reviewed site_url, the trusted snapshot hash and the recomputed
draft digest exactly, and no permit was issued before. A permit is single-use: a
second issue for the same review is refused. Timestamps are ordered: a decision before
the opening and a permit before the decision are refused, and a validity window that
overflows the clock is refused. The permit carries `executes: False` and a boundary
string stating it authorizes nothing by itself. A permit is a plain dict; there is no
permit-verification function - any consumer checks the ledger, not the dict.

`audit_state` reports `open` / `approved` / `rejected` / `permit_issued`.
`dumps`/`loads` round-trip the ledger for caller-side persistence. Records are
hash-chained (seq + prev_hash + record_hash); `loads` and every direct call
(`open_review` with a ledger, `record_decision`, `issue_permit`, `audit_state`)
re-verify the chain, each record's fields per kind, and the per-review order (one
open, then at most one decision, then at most one permit; timestamps ordered; permits
consistent with the opened review and inside its validity window). Edited, rechained
or out-of-order ledgers are refused, never extended. The module never writes files:
persistence location and storage safety are the caller's job.

## Limits (stated plainly)

- Reviewer identity is a caller-supplied text label, not authentication. The module
  cannot know who made a decision; it only records what the caller asserts.
- The ledger is tamper-evident, not tamper-proof. Anyone who can rewrite the stored
  ledger can recompute the chain; integrity checks catch accidental corruption and
  casual edits, not a storage attacker. Truncating or rolling back a persisted ledger
  to an earlier prefix also passes every check - that defeats single-use (a permit can
  be issued again) and erases a rejection. Treat the stored ledger as append-only and
  protect it accordingly.
- The clock is caller-supplied. Order is enforced within a review (open, then
  decision, then permit) and validity windows are checked, but the timestamps
  themselves are whatever the caller asserts; nothing authenticates them.
- A permit binds only the exact site_url, the trusted snapshot hash and the recomputed
  draft digest reviewed. If the live form changed after the snapshot was taken, this
  gate cannot see that; the planner's own contract already states hashes do not
  establish the live form still matches.
- No execution is performed or wired: no live research, no form fill, no submission,
  no external calls, no account use. Browser execution, m00 approval flow wiring and
  m13 submission wiring remain separate future integrations.
- Approval here is a process record, not consent for any real application; the human
  decision itself is outside the module and is the applicant's own review step.

## Validation doctrine

Exact builtin dicts (subclasses refused), review ids 1-64 chars of `A-Za-z0-9._/-`,
text fields non-blank and at most 256 characters, valid_hours a finite number in
(0, 720], timestamps timezone-aware ISO, ledger capped at 512 records, hashes exactly
64 lowercase hex. Every refusal raises ValueError with an `APPREX: ` message.
Standard library only (`hashlib`, `json`, `math`, `re`, `unicodedata`, `datetime`, `__future__`).
No caller object is mutated; ledger extensions return new lists.

## Verification scope

`tests/modules/test_m02_reviewed_execution.py` (40 tests) pins the golden path, the
gate refusals (non-complete drafts, execution flags, handoff requirements, undecided /
rejected / decided reviews, single-use permits, digest recomputation and tampered
drafts, exact-string subclass boundaries, exact-hash and site matching, ordered
timestamps and the inclusive validity deadline), validation bounds, ledger chain,
content and order verification, serialized-text bounds, dumps byte stability and the
hermetic import set. Not run: the full suite, any browser, any network, any real
review by a real person.
