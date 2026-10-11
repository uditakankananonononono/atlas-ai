# M20 Row 1547 Shock Testing contract

Ledger source pin: audits/coverage-register.json row 1547, requirement verbatim "Shock Testing", description verbatim "" (empty - the requirement title is the whole spec).

Purpose: multi-profile validation and aggregation bookkeeping over caller-supplied shock pulse declarations. This is NOT a new physical model and NOT a shock-testing capability: the pulse formula and shape factors are reused unchanged from the existing _shock function. It is a bounded plan over caller-supplied shock pulse declarations (pulse shape, peak acceleration, duration), for supplied specimen count, axes and declared acceptance criteria. Pure stdlib, no I/O, deterministic.

Delta against the existing mechanism `_shock` in `backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py` (read on live main a294723b7a8f7bbe6067804ee4d7d325e1a8bde9, line 228):
- Existing: single pulse, three shape factors (half_sine 2/pi, rectangular 1, terminal_peak_sawtooth 0.5), one estimated delta velocity, plain untagged ValueError for an unsupported shape, no declaration schema beyond two positive numbers.
- The shock formula and shape factors are IDENTICAL to that function (estimated delta velocity = peak x 9.80665 x duration_ms / 1000 x factor, factors half_sine 2/pi, rectangular 1, terminal_peak_sawtooth 0.5). This unit is NOT a new computation path and is not offered as proof of new physics; a source audit may fairly read it as a duplicate of _shock's arithmetic.
- New (interface only): bounded multi-profile declaration (1 to 20 profiles) with exact input and profile key sets, SHOCK1547-tagged refusals instead of the untagged ValueError, specimen_count (integer 1..1000), axes (1..3 unique of x/y/z), acceptance_criteria (0..10 non-empty texts of at most 64 chars, never evaluated), shape counts in sorted order, max estimate, plan explicitly labeled plan_only with test_executed False.

Input keys (exactly): profiles, specimen_count, axes, acceptance_criteria. Profile keys (exactly): pulse_shape, peak_acceleration_g, duration_ms. Peak in (0, 100000], duration in (0, 60000], finite, non-bool numbers.
Refusals: ShockError (a ValueError) with prefix "SHOCK1547: ". Output carries three fixed limits strings.
Validation order pins: strict builtin types only (type(x) is, never isinstance, so subclasses and bool are refused); strict key types (every mapping key must be exactly str); container length and key counts are checked before any set construction or iteration (root and profile key counts, profiles 1..20, axes 1..3, criteria at most 10), pinned by a sys.setprofile ordering test (the count's len call precedes the first caller-dict iteration). Raw text caps run first where they apply: acceptance_criteria entries at most 64 characters (cap before strip, before Unicode), axes entries at most 8 (cap before Unicode, before the enum), pulse_shape at most 32 (cap before the enum; the finite enum runs before any Unicode walk, so a bad shape is refused as unsupported). Unicode refusal (Cc/Cf/Zl/Zp refuse, Zs accept, explicit U+00AD and U+2060 pins) applies to free text that is echoed or carried: axes and acceptance_criteria. Cs surrogates: only acceptance_criteria carries the Cs residual (a lone surrogate is neither refused nor normalized there; consumers must treat it as opaque). The finite enums (pulse_shape, axes) refuse any surrogate outright, because a surrogate can never match an enum member.

Scope: bounded exact deterministic mechanism over caller-supplied declarations. No physical test, solver execution, certification, or release authority; plans are labeled plans, never results. No executed-test or survivability claims.

New files only: shock_testing1547.py, test_m20_shock_testing1547.py, this document. The shared cluster file engineering_1510_1559.py is not edited.

Limits and residual disclosures:
- The delta-velocity figure is the classical idealized shape-factor estimate over supplied numbers, not a measured or simulated specimen response.
- Supplied acceptance criteria are carried as bookkeeping only and are never checked against the estimate.
- No statement is made about test standards, fixtures, or specimen survival; those stay with the human test engineer.
- Ledger status "verified-pushed" is a builder attribution read from the ledger, not re-verified by this unit; this unit does not claim the row closed.

## Change note

The raw cap was changed from 200 to 64 as a builder default; values 65-200 previously accepted are now refused.

## Build chronology disclosure (builder-stated)

Preservation violation, stated plainly: local commit ce24bbaf carries all three new files in one commit whose message says only "test(m20)" (mislabeled scope, deliberately not amended); an accidental empty commit, full object sha 8d93cef1ad79c02da5cd15d2273d9868cc70d8c5 (message "noop", parent ce24bbaf), was created by builder error and then removed from the branch tip by a builder-run local soft reset to HEAD~1. That reset is the preservation violation. Recoverability is builder-stated, not independently verified: the builder's local git cat-file shows the object intact and the reflog holds all three entries, and no gc or reflog expiry has been or will be run by the builder.
- Provenance of this section: added by the builder as an uncommitted additive patch to the working-tree copy of this document; the branch's committed content is unchanged.
