# Advanced thinking-layer quiz (m20.thinking_quiz)

Builder: Instinct agent (builder task). Base: main `2acdcd3301a988bb8298308389c0b1e307c27e70` (own ls-remote at branch time, 2026-10-11 18:04:59 IST; path verified FREE). Branch: `review/c3-thinking-quiz`. No push, no amend, no rebase, no delete. New files only; C2 (`launch_quiz_c2.py`) untouched. No overlap with the landed c3_layers packet pipeline (no sessions, answers or clarify logic there; none reimplemented here).

cross-account builder package, provenance held privately

## What the code does

`backend/app/modules/m20_general_cognitive_worker/thinking_quiz.py`. Stdlib only (no imports beyond the stdlib — actually none at all); deterministic (constant bank order, sorted trait dicts, floats rounded to 6 places, no wall clock except the caller-supplied `as_of`); no network, no I/O, no model training, no mind replication — answers are the owner's own supplied words and the profile is arithmetic over them.

- Layered question bank: 4 launch stages (idea, audience, positioning, launch) x 5 thinking dimensions (values, evidence, taste, risk, voice) = 20 real questions, each with 3 real choices; every choice carries explicit trait weights (1.0 primary, 0.5 secondary) over a 12-trait vocabulary (`TRAITS`).
- `ThinkingQuiz` sessions: `start(owner, consent=..., as_of=...)` requires `consent=True` (`FLEET_REFUSED_NOCONSENT`), owner-scoped access (`FLEET_REFUSED_OWNER`), bounded session count (`FLEET_REFUSED_LIMIT`), unknown session `FLEET_REFUSED_UNKNOWN`.
- Quiz flow: `current_question` returns the first unanswered question in bank order (stage then dimension), `None` when complete; `answer` validates question/choice ids (`FLEET_REFUSED_UNKNOWN:question_id|choice_id`), refuses re-answering (`FLEET_REFUSED_DUPLICATE:question_id`), accepts an optional explanation (length-capped, never copied into the profile).
- Profile: `profile` computes exact trait totals, per-stage coverage, per-dimension normalized trait shares (rounded 6), completeness, and a top-3 `thinking_signature` (ties broken alphabetically). The profile contains no free-text explanations.
- Suggestions: `suggest(owner, sid, stage=None, limit=3)` is the real consumer of the profile: it normalizes trait totals and scores each of the 10 `SUGGESTION_RULES` by dot product, returning the top `limit` sorted by (-score, id). Different answer patterns yield different top suggestions (tested).
- Lifecycle gates consistent with C2: `edit` changes an existing answer's choice (and re-keys its traits), `delete` removes the session, `revoke` wipes answers and blocks all further use (`FLEET_REFUSED_REVOKED`); `answers_snapshot(..., allow_revoked=True)` proves the wipe.

## Refusals

All `ThinkingQuizError` (a `ValueError`), message `FLEET_REFUSED_<CODE>[:field]`: NOCONSENT, OWNER, UNKNOWN ([:question_id|choice_id]), DUPLICATE:question_id, LIMIT, INPUT, REVOKED.

## LIMITS

20 questions fixed in code; owner, as_of and explanation length caps (200/100/4000); sessions per instance capped (default 100, max 1000); suggest limit 1..20. Answers are self-reported; the profile describes the supplied answers, not the person. No scraping, no accounts, no sends.

## Verification (builder-stated)

- Tests-first: RED captured (`red.log`, collection error before the module existed), then GREEN.
- 18 tests pass on CPython 3.12.15 (`/home/sandbox/venv-pair691/bin/python`).
- CPython 3.10.12: NOT GREEN, pre-existing repo condition, not caused by this unit: collecting any m20 test module (including the existing `tests/modules/test_launch_quiz_c2.py` on unmodified main) fails at `backend/app/modules/m25_knowledge_copilot/schemas.py` with `ImportError: cannot import name 'StrEnum' from 'enum'` (StrEnum is Python 3.11+; m25 landed in 5337085b). This unit adds no import of m25 and changes nothing about it.
- Mutation battery: 16 mutants (signature order, total rounding, dimension shares, suggest normalization, suggest ordering, consent gate, owner gate, revoke wipe, revoke block, duplicate gate, completeness math, session cap, stage counting, bank order, edit trait update, suggest stage filter). Taxonomy: 13 KILLED by assertion failure, 2 KILLED by test error (m03, m12), 1 SURVIVED, 0 timeout/non-compile.
  - SURVIVED m02-no-round-total — disposition: EQUIVALENT, justified: every bank weight is 1.0 or 0.5, exactly representable in binary floating point, so trait sums are exact and `round(x, 6)` is the identity on them; no discriminating test is possible without changing the bank.
- Raw per-mutant output: `mut-m01..m16.log` in the evidence archive.
