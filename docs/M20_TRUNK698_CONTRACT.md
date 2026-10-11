# TRUNK698-DAG-01: bounded commit-graph analysis for trunk-based development

Targets row698 "Trunk-Based Development" (extra-doc category 5, "Integrates
frequently"; ledger status PARTIAL) for SCOPED acceptance only, not full title
closure. The existing `software_practice_685_709._trunk` only compares a caller
`age_hours` to a threshold and returns a hard-coded `direct_push_protected:true`;
this unit derives age, divergence and check coverage from supplied graph records.
Row title/description: Trunk-Based Development - Integrates frequently.

Function: `trunk_graph698.analyze_trunk(data) -> dict` (stdlib only, ValueError on
refusal -> 422 when wired by the separate patch). No route is mounted here.

## Input (unknown keys refuse; no "protected"/"required" claim flags exist)
`source_ref`, `trunk` (branch name), `reference_time` (tz-aware ISO-8601),
`max_branch_age_hours` (finite, 0 < x <= 8760), `required_checks` (non-empty,
unique names), `commits[{sha,parents,committed_at,source_ref?}]` (40 lowercase hex),
`branches[{name,tip,source_ref?}]`, `checks[{name,sha,conclusion,completed_at?,source_ref?}]`.
Conclusions: success=passed; failure/cancelled/timed_out=failed; skipped/neutral=not_success; pending=pending.

## Output
Per branch (sorted by name): `state` (trunk | merged | ahead | diverged | unrelated),
`ahead` (commits reachable from tip but not trunk), `behind`, `merge_bases` (all
maximal common ancestors, so criss-cross gives several; empty = unrelated),
`unmerged_commits`, `merge_commits_in_unmerged`, `oldest_unmerged_commit_at` (UTC),
`age_seconds` (reference_time minus oldest unmerged commit; 0 when merged),
`stale` (age strictly greater than threshold; equal is not stale; trunk is exempt),
`required_checks` ({name: {status, stale_ancestor_shas}}), `required_checks_covered`.
Plus `trunk` summary, `stale_branches`, `unreachable_commits` (reachable from no branch
tip), sorted `source_trace`, `reference_time` in UTC, `branch_protection_verified:false`,
`main_mutated:false`, `limits`. Output does not depend on input ordering.

## Coverage rule
A check covers a tip only if a record with the same name AND the exact tip SHA is
`success`. Records on ancestors of any conclusion are reported as `stale_ancestor_shas` and never count;
a failing tip record is `failed` even if an ancestor passed; absent record is `missing`.

## Refusals (exact messages tested)
cycles (incl. self-parent), unknown parent/tip/check sha, duplicate parent, duplicate or
conflicting duplicate commit/branch/check record, missing trunk, naive/malformed/
leap-second/out-of-range timestamps, commit after reference_time, commit older than its
parent (ambiguous clock), check completed_at after reference or before its commit,
unsupported conclusion, invalid names/SHAs, non-boolean-safe numeric threshold.
Graph structure is checked before clocks.

## Bounds (N accepted, N+1 refused)
commits 2000, branches 64, checks 512, required_checks 16, parents/commit 8,
names 100 chars. Ancestry uses bitsets over a Kahn topological order (no recursion).

## Limits (residual)
Analyzes supplied records only; it does not read git or GitHub, cannot verify
branch protection, required-status settings, signatures, authorship or runner
trust, and never mutates protected main. Branch age is oldest-unique-commit age,
not branch creation or PR age. Timestamps are caller claims. Not a merge-readiness
or release decision. Ledger, STATUS and rows 857/858/859 untouched.

## Input-boundary repair

SHA/name/timestamp patterns use fullmatch, so trailing LF is refused rather
than accepted as an end-anchor exception. Timestamp digits are ASCII-only.
Ancestor records of any conclusion remain listed, not only successful passes.
This is supplied-data validation, not approval or authority to mutate a branch.
