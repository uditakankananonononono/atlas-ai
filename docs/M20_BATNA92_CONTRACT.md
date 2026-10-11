# Row 92 BATNA: standalone delta contract (BATNA92)

Status: unreviewed build. Nothing here is accepted or landed.

## Relationship to the existing row 92 mechanism
Row 92 ("BATNA Identification - Knows best alternative to negotiated
agreement", register category "Executive Function & Meta-Cognition") is already
implemented in `backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py`
(`_batna`, line ~250, dispatch key `batna_identification`). This module does
NOT replace it and does not edit it. It is a separate, additions-only delta.

Exact delta over `_batna`:
1. Exact ties: tied best options are all reported (`best_names`, `is_tie`).
   `_batna` uses a stable sort and silently returns the first of equal bests.
2. Exact arithmetic: utilities are compared as `fractions.Fraction`, so no
   float rounding decides a rank.
3. Competition ranking (1,1,3) per option.
4. Every refusal raises `Batna92Error` whose message starts with `BATNA92:` and
   carries a stable `.code`.
5. Missing or uncomparable utilities are refused, never defaulted.
This module does not compute net value from value and cost: the caller
supplies one declared utility per option.

## Frozen interface
Module `batna92`. Version constant `BATNA92_VERSION = "1"`.

`identify_batna(options) -> BatnaRecord`
- `options`: a list or tuple of mappings, each with exactly keys `name` (non-empty
  str, unique after no normalization) and `utility` (int, float, Fraction or
  Decimal; finite; not bool).
- Pure, offline, no I/O, input not mutated.

`BatnaRecord` (frozen dataclass), fields in this order:
- `version: str`
- `options_count: int`
- `best_names: tuple[str, ...]` (input order)
- `best_utility: Fraction`
- `is_tie: bool` (len(best_names) > 1)
- `ranking: tuple[RankEntry, ...]` sorted by utility descending, ties in input order
- `margin_to_next: Fraction | None` (best utility minus the highest strictly lower utility; None if no lower one exists)
- `limits: tuple[str, ...]` (the LIMITS constant)
- `to_dict() -> dict` : JSON-safe; Fractions rendered as strings "p/q" (or "p" when integer).

`RankEntry` (frozen dataclass): `name: str`, `utility: Fraction`, `rank: int` (competition rank starting at 1).

`Batna92Error(ValueError)`: attributes `code: str`, `detail: str`; `str(e) == f"{code}: {detail}"`.

## Refusal codes (all prefixed `BATNA92:`)
- `BATNA92:BAD_SHAPE` options is not a list/tuple.
- `BATNA92:NO_OPTIONS` empty options.
- `BATNA92:BAD_OPTION` an item is not a mapping, has unknown/missing keys other than utility, or name is not a non-empty str.
- `BATNA92:DUPLICATE_NAME` two options share a name.
- `BATNA92:MISSING_UTILITY` the `utility` key absent or None.
- `BATNA92:UNCOMPARABLE` utility is bool, a non-number type (including str), NaN or infinite.

Check order: shape, emptiness, per-option in input order (option shape, name,
missing utility, uncomparable), then duplicate names after all options pass.

## LIMITS (reported verbatim in `limits`)
1. Utilities are caller-declared; nothing here verifies they are true or comparable in reality.
2. A single option set is ranked; no sensitivity, probability or risk analysis.
3. One option is not a negotiation BATNA proof: it is merely the only supplied option.
4. Names are compared exactly, with no case or whitespace normalization.
5. Not a replacement for the landed `batna_identification` mechanism.

## Source pin
Register row 92 text and the file path/line above were read from public main
4088674f. If that row text or the dispatch changes, this contract is stale.
