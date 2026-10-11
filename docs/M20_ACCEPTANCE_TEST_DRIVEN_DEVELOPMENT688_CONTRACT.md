# M20 Row 688 Contract: Bounded Declared ATDD Agreement Bookkeeping (ACCEPT688)

Ledger source (audits/coverage-register.json, row 688):

> - requirement: "Acceptance Test-Driven Development"
> - description: "Tests from user perspective"

Ledger status (audits/additional-2000-features.json, id 688, read at
a294723b7a8f7bbe6067804ee4d7d325e1a8bde9): PARTIAL.

## Delta from the existing mechanism

Existing mechanism: `_atdd` at
`backend/app/modules/m20_general_cognitive_worker/software_practice_685_709.py:22`
(shared cluster file, not edited). It echoes the caller's
`acceptance_criteria`/`examples`/`stakeholders`/`agreed_by` raw, pins
`executable_before_implementation=True`, and computes
`agreement_complete` as `set(stakeholders) <= set(agreed_by)`. The cluster
boundary set (`_tdd` at line 21 caller-declared red/green evidence; `_review`
at line 25 with `self_approval_forbidden=True`) is unchanged.

This row-688 unit changes the surface materially:

- **Typed exact validation with row-tagged refusals.** The mechanism indexes
  raw fields and raises whatever the data triggers (`KeyError`/`TypeError` on
  bad shapes); the unit refuses missing, blank, mistyped, duplicated and
  oversize inputs with exact `ACCEPT688:` codes before any bookkeeping.
- **Bookkeeping beyond the subset check.** The unit also reports
  `pending_agreement` (stakeholders with no declared agreement),
  `unlisted_agreements` (declared agreements from non-stakeholders),
  `uncovered_criterion_ids` (criteria without any example) and
  `orphan_example_criterion_ids` (examples pointing at nonexistent criteria),
  all sorted and deterministic.
- **Execution-request refusal.** Keys that ask the unit to execute, run tests,
  deploy, release or certify are refused (`EXECUTION_REQUEST:<key>`); the
  mechanism has no such gate.
- **Explicit non-verification.** `caller_declared_agreement=True` and
  `tests_executed=False` are pinned in every record: agreement flags are
  caller declarations, never observed facts.

Scope (Package B line, verbatim): bounded declared bookkeeping over
caller-supplied artifacts only; never runs caller code, a repository test
suite, or any external tool; no coverage, quality, or release-authority
claims. The row-specific bound: agreement bookkeeping over supplied
criteria/examples/stakeholders; never executes acceptance tests against real
software.

## Refusal codes (`ACCEPT688:`)

`BAD_TYPE:request`, `BAD_TYPE:key`, `OVERSIZE:request`,
`EXECUTION_REQUEST:<key>`, `UNKNOWN_KEY`, `MISSING:feature`,
`BAD_TYPE:feature`, `EMPTY:feature`, `OVERSIZE:feature`,
`MISSING:acceptance_criteria`, `BAD_TYPE:acceptance_criteria`,
`EMPTY:acceptance_criteria`, `OVERSIZE:acceptance_criteria`,
`BAD_TYPE:criterion`, `MISSING:criterion_id`, `BAD_TYPE:criterion_id`,
`OVERSIZE:criterion_id`, `EMPTY:criterion_id`, `MISSING:criterion_text`,
`BAD_TYPE:criterion_text`, `OVERSIZE:criterion_text`, `EMPTY:criterion_text`,
`DUPLICATE:criterion_id`, `BAD_TYPE:criterion`, `OVERSIZE:criterion`,
`UNKNOWN_FIELD:criterion`, `MISSING:examples`, `BAD_TYPE:examples`,
`OVERSIZE:examples`, `BAD_TYPE:example`, `MISSING:example_criterion_id`,
`BAD_TYPE:example_criterion_id`, `OVERSIZE:example_criterion_id`,
`EMPTY:example_criterion_id`, `BAD_TYPE:example`, `OVERSIZE:example`,
`UNKNOWN_FIELD:example`, `MISSING:example_text`, `BAD_TYPE:example_text`,
`OVERSIZE:example_text`, `EMPTY:example_text`, `MISSING:stakeholders`,
`BAD_TYPE:stakeholders`, `EMPTY:stakeholders`, `OVERSIZE:stakeholders`,
`BAD_TYPE:stakeholder`, `EMPTY:stakeholder`, `DUPLICATE:stakeholder`,
`BAD_TYPE:agreed_by`, `OVERSIZE:agreed_by`, `BAD_TYPE:agreement`,
`EMPTY:agreement`, `DUPLICATE:agreement`.

`OVERSIZE:request` also fires when the request carries more than 64 keys;
every container's length or key count is checked BEFORE any iteration or set
construction over it.

(`OVERSIZE:<field>` fires on the raw length/count guard for that field;
`BAD_TYPE:<field>` on type or Unicode-category failures - Cc/Cf/Zl/Zp refused,
Zs accepted - checked after the length guard for string fields;
`EMPTY:<field>` on blank-or-missing content after stripping;
`MISSING:<field>` on absent required input. Request keys: over-128-char
string keys refuse `OVERSIZE:request` before the category check;
`UNKNOWN_KEY` is a FIXED reason with no caller key echo, same rule as the
nested `UNKNOWN_FIELD:<entry>` reasons.)

## Entry exact schema (pinned)

- Each criterion is an exact dict (`type(x) is dict`) of AT MOST 2 keys
  (`OVERSIZE:criterion` on a third key, checked BEFORE the key names); any
  key outside exactly `{'id', 'text'}` - including a non-string key - refuses
  `UNKNOWN_FIELD:criterion` with a FIXED reason and no caller key echo.
  Examples are the same shape over exactly `{'criterion_id', 'text'}`
  (`OVERSIZE:example`, `UNKNOWN_FIELD:example`).
- All container and scalar checks use strict `type(x) is` identity, never
  `isinstance`, so subclassed str/list/dict values refuse.

## Bookkeeping rules (pinned)

- `agreement_complete` is `set(stakeholders) <= set(agreed_by)`, exactly the
  mechanism's rule; `pending_agreement` and `unlisted_agreements` are the two
  sorted set differences. A missing `agreed_by` defaults to `[]` (never a
  refusal).
- `uncovered_criterion_ids` / `orphan_example_criterion_ids` are sorted set
  differences over declared criterion ids; example duplicates are allowed
  (they are data, not identity).
- All string fields are stripped before echo; ids/texts cap at 128/512 raw
  chars; counts cap at 128 criteria, 256 examples, 64 stakeholders, 64
  declared agreements.
- Output is deterministic: same input, byte-identical JSON under sort_keys.

## Build chronology (disclosed)

- 2026-10-11 21:55:54 IST: the three files were committed LOCALLY as
  cec98940cc2560676345d4e3d78ec724294e203e (branch review/row688) about 27
  seconds before an explicit patch-only reminder. The package was already
  patch-only: making this local commit was a PATCH VIOLATION, not excused by
  reminder timing. The original commit is kept, never pushed or amended.
- 2026-10-11 ~22:00 IST: validation repair 1 (request key-count cap
  before iteration; explicit U+00AD/U+2060 pins; Cs residual line) applied as
  UNCOMMITTED working-tree edits.
- 2026-10-11 ~22:03 IST: repair 2 (exact entry schema: cap-first
  OVERSIZE:<entry>, fixed no-echo UNKNOWN_FIELD:<entry>, strict `type(x) is`
  throughout) applied as UNCOMMITTED working-tree edits.
- 2026-10-11 ~22:08 IST: repair 3 (root UNKNOWN_KEY made a FIXED no-echo
  reason; echo form withdrawn) applied as UNCOMMITTED working-tree edits.
- The current working tree, not the commit, is the delivered state.

## Limits and residual disclosures

- This is a bounded audit unit, not shipped product code.
- Agreement flags are caller-declared and never verified; the unit does not
  contact stakeholders or check any external system.
- It never executes acceptance tests, caller code, a repository suite, or any
  external tool; `tests_executed` is always `False`.
- `executable_before_implementation=True` is a fixed constant inherited from
  the old mechanism, not evidence of executability when `tests_executed` is
  `False`.
- Bookkeeping is over caller-supplied criteria, examples and stakeholders
  only; no coverage, quality, or release-authority claim is made.
- Unicode screening refuses the full Cc, Cf, Zl and Zp categories on any
  echoed text and accepts Zs; U+00AD (SOFT HYPHEN, Cf) and U+2060 (WORD
  JOINER, Cf) are pinned explicitly by test.
- Unicode categories Co (private-use) and Cn (unassigned) are not screened
  and remain accepted; this is a disclosed residual, not Unicode validation.
- Residual (disclosed, kept): unpaired-surrogate text (category Cs) is NOT
  screened by this unit; per the settled policy no Cs refusal is added, and
  this residual stays disclosed rather than closed.
- Tests run hermetically direct-file on Python 3.14.7 and 3.10.12 only; the
  repository FULL SUITE is UNVERIFIED here (repo conftest imports
  `cryptography`, absent from both interpreters used).
- No closure claim is made for row 688 by this unit.
