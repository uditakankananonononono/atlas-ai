# Source pin: audits/coverage-register.json row 702
Requirement: "Release Notes". Description: "Informs users".
Read public base. Register status
is historical bookkeeping, not a scoped closure or acceptance claim.

## Existing mechanism and delta
backend/app/modules/m20_general_cognitive_worker/software_practice_685_709.py:56
_release filters caller-supplied changes by truthy flags and echoes version,
audience, upgrades, known issues and source IDs. Cluster boundaries include
_review:25 (checklist, approval, unresolved blockers, no self-approval) and
_tdd:21 (caller-declared RED/green booleans). None of these is modified.

Delta: plan_release(request) strictly validates a closed supplied-change schema,
exact booleans, unique change IDs, text/type/limit checks, exact draft sections
and an input snapshot digest. Supplied facts remain unverified. No Git, caller
code, test suite or external tool is executed. This is a new supplied-list
component, not the earlier independent local Git-history draft mechanism.

## Interface and refusals
Request exactly version, audience, changes, upgrade_steps, known_issues.
Each change exactly id, description, user_visible, breaking. Flags exact bool.
Text nonempty, <=1000 chars, Unicode Cc/Cf/Zl/Zp refused; text preserved as supplied.
Lists <=10,000, may be empty. IDs unique. Input order preserved. Result highlights
contains only user_visible changes; breaking_changes independently includes
breaking changes even when not user_visible. No inferred impacts or outcomes.
Digest identifies input bytes under sorted compact JSON, not source truth.
Output status draft_only; published/repository_verified/release_authorized false.
Every refusal ValueError starts RELEAS702: with fixed diagnostic; no supplied
ID/value is echoed. Caller must escape text before rendering to a UI.

## Evidence
Test-first module-missing RED retained. Isolated stdlib unittest.
No shared cluster, routing or registry edits.

## Limits and residuals
Bounded bookkeeping over supplied artifacts, no closure claim. No publishing,
messages, spend, accounts, legal advice, release permission, user-notification,
repository completeness, quality, actual coverage or execution claims.
FULL-SUITE UNVERIFIED. No mounted auth/tenant/routes, production performance,
Python3.12, Docker PG or external validation. Independent gate: separate record.

Policy revision: dictionary key counts checked before set construction; list
counts checked before iteration; raw length before strip/Unicode. Zs accepted.
Full Cf category refused with explicit U+00AD/U+2060 pins. Cs surrogates are not
newly refused; JSON UTF-8 digest may fail on lone surrogates, a disclosed residual.

Strict-type revision: request/change objects must be exact dict, all three
input collections exact list, and every text field exact str. Subclasses are
refused before their methods run. Existing caps and Cs residual unchanged.

Key-type revision: after exact object type and key-count guards, every request
and change key must be exact str. Non-str and str-subclass keys refuse with
fixed RELEAS702: unknown field, without caller-key echo. Exact-dict set spies
pin request and change count-first ordering without relaxing type boundaries.
