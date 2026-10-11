# ADVERSE86: adverse-selection rule flags over declared signals (row86)

Targets row86 "Adverse Selection Detection - Identifies when bad actors
self-select" (source doc 1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY,
extracted line 115; register row 86 currently lands in
`negotiation_behavior_0085_0109.py::_adverse_selection`) as a bounded
ADDITIVE module. This document scopes the mechanism only; it does not claim
the row title is fulfilled.

## Delta from the existing mechanism

The register's `_adverse_selection` takes a float sample of offered risk
scores and returns one z-score boolean with a heuristic confidence. This
unit takes a different surface (supplied actor/attributes + declared
signals) and returns deterministic rule flags with stable rule ids in exact
rational arithmetic. It does not replace, edit or wire over the existing
mechanism.

## Function

`adverse_selection86.check_adverse_selection(data) -> dict` (stdlib only).
Every refusal is a `ValueError` whose message starts with `ADVERSE86:`.

## Input (unknown keys refuse)

- `source_ref` (non-blank, <= 200 chars); `signal_basis` must be exactly
  `"declared_signals"`.
- `actor`: `{id, source_ref}`; id is `[A-Za-z0-9_-]{1,40}` and may not name
  a protected-trait token.
- `signals`: 1..32 of `{id, class, source_ref?}`; class is exactly
  `adverse` or `favorable`; ids unique, same grammar and guard as the actor
  id.
- `actor_signal_ids`: <= 32 declared-present signal ids; each must be a
  declared signal, no duplicates.
- `pool`: `{adverse_share, source_ref}`; share is an integer or `p/q`
  string within [0, 1] (|p| <= 10^12, 0 < q <= 10^6).
- `thresholds`: `{concentration, pool_gap_margin, min_declared}`;
  rational in [0, 1] for the first two; `min_declared` an integer in
  [0, len(signals)]. Floats, decimals, booleans and exponent forms refuse.

Row88-shaped input (utility tables, menus) refuses: no overlap with the
landed screening-menu mechanism.

## Rules (deterministic, emitted in rule-id order)

- `ADVERSE86-R1` adverse majority: adverse present > favorable present.
- `ADVERSE86-R2` adverse concentration: at least one adverse present and
  adverse share of declared-present signals >= `concentration` (inclusive).
- `ADVERSE86-R3` pool adverse gap: share - pool adverse share >=
  `pool_gap_margin` (inclusive).
- `ADVERSE86-R4` insufficient disclosure: declared-present count <
  `min_declared`.

Shares are exact `Fraction`s; `adverse_share` renders as a normalized `p/q`
string and is `null` when nothing is declared present (R2/R3 cannot fire).

## Output

`actor_id`, `present_total`, `adverse_present`, `favorable_present`,
`adverse_share`, `pool_adverse_share`, `flags` (rule_id + detail naming the
exact quantities), `flags_total`, `ok` (true only when no rule fires),
`interpretation`, `limits`.

## LIMITS

- Flags fire on the supplied actor attributes and declared signal
  vocabulary only; nothing is observed, inferred or claimed about any real
  person or population.
- A flag is a deterministic rule firing over the caller's declarations, not
  a determination that any actor is bad, risky, or should be priced, denied
  or excluded; every such decision stays with a human.
- No statistical inference: shares are exact ratios of declared counts
  compared against declared thresholds; no distributions, samples,
  confidence or significance are computed or implied. Declared rule flags
  only.
- No utility tables, menus, or incentive/participation constraints:
  screening-menu analysis is a separate mechanism (row88) and this unit
  accepts none of its inputs.
- The protected-trait guard is a coarse id-token filter, not a proof that a
  flag set is non-discriminatory; legal and ethics review remain with a
  human. No counterpart is contacted, persuaded or deceived.

## Boundaries and non-claims

- Stdlib-only (asserted by the test suite). No wiring produced: mounting
  the checker into a dispatch or HTTP surface is integrator work and would
  require editing existing files, out of scope.
- Validated on CPython 3.12.14, pytest 9.1.1 (SQLAlchemy present only
  because the repo's tests/modules conftest imports it). The repo-wide
  floor and mounted surfaces were not run for this package.
