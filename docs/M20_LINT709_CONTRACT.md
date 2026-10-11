# M20-LINT709-AST-01: Linting, supplied lint report audit

Target: row 709 "Linting" / "Catches issues" (title and description as recorded in the repository at base 98bbd4ec; not re-checked against any external source, this unit is offline). The existing method `software_practice_685_709.py::_lint` only counts caller severities and echoes caller flags. This unit is a bounded SCOPED capability, not full title closure: it audits a supplied lint report against a supplied ruleset. It does not run a linter, scan source or fix anything. Wiring is out of scope for this unit and is delivered as a separate unapplied patch.

## What it is
`lint_audit709.audit({ruleset, rules, findings})`.
- `ruleset`: id string. `rules`: 1..64 of `{rule_id, severity}`, severity in error, warning, info, unique rule ids.
- `findings`: 0..256 of `{rule_id, severity, path, line, suppression}`; `suppression` is null or `{reason}`.

Output: `algorithm`, `ruleset`, `status`, `rule_count`, `finding_count`, `counts_by_severity` (all three keys), `blocking`, `suppressed_errors`, `violations`, `rules_without_findings`, `suppression_requires_reason` (true), `limits`, and the always-false flags `linter_executed`, `source_scanned`, `findings_verified`, `completeness_assessed`.

## Rules
- A finding is an error finding when its reported severity is error OR its rule's declared severity is error. An error finding with no suppression, or a suppression whose reason is blank after stripping, is blocking (`blocking` entries carry `index` (1-based), `rule_id`, `path`, `line`). An error finding with a non-blank suppression reason is not blocking and is listed in `suppressed_errors` for review.
- Violations (data problems in the report itself, each with `index` and `code`, sorted by index then code): `unknown_rule` (rule id not in the ruleset), `severity_mismatch` (reported severity differs from the declared one), `suppression_reason_blank`, `duplicate_finding` (same rule id, path and line as an earlier finding; reported on the later one).
- `status`: `blocked` when anything blocks; else `report_inconsistent` when there are violations; else `clean`.

## Refusals (ValueError, `LINT709_REFUSED_<REASON>:<field>`; 422 once mounted)
Reasons: BAD_TYPE, UNKNOWN, MISSING, EMPTY, OVERSIZE, CONTROL_CHARS, BAD_FORMAT, BAD_VALUE, DUPLICATE. Fields are schema names only: input, key, ruleset, rules, findings, rule_id, severity, path, line, suppression, reason; offending values are never echoed.

Order: (0) input is a dict; (1) preflight fence, containers only and no per-character work: exact dict and list types (subclasses refused unmeasured and uniterated), at most 580 containers, 8 keys per dict, 64 items per unlisted list (rules 64, findings 256), 64 characters per key, 10000 characters per string, depth at most 5, all giving OVERSIZE (BAD_TYPE for subclasses); (2) non-string keys; (3) unknown or missing keys at each level; (4) ruleset, list types, empty rules; (5) each field's own raw cap (rule_id and ruleset 64, severity 16, path 128, reason 200) across the whole report before any item is validated; (6) per-item validation in list order, rules first, then findings; (7) compute. A field cap beats content errors and the global fence beats everything.
Field rules: ids `[A-Za-z0-9_.:-]{1,64}`; path relative segments `[A-Za-z0-9_.-]`, no `.` or `..` segment, no empty segment; line an exact non-bool integer 1..1000000; Cc, Cf, Zl, Zp characters are refused in every string value, with no whitespace carve-out (reasons are one-line text). Keys are not content-scanned: a key is only type-checked (non-string keys are refused BAD_TYPE) and length-checked (over 64 characters is OVERSIZE), and an unknown key, including one that carries control characters, is refused UNKNOWN with the schema field name and no echo of the key. All strings are exact `str` (subclasses refused).

## INTERPRETATION CHOICES
1. Both reported and declared severity decide blocking, so a mislabelled severity cannot hide an error.
2. A blank suppression reason does not unblock and is a violation, not a refusal; a non-string reason is a refusal.
3. A duplicate is the same (rule id, path, line); both findings still count.
4. Refusal code format `LINT709_REFUSED_<REASON>:<field>` and the preflight caps (580 containers: the legitimate maximum is 579).
5. `status` precedence blocked, then report_inconsistent, then clean.
6. Empty `findings` is a clean report; empty `rules` is refused.
7. The field name on a container-budget refusal follows traversal order.

## LIMITS
The report is caller-supplied and is neither verified nor authenticated; nothing is linted or scanned. Rule ids, paths and line numbers are labels and are not checked against any file. A clean status means the supplied report has no blocking finding and is consistent with its own ruleset, not that the code is clean. Completeness is not assessed: findings a linter should have raised but did not are invisible. Suppression reasons are checked for presence only, not for truth or adequacy. Does not close other rows.

## Test and mutation notes
- The module draft was written before the tests were committed; the tests were then committed first against an absent module (red) and the draft restored afterwards, so the red run is real but the order of authorship is disclosed here.
- AST battery over every comparison, boolean operator and bool/int/string constant of the module, run on an isolated copy with the baseline checked first. First solo pass: 296 sites, 292 mutants, 21 survivors. An earlier attempt at this pass crashed on a harness timeout while two batteries ran at once and was discarded. The real survivors (the five limits sentences, the list cap table, the per-field cap pass for each field across all items, the finding rule id label, the suppression and rule field labels, the container boundary on the generic admission path) were pinned with four new tests added after the first green run. Second solo pass: 296 sites, 292 mutants, 285 killed, 7 survivors, each argued equivalent:
  1. Four role labels (`"other"` at two sites, `"suppression"` as a role, `"rule"`) -> label plus `~`: a role label is only compared against the specific names `top`, `finding`, `rules`, `findings`; any other string behaves as the default.
  2. `"rules"` -> `"rules~"` in the list-element branch: rule dicts then take the generic admission path with the same cap, depth and budget, and no rule dict has role-specific children, so every outcome and error field is the same.
  3. `depth + 1 > MAX_DEPTH` -> `>=` and `1` -> `2` on the rule and finding dict path: those dicts are always at depth 2 against a limit of 5, so the comparison is never near its boundary.
- A first pass of an earlier unit's mutation battery had a stale `.pyc` problem (same-size mutants reused cached bytecode); the battery program now disables bytecode writing. A battery run whose isolated copy lacks a file read by a doc test is void, because every mutant then dies at baseline; the baseline is checked first.

## Wiring (separate, unapplied patch)
`POST /api/v1/api/modules/20/lint-audit709/audit` via `lint_audit_routes709.py`, included from `routes.py`, with a mounted OIDC test (401 unauthenticated, 200 equals `audit()`, 422 malformed).
