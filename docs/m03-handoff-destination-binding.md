# Grant handoff review binds recipient and action

ReviewApproval previously retained only handoff ID and artifact hash. A replaced
handoff with the same ID/artifact but another recipient or action passed the
local assert_dispatchable check. Approval now records recipient/action and the
check requires their exact nonempty equality. Old four-field approval objects
still construct with empty default fields, but fail dispatch checks until reviewed
again. Artifact integrity checks remain.

Local deterministic report/handoff tests replace recipient and action separately:
both pass through the old guard and are refused after repair. No external send,
publish or submission was performed. This is a local binding check, not authenticated
reviewer identity, durable approval storage, replay prevention or authority proof.
Caller-supplied handoffs/approvals can still be forged; all external effects still
need the real approval center integration. The corpus-ID candidate is an ancestor.
