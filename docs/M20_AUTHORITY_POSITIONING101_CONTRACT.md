# Row 101 Authority Positioning - contract

## Ledger source pin
audits/additional-2000-features.json, id 101: requirement "Authority Positioning"; description "Establishes expertise and credibility"; status PARTIAL (read from main dcab66a2ea4303ea2c763074ef272f3e0cbe17e3).

## Delta against the existing mechanism
Existing: `_authority_positioning`, backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:516. It combines caller evidence records as a noisy-or of reliability x relevance x exp(-age_days/365), with a fixed plus/minus 0.15 band and a 0.5 threshold. Those weights and the band are heuristics.
This module (new file authority_positioning101.py, nothing existing edited): an exact, integer rule over dated credential declarations. No decay constant, no band. A credential is counted only if it has a named `verified_by` check, is attributable, is not expired on `as_of` (valid through the expiry day inclusive) and is relevant. Counted points: direct 2, adjacent 1. Level: "supported" needs at least 4 points and at least 2 distinct issuers; "limited" needs at least 1 point; otherwise "none". Every uncounted credential is listed with ordered reasons (unverified, unattributable, expired, not_relevant) and must be disclosed. `release_allowed` is true only when the caller says the use is disclosed and the level is not "none".

## Interface
`assess({"claim", "credentials", "as_of", "disclosed"})` -> dict. Credential keys: id, kind (degree, license, publication, experience, affiliation), issuer, relevance (direct, adjacent, none), verified_by, issued_on, attributable, optional expires_on. Dates are ASCII YYYY-MM-DD, followed by calendar validation. Week-date refusal is now consistent on Python 3.10 and 3.12 (earlier Python 3.12 accepted week dates). Basic-date refusal is retained, not new behavior.

## Refusals (prefix `AUTHOR101:`, exception AuthorityError)
Non-mapping input; unknown keys; claim blank or over 500 characters; credentials not a list or over 100; missing or malformed as_of; non-boolean disclosed or attributable; unknown kind or relevance; blank id or issuer; duplicate id; malformed dates; issued_on after as_of; expires_on before issued_on.

## Limits
Supplied declarations only. This function checks consistency and dates, not the truth of any declaration, and verifies no credential. It is not a prediction of persuasion or any outcome and gives no advice. Intended for transparent use: cite only counted credentials and disclose the uncounted ones. Boundaries pinned at N and N+1: 100/101 credentials, 500/501 claim characters, 3/4 points, 1/2 issuers, expiry on and before as_of, issue day equal to and after as_of.

## Status
Prep only. Independent mutant-battery audit still required before landing. Full test suite not run: only this row's tests were run.
