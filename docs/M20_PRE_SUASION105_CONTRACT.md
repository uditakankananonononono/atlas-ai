# Row 105 Pre-Suasion - contract

## Ledger source pin
audits/additional-2000-features.json, id 105: requirement "Pre-Suasion"; description "Primes attention before persuasion attempt"; status PARTIAL (read from main).

## Delta against the existing mechanism
Existing (delta base): `_pre_suasion`, backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:547, reached through `run()` in that file. This module is a new file; the existing file, its routes and its tests are not edited and keep their behavior.
Behavior differences, each a deliberate refusal or change here and not a defect finding:
- `bool(disclosed)` coercion: here `disclosed` must be exactly true or false.
- Negative weights were clamped to 0: here they are refused.
- Float and numeric-string weights were coerced: here only exact integers (bool refused) are accepted.
- The weights list had no size cap: here 2 to 20 items, each 0 to 1,000,000,000.
- Any truthy `context` was accepted: here a string of 1 to 200 characters, not blank, with no control, format, line-separator or paragraph-separator character.
- A fixed plus/minus 0.1 band labeled "uncertainty" was emitted: it was not derived from data, so it is removed. Only computed values are reported.
- Shares were rounded floats: here they are exact reduced fractions.

## Interface
`review({"context", "disclosed", "attention_weights"})`; exact keys only; returns `row`, `context`, `disclosed`, `shares` (list of "p/q" strings, in input order), `max_share` ("p/q"), `max_share_index` (sorted list, all ties), `balance`, `concentration_check`, `covert_influence_blocked`, `allowed`, `limits` (three strings).
`balance` is the Shannon entropy of the nonzero shares divided by ln(n), rounded to 6 places half-even, clamped to [0, 1]; n is at least 2. It is a float and is pinned with a tolerance, not with exact library bits. `concentration_check` is true when the largest share is at most 1/2 (exact comparison) and is informational only. `allowed` equals `disclosed`; an undisclosed plan sets `covert_influence_blocked` true and `allowed` false.

## Refusals (prefix `PRESUA105:`, exception PreSuasionError)
Each message names the schema field and never includes a supplied value: non-mapping input (a dict subclass is refused untouched); too many keys (checked before any key is read); unknown key; missing key; `context` wrong type, over 200 characters (cap checked before strip and character scan), blank, or containing a forbidden character; `disclosed` not an exact bool; `attention_weights` not a list of 2 to 20 items (length checked before any item is read; a list subclass is refused untouched), an item that is not an exact integer from 0 to 1,000,000,000, or a total of 0.

## Limits
Supplied weights only; nothing here measures where anyone's attention goes. Context-setting must be disclosed; an undisclosed plan is never allowed. The unit never decides how to prime anyone, never sends or posts anything, predicts no response and gives no advice. Boundaries pinned at N and N+1: 2/1 and 20/21 weights, weight 0/-1 and 10^9/10^9+1, context 200/201.

## Status
Independent gate: separate record. Full test suite not run: only this row's tests were run.
