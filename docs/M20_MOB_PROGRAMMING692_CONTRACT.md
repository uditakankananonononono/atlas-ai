# Row 692: Mob Programming ("Teams on one problem")

Module: `backend/app/modules/m20_general_cognitive_worker/mob_programming692.py` (standard library only).
Tests: `tests/modules/test_m20_mob_programming692.py`.

## Scope

The source row text is "Mob Programming - Teams on one problem". It gives no more detail, so this
contract implements a bounded reading of it: a whole team works on a single task with one driver at
the keyboard at a time. The module plans the rotation and audits a recorded session. It does not run
sessions, contact people or touch external systems. Results are for human review.

## API

`plan_mob_session(participants, task, session_minutes, rotation_minutes, start_driver=None, break_every_minutes=None, break_minutes=5)`

- At least 3 unique, non-empty participant names; non-empty task; positive integer minutes (bool rejected); `rotation_minutes <= session_minutes`.
- Each turn has one driver, one navigator and the rest as `mob`. The navigator becomes the next driver and the previous driver goes to the back of the queue.
- The last turn is shortened so work minutes equal `session_minutes` exactly.
- Breaks (optional) are inserted only at a turn boundary once `break_every_minutes` of work have passed since the last break, never after the final turn. They do not change who drives next. `total_wall_minutes` includes breaks; `driver_minutes` does not.
- Returns turns, `driver_minutes`, `driver_minutes_spread`, `everyone_drives`, `work_minutes`, `total_wall_minutes`, `human_review_required: true`.

`audit_session_log(log, participants, max_driver_share=0.5)`

Checks a recorded log of `{driver, start_minute, end_minute}` entries. Violation codes: `empty_log`, `unknown_driver`, `bad_interval`, `overlap` (two drivers at once), `driver_share_exceeded`, `never_drove`. `ok` is true only when there are none.

## Not covered

No routes or wiring are included. No persistence, no calendar or chat integration, no check that the
navigator actually navigated. Fairness is measured in driver minutes only.

## Recovered-package bounded repair

Recovered runtime/test/doc identities478d1f75/7417309d/b3fed7da verified before
repair on public c0993650. Audit found unbounded session/participant/task growth,
incidental exceptions for malformed log entries, bool/nonfinite intervals, NaN
share bypass, unchecked unused break_minutes and inconsistent driver trimming.
New RED50 failed/21 passed on recovered runtime; no claim of original RED custody.

Exact builtins only (participants exact list/tuple, log exact list, entry exact dict,
name/task exact str, plan minute exact int, audit minute/share exact int/float).
Participants3..32, name raw200, task raw2000, work/rotation/break parameters1..1440.
All plan parameters validated even unused breaks. Derived total turn+break records
<=2000 checked before allocation. Logs0..2000; each exact key set driver/start_minute/
end_minute, cardinality3 before key traversal/set. Times finite0..1000000 (bool
refused); share finite0<share<=1 (bool refused). Invalid type/shape/number ValueError,
no incidental AttributeError/TypeError or huge-int overflow. Chronological bad
interval (end<=start) remains a diagnostic bad_interval, not malformed-type refusal.
Empty log remains not-ok diagnostic. Driver/name/task controls Cc/Cf/Zl/Zp refused,
raw caps before scan; Zs accepted, name/task stripping retained. Padded log drivers
normalized consistently. Outputs retain validated names/task (this recovered API
intentionally echoes supplied plan labels); error messages use fixed field names.

Honesty on plan/nonempty/empty audit: session_executed=false,
evidence_independently_verified=false, human_review_required=true. No attendance,
software quality, real session compliance or external action claim. No routes/init/
shared cluster edits. Real3.12.14 unchanged conftests.
Own16 flips initially8 killed/8 survived; combined-fault/boundary pins added for
real gaps. Final13 killed/3 EQ: later task cap masked by earlier raw task2000;
share/minute isfinite removal masked by bounded comparisons excluding NaN/inf;
these are redundant checks, not unpinned accepted nonfinite values. (Final exact
battery accounting in separate receipt.) FULL-SUITE UNVERIFIED.
