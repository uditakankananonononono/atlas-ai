# P246 / L194 line coverage contract

Source line, verbatim from the doc at [P246|L194]:

> 5. Verify every line, every word, every module, every tool, every benchmark, every test, and every discovery claim.

Module: `backend/app/modules/instinct_doc/line_coverage_p246.py`. Tests: `tests/modules/test_line_coverage_p246.py`.

## What this is

A bounded, offline check over a supplied line map and a supplied list of evidence declarations. It reports which distinct requirement lines have a declared `COVERED_BY_DECLARATION` record and which do not. It is standard library only and does no I/O. Nothing here verifies a line.

## What this is not (gaps, stated plainly)

- "every word": unbounded. Words are display only and are never match keys. No word-level check exists.
- "every discovery claim": unbounded. Nothing here finds or checks discovery claims.
- "every module, every tool, every benchmark, every test": covered only to the extent a declaration names a line ID. The module does not inspect any of them.
- The module does not judge whether an evidence reference exists, is adequate, or is true. A `COVERED_BY_DECLARATION` record means someone declared it, nothing more.
- No claim is made that P246|L194 or any other line is fulfilled. The output carries `line_fulfilled: false` and `evidence_adequacy_assessed: false`.
- Non-duplication against the unit 11 audit pack is UNVERIFIED. The output carries `unit11_non_duplication: "UNVERIFIED"`. Unit 11 was not read.
- Fonts: not used. Nothing here renders text.

## Buckets (never mixed)

Counts below are for the V3 line map (sha256 `0279c43bb39a70d0d9ec7e8289aeefd8c1e82828e27e3b8573a055bf45527ff5`), taken from the raw run `real-v3-run.txt`.

| bucket | count | meaning |
|---|---|---|
| source rows | 239 | every row in the map |
| decorative rows | 1 | class DECORATIVE, excluded everywhere |
| non-decorative source rows | 238 | source rows, not distinct requirements |
| section header rows | 14 | `dup_of` is the literal `SECTION HEADER` |
| duplicate rows | 100 | `dup_of` is a real `P<n>\|L<n>` reference (restatements) |
| distinct requirements | 124 | 93 NON-SCIENCE + 31 SCIENCE |
| duplicate rows by class | 68 NON-SCIENCE, 32 SCIENCE | |

The `dup_of` column is overloaded: it holds both real references and the header marker. 114 flags = 100 real references + 14 headers. 175 NON-SCIENCE rows = 93 distinct + 68 restatements + 14 headers.

Default denominator: 93 distinct NON-SCIENCE requirements. SCIENCE (31) is reported separately as `other_class_requirements`; it enters a denominator only if `include_classes` lists it. Headers and decorative rows never enter a denominator. Row kind precedence: decorative, then header, then duplicate. With no evidence the real map gives 0 covered and 93 uncovered.

## Request

`compute_line_coverage(request)`, request keys: `line_map` (rows with `P`, `L`, `class`, `mission`, `summary`, `dup_of`), `evidence`, `include_classes` (default `["NON-SCIENCE"]`). Numeric strings from CSV are accepted for P and L. Unknown fields are refused. Bounds: 1..2000 rows, 0..20000 evidence records, summary text 2000 characters, evidence_ref 2048 characters. Errors raise `LineCoverageError` with the exact offending row or field.

## Evidence schema (fixed)

`{line_id, status, evidence_ref, declared_at, source}`

- `line_id`: exact `P<n>|L<n>`. No fuzzy matching. No leading zeros.
- `status`: `COVERED_BY_DECLARATION` or `UNCOVERED`. No third status.
- `evidence_ref`: a path or URL string. Required for `COVERED_BY_DECLARATION`. Never fetched.
- `declared_at`: timezone-aware ISO timestamp. Rejected if naive.
- `source`: `self` or `audit`.

The `declared_at` and `evidence_ref` rules above are this module's own design choices, not peer-specified details.

## Rules

1. Duplicates roll up canonically via `dup_of` (chains resolved) before exact ID matching. Evidence on a duplicate row counts for the canonical target and is listed in `evidence_rolled_up`. Duplicates are excluded from the uncovered count.
2. Cycles, self references, dangling references and repeated line IDs in the map are refused.
3. A duplicate whose canonical row has a different class follows the canonical row's class and is listed in `cross_class_duplicates`. The real V3 map has none.
4. If a line has both a COVERED and an UNCOVERED declaration, UNCOVERED wins and the line is listed in `conflicting_declarations`.
5. Lines covered only by `source: self` declarations are listed in `self_declared_only`.
6. Evidence for unknown line IDs is listed in `unknown_line_evidence`, not refused and not counted. Evidence on header or decorative rows is listed in `evidence_on_non_requirement_rows`, not counted.
7. Output order is by L then P. Input order does not change output. Inputs are not mutated.

## Inert data

Text in the map, summaries, mission fields and evidence references is data only. It is never interpreted as an instruction, and it is never executed or fetched.

## Packaging

The module sits in `backend/app/modules/instinct_doc/` with no `__init__.py` by design (PEP 420 namespace; the single owner of that file is another builder). Wiring into the app is not part of this change and would be a separate unapplied patch. The tests load the module from its file path when the app package is not importable.
