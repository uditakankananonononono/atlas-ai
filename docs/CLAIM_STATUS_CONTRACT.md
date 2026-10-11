# Claim Status Check — Contract (unit P65|L55)

Bounded mechanism: `backend/app/reports/claim_status.py`. A report check that
every claim carries an explicit status label — VERIFIED or UNVERIFIED by
default — and fails when a claim is unmarked, carries conflicting labels, or
carries a label that is ambiguous at the structure level. This document
scopes the mechanism only. It does not claim that any doc line is fulfilled;
it describes a bounded check that exists and runs.

## Claim grammar (the complete claim surface)

Anything not matching this grammar is prose, not a claim.

1. **Table claims** — every body row of a markdown table whose header
   contains EXACTLY ONE `Label` or `Status` column (case-insensitive).
   Claim text is the first cell; status is the label cell, normalized with
   `strip().upper()`. The header and the `|---|` separator row are not
   claims. A pipe-run of three or more lines without a separator row is not
   a table.
2. **Marker claims** — lines beginning with `CLAIM:` (case-insensitive, an
   optional bullet or numbered-list prefix allowed) whose body carries a
   bracketed `[LABEL]` marker.

Fenced code blocks are skipped entirely, with CommonMark fence pairing: an
opening fence is a run of three or more backticks or tildes (an info string
is allowed on the opener); the fence closes only on a line whose run uses
the SAME delimiter character and is at least as long as the opener. A
mismatched or shorter run does not close the fence.

Label matching is case-insensitive after `upper()` normalization. The
accepted label set is a parameter; default `{"VERIFIED", "UNVERIFIED"}`. An
empty accepted-label set is refused with `ValueError`.

## Outcomes

- A claim whose label cell/marker holds exactly one accepted label (and no
  unrecognized bracketed token) is **marked**.
- A claim with an empty label cell, a missing label cell, or no recognized
  token is **unmarked** (recorded with 1-based line number and reason).
- A marker claim carrying two or more DIFFERENT accepted labels is
  **conflicting** (recorded with the labels found).
- **structural-ambiguous** (fail-closed): a marker claim carrying one
  recognized label plus any unrecognized bracketed token; every body row of
  a table whose header names two or more label columns; and a truncated
  claim table (a pipe-run of one or two lines carrying a label header).
  Recorded with line and reason; never silent, never an IndexError.
- `ok` is true only when at least one claim was found and there are no
  unmarked, no conflicting, and no structural-ambiguous findings. A
  zero-claim document is **vacuous**: `ok` is false and `vacuous` is true.
  A check that finds nothing proves nothing.

## CLI

`python -m app.reports.claim_status [--labels A,B] PATH...`

- exit 0: every claim marked
- exit 1: unmarked, conflicting, or structural-ambiguous findings, or a
  claim-free file in a mixed run; findings printed as
  `path:line: UNMARKED|CONFLICTING|STRUCTURAL-AMBIGUOUS|VACUOUS: ...`
- exit 2: zero claims found across all inputs, or an unreadable input

## API

`extract_claims(text, labels=...)` -> list[Claim(line, text, status, source)]
· `check_text` -> per-document grading (`claims`, `claims_total`, `marked`,
`unmarked`, `conflicting`, `structural_ambiguous`, `vacuous`, `ok`) ·
`check_file` · `check_paths` -> aggregate with per-file results and
files_with_zero_claims.

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
