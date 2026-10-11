Source pin: instinct doc P254|L201, line map v4. Verbatim: "Output: Dataset counts and sources,"

# P254|L201 Dataset counts and sources - contract

Module: `backend/app/modules/instinct_doc/dataset_register_p254.py`. Pure stdlib, fully offline. No clock, randomness, I/O, filesystem or network; nothing is fetched, resolved or authenticated. Same call sequence gives byte-identical output. No wiring: no route, no registration.

## API
- `create_register()` returns an empty immutable register.
- `add_entry(register, entry)` returns a NEW register. The input register and entry are never mutated. A refused entry changes nothing.
- `summary(register)` returns the rollup dict (below).
- `render(register, project_id=None)` returns text (below).

## Entry
Exactly six fields: id (<=64, unique in the whole register), project_id (<=64), dataset (<=128), records (strict int, bool refused, 0..10**15), source (<=256), source_ref (<=256; recorded verbatim, never resolved). Text fields must be nonblank (whitespace-only counts as blank). No unknown or missing fields, no truncation, no coercion.

## Injection defense (mandatory)
Every interpolated text field (id, project_id, dataset, source, source_ref) rejects any character whose Unicode category is Cc, Zl or Zp, refused as `P254:unsafe_chars:<name>`. No accepted entry can forge, split or hide a render line. Render line-count invariant: the rendered output for a non-empty selection is exactly (projects rendered) + (entries rendered) lines, joined by `\n`, no trailing newline, no carriage returns. An empty selection renders as `""`.

## Render format
Projects sort by case-sensitive Unicode project_id; entries sort by id within a project. Header: `project <project_id> (<n> entries, <total> records)`. Entry line: `<id> <dataset> <records> records from <source> [<source_ref>]`. A supplied project_id with no entries is refused `P254:unknown_project:<project_id>`.

## Summary rollup
`projects` (sorted by id): per-project entries count, exact integer records total, datasets sorted. Top level: entry_count, total_records (exact sums), status exactly `declared_register_only`, counts_verified / sources_resolved / completeness_verified exactly False always, boundary verbatim: "Only supplied entries are recorded. Counts are caller declarations, named sources are stored verbatim and never resolved or authenticated, and an empty register does not prove the absence of datasets."

## Refusals (ValueError, exact text, P254: prefix)
`P254:bad_type:register`, `P254:bad_type:entry`, `P254:unknown_fields:entry`, `P254:empty_field:<name>`, `P254:bad_type:<name>`, `P254:text_too_long:<name>`, `P254:unsafe_chars:<name>`, `P254:count_out_of_range:records`, `P254:duplicate_id:<id>`, `P254:limit_exceeded:entries` (>4096), `P254:unknown_project:<project_id>`, `P254:bad_type:project_id`.

## Order of checks for one entry
non-register (`bad_type:register`), non-dict entry, unknown fields, missing field (`empty_field:<name>`), then per text field in id, project_id, dataset, source, source_ref order: type (bool anywhere is `bad_type`), blank, too long, unsafe chars; then records type, records range, duplicate id, entry cap.

## Interpretation choices (flagged for review - invented in the family shape; the source line pins nothing beyond "Output: Dataset counts and sources,")
- Ledger shape (immutable register + render + summary) blends P252's append-log with P262's flagged rollup; field names reuse the family report schema (id, project_id, source_ref, status, boundary).
- Limits invented: text 64/64/128/256/256 mirrors P252; records cap 10**15 and entry cap 4096 are resource bounds (4096 matches P252's per-task cap and is exactly N/N+1-testable), not measured limits.
- No per-project seq: entries sort canonically by id; insertion order is unobservable.
- Only Cc/Zl/Zp are rejected (as mandated); other invisible categories (Cf, Mn) are accepted and documented as out of scope.
- Counts are caller declarations and never cross-checked; a project may appear with any number of datasets; dataset names are not unique-keyed.

## Limits
Output artifact only. It records and renders supplied dataset counts and named sources; it does not count real records, verify datasets exist, resolve or authenticate sources, or detect omitted datasets. Empty register is not evidence of absence. Passing tests is not audit acceptance.
