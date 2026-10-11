# Row 103 Liking Enhancement - contract

## Ledger source pin
audits/additional-2000-features.json, id 103: requirement "Liking Enhancement"; description "Builds rapport and similarity"; status PARTIAL (read from main).

## Delta against the existing mechanism
Existing: `_liking`, backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:537. It treats caller-declared commonalities as a set, computes authenticity precision and coverage as floats, reports a rapport_score = sqrt(precision*coverage), a +/-0.15 band, and blocks unsupported claims.
This module (new file liking_enhancement103.py, nothing existing edited) drops the sqrt score and the band. Each commonality carries `confirmed_by_both`; only confirmed ones can support a claim. Matching is trim plus lower-case, duplicates are refused, outputs are sorted. It reports `supported`, `unsupported` (claimed but not confirmed, which includes claims that match only an unconfirmed commonality), `unconfirmed`, and exact reduced fractions: precision = supported/claimed, coverage = supported/confirmed (null when the denominator is 0). `usable` = at least one claim and none unsupported; `allowed` = usable and the caller states the use is disclosed.

## Interface
`review({"commonalities": [{"topic", "confirmed_by_both"}], "claimed": [str], "disclosed": bool})`. Lists up to 50 items; topics and claims 1 to 100 characters after being non-blank.

## Refusals (prefix `LIKING103:`, exception LikingError)
Non-mapping input; unknown keys; commonalities or claimed not lists or over 50; missing or non-boolean disclosed; non-mapping commonality; unknown commonality key; blank or over-long topic or claim; non-boolean confirmed_by_both; duplicate topic or claim after normalising.

## Limits
Supplied declarations only; whether a commonality is real is the caller's statement. An invented similarity is blocked, never suggested. Not a prediction that anyone will like anyone and not advice. Boundaries pinned at N and N+1: 50/51 items for each list, 100/101 characters, empty-claim and empty-confirmed fractions.

## Status
Prep only. Independent mutant-battery audit required before landing. Full test suite not run: only this row's tests were run.

## Known residuals (permanent, disclosed; each pinned by a test)
1. No Unicode normalization and no casefold: matching is strip plus lower-case only. A precomposed e-acute and an e followed by a combining acute accent do not match, and "Stra\u00dfe" and "STRASSE" do not match; the claim is reported as unsupported.
2. Control and format characters are accepted: a topic or claim containing characters such as U+202E, U+200B or NUL is not refused and is echoed unchanged in the output lists.
3. Unknown-key echo is uncapped: an unknown top-level key, or an unknown key inside a commonality record, is refused with a message that repeats the whole key (repr) with no length limit; checked at 4000, 5000 and 100000 characters.
The pins in the test file describe exactly these behaviors; they do not say the behavior is desirable.
