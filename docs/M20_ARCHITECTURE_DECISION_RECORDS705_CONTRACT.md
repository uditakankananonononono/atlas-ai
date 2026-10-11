Source pin: `audits/coverage-register.json`, row 705, requirement "Architecture Decision Records", description "Documents decisions", source_document_id `1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY`, read at public main `a294723b7a8f7bbe6067804ee4d7d325e1a8bde9`. `audits/additional-2000-features.json` row 705 is PARTIAL at that base. Historical register depth labels do not establish present execution or closure.

# Row705 bounded ADR record bookkeeping

## Existing mechanism and delta

At the pinned base, `backend/app/modules/m20_general_cognitive_worker/software_practice_685_709.py:66` contains `_adr`: it echoes supplied title/context/decision/consequences, defaults status to proposed, echoes alternatives/supersedes and labels immutable_history_required True. The wrapper at line 83 labels the shared diagnostics without repository verification or release authority. The cluster's `_tdd` at line 21 echoes caller-declared red/green evidence, and `_review` at line 25 keeps supplied review findings/approval with self_approval_forbidden True. These are not execution evidence for this addition.

This standalone addition validates a bounded exact schema, text/list types, declared status vocabulary and resource caps, then returns fresh list containers, a detached record and exact list counts. It explicitly says history immutability is not enforced. It does not alter the shared mechanism, add routes, integrate persistence or interpret acceptance as approval. It neither runs caller code nor executes a repository test suite or external tool. Builder tests exercise only this unit, not caller artifacts.

## API and deterministic validation

`architecture_decision_records705(data)` takes exactly a built-in dict. Required keys in validation order: title, context, decision, consequences. Optional keys: status, alternatives, supersedes. Unknown keys, including non-string keys, are refused. More than seven keys are refused before scanning key contents. Dict, str and list subclasses are refused rather than invoking custom behavior.

Validation order is mapping type, allowed keys, required-key presence, title, context, decision, status, alternatives, consequences, supersedes. When multiple faults exist the first in that order is reported. Nothing is coerced.

- title: exact str, raw length at most 200.
- context and decision: exact str, raw length at most 4000 each.
- supersedes: absent or None becomes None; otherwise exact str with raw length at most 200. It is an opaque supplied reference, not a resolved link.
- Text must have at least one non-whitespace character. Cc, Cf, Zl and Zp Unicode categories are refused. Type and raw length are checked before strip/category scanning. Accepted text is preserved exactly, not stripped or normalized.
- status: exactly one of proposed, accepted, rejected, deprecated, superseded; defaults to proposed. Explicit None and case/spacing variants are refused. Type and a raw length cap of 10 precede enum membership. The exact enum only admits safe ASCII text, so no Unicode scan or stripping is needed for status. Every status is a caller declaration, not a workflow transition or reviewed decision.
- alternatives: exact list of 0 to 32 text items; defaults to a new empty list.
- consequences: exact nonempty list of 1 to 32 text items.
- Each list item has the same text rules, with raw length at most 1000. List type/count are checked before iterating or allocating the result list. Order and duplicate entries are preserved.

## Exact refusals

Every refusal is ValueError with the exact prefix `ARCHIT705: `:

- `input must be a dict`
- `unknown fields`
- `missing title`, `missing context`, `missing decision`, `missing consequences`
- `<field> must be nonblank safe text`
- `<field> raw length exceeds <cap>`
- `status must be a declared ADR status`
- `status raw length exceeds 10`
- `alternatives must be a list`, `consequences must be a list`
- `alternatives count exceeds 32`, `consequences count exceeds 32`
- `consequences must not be empty`

Text fields use their key names. List items use zero-based names such as `alternatives[0]` or `consequences[1]`. Caps are the decimal limits specified above. No caller text is included in refusal messages.

## Output

`record` contains exactly title, status, context, decision, alternatives, consequences, supersedes. `counts` contains alternatives and consequences lengths. The list containers do not alias input lists. There is no durable store.

`scope` is `caller_supplied_adr_bookkeeping_only`. `immutable_history_required` and `human_review_required` are True labels. `history_immutability_enforced`, `architecture_validated`, `repository_behavior_verified`, `release_authorized` and `evidence_verified` are always False. Output accepted or superseded status does not weaken these bounds.

## Builder receipts

Actual interpreter: Python 3.10.12. Initial fifteen hermetic stdlib unittest methods passed; the later policy repair has eighteen methods GREEN. The targeted status raw-cap test first failed by ASSERT against the preserved original runtime. Explicit U+00AD and U+2060 pins exercise every free-text field and both list types; status refuses them by its exact enum. Separate pins preserve Zs U+00A0 and the accepted Cs U+D800 residual. Before implementation, the same test file failed with FileNotFoundError for the absent target module; this is a genuine missing-module RED, not an observed assertion failure against an existing implementation. Its pre-implementation sha256 and original output are retained in the builder evidence.

Initial fifteen builder source-removal/replacement probes were run: 12 ASSERT, 2 ERROR, 1 mixed, 0 survivors. The policy repair rerun adds the new raw-status-cap probe: sixteen probes, 13 ASSERT, 2 ERROR, 1 mixed, 0 survivors. ERROR-only detections are not assertion-backed refusal proofs. These are builder probes, not an independent mutant battery. An independent audit is still required before any landing. The source-only API is not mounted into application routes. FULL-SUITE UNVERIFIED. No Python 3.12 execution was performed.

## Limits and residual disclosures

Bounded declared bookkeeping over caller-supplied artifacts only. No architecture validation, code execution, quality/coverage certification, approval, merge, deployment, release authority, legal advice, or closure claim. No external effects, file writes, persistence or repository changes occur when this function runs. The builder patch adds only the three named files; cluster files and ledgers remain untouched.

No ADR chronology, status-transition policy, cross-record identity, supersedes existence, cycle detection or history immutability is enforced. Free text may contradict status or other fields; duplicated alternatives are not resolved. No factual assertion, referenced artifact, reviewer consent or claimed decision is verified. Text screening is category-based, not a general security sanitizer: other categories including Cs and private-use characters may be accepted; no normalization, grapheme cap, content moderation or injection detector is supplied. Python's runtime Unicode table determines category membership. Caller allocation before entry and arbitrary concurrent caller mutation are outside the resource bound. This unit does not fulfill the entire row title beyond the explicitly described record bookkeeping.
