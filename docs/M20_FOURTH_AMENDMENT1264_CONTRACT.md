# Row 1264 Fourth Amendment - contract

Ledger pin: audits/coverage-register.json row 1264, title "Fourth Amendment", status PARTIAL, requirement description empty (the title is the whole spec). Main read: a294723b7a8f7bbe6067804ee4d7d325e1a8bde9. The package's mechanism note was from 7a42efec and was re-read at a294723b.

"Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use."

## Interface

`map_fourth_amendment(payload)` in `backend/app/modules/m20_general_cognitive_worker/fourth_amendment1264.py`. Refusals are `FOURTH1264: <code>: <message>`; they name the field, never the value or an index. Input fields: matter_id, jurisdiction, as_of (strict YYYY-MM-DD), conduct {actor, activity, description}, authorities 1..20 {id, citation, source, last_checked}, optional standing, warrant, exceptions (max 10), scope_items (max 10), suppression_questions (max 10), sourced_facts (max 20), assertions (max 20). Labels are closed sets (actor, activity, standing basis, warrant status, exception name, asserted_by, limit_source). Output: the declared values, `open_elements` (the questions not declared), `needs_authority_link`, `stale_authority_ids` (last_checked before as_of), `review_state` (incomplete or counsel_review_required), and fixed flags: legal_conclusion null, reasonableness_decided false, suppression_decided false, authority_independently_verified false.

## Delta against existing code

legal_support_1260_1309.py:21 (SPECS row 1264, output key search_seizure_map) is served by analyze_legal_feature at :96, a shared template for rows 1260-1309. It passes a free-form `row_inputs` object through untouched and never inspects conduct, standing, warrant, exception, scope or suppression. This unit adds typed, bounded declarations for exactly those six, closed label sets, authority reference integrity (an unknown or repeated reference is refused, where the template marks it), and a declared-versus-open map. The shared file is not edited. The template's own output is unchanged.

## Rules

Text fields: type, then length cap 200 on the raw length first, then blank, then Unicode: no Unicode control, line/paragraph separator or bidi/format characters. The check is by general category: Cc, Cf (the whole format category, including U+00AD, U+2060, U+200B-200F, U+202A-202E, U+2066-2069, U+FEFF), Zl and Zp are refused; Zs (ordinary and non-breaking spaces) and other categories are accepted, and no new Cs (lone surrogate) refusal exists. Labels: exact str, then a raw length cap of 32 before the closed-set membership test (over the cap is refused as labels exceeding 32 characters). Authority references: exact str, then a raw cap of 200 (the id length limit) before membership in the supplied ids. Dates (as_of, last_checked): exact str, then an exact raw length of 10 as the first content check, then the ASCII digit pattern, then a calendar check; the generic 200-character text cap and Unicode scan are not used for dates. Lists: exact list type, then length cap, then entry rules; a list subclass is refused as a type error. Objects: exact dict type, then the key count is checked against the number of allowed fields before any key is hashed or scanned (more is refused as invalid_count, field named), then every key must be exactly str (a str subclass or non-text key is refused before the allowlist), then unknown fields are refused. There is no numeric input in this unit, so number-grammar and decimal rules do not apply: policy not applicable: pure offline, caller-supplied declarations only, no network, filesystem, clock or randomness (the as_of date is caller-supplied; the clock is never read).

## Evidence (builder-stated)

Order slip: I drafted the module at 21:52 before the tests. To get a RED I moved the draft out, wrote the tests, and ran them with the module absent: collection error (FileNotFoundError), 21:52:52. That RED is import-level only, not a behavioral failure on each test. The unchanged draft was then restored and the tests ran green after one test fix (the 10 MB allocation was built inside the traced window; 33 passed, 1 failed, then 34 passed at 21:53:14). Five tests were then added (39 passed).

Chronology disclosure (permanent): the module draft was written BEFORE the tests; the RED was import-level only (module moved out, collection error), not a per-test test-first RED; and this unit was committed locally as 6e362665efeca63e41a74fa0d5f374ca79c56421 although the assignment was patch-only (nothing pushed, no amend, rebase or reset).

Mutants: 44 hand-written, one at a time (text type, length operator and cap, blank, Unicode categories and every range end, label and list type, list cap and minimum operators, date regex, reference membership and distinctness, unsupported fields, staleness operator, link rules, open-element order, flag values, fact/assertion merge, input mutation, value echo, review state). First run: 35 killed, 9 survived. After adding tests (not independent): 41 killed, 3 survive. Survivor dispositions, each a claim for the auditor only: DEL check (DEL is already category Cc), the date regex digit class and fullmatch versus match (date.fromisoformat on 3.12.14 rejects non-ASCII digits and trailing text with the same refusal message). One first-run survivor was a no-op mutant and was rewritten. Python 3.12.14.

## Repair after review (uncommitted patch on top of 6e362665)

Core findings applied: dict key count first at every object (payload and each record), exact `type(key) is str` before the allowlist, full Cf category refusal with Zs accepted. These repair tests were written first this time: RED 22:38:29 on the unchanged runtime (5 failed, 38 passed), then green. Two earlier expectations changed on purpose: a record with one extra field is now refused by count (invalid_count, for example conduct exceeds 3 fields) instead of unsupported fields, and U+2060 and U+206A-206F, previously accepted, are now refused as Cf.

## Second repair (uncommitted patch, builder receipts)

Label raw cap (32), reference raw cap (200) and date raw length (10) added ahead of their membership or pattern checks, each pinned at N and N+1, with a 10 MB input refused under 1 MB of traced allocation and source-order pins. Count-first, strict keys, full Cf and the 200 text cap are unchanged. RED 22:42:30 on the unchanged runtime: 7 failed, 42 passed (one of the 7 is the doc scrub check). Date refusals for blank, control or Unicode as_of values now carry the ISO date message rather than the text messages.

Receipts, all builder-run and not independent: the first mutation battery was 44 mutants, 41 killed and 3 survivors after tests were added; the repaired battery was 53 mutants, 51 killed and 2 survivors, which are unproved equivalence claims for an auditor (date regex digit class, fullmatch versus match). The battery after this second repair was 67 mutants, 65 killed and the same 2 survivors; this is also a builder receipt, run after the tests were written, not independent.

## LIMITS

- Bookkeeping only. It does not rule on reasonableness, standing, warrant validity, exceptions or suppression, and does not predict outcomes.
- It does not verify any citation, authority, fact or assertion; a link is only a caller-supplied id match. Staleness is a date comparison of caller values.
- Closed label sets are a bookkeeping simplification, not a statement of the doctrine; `other` exists for the rest.
- Full suite unrun; only the row 1264 test file ran. No integration into any router or the cluster files.
- No Unicode normalization is applied; look-alike characters are accepted as different text. Lone surrogates (Cs) are accepted by policy and may fail later at a serialization boundary the unit does not control.
