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

## Round 2 repair (this commit)

Defects found by independent review of the first commit and fixed in the core, each with pinned tests:
1. Timestamps accepted NaN and infinity. All numeric time inputs (`at`, history `at`, consent `granted_at` and `expires_at`) must now be finite.
2. `allowed_kinds` given as a string matched by substring. Every `tos` entry must now be a dict, `allowed_kinds` a list of non-empty strings, `automation_allowed` a bool; entries for every platform are validated, not only the acted-on one.
3. `privacy.purpose_allowed` as a list raised AttributeError instead of ValueError. `privacy` fields are now fully typed: `personal_categories` a list of strings, `purpose_allowed` a dict of non-empty string keys to lists of strings. `review_kinds` must be a list of strings.
Pinned defaults: a declared platform with no `allowed_kinds` denies (does not crash); consent with absent `revoked` is not revoked and with absent `expires_at` does not expire; a non-personal category with no purpose is allowed; a personal category with no purpose is denied.

## Round 3 repair

Round 2 used `math.isfinite(v)` on every numeric time input. That raises `OverflowError` for an ordinary
JSON integer such as `10**400`, which affected action `at`, history `at` and consent `granted_at` and
`expires_at`. Fix: integers are never converted to float. Every time value and every rate `window_seconds`
must satisfy `abs(v) <= 2**53` (every such integer is exact as a float); anything larger, and NaN and
infinity, raises `ValueError`. Counts and `max` are not bounded and compare as plain integers, so huge
values cannot overflow. Pins cover the action, history and consent paths, the window, the exact boundary
(accepted at `2**53`, rejected at `2**53 + 1`), and huge counts.
Three more pins were added for survivors reported by independent review of round 2: a non-list
`recent_actions` (including an empty tuple) raises `ValueError`; a wildcard-only rate limit allows within
the limit and denies over it; the exact reason strings of the privacy branches.

## Round 4 repair (correction of an earlier claim)

Credit: an independent reviewer (auditor B17) found that the round 3 rate-window check was NOT exact. It
computed the window edge as `at - window_seconds` in float arithmetic. With `at = 0.5`,
`window_seconds = 9007199254740991`, `max = 1` and one history entry at `-9007199254740990`, the exact edge
is `-9007199254740990.5`, float subtraction rounded it to `-9007199254740990`, the entry fell outside the
window and the action was allowed when it should be denied (fail open). The round 3 wording that time
arithmetic was exact within the `2**53` bound, and the closure built on it, were wrong and have been
revoked. Accepting values up to `2**53` was never the same thing as computing with them exactly.

Fix: window membership now uses `fractions.Fraction`, which is exact for the finite floats and bounded
ints this module accepts: `at - window < entry_at <= at` (left-open, right-closed), unchanged semantics and
unchanged accepted range (`abs(v) <= 2**53`). No other policy changed (consent, counts, receipts, denial
and type rules are as in round 3).
Pins: the original fixture; exact edge cases just inside, just outside, on the left edge, on the right
edge, and in the future, using `math.nextafter`; and an oracle test that recomputes membership with
`Fraction` independently of the module over mixed int/float values around +-2**52 and +-2**53 with windows
from 1 to `2**53`, comparing the verdict for 2,000+ combinations.
A subclass of `int` that lies through `__abs__` is a separate type-policy matter and is not addressed here.

## Mutation evidence (author runs, hand-written, one at a time, raw logs per mutant)

Round 1 (commit 2c1a141b): 40 mutants; first run 37 killed, 3 survived; after 2 added tests 39 killed, 1 survived (m25).
Round 2 (this commit): 52 mutants against the repaired core. First run: 49 killed, 3 survived (m25, m43, m52). A test was added for m52 (substring regression: kinds like "po" must not match "post"). Final run: 50 killed by test failure, 2 survived, 0 timeouts. Test count: 120 on Python 3.10.12.
Round 3 (this commit): 61 hand-written mutants against the repaired core (the earlier 52 adapted to the new code, plus 9 for the bound, the window bound, the recent-list guard, the wildcard fallback and the reason string). 59 killed, 2 survived (m25, m43, equivalent as above), 0 timeouts. Test count: 138 on Python 3.10.12.
Round 4 (this commit): 69 hand-written mutants (the 61 adapted to the new code plus 8 for float subtraction, float-only edge, truncation, off-by-one and right-open). 66 killed, 3 survived: m25 and m43 as above, and a20 (`float(e["at"])` instead of `Fraction(e["at"])` in the comparison), which is equivalent here because every accepted entry time is a float or an int with `abs <= 2**53`, which converts to float exactly, and Python compares Fraction with float exactly. No timeouts. Test count: 142 on Python 3.10.12. The killed-by-error versus killed-by-assertion split is not separated in the script summary. One of the 61, converting the integer to float before the bound check, is killed by an `OverflowError`; killed-by-error and killed-by-assertion are not separated in the script summary.
Survivors, scoped:
- m25 (a `None` action purpose may match a consent purpose): equivalent through `preflight`, since consent purposes are validated as non-empty strings and never equal `None`.
- m43 (remove the list-or-tuple check on `allowed_kinds`): equivalent through `preflight`, since the next line's string-list validation rejects non-lists itself. The first guard is redundant.
Neither equivalence holds for a caller that bypasses the module's validation. An independent reviewer ran a larger variant set against commit 1 (reported as 83 variants, 17 survivors, including malformed guards); the author did not run it and has not re-measured it against this commit.

## Not covered

- No real ToS, robots, API terms or statute is read or modeled. Rules exist only if the caller declares them.
- The caller supplies the time and the action history. A caller who omits history defeats the rate check. No clock, no persistence, no counting across calls.
- Consent records are trusted as declared; their authenticity is not checked.
- Purpose limitation is a declared category-to-purpose table, not a privacy-law test.
- No contacting, submitting or account action is performed or approved here. This is not an approval gate for the user's own review of outbound messages.
- Not wired into any route or registry; the existing m03, m06 and m18 gates are untouched.
- Time values beyond 2**53 in absolute value are rejected, not handled. Callers with larger values (for example nanosecond epochs) must scale them first.
- Not run: the repo conftest, mounted auth/tenant tests, Python 3.12. Environment was Python 3.10.12.
- The `instinct_doc` directory has no `__init__.py` (namespace package); ownership of that marker is undecided.
- Reviewer exceptions and non-ValueError failures from caller-supplied objects with custom `__len__` or `__eq__` behavior are not handled.
