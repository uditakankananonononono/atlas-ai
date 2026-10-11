# M20 Row 1262 Constitutional Law - contract

## Ledger source pin
- `audits/coverage-register.json` row 1262:
  requirement "Constitutional Law", description "" (empty).
- `audits/additional-2000-features.json` row id 1262: requirement "Constitutional Law", description "" (empty), status PARTIAL.
- The description is empty, so the title "Constitutional Law" is the whole spec. This contract states its own reading of that title; it is not a ledger requirement.

## Scope
Bounded declared legal-support bookkeeping over caller-supplied data only. It is jurisdiction, as-of and provenance-bound, and separates sourced facts from assertions and from analysis. It never reaches a legal conclusion, never files, serves or contacts anyone, and never verifies supplied assertions or authority references. It never decides constitutionality.

Standing boundary: "Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use."

## Interface
`map_constitutional_scrutiny(data)` in `backend/app/modules/m20_general_cognitive_worker/constitutional_law1262.py`.
Input keys (exact set): `jurisdiction`, `as_of` (ASCII `YYYY-MM-DD`, exact raw length 10 checked before the regex), `authorities` (1-20 objects with exactly `id`, `citation`, `jurisdiction`, `source_url` http/https), `elements` (1-20 objects with `element`, `kind`, `text`, optional `source_id`).
`element` is one of state_action, right, scrutiny_level, governmental_interest, tailoring. `kind` is sourced_fact, assertion or analysis; a sourced_fact needs a `source_id` that matches a supplied authority id. The scrutiny level is whatever label the caller supplies; nothing is computed.
Output: entries grouped per element in input order, `missing_elements`, `jurisdiction_mismatch_source_ids`, `legal_conclusion` always None, `authority_independently_verified` always False.

## Refusals (all `CONSTI1262:<CODE>`, fixed text, never echoing input)
SHAPE, KEYS, TYPE, TEXT_LONG (raw length over 500, checked first), TEXT_EMPTY, TEXT_HIDDEN (the full Cc, Cf, Zl and Zp categories, which includes DEL, U+00AD, U+200B-200F, U+202A-202E, U+2060-2064, U+2066-2069, U+FEFF; Zs is accepted), COUNT_MAX / COUNT_MIN (list length and dict key count, max 64 keys, checked before any set construction, iteration or item parse), DATE, ENUM, SOURCE_REQUIRED, SOURCE_UNKNOWN, DUP, URL.

## Delta against the existing mechanism (citations re-read at main a294723b; line numbers re-verified against the landing main)
- Existing: `backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py:19` (SPECS row 1262, "map state action, right, scrutiny level, governmental interest and tailoring") run through `analyze_legal_feature` at line 96. It passes `row_inputs` through unexamined at the `inputs` key; it has no per-element structure, no required-element check, no length/count caps, no hidden-character refusal, and its errors are free-text ValueErrors. Its row 1262 test (`tests/modules/test_m20_legal_1260_1309.py:57-59`) checks as_of, source_url, actor_id and the unsupported-row refusal. That file was not edited.
- Delta: the five named elements are first-class and each entry is tagged by kind; missing elements are listed; sourced facts must link to a supplied authority; fixed row-tagged refusals; caps checked before parsing.
- Not delta: no tenant or actor isolation, no staleness or contrary-authority flags (the shared template has them; this module does not).

## Limits and residual disclosures
- Builder-stated; nothing here is a closure claim.
- Full repo suite is unverified (not run). Only `tests/modules/test_m20_constitutional_law1262.py` was run, on Python 3.12.14.
- Authority references and assertions are accepted as supplied and never checked; a linked source id means only that the id matches a supplied entry.
- Caller text is echoed in output entries after strip; the banned-word check covers generated keys and values only.
- Residual: lone surrogates (category Cs) are not refused; no new refusal was added for them.
- source_url accepts any http(s) URL with a host; credentials, queries, fragments, spaces and non-default ports are not refused and are echoed as supplied.
- Containers and text use strict builtin types (`type(x) is dict/list/str`); subclasses are refused (SHAPE or TYPE).
- Text order: type, raw length cap, screen of the RAW text (so edge LF, TAB, U+0085, Zl and Zp are refused, not trimmed away), then strip, then the empty check. Dict keys must be exactly `str` (KEYS), checked after the key count and before any set construction.
- Mutation note: the survivors `ascii_flag_off` (ASCII regex flag removed) and `date_len_ne` (`!= 10` weakened) are equivalent by the [0-9]-class + fullmatch + length-10 argument: a shorter string or one with non-ASCII digits fails the fullmatch and returns the same DATE refusal; this equivalence is by reasoning, not proven.
