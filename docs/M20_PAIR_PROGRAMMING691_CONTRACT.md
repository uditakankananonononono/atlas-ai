# PAIR-PROGRAMMING691: bounded session-rotation and alignment diagnostics

Candidate SCOPED unit for ledger row 691 (Pair Programming - "Collaborates
on code"). The existing software_practice_685_709 cluster dispatches
pair_programming through a lambda shared with mob_programming that echoes
caller fields; this unit gives row 691 its own computation in
backend/app/modules/m20_general_cognitive_worker/pair_programming691.py.

Caller supplies a session record: session_id and task text, exactly 2 unique
participant IDs, 1..64 timed driver rotations and 1..16 shared-understanding
checks. Each rotation names a participant driver, a positive duration of at
most 180 minutes and an optional handoff note. Each check pairs bounded item
text with a real boolean confirmed flag. Missing, mistyped, duplicated,
out-of-range or unknown-driver inputs refuse with ValueError; nothing is
mutated or defaulted.

Computed, not echoed: per-participant drive minutes and exact drive shares,
a dominant driver at or above 0.75 of total minutes, participants who never
drove, consecutive same-driver rotation indexes, driver switches missing a
handoff note, and unconfirmed understanding items. Gaps roll up into a
named list and a two-state status (session_rotation_sound /
session_rotation_gaps). Balanced rotation requires no dominant driver and
both participants driving.

The output keeps honest labels: collaboration_observed=False,
code_changes_made=False, source_truth_verified=False, with an explicit
boundary string. This checks supplied records; it does not observe a real
pair, write or review code, or verify the session happened.

Synthetic tests pin the exact sound-session envelope, the 0.75 dominance
boundary from both sides, alternation, handoff-note and never-drove gaps,
unconfirmed alignment, the 180-minute bound, and typed refusals. Mounted
router wiring is not part of this package; auth/tenant behaviour is
untested here.
