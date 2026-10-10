# Cost estimate helper v1 - additive integration

Unit: ATLAS-M23-NET-COST-VALIDATION-02.
Base: f37156c7fc7aec8cf7bec6ecbd0f8aa39ecb18fa.

Standalone written interface proposal, not a shared API or existing binding.
No imports from the app, routes, services, database, environment or HTTP.
Existing lifecycle rows 36 and 39 remain unchanged and unsafe pending integration.
Tests executed by integrator; see M23_CONTRACT_INTEGRATION_20261010.md for current bindings and limits.

## `estimate_net_cost(data: Mapping) -> dict`

Required known inputs for a full estimate:

- `currency`: an uppercase three-letter currency label, no implicit USD.
- `years`: finite nonnegative number. Zero and fractional years are allowed.
- `annual_costs`: an object with `tuition`, `fees`, `living` money objects.
  Each is `{amount: number, currency: label}`. No absent fee defaults to zero.
- `aid`: list of up to 500 objects `{amount, currency, timing}`.
  Empty list explicitly means no aid in this scenario.
  `timing` is `annual` or `program_total`. Annual aid is prorated by years;
  program-total aid is subtracted once, including when years is zero.

Gross = (tuition + fees + living) * years. Aid scenario total is the sum of
annual aid * years plus program-total aid. Net is max(0, gross - aid).
Excess is reported as `unapplied_aid`, never a refund or cash entitlement.
Flat annual rates and annual aid proration are scenario assumptions, not
verified school policy. No inflation, exchange rates, renewal checks, loan
interest, disbursement schedules or aid confirmation are inferred.

Outputs: `status` (`estimated` / `unknown_inputs`), `currency`, `years`,
`gross_cost`, `aid_scenario_total`, `net_cost`, `unapplied_aid`,
`unknown_inputs` (sorted unique field paths), `estimate_only: true`, `boundary`.
Monetary outputs and years are canonical decimal strings or null. Zero is `"0"`.
Gross can remain known when only aid is unknown. No net is given with any
unknown required input, including currency or timing. A missing/None value
means unknown, never zero, and never authorizes deduction.

## `summarize_awards(data: Mapping) -> dict`

`currency` and `awards` are required for a known subtotal. `awards` is a list
of up to 500 objects `{amount, currency, timing, accepted}`. All known currency
labels must match the target. All known timing labels must match one another.
No sum is performed across currencies or across annual/program-total timing.
An empty list explicitly means zero offered and zero accepted, with null timing.
`accepted` must be literal true or false, not a string or number.

Outputs: `status`, `currency`, `timing`, `total_offered`, `accepted_total`,
`unknown_inputs`, `award_count`, `estimate_only`, `boundary`.
All face amounts are treated as supplied offered awards. That is not verified
award status. An unknown accepted flag allows offered total but suppresses
accepted total. Unknown amount/currency/timing suppresses both totals, even
on an unaccepted award. A total is face value at the stated timing, not
annualized or disbursed cash. No payment or aid guarantee is made.

## Validation and errors

Both functions raise `ValueError` on invalid known inputs or conflicts before
returning totals, even when other inputs are unknown. Inputs must be mappings;
collections must be lists containing mappings, not implicit iterables.

Numbers accept int, float, Decimal or decimal text, but never bool. Parsing
uses Decimal(str(value)); text accepts signed decimal/scientific notation
without whitespace or underscores. Reject NaN, infinity, negatives, numbers
above 1e30, representations over 128 characters, and decimal exponents outside
[-28, 30]. Finite numeric bounds apply to years as well. Decimal arithmetic
uses local precision 200; no currency rounding is performed. Floats retain
their supplied decimal representation, not a claim of original precision.

Currency labels are syntactic labels only, not an ISO registry validation.
No normalization, currency conversion, network access or external effect.
Unknown extra fields are ignored; callers must map legacy input explicitly.
Functions do not mutate their input. No state, bindings or shared APIs added.

## Integration decisions left to the peer

1. Accept or change this standalone interface and its decimal-string outputs.
2. Map legacy lifecycle row 36 scalars and row 39 awards to explicit currencies,
   timing and acceptance. Do not assume a legacy aid amount is annual or total.
3. Decide desired fractional-year, zero-year, rate/proration and numeric bounds.
4. Wire errors and unknown statuses to API/UI, select currency registry policy
   and rounding rules, and preserve estimate-only/no-guarantee labels.
5. Execute authored tests and regression checks independently, including test
   harness behavior. The test file loads this helper by path to avoid importing
   the module's database-connected package initializer; repository conftest
   behavior is not verified here.

Test file: `tests/modules/test_m23_cost_estimate_validation_02.py`.
Historical preparation had no test execution. Integration now covers helper and additive route tests.
