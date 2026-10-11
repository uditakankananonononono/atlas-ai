# Row 1260 sentencing grid lookup: contract

Row text in the ledger: "Sentencing Guidelines" (title only; the ledger description is empty). Anything beyond the title below is the scope of this additive mechanism, not ledger text. The words "grid lookup + range" are this unit's own scoping vocabulary, not ledger text.

Module: `backend/app/modules/m20_general_cognitive_worker/sentencing_grid1260.py`. Tests: `tests/modules/test_m20_sentencing_grid1260.py`. Standard library only (`unicodedata`, `typing`, `__future__`).

## Relation to what already exists (not replaced, not edited)

Row 1260 already has a mechanism on main: `backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py` (blob fe80376c7a5ff3cf4291103c03b2b2bb85d73736 at the time of writing), spec `(1260, "sentencing_guidelines", "guideline_calculation_map", "map guideline edition, offense characteristics, adjustments and departures without computing a sentence")`, with tests in `tests/modules/test_m20_legal_1260_1309.py` and `tests/modules/test_m12_legal_1260_1309.py`. That mechanism maps supplied material for counsel and does not compute a sentence. The same directory also contains `sentencing_guidelines1260.py`: bounded declared legal-support bookkeeping that maps caller-supplied guideline material into a provenance-bound receipt and never computes a sentence, a range, an offense level or a category. Both are untouched by this unit and stay the row's existing implementations. This module computes nothing from real guideline data and its test grid is invented.

Exact delta: this module adds one narrow thing that the existing one states it does not do. The caller declares a table (levels, categories, a `[min, max]` cell for each declared cell) plus named integer level adjustments. `lookup(base_level, category, offense=[...], offender=[...])` adds the chosen deltas to the base level and returns the declared cell range. It is integer addition and a dictionary read. It does not replace, wrap, import, or register with the existing module, and it edits no ledger, register or cluster file.

## Interface

`SentencingGrid(declaration)` with keys `name`, `edition`, `source`, `unit`, `levels`, `categories`, `cells` (required) and `offense_adjustments`, `offender_adjustments` (optional objects of name to integer delta). Cells are keyed by level as a string and then category. `lookup(...)` returns `range` (`min`, `max`, `unit`), `base_level`, `adjusted_level`, `category`, `applied_adjustments` (kind, name, delta, in the order applied), `grid` (name, edition, source as the caller declared them) and `disclaimer`. The declaration is never copied; the grid keeps only validated values stored in fresh containers, so later edits to the caller's declaration do not change the grid.

## Refusals (all start with `SENT1260: `)

Declaration: not an exact dict (subclasses refused), unknown or missing keys, blank text fields, text over 256 characters, category or adjustment names over 64 characters, more than 64 levels, categories, cell rows or adjustment entries (count caps are checked before iteration), text containing control, format or line/paragraph separator characters (Unicode Cc, Cf, Zl or Zp), levels not a non-empty strictly ascending list of integers or not contiguous, categories empty/duplicate/blank, a cell at an undeclared level or category, a cell that is not `[min, max]` non-negative integers with min <= max (booleans and floats refused), adjustment tables that are not objects, blank names, or non-integer deltas.
Lookup: base level not an integer (booleans refused), category not a string or not declared, adjustment names not a list of strings, an unknown adjustment name, the same adjustment listed twice, an adjusted level outside the declared levels (refused, never clamped), and a missing cell (refused, never inferred, interpolated or filled).

## LIMITS (stated plainly)

- Title-only scope. The mechanism is a lookup in a table the caller declares. It contains no guideline data of its own.
- Nothing is checked against any real guideline, edition, jurisdiction or amendment. `edition` and `source` are free text copied back as declared. The test grid is invented.
- It is not a sentence, not a prediction, not legal advice and not a claim about any real case. It does not apply departures, mandatory minimums, statutory maximums, criminal-history rules, grouping or any judgment; only the adjustments the caller declares as integer deltas.
- Ranges are returned as declared. The module does not check that a declared range is internally consistent with a real table.
- A licensed practitioner must verify any table and any use of a result.
- Not wired: no registry entry, no route, no job. It was not run inside any pipeline.
- Not run: the full repository test suite, Postgres, CI.

## Tests and mutants

66 tests in the file above. Hand-written mutants (one at a time, classified as assertion kills or exception kills) are listed in the delivery logs, not claimed here as a whole-module proof.
