# P68|L57 - in-silico-only biology guardrail contract

Source pin: instinct doc P68|L57. Contract text, verbatim:

> - All biological, medical, CRISPR, biohacking, phage, mosquito, xenobot, vaccine, enviropig, organoid, microbiome, and clinical work must be computational / in silico only unless explicitly approved by proper institutional biosafety, ethics, and legal review.

Module: `backend/app/modules/instinct_doc/insilico_guardrail_p68.py`. Pure stdlib, no I/O, network, clock, ML or external lists.

## API
`classify(item) -> dict`, `classify_batch(items) -> list[dict]`.

Item has exactly: `id` (nonblank, <=64 chars), `domain_terms` (list of 0..32 strings, each <=64 chars, lowercased by the caller),
`execution_mode` (`computational` or `physical`), `approval_ref` (optional string, <=128 chars; absent or null means none).
Lengths count characters.

Closed term set (exactly the 12 contract terms): biological, medical, crispr, biohacking, phage, mosquito, xenobot, vaccine, enviropig, organoid,
microbiome, clinical. Exact whole-term match only: no stemming, no substrings, no case folding (uppercase and near misses such as `crisprx`, `vaccines` do not match).

## Verdicts
- `not_bio_scoped`: no closed-set term matched (any mode, any approval_ref).
- `allowed_in_silico`: matched and `computational`.
- `refused_physical_without_review`: matched, `physical`, no approval_ref.
- `flagged_physical_with_review_ref`: matched, `physical`, approval_ref present. This is a flag for human review, not an approval. The module never claims an approval is valid.

Record: `contract, id, verdict, execution_mode, matched_terms (sorted, unique), approval_ref (verbatim or null), approval_validated=false, biosafety_review_performed=false, safe_claim=false, limits`.

## Refusals (ValueError, exact text)
`P68:unknown_fields:item`, `P68:empty_field:<name>`, `P68:bad_mode:<value>`, `P68:bad_type:<name>`, `P68:limit_exceeded:domain_terms` (>32), `P68:text_too_long:<name>` (id >64, term >64, approval_ref >128).
Check order inside an item: object type, unknown keys, missing required keys, then id, domain_terms (count, then each element), execution_mode, approval_ref. First failure wins.
`name` is the field name; a non-object item is `P68:bad_type:item`, a non-list batch is `P68:bad_type:items`.

Decisions beyond the brief text (documented for review): a missing required key is `P68:empty_field:<key>`; a blank (whitespace-only) approval_ref is `P68:empty_field:approval_ref`
rather than being read as "no reference"; `classify_batch` refuses duplicate ids with `P68:duplicate_id:<id>`.

## Batch
Verdicts return in sorted-id order (plain string order, so `B` < `a`). Items without a usable string id sort after the others in input order. The batch is refused on the first bad item in that order; no partial output.

## Limits
Lexical gate, not a biosafety review. It never emits a safe claim. approval_ref is recorded, never authenticated or resolved. The term set is closed; widening it is a contract change.
