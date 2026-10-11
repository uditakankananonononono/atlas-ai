# M20 Evidence Analysis 1282: custody completeness contract

Source: audits/additional-2000-features.json row 1282, requirement "Evidence Analysis", description empty. The title is the whole source. This unit is an explicitly chosen bounded mechanism: custody completeness and gaps over caller-declared records, with weight tags passed through.

## Relation to the existing row 1282 mechanism

Row 1282 already has `backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py` (row entry `evidence_analysis`, method `admissibility_issue_map`, which maps provenance, purpose, relevance, foundation, exclusion and objection issues as a legal review template). This module is additive and does NOT replace, call, import, edit or re-certify it. Delta: this module checks the mechanical consistency of a declared chain of custody, which the existing mechanism does not do. It makes no admissibility judgment. No ledger, coverage register, wiring or existing file is edited.

## Entry point

`analyze_evidence(items)` in `backend/app/modules/m20_general_cognitive_worker/evidence_analysis1282.py`. Pure function, stdlib only, no file, network, clock or randomness access.

Each item (all keys exact; unknown keys refused): `evidence_id`, `type`, `source`, `timestamp` (ISO-8601 with an explicit UTC offset), optional `weight_tag`, optional `custody`: a list of transfers `{"from", "to", "at", optional "note"}`.

Result per item, in the caller's order: the id, type, source and timestamp as given; `weight_tag` exactly as given or `None` when absent; `custody_status` of `CUSTODY_COMPLETE`, `CUSTODY_GAPS` or `NO_CUSTODY`; `gaps` and `custody_events`. Plus a `summary` count and the fixed flags `admissibility_judged: False`, `weights_invented: False`.

Gap codes: `CUSTODY_EMPTY` (no transfers declared), `FIRST_FROM_NOT_SOURCE` (first transfer not from the declared source), `HOLDER_DISCONTINUITY` (a transfer not from the previous transfer's holder), `TIME_REVERSED` (a transfer dated before the previous one; equal times are fine), `BEFORE_ITEM_TIMESTAMP` (a transfer dated before the item timestamp; equal is fine). Times compare in UTC.

## Refusals

Every refusal raises `EvidenceError` (a `ValueError`) whose message starts `EVID1282: `: items not a list or empty, more than 1000 items, item not an object, missing or unknown keys, text fields that are empty, multi-line, control characters or longer than 500 characters, duplicate `evidence_id`, timestamps without an explicit offset or not ISO-8601, `weight_tag` that is not a plain string of at most 64 characters (including `None`), `custody` not a list, more than 200 transfers, transfer not an object, bad transfer fields or `note`.

## LIMITS

- Checks the consistency of what the caller declared. It does not establish that evidence is authentic, that any transfer occurred, or that the source is who the caller says.
- No admissibility, relevance, foundation, privilege or probative-weight judgment. Weight tags are the caller's words, never computed, ranked, normalized, defaulted or merged.
- The source-equals-first-holder and previous-holder-equals-next-from rules compare strings exactly; no name normalization, aliasing or fuzzy matching.
- The first-transfer rule treats the declared `source` as the first holder. That is a convention of this mechanism, not a legal rule.
- Not a legal opinion; counsel decides evidentiary questions. No jurisdiction logic.
- Ordering is by timestamp comparison between neighbours only; a non-adjacent inconsistency that is not also an adjacent one is not detected.
- Title-only scope: no storage, no files, no hashing, no signatures, no persistence, no API or route wiring, no integration with the existing legal modules.
- Not shown to be verified or mounted; any coverage or ledger claim belongs to the peer's own review.

## Evidence

Tests: `tests/modules/test_m20_evidence_analysis1282.py` (loads the module by path; hermetic). A first set of 112 collected tests was written before the module; the first run failed at collection because the module did not exist (the module is then written and that set passed). 18 further collected tests (130 in total) were added AFTER the first passing run and the first mutant run, to kill surviving mutants; those 18 are not test-first. One mutant (dropping the `utcoffset() is None` half of the naive-timestamp check) still survives; it is believed equivalent but that is the author's unproved claim.

Unicode text-helper boundary: no Unicode control, line/paragraph separator or bidi/format characters. The length cap is checked before Unicode scanning; refusals name the field, never its value. Cc, Zl, Zp, DEL, U+200B-200F, U+202A-202E, U+2066-2069 and U+FEFF are refused. Ordinary internal spaces and printable non-ASCII are allowed. Existing blank-text and outer-whitespace rules are unchanged.

Unicode text-helper boundary: no Unicode control, line/paragraph separator or bidi/format characters. After the string-type guard, raw length is checked before strip, Unicode scan or copying. RAW length is the cap; oversize raw strings are refused, including a 10MB probe, without calling strip. This order changes oversize error precedence but does not widen the cap. Cc/Zl/Zp and the named bidi/format ranges are refused. Internal spaces and printable non-ASCII are allowed; existing outer-whitespace rules remain unchanged.
