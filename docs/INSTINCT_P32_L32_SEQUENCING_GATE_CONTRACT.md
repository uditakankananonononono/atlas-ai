# P32|L32 - M30 sequencing gate (contract)

Source line, verbatim from line map v4 row P32/L32 (class NON-SCIENCE, mission M30):

> Sequencing: after all prior tasks are done, proceed to the last task (transitional, no standalone deliverable)

Source pin: instinct doc P32|L32, line map v4.

Provenance: this text is the line-map summary cell, relayed by the integrator from
`instinct-line-map-f35fc911.csv` (line 33 of the file, row P=32, L=32). I did not see the original instinct doc.
The P32 line itself gives no range. The range comes from the line map v4 row P33|L33 (mission M31), whose summary reads
verbatim:

> Claire PA sci-fi AGI upgrade (social scanning, acting, idea generation, outreach, competition applications, user-thinking copy via launch quizzing); merge Meemee capabilities; improve Sugarcode x1,000,000; only after missions 1-27; then send candy line (IN FLIGHT this side)

The gate range is missions 1-27, per that "only after missions 1-27" text. Missions M28, M29 and the gate itself (M30) are not
required. (Revision: the first version used tasks 2-30 from the assignment; the integrator corrected it to the P33 text.)

## What it is

`backend/app/modules/instinct_doc/sequencing_gate_p32.py` is the GATE mechanism only. It answers one question
from records the caller supplies: is a task-31 start blocked? It does not do tasks 1-27, does not start task 31
and does not send the candy line. The source line says "transitional, no standalone deliverable", so the gate
has no output beyond a verdict.

Composition, by import, no duplicated logic (each sibling is loaded by file path and cached):

| Piece | From | Used for |
|---|---|---|
| Coverage | P246 `compute_line_coverage` | a task line is covered only if it has a COVERED_BY_DECLARATION record and no UNCOVERED record |
| Audit marks | P243 `create_ledger`, `add_entry` | pass / fail / pending marks per task, with P243's own validation |
| Release decision | P247 `evaluate` | one `all_present` gate over `task-1`..`task-27`; its `release` decides the verdict |

## Rule

A task N in 1..27 is complete when both hold:

1. Its mapped line is covered per P246 (see above).
2. The P243 ledger holds at least one entry with `project_id` equal to `task-N`, and every such entry has mark `pass`.

The gate is open (`GATE_OPEN`, `start_allowed` true) only when all 27 tasks are complete. Otherwise
`GATE_BLOCKED`. A missing mapping, line, evidence or audit entry blocks; it never opens.
GATE_OPEN means the supplied records meet the declared rule. It is not proof that any task is done.
Result keys: `feature`, `source_lines`, `verdict`, `start_allowed`, `target_task`, `required_tasks`,
`complete_tasks`, `blocked_tasks`, `counts`, `release_decision`, `claims`, `method_limits`, `action`.
`action` is always `"none"`. Every `claims` flag is false.

## Request

`check_sequencing_gate(request)` and `render(request)`. Request fields: `line_map` (P246 rows, required),
`evidence` (P246 records, default empty), `audit_entries` (P243 entries, default empty), `tasks` (required),
`start_task` (required, must be exactly 31). Each `tasks` item is exactly `{"task": int, "line_id": "P<n>|L<n>"}`.
The result and the input are never mutated; the output is rebuilt on every call.

## Refusal codes

All refusals are `ValueError` with a message that starts with `P32:` and never contains input text.
Codes: `P32:bad_type:request`, `P32:unknown_field:request`, `P32:missing_field:<field>`,
`P32:bad_type:<field>`, `P32:control_chars:<field>`, `P32:too_deep`, `P32:bad_target`,
`P32:limit_exceeded:tasks`, `P32:unknown_field:tasks`, `P32:missing_field:tasks`,
`P32:bad_task_number`, `P32:bad_line_id`, `P32:duplicate_task`, `P32:duplicate_line`,
`P32:coverage_refused`, `P32:audit_refused:<kind>` (kind is the P243 code kind, for example `bad_mark`).

Hostile input: every string and dict key anywhere in the request is checked first for Unicode categories
Cc, Zl and Zp. A hit refuses with `P32:control_chars:<field>`. Exact types only: dict, list, str, int, bool,
float, None; subclasses and other objects are refused. Render output has one header line plus one line per
blocked task, under both `split("\n")` and `splitlines()`.

## Free check - interpretation

"FREE check" in the assignment was not defined. INTERPRETATION CHOICE: I read it as "no cost and no side
effects": the module and tests use the standard library only, make no network call, no file write, no clock read
and no subprocess, spend nothing and start no model. A test walks the module AST to enforce this. If FREE meant
something else (for example "free of a dependency on a specific task list"), this needs a decision.

## Interpretation choices

Nothing below is pinned by the one-line source. Each is mine.

1. INTERPRETATION CHOICE: the required set is missions 1..27 (27 tasks), read from the P33|L33 text quoted above and set by the
   integrator after audit. The "missions" in that text and the "tasks" numbered here are treated as the same numbers, which
   is a reading of the map, not something it states. The range is the constants `FIRST_TASK` and `LAST_TASK`.
2. INTERPRETATION CHOICE: the task-to-line mapping is supplied by the caller in `tasks`, because the line map does not say
   which line is which task number. An unmapped task blocks (reason `unmapped`) rather than refusing.
3. INTERPRETATION CHOICE: "complete mark" = P246 covered line plus an all-pass P243 entry set under `project_id` `task-N`.
   Entries for other project ids (task-1, task-31, anything else) are ignored.
4. INTERPRETATION CHOICE: P246 is called with every class present in the line map, so SCIENCE and NON-SCIENCE task lines
   are both checked. A task mapped to a duplicate, header or decorative row is not covered (`line_not_covered`).
   A COVERED record plus an UNCOVERED record on the same line is a conflict and does not count.
5. INTERPRETATION CHOICE: verdict strings `GATE_OPEN` and `GATE_BLOCKED`; reasons `unmapped`, `line_not_in_map`,
   `line_not_covered`, `no_audit_entry`, `audit_not_pass`, listed in that fixed order per task.
6. INTERPRETATION CHOICE: P247 gate id `task_marks`, kind `all_present`, required `task-1`..`task-27`. The P247 decision is
   returned whole as `release_decision`.
7. INTERPRETATION CHOICE: limits: at most 27 `tasks` items (28 refuses), nesting depth 8, 300000 nodes. P246 and P243 keep
   their own limits; their refusals surface as `P32:coverage_refused` and `P32:audit_refused:<kind>` without
   their text, so no input is echoed.
8. INTERPRETATION CHOICE: `start_task` must be exactly the int 31. The gate gates one target only.

## Limits

- It cannot tell that a task is missing from a caller's list beyond the required 1..27.
- It does not check that evidence or marks are true. Self-declared marks pass as easily as audited ones.
- It does not read the original instinct doc and does not enforce anything outside its own return value.
- Wiring, ledger and STATUS entries, and the later candy line, belong to the integrator.
