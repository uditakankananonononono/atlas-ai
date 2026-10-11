# Row 104 Unity Building - contract

## Ledger source pin
audits/additional-2000-features.json, id 104: requirement "Unity Building"; description "Creates shared identity and purpose"; status PARTIAL (read from main).

## Delta against the existing mechanism
Existing: `_unity`, backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:542. It takes one set of declared commonalities and goals, computes float alignment and conflict shares over the union, a +/-0.2 band, and calls the result usable when alignment exceeds conflict.
This module (new file unity_building104.py, nothing existing edited) takes two parties' goal lists and explicit conflict pairs (a goal of party A against a goal of party B). Output: `shared`, `only_a`, `only_b`, named `conflicts`, `conflict_count`, exact reduced `alignment` = shared / union (null if the union is empty), and `identity_claim`: `none` when nothing is shared, `shared_goal_with_named_conflicts` when something is shared but conflicts exist, `shared_goal` otherwise. `allowed` needs a claim other than `none`, `disclosed` true and `individual_choice_preserved` true. No band, no usable-by-majority rule: conflicts are never netted off against agreement.

## Interface
`review({"goals_a", "goals_b", "conflicts", "individual_choice_preserved", "disclosed"})`; goals are lists of up to 50 strings (1 to 100 characters, trimmed and lower-cased, duplicates refused); conflicts are up to 50 `[goal_a, goal_b]` pairs, sorted and de-duplicated by refusal.

## Refusals (prefix `UNITYB104:`, exception UnityError)
Non-mapping input; unknown keys; any of the five keys missing; non-boolean flags; goals not lists, over 50, blank, over 100 characters or duplicated; conflicts not a list, over 50, not a pair, referencing a goal not on the matching side, or duplicated.

## Limits
Supplied declarations only. Shared identity may not erase a conflict or a person's own choice. Not a prediction of cohesion and not advice; invented common ground is never suggested. Boundaries pinned at N and N+1: 50/51 goals per side, 50/51 conflicts, 100/101 characters.

## Status
Prep only. Independent mutant-battery audit required before landing. Full test suite not run: only this row's tests were run.

## Known residuals (permanent, disclosed; each pinned by a test)
1. Self-conflict accepted: a conflict pair [x, x] is accepted when x is in both goal sets. It is counted as a named conflict, so `identity_claim` is `shared_goal_with_named_conflicts` and `conflict_count` is 1; `allowed` is still true when both flags are true. The conflict stays visible but does not block.
2. No Unicode hygiene: goals containing control or format characters such as U+202E (right-to-left override) are accepted, matched and echoed unchanged in the output.
3. Unknown-key echo is uncapped: an unknown input key is refused with a message that repeats the whole key (repr), with no length limit; checked at 4000, 5000 and 100000 characters.
4. Matching is strip plus lower-case only. There is no NFC normalization and no casefold: "\u00e9" and "e" plus a combining acute accent do not match, and "Stra\u00dfe" and "STRASSE" do not match.
The four pins in the test file describe exactly these behaviors; they are not a statement that the behavior is desirable.
