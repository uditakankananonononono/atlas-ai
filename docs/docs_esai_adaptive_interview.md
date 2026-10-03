# Adaptive interviewer (scoped, unaudited, repaired after independent review)
Local-model follow-up questions and PROPOSED quote items. Loopback only (no redirects, 8s timeout per call, max 2 concurrent model calls, else labeled fallback). Every failure becomes a labeled FALLBACK (fixed 5-question script); the saved student turn is never lost.
- Questions: lexical checks only (one question, no draft text, no leading templates, no content words the student never said, must reuse a word from the latest answer). This is NOT proof of semantic grounding or quality.
- Items: quote must be an exact copy (case/punctuation sensitive); label words must appear in the answer. Items stay "proposed_unverified" and feed BrandID labels only after the student confirms (POST .../insights/{ordinal}/{index}/confirm).
- Concurrency: compare-and-set on question_index; loser gets HTTP 409. Insight rows unique per (session, ordinal) on new DBs.
- Real model (Qwen2.5-0.5B Q4): with these guards 0/4 questions and 0 items pass, so every turn is labeled fallback. The 0.5B model is too weak; a larger model on the user's hardware is untested (Dell i5 specs unknown).
- Not pushed. Separate from f952af2; interaction with f952af2 NOT checked (object not available in this workspace).

## Revision 2 (span-anchored questions)
Free-form model questions failed the lexical guards on every real turn, and the guards also reject honest paraphrase. They stay strict (off by default, `freeform=True` to try). New default tier `adaptive_span_anchored`: the model picks an exact 3-14 word span of the student's answer plus a type from a closed list (scene/feeling/reason/change); the question text is written by us around that span, so it cannot add student facts. Span quality is NOT verified (e.g. 0.5B picked "nobody else would"). Fallback stays labeled.
Real runs (transcripts in scripts/verification): Qwen2.5-0.5B Q4: 3/4 turns got an anchored question (2 fallbacks of 4 asked; spans weak), 0 of 9 extraction items passed. Qwen2.5-1.5B Q4: calls took 20-40s under memory pressure in this 2GB sandbox and mostly timed out (20s limit); only 2 anchored questions, no extraction. No claim about the user's Dell i5.
Confirmation records the acting actor id; the auth model has no student-only role, so that is recorded, not enforced. No frontend/confirm UI exists.
