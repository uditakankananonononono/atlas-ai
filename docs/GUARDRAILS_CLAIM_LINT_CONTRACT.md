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

- No listed phrase -> verdict `emitted`, digest ledgered, record returned.
- A listed phrase -> the refusal is ledgered (category, phrase, offset, text
  digest) and `GuardrailRefusal("LINT:refused:false_claim")` is raised. The
  caller never receives the text as emitted.

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
