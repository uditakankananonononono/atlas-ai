# Claim Status Check — Contract (unit P65|L55)

Bounded mechanism: `backend/app/reports/claim_status.py`. A report check that
every claim carries an explicit status label — VERIFIED or UNVERIFIED by
default — and fails when a claim is unmarked or carries conflicting labels.
This document scopes the mechanism only. It does not claim that any doc line
is fulfilled; it describes a bounded check that exists and runs.

## Claim grammar (the complete claim surface)

Anything not matching this grammar is prose, not a claim.

1. **Table claims** — every body row of a markdown table whose header
   contains a `Label` or `Status` column (case-insensitive). Claim text is
   the first cell; status is the label cell, normalized with
   `strip().upper()`. The header and the `|---|` separator row are not
   claims. A pipe-run without a separator row is not a table.
2. **Marker claims** — lines beginning with `CLAIM:` (case-insensitive, an
   optional bullet or numbered-list prefix allowed) whose body carries a
   bracketed `[LABEL]` marker.

Fenced code blocks (` ``` ` or `~~~`) are skipped entirely. Label matching is
case-insensitive after `upper()` normalization. The accepted label set is a
parameter; default `{"VERIFIED", "UNVERIFIED"}`.

## Outcomes

- A claim whose label cell/marker holds exactly one accepted label is
  **marked**.
- A claim with an empty label cell, a missing label cell, or no accepted
  label is **unmarked** (recorded with 1-based line number and reason).
- A marker claim carrying two or more DIFFERENT accepted labels is
  **conflicting** (recorded with the labels found).
- `ok` is true only when there are no unmarked and no conflicting claims.

## CLI

`python -m app.reports.claim_status [--labels A,B] PATH...`

- exit 0: every claim marked
- exit 1: unmarked or conflicting claims; findings printed as
  `path:line: UNMARKED|CONFLICTING: ...`
- exit 2: vacuous run (zero claims found across all inputs) or an unreadable
  input. A check that finds nothing proves nothing, so zero claims never
  exits 0.

## API

`extract_claims(text, labels=...)` -> list[Claim(line, text, status, source)]
· `check_text` -> per-document grading · `check_file` · `check_paths` ->
aggregate with per-file results and files_with_zero_claims.

## Boundaries and non-claims

- Stdlib-only (asserted by the test suite). No wiring produced: the check is
  a library/CLI; mounting it into CI or HTTP surfaces is integrator work and
  would require editing existing files, out of scope.
- The check reads marker conventions; it cannot tell whether a VERIFIED label
  is TRUE — it checks that claims are marked, not that the markings are
  honest. Human review of labels remains required.
- Validated on CPython 3.12.14, pytest 9.1.1 (SQLAlchemy 2.1.4 present only
  because the repo's tests/modules conftest imports it). The repo-wide floor
  and mounted surfaces were not run for this package.
