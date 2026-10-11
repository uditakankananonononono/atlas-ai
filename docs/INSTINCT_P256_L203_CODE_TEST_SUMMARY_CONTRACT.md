# P256|L203 Code and test summaries - contract

Source pin: instinct doc P256|L203, verbatim: "Output: Code and test summaries," (supplied verbatim by delegation; nothing more is pinned). Output-format section sibling of P252|L199 and P262|L209.

Module: `backend/app/modules/instinct_doc/code_test_summary_p256.py`. Pure stdlib. No clock, randomness, I/O, filesystem or network. Same input gives byte-identical output. No wiring: no route, no registration.

## API
- `summarize_projects(projects)` returns the canonical summary dict. The input list and records are never mutated. A refused call returns nothing and changes nothing.

## Project record
Exactly eight fields, no unknown or missing keys, no truncation, no coercion:
- `id`: nonblank string 1..128 chars, unique across the call.
- `code_files`, `code_lines`, `test_files`, `test_lines`, `test_cases`: strict int (`type is int`; bool refused) in 0..10000000.
- `coverage_percent`: null (no claim) or a number (`type in (int, float)`, bool refused) in 0..100 inclusive. NaN and infinities fail the range check and are refused. Stored exactly as supplied; never rounded.
- `source_refs`: list of 0..16 unique nonblank strings, each 1..256 chars.

## Coverage marking (mandatory honesty shape)
- percent null -> `NO_CLAIM`.
- percent set, no refs -> `UNVERIFIED`.
- percent set, refs supplied -> `EVIDENCE_DECLARED`.
Refs are recorded (sorted), never authenticated, resolved or fetched; reference presence never verifies a claim. `unverified_coverage_project_ids` lists every UNVERIFIED project id. `coverage_counts` includes all three statuses even at zero. Every claim without refs is UNVERIFIED - there is no fabrication or self-verification path.

## Output
- `projects`: rows sorted by case-sensitive Unicode id. Each row echoes the five counts and carries `coverage: {percent, status, source_refs, caller_declared: true}` and `stats_are_caller_supplied: true`.
- `totals`: exact integer sums over the five count fields. No ratios or other derived metrics are computed.
- `status`: exactly `supplied_stats_summary_only`.
- `stats_measured`, `coverage_measured`, `evidence_verified`, `completeness_verified`: exactly False, always.
- `boundary` (verbatim): "Only supplied stats are summarized. Nothing is measured: no code is read, no tests are run and no coverage is computed. Coverage claims are caller declarations marked UNVERIFIED without supplied source refs; refs are recorded, never authenticated, and never verify a claim. An empty summary does not prove the absence of projects."
- Empty input is a valid empty summary; it never evidences the absence of real projects.

## Refusals (ValueError, exact text, P256: prefix)
`P256:projects: expected list of at most 256 records`, `P256:project: exactly id,code_files,code_lines,test_files,test_lines,test_cases,coverage_percent,source_refs required`, `P256:id: expected nonblank string of length 1..128`, `P256:duplicate project id: <id>`, `P256:<count-field>: expected integer 0..10000000`, `P256:coverage_percent: expected null or number 0..100`, `P256:source_refs: expected list of at most 16 references`, `P256:source_ref: expected nonblank string of length 1..256`, `P256:duplicate source_ref: <ref>`.

## Order of checks
Projects container (type, size); then per project in input order: record shape, id text, duplicate id, the five counts in FIELDS order, percent, refs container, ref text, duplicate ref. Sorting determinism applies to valid input, not to error selection across multiple malformed records.

## Interpretation choices (flagged for review - every shape below is invented, in the family conventions of P252/P262)
- The source line pins nothing beyond "Output: Code and test summaries,". All field names, statuses, limits and refusal texts are invented; the `P256:` refusal prefix and UNVERIFIED marking were mandated by delegation.
- Field names reuse the family report schema: `id`, `source_refs`, `status`, counts + caller-declared flags + boundary (P262 shape).
- Statuses `NO_CLAIM` / `UNVERIFIED` / `EVIDENCE_DECLARED` are invented; `EVIDENCE_DECLARED` deliberately avoids any "verified" wording because refs never verify.
- Limits: 256 projects and 16 refs match P262 caps; id 128 / ref 256 match P262 text limits; 10000000 count cap is a resource bound, not a measured one.
- Refs supplied with a null claim are recorded with status `NO_CLAIM` (refs evidence claims; without a claim they are inert). No refusal.
- Counts are caller-supplied and never cross-checked (test_lines may exceed code_lines).
- Only exact integer sums are derived; no ratios, percentages or aggregates beyond totals.
- Per-call function (P262 shape), not an append-log (P252 shape): the line reads as a one-shot summary artifact.

## Limits
Output artifact only. It summarizes supplied stats; it does not inspect code, run tests, measure coverage, verify claims or detect omitted projects. Passing fixture tests prove bounded validation and rollup only, not real coverage, quality or completeness. Passing tests is not audit acceptance.
