# Adaptive interviewer (scoped, unaudited, repaired after independent review)
Local-model follow-up questions and PROPOSED quote items. Loopback only (no redirects, 8s timeout per call, max 2 concurrent model calls, else labeled fallback). Every failure becomes a labeled FALLBACK (fixed 5-question script); the saved student turn is never lost.
- Questions: lexical checks only (one question, no draft text, no leading templates, no content words the student never said, must reuse a word from the latest answer). This is NOT proof of semantic grounding or quality.
- Items: quote must be an exact copy (case/punctuation sensitive); label words must appear in the answer. Items stay "proposed_unverified" and feed BrandID labels only after the student confirms (POST .../insights/{ordinal}/{index}/confirm).
- Concurrency: compare-and-set on question_index; loser gets HTTP 409. Insight rows unique per (session, ordinal) on new DBs.
- Real model (Qwen2.5-0.5B Q4): with these guards 0/4 questions and 0 items pass, so every turn is labeled fallback. The 0.5B model is too weak; a larger model on the user's hardware is untested (Dell i5 specs unknown).
- Not pushed. Separate from f952af2; interaction with f952af2 NOT checked (object not available in this workspace).
