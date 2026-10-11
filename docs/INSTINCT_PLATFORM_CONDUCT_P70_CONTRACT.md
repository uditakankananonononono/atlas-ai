# P70 platform conduct preflight: contract

Source line: [P70|L59] "Respect platform terms of service, privacy laws, rate limits, and user consent."

Module: `backend/app/modules/instinct_doc/platform_conduct_p70.py` (standard library only).
Tests: `tests/modules/test_platform_conduct_p70.py`.

## What it is

A declared-input preflight gate for ONE proposed outbound action. `preflight(action, declarations)`
returns `allow`, `needs_review` or `deny` with a reason per check. It performs no action. It is a bounded
mechanism over what the caller declares. It is NOT legal compliance, NOT a reading of any real terms of
service, NOT proof a platform permits anything, NOT coverage of any privacy statute, and NOT fulfilment
of the whole doc line. Every result carries `scope: "declared-input-only"`, `performs_no_action: true`
and `not_legal_compliance: true`.

## Inputs

Action: `platform`, `kind`, `at` (number, caller-supplied time), `count` (default 1), `subjects`,
`data_categories`, `purpose`, `automated`.
Declarations: `tos` (per platform: `allowed_kinds`, `automation_allowed`), `rate_limits` (per platform and
kind, or `"*"`: `max`, `window_seconds`), `recent_actions` (caller-supplied history), `consent` records
(`subject`, `purpose`, `granted_at`, optional `expires_at`, `revoked`), `privacy`
(`personal_categories`, `purpose_allowed`), `review_kinds`.

## Checks

1. `tos_declared`, `tos_kind_allowed`, `tos_automation`: the platform must be declared, the kind declared allowed, and automated actions only where declared allowed.
2. `rate_limit`: a limit must be declared (kind-specific beats `"*"`). History entries for the same platform (and kind, unless the wildcard applies) with `at - window < entry.at <= at` plus this action's count must not exceed `max`. Entries after `at` are ignored.
3. `consent`: every subject needs a record with the same purpose, `granted_at <= at`, not revoked, and no expiry or `expires_at > at`.
4. `privacy_purpose`: declared personal categories must be allowed for the declared purpose. Categories given with no privacy declaration are denied.

Missing declarations deny (fail closed). Malformed input raises `ValueError`. `needs_review` only when
every check passes and the kind is in `review_kinds`; a deny always wins.

## Mutation evidence (author run, hand-written, one at a time, raw logs per mutant)

40 mutants. First run: 37 killed, 3 survived (m25, m26, m39). Two tests were added for m26 and m39. Final
run: 39 killed by test failure, 1 survived. m25 (allow a `None` action purpose to match a consent purpose)
is an equivalent mutant through `preflight`: consent purposes are validated as non-empty strings, so they
never equal `None`. It would differ only if a caller bypassed validation. No timeouts occurred.
Test count: 45 on Python 3.10.12.

## Not covered

- No real ToS, robots, API terms or statute is read or modeled. Rules exist only if the caller declares them.
- The caller supplies the time and the action history. A caller who omits history defeats the rate check. No clock, no persistence, no counting across calls.
- Consent records are trusted as declared; their authenticity is not checked.
- Purpose limitation is a declared category-to-purpose table, not a privacy-law test.
- No contacting, submitting or account action is performed or approved here. This is not an approval gate for the user's own review of outbound messages.
- Not wired into any route or registry; the existing m03, m06 and m18 gates are untouched.
- Not run: the repo conftest, mounted auth/tenant tests, Python 3.12. Environment was Python 3.10.12.
- The `instinct_doc` directory has no `__init__.py` in this commit (namespace package); see the hand-off note about who owns that marker.
