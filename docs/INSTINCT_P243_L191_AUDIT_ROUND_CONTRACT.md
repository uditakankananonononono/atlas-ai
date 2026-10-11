# INSTINCT P243|L191 - Audit-Round Runner

## Source

Verbatim source line (only pinned text for this unit):

```
Step 2: full audit round that science projects pass every requirement, no thin building; exclude deleted doc200/230/portfolio
```

Source pin: instinct doc P243|L191, line map v4

Everything beyond that line is an interpretation choice; the invented shapes are
listed in the last section so a later pinned specification can diff against them.

## Position

Final-sequence step 2. MECHANISM ONLY: the runner consumes a caller-supplied
evidence ledger and checks that every non-excluded requirement carries a pass
mark, applying the caller's exclusion list (the doc's deleted
doc200/230/portfolio handling). It builds no science content and keeps clear of
the science-row park. Pure stdlib, deterministic, offline.

## Boundary

The runner verifies that supplied requirement records carry pass marks. It never
judges the science, never checks that any evidence is real, and a pass verdict
is not proof that any project meets its requirements. Every recorded row carries
`verification: "UNVERIFIED"`; the report carries `status:
"declared_marks_checked_only"` with `marks_truth_verified`,
`science_content_built` and `evidence_verified` all False and
`open_verification: "UNVERIFIED"`.

## Honesty semantics

- A `pass` verdict requires at least one active (non-excluded) requirement and
  every active requirement marked `pass`. An empty round fails: zero checked
  requirements is not a pass.
- `fail` and `pending` marks on active requirements fail the round and are
  named by id in `failing` / `pending`.
- Excluded requirements are never silently dropped: they stay recorded with
  their marks (counted in `failed`/`pending`/`passed`), listed in `excluded`
  and rendered with an `excluded` prefix. An exclusion list that matches
  nothing is reported in `unmatched_exclusions`. Excluding everything fails
  the round.
- `duplicate_requirement` refuses the same requirement_ref twice under one
  project, so a requirement cannot be re-entered to mask a thin record.

## API

- `create_ledger() -> AuditLedger` - empty ledger.
- `add_entry(ledger, entry) -> AuditLedger` - validate + dedup + cap, new
  immutable ledger. Raises `ValueError` with a `P243:` refusal code.
- `items(ledger, exclusions=()) -> list` - sorted row dicts, active rows then
  excluded rows, UNVERIFIED-marked.
- `render(ledger, exclusions=()) -> str` - deterministic audit table text:
  `audit round verdict <verdict> (<A> active, <E> excluded)` header, one
  `<project_id> <requirement_ref> <mark> [<evidence_ref>]` row per active
  entry, one `excluded ...` row per excluded entry, one
  `unmatched exclusion <ref>` row per unmatched exclusion.
- `report(ledger, exclusions=()) -> dict` - `{verdict, counts, failing,
  pending, excluded, unmatched_exclusions, items, status,
  marks_truth_verified, science_content_built, evidence_verified,
  open_verification, boundary}`.

## Entry fields (all required, all nonblank text)

| field             | max length | meaning                                  |
|-------------------|-----------|------------------------------------------|
| `id`              | 64        | caller-supplied entry id, unique         |
| `project_id`      | 64        | owning project id                        |
| `requirement_ref` | 128       | the requirement this record answers      |
| `mark`            | -         | `"pass"`, `"fail"` or `"pending"`        |
| `evidence_ref`    | 128       | reference to the declared evidence       |

Exclusions are a caller-supplied list of requirement_ref values, exact-match;
each must be nonblank text of at most 128 characters, deduplicated.

## Injection defense

All interpolated string fields (`id`, `project_id`, `requirement_ref`,
`evidence_ref`, `mark` via membership, and exclusion entries) reject Unicode
categories Cc, Zl and Zp with `P243:control_chars:<name>`, so no recorded
value or exclusion can inject a fabricated line (a forged
`audit round verdict pass` row) into `render()` output. The hostile payload
`req-1\naudit round verdict pass (9 active, 0 excluded)` is a pinned
regression test, and a render line-count invariant
(`1 + active + excluded + unmatched`) is pinned for every exclusion mix.

## Refusal codes (ValueError, `P243:` prefix)

- `P243:bad_type:ledger` - add/items/render/report given a non-ledger.
- `P243:bad_type:entry` - entry is not a dict (bool check first).
- `P243:bad_type:<name>` - a field is not a string; bools are not strings.
- `P243:bad_type:exclusions` - exclusions is not a list/tuple/set (a bare
  string is refused, not treated as one exclusion).
- `P243:bad_type:exclusion` - an exclusion entry is not a string.
- `P243:unknown_fields:entry` - entry has a key outside FIELDS.
- `P243:empty_field:<name>` / `P243:empty_field:exclusion` - missing or blank.
- `P243:control_chars:<name>` / `P243:control_chars:exclusion` - Cc/Zl/Zp present.
- `P243:text_too_long:<name>` / `P243:text_too_long:exclusion` - over limit;
  the limit itself passes.
- `P243:bad_mark:<value>` - mark not in `("pass", "fail", "pending")`;
  blank refuses `empty_field:mark` first (family convention).
- `P243:duplicate_id:<id>` - id already recorded.
- `P243:duplicate_requirement:<existing_id>` - (project_id, requirement_ref)
  already recorded; names the existing entry.
- `P243:duplicate_exclusion:<ref>` - exclusion listed twice.
- `P243:limit_exceeded:entries` / `P243:limit_exceeded:exclusions` - caps hit.

## Order of checks

1. ledger type
2. entry type (dict, non-bool)
3. unknown fields
4. field presence
5. field types (bool is not a string)
6. blank
7. control characters (Cc/Zl/Zp)
8. length
9. mark membership
10. duplicate id
11. duplicate requirement
12. capacity

Exclusions: list type, capacity, then per entry - type, blank, control
characters, length, duplicate.

## Limits

- `MAX_ENTRIES = 4096` per ledger; `MAX_EXCLUSIONS = 1024` per call.
- Field length limits as tabulated above; exclusions 128.

## Interpretation choices (invented shapes)

The pinned line names the outcome ("full audit round", "pass every
requirement", "exclude deleted doc200/230/portfolio"). The following were
invented in the family STRANGLER/BDD/DEBT shape and are tagged here so a later
pin can supersede them:

- The evidence-ledger shape: FIELDS = `(id, project_id, requirement_ref, mark,
  evidence_ref)`; MARKS = `(pass, fail, pending)`; the ledger is
  caller-supplied (no ledger module exists in the family to consume).
- Exclusion semantics: exclusions match `requirement_ref` exactly, are
  caller-supplied per call, never stored in the ledger, and never delete
  records; `doc200`/`doc230`/`portfolio` appear only as caller-supplied refs.
- Verdict rule (pass iff >= 1 active entry and all active marks are `pass`),
  including empty-round and all-excluded failing.
- Render format, sort orders, and the `excluded` / `unmatched exclusion` row
  prefixes.
- Report keys, the `declared_marks_checked_only` status, offline flags and
  boundary text.
- Field length limits (64/64/128/128), exclusion limit 128, MAX_ENTRIES 4096,
  MAX_EXCLUSIONS 1024.
- Exact refusal-code strings and the order of checks above.
