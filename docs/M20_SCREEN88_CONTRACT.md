# SCREEN88-IC-01: screening-menu IR/IC checker over a declared utility table

Targets row88 "Screening Mechanism Design" (extra-doc category "Executive Function
& Meta-Cognition", "Creates self-selection filters"; ledger status PARTIAL) for
SCOPED acceptance only, not full title closure. Row title/description confirmed
in the live source doc 1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY ("Screening
Mechanism Design - Creates self-selection filters").

Base comparison: current owner `negotiation_behavior_0085_0109._screening` takes one
cost and one benefit per type, computes net utility, and checks only that nets are
distinct; its own output says it "cannot verify full incentive compatibility across
counterfactual choices". It checks no participation constraint, no deviation to
other offered options, and no outside option. This unit does.

Function: `screening_menu88.check_screening_menu(data) -> dict` (stdlib, exact
`Fraction`; ValueError on refusal -> 422 when wired by a separate unapplied patch).

## Input (unknown keys refuse)
`source_ref`; `utility_basis` must be exactly `"declared_table"`; `tie_policy`
{weak_ic, weak_ir} both explicit booleans; optional `select` boolean;
`types[{id,source_ref}]` (<=16), `options[{id,source_ref}]` (<=16),
`outside_options[{type_id,utility,source_ref}]` (exactly one per type),
`utilities[{type_id,option_id,utility,source_ref?}]` (complete T x O matrix, no
duplicates/unknown IDs; record source_ref falls back to the top-level one),
`menus[{id,option_ids,mapping,source_ref}]` (<=64; mapping gives exactly one
option or `"outside"` per type; mapped option must be in the menu).
Utilities are integers or strings `p` / `p/q` (|p|<=10^12, 0<q<=10^6); floats,
decimals, bools and exponent forms refuse. IDs are `[A-Za-z0-9_-]{1,40}`, may not
be `outside`, and may not contain a protected-trait token (gender, sex, race,
religion, age, disability, ethnicity, nationality, pregnancy, orientation, caste,
ancestry) split on `_`/`-`. This is a coarse guard, not a non-discrimination proof.

## Rules (per menu, per type with intended choice c)
- IR: if c is an option, u(c) >= outside(t). Strict (u(c) > outside) unless `weak_ir`.
  Violation reports exact `shortfall` = outside - u(c) (0 for an unaccepted tie).
- IC: for every other option a offered in the menu, u(c) >= u(a). Strict unless
  `weak_ic`. If c is `outside`, the type must not prefer any offered option.
  Violation reports `deviation`, utilities and exact `gain` = u(a) - u(c).
- Ties (IR vs outside, IC vs alternative) are always listed with
  `accepted_as_weak`; they are not violations only when the matching weak flag is true.
  `weak_ic` never excuses an IR tie and vice versa.
- `feasible` = no IR and no IC violations. `feasible_menu_ids` sorted; with
  `select:true`, `selected_menu_id` is the lexicographically smallest feasible id
  (deterministic tie-break only, not optimization); else null.
  `no_feasible_menu` is true when none are feasible.

## Output
Per menu (sorted by id): `feasible`, `ir_violations`, `ic_violations`, `ties`, echoed
sorted mapping; plus `feasible_menu_ids`, `selected_menu_id`, `no_feasible_menu`,
`tie_policy`, sorted `source_trace` (types, options, outside options, utilities, menus),
`utility_interpretation` ("declared table values only; not inferred from or claimed
about real people"), `welfare_claim:false`, `counterpart_contacted:false`, `limits`.
Rationals are normalized strings ("3/2", "0"). Output order is independent of input order;
input is not mutated.

## Limits (residual)
Declared table only: nothing is validated against or inferred about real people. Pairwise
exact comparison within supplied menus; no menu is generated or optimized, no
equilibrium, mixed strategies, multi-dimensional types, prices/transfers, welfare,
profit or fairness claim. Protected-trait guard is token-level only; legal/ethics review
stays with a human. No counterpart contact, persuasion or deception. Ledger, STATUS,
dispatcher and routes untouched; row88 wiring is a separate unapplied patch.
