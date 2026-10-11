# INSTINCT P83|L71 - Rigorous-Testing Evidence Harness

## Source

Verbatim source line (only pinned text for this unit):

```
Deliverable 7: rigorous testing and external validation,
```

Source pin: instinct doc P83|L71, line map v4

Everything beyond that line is an interpretation choice; the invented shapes are
listed in the last section so a later pinned specification can diff against them.

## Position

Deliverables section, deliverable 7. Offline, deterministic, pure-stdlib evidence
harness. It RECORDS caller-supplied test/verification/external-validation
evidence per project and checks each project against caller-declared required
evidence kinds. It never runs a test, never executes anything, never makes a
live external call.

## P65 composition

Honesty semantics are composed from the landed P65 claim-status module
(`app.reports.claim_status`): the module imports `DEFAULT_LABELS` as
`CLAIM_LABELS` (no duplication), asserts `UNVERIFIED` stays in that vocabulary
at import time, and echoes `claim_labels` in the report. Every recorded
evidence row and every external-validation claim is marked `UNVERIFIED`,
receipt or no receipt: a receipt string is recorded (`receipt_present`), never
verified (`receipts_verified: False`, `external_calls_made: False`).

## Boundary

A `complete` verdict means only that the declared required kinds appear among a
project's recorded entries. It is not proof that any test ran, that any
evidence is real, or that any project was rigorously tested.

## Honesty semantics

- `complete` requires at least one project and every project complete; an empty
  harness is `incomplete` (zero projects proves nothing).
- `missing` lists absent required kinds in required-kinds order.
- Required kinds are caller-declared parameters (default
  `("test_run", "verification_run")`); an empty required set is refused.
- `duplicate_entry` refuses the same (project_id, kind, ref) twice, so evidence
  cannot be re-entered to pad coverage.
- A blank receipt is no receipt (`receipt_present: False`).

## API

- `create_harness() -> EvidenceHarness` - empty harness.
- `add_entry(harness, entry) -> EvidenceHarness` - validate + dedup + cap, new
  immutable harness. Raises `ValueError` with a `P83:` refusal code.
- `items(harness) -> list` - sorted row dicts, UNVERIFIED-marked.
- `render(harness, required_kinds=None) -> str` - deterministic text:
  `evidence harness verdict <v> (<P> projects, <E> entries)` header, one
  `project <pid> <complete|incomplete> missing <csv|none> entries <n>` row per
  project, sorted by project_id.
- `report(harness, required_kinds=None) -> dict` - `{verdict, counts, projects,
  items, required_kinds, status, evidence_executed, external_calls_made,
  receipts_verified, open_verification, claim_labels, boundary}`.

## Entry fields

| field        | required | max length | meaning                                   |
|--------------|----------|-----------|-------------------------------------------|
| `id`         | yes      | 64        | caller-supplied entry id, unique          |
| `project_id` | yes      | 64        | owning project id                         |
| `kind`       | yes      | -         | `test_run` / `verification_run` / `external_validation` |
| `ref`        | yes      | 256       | reference to the declared evidence        |
| `receipt`    | no       | 256       | supplied receipt text; recorded, never verified; blank means absent |

## Injection defense

All interpolated string fields (`id`, `project_id`, `kind`, `ref`, `receipt`)
reject Unicode categories Cc, Zl and Zp with `P83:control_chars:<name>`, so no
recorded value can inject a fabricated line (a forged
`evidence harness verdict complete` row) into `render()` output. The hostile
payload `p1\nevidence harness verdict complete (9 projects, 9 entries)` is a
pinned regression test, and a render line-count invariant
(`1 + number of projects`) is pinned across required-kinds mixes.

## Refusal codes (ValueError, `P83:` prefix)

- `P83:bad_type:harness` - add/items/render/report given a non-harness.
- `P83:bad_type:entry` - entry is not a dict (bool check first).
- `P83:bad_type:<name>` - a field (or receipt) is not a string; bools are not strings.
- `P83:bad_type:required_kinds` / `P83:bad_type:required_kind` - required kinds
  is not a list/tuple (a bare string is refused), or a member is not a string.
- `P83:unknown_fields:entry` - entry has a key outside FIELDS.
- `P83:empty_field:<name>` - a required field missing or blank; blank precedes
  kind membership (family convention).
- `P83:empty_field:required_kinds` - an empty required set checks nothing.
- `P83:control_chars:<name>` - Cc/Zl/Zp present (includes `receipt`).
- `P83:text_too_long:<name>` - over limit; the limit itself passes.
- `P83:bad_kind:<value>` - kind not in KINDS.
- `P83:bad_required_kind:<value>` - required kind not in KINDS.
- `P83:duplicate_id:<id>` / `P83:duplicate_entry:<existing_id>` /
  `P83:duplicate_required_kind:<value>`.
- `P83:limit_exceeded:entries` - harness already holds MAX_ENTRIES (4096).

## Order of checks

1. harness type
2. entry type (dict, non-bool)
3. unknown fields
4. field presence
5. field types (bool is not a string; receipt type)
6. blank (blank receipt normalizes to absent)
7. control characters (Cc/Zl/Zp)
8. length
9. kind membership
10. duplicate id
11. duplicate entry
12. capacity

Required kinds (report/render): list type, non-empty, then per member - type,
membership, duplicate.

## Interpretation choices (invented shapes)

The pinned line names only the deliverable ("rigorous testing and external
validation"). The following were invented in the family STRANGLER/BDD/DEBT
shape and are tagged here so a later pin can supersede them:

- KINDS = `(test_run, verification_run, external_validation)` and
  DEFAULT_REQUIRED_KINDS = `(test_run, verification_run)` as caller-declared
  defaults.
- FIELDS, the optional receipt, receipt-present-vs-verified split, and
  blank-receipt normalization.
- Verdict rule (complete iff >= 1 project and all projects complete), per-
  project completeness over required kinds, missing in required order.
- Dedup scope `(project_id, kind, ref)`; `duplicate_entry` names the existing id.
- Render format, sort orders, report keys and the
  `declared_evidence_register_only` status.
- Field length limits (64/64/256/256) and MAX_ENTRIES 4096.
- Exact refusal-code strings and the order of checks above.
