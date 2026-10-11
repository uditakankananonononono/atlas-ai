# Code Review engine contract (ledger row 690)

Source text of the row (feature document, "Code Review - Improves quality"; category Technical & Engineering).
Module: `backend/app/modules/m20_general_cognitive_worker/code_review690.py` (stdlib only).
Tests: `tests/modules/test_code_review690.py`.

## API

`parse_unified_diff(text) -> list[{path, added: [(line_no, text)], removed: int}]`
Raises `CodeReviewError` on a diff with no hunk, a malformed hunk header, or hunk line counts that disagree with the header.

`review(diff, review_checklist, *, author, reviewer=None, requested_decision=None, max_added_lines=400, max_line_length=120) -> dict`

- `requested_decision` is `None`, `"approve"` or `"request_changes"`.
- `"approve"` needs a reviewer. A reviewer equal to the author (case and whitespace insensitive) raises `SelfApprovalError`.
- Approval is recorded (`decision = "approved_by_reviewer"`, `approval = {reviewer, author}`) only when no blocking finding exists. Otherwise `decision = "request_changes"` and `approval = None`.
- Without a requested decision: `no_issues_found` (no findings) or `comments_only`.

## Checks (heuristics)

All checks are line/regex based and run on added lines only. They are heuristics, not semantic analysis.

| rule | severity |
|---|---|
| hardcoded-secret (name = quoted literal of 8+ chars; the value is never echoed) | blocking |
| conflict-marker | blocking |
| dynamic-exec (`eval(` / `exec(`) | blocking |
| bare-except | warning |
| debug-leftover | warning |
| todo-marker | warning |
| missing-tests (code file changed, no test file changed) | warning |
| oversized-change (added lines > `max_added_lines`) | warning |
| trailing-whitespace | nit |
| long-line (> `max_line_length`) | nit |

## Checklist

Each checklist string is matched by keyword to rules (for example "no debug code", "tests", "secrets"). Matched item: `pass` if none of its rules fired, else `fail`. An item with no keyword match is `needs_human`; the engine never marks it passed.

## Output

`input_sha256`, `files`, `added_lines`, `findings`, `checklist`, `unresolved_blockers`, `decision`, `approval`, `heuristic_rules`, `human_review_required` (always true), `boundary`.

## Boundary

Prepared review evidence only. No merge, release, deployment, approval of a merge, or repository mutation is performed. Output is deterministic for the same input.

## Not covered

No semantic or type analysis, no language-specific parsing, no persistence, no HTTP route (wiring not included), no reviewer identity verification beyond the string comparison.
