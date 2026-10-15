# Sentience / AGI-Claim Emission Lint - Contract (group 138, line 62)

Bounded mechanism: `backend/app/runtime/guardrails/claim_lint_gate.py`. An
enforced runtime check over user-facing text BEFORE it is emitted. This
document scopes the mechanism only.

## Rule

`emit(emission_id, body, channel=..., now=..., ledger=...)` screens the text
against a CLOSED list of false-sentience and false-AGI phrases
(`PROHIBITED_CLAIMS`, in the module). Matching is case-insensitive
exact-phrase substring search with per-character lowercase index mapping
(the P69 discipline), so reported offsets index the caller's original text.
Each body is screened in two forms: first the CRLF-normalized raw form
(each CRLF pair counts as one LF), then a whitespace-collapsed form in
which every run of spaces, TABs, LF or CR becomes a single space. Phrases
are tried in closed-list order (categories and phrases as listed); for each
phrase the raw form is tried before the collapsed form, and the first match
wins. A match found through a CRLF pair reports the CR's raw offset; a
match found through a collapsed run reports the raw offset of the run's
first character.

- No listed phrase -> verdict `emitted`, digest ledgered, record returned.
- A listed phrase -> the refusal is ledgered (category, phrase, offset, text
  digest) and `GuardrailRefusal("LINT:refused:false_claim")` is raised. The
  caller never receives the text as emitted.

## Body text and digests

Bodies are free-form user-facing text: LF, TAB and CRLF pairs are admitted;
a lone CR and every other control, format or line/paragraph separator
character is refused. The length cap applies to the raw text before any
normalization. The body is never coerced, so the ledgered text digest is
bound to the caller's raw bytes exactly as passed.

## The closed phrase list

Two categories. sentience_claim: "i am sentient", "atlas is sentient",
"claire is sentient", "i am conscious", "atlas is conscious",
"claire is conscious", "i am self-aware", "i am self aware",
"atlas is self-aware", "claire is self-aware", "i am alive",
"i have feelings", "i feel emotions", "i have emotions", "i am a human",
"i am human". agi_claim: "atlas is an agi", "atlas is agi",
"claire is an agi", "claire is agi", "atlas has achieved agi",
"achieved artificial general intelligence", "atlas is superintelligent",
"claire is superintelligent", "achieved superintelligence",
"atlas is a superintelligence", "i am an agi", "i am superintelligent",
"i am a superintelligence". Extending the list is a contract change.

## Limits (named, none hidden)

- Lexical exact-phrase screen; a clear verdict means only that no listed
  phrase matched. Implied claims, paraphrases and images are out of scope;
  human review remains the backstop.
- Substring matching can catch benign text (e.g. "humane" contains no listed
  phrase, but a phrase embedded in a longer word would match); that bias
  toward refusal is deliberate.
- Only text digests are stored; the lint keeps no content copy.
- Whitespace policy: LF, TAB and CRLF pairs are admitted; a lone CR is
  refused; screening also covers the whitespace-collapsed form, so a listed
  phrase split across spaces, tabs or newlines still matches; offsets
  always index the caller's original text.
- The ledger is an unkeyed hash chain: tamper-evident, not tamper-proof. A rehashed edit is not detectable; safe storage of the serialized ledger is the caller's job.
