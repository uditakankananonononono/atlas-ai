# Row 1544 Accelerated Life Testing - ACCLIF contract (PREP-only, local candidate)

## Ledger source pin
audits/additional-2000-features.json, id 1544, requirement: "Accelerated Life Testing", status: verified-pushed (ledger attribution, not re-verified here). Coverage register: audits/coverage-register.json.
Description: (empty). The ledger description is empty, so the requirement title is the whole specification; everything below is DESIGN text for a bounded, deterministic mechanism over caller-supplied declarations, not ledger text.

## Model check
The `model` value is checked as: exact type `str`, then raw length at most 128, then equality with `arrhenius`; anything else (including a str subclass or an object with its own `__eq__`, which is never called) refuses with `unsupported_model`.

## Existing mechanism and delta
Existing (main a294723b): `_alt` at backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:219 computes one Arrhenius factor in float from one use and one test temperature (all values positive and finite), no upper bounds, no stress-level list, no counts. Test: tests/modules/test_m20_engineering_1510_1559.py:67 (`test_1544_arrhenius_acceleration`).
This unit (new file `accelerated_life_testing1544.py`, function `run(request)`): closed schema; model must be "arrhenius"; failure mechanism must be declared; a list of stress levels (id, temperature_k, hours, units_on_test, failures); exponent computed exactly as a fraction from a fixed Boltzmann constant (8.617333262e-5 eV/K); acceleration factor = exp(exponent) as float; exact device-hours per level and in total; failures may not exceed units; each level is labeled above_use, at_use or below_use; |exponent| above 700 is refused.

## Scope
Model bookkeeping over supplied stress levels only. No extrapolated-life, MTTF, reliability or field claims are produced; the output says mechanism equivalence is not validated. Bounded exact deterministic mechanism over caller-supplied declarations. No physical test, no solver execution, no certification, no release authority; any output is a labeled bookkeeping result, never a test result. Nothing is persisted; no route or registry entry is added (integration is a separate step).

## Limits (N / N+1 pinned by tests)
- MAX_LEVELS = 32
- MAX_TEXT = 128 characters
- MAX_KEYS = 64 (checked before any iteration)
- activation energy: 0 < value <= 10 eV
- temperatures: 0 < value <= 10000 K
- hours per level: 0 < value <= 10 ** 9
- units_on_test: 1 .. 10 ** 6; failures: 0 .. units_on_test
- |exponent| <= 700
- integers wider than 64 bits refused; bool, NaN, inf refused

## Key type
At the request and stress-level dicts the key count is checked first, then every key must be an exact `str` (`type(key) is str`) before any set or allowlist comparison; a str-subclass or non-str key refuses with `unknown_key`. Pinned with a spy key counting `__hash__` and `__eq__` calls after the input is built; no claim is made about hashing done while the caller builds the input.

## Refusals
Every refusal is `ValueError("ACCLIF1544:<code>")` with a fixed token; no request text is echoed. Codes:
- `ACCLIF1544:invalid_request`, `unknown_key`, `invalid_count:keys`, `unsupported_model`
- `ACCLIF1544:invalid_text:failure_mechanism`, `invalid_text:id` (empty, blank, over length, or containing any character of Unicode category Cc, Cf, Zl or Zp; the full Cf category is refused, including U+00AD and U+2060 as explicit pins; Zs such as U+00A0 is accepted). The length cap is checked before the blank and Unicode checks
- `ACCLIF1544:invalid_number:<field>` for activation_energy_ev, use_temperature_k, temperature_k, hours, units_on_test, failures
- `ACCLIF1544:invalid_count:stress_levels`, `invalid_item:stress_levels`, `duplicate_id:stress_levels`
- `ACCLIF1544:failures_exceed_units`
- `ACCLIF1544:invalid_range:exponent`

## Limits and residual disclosures
- The acceleration factor is a float from `math.exp`; the exponent is exact. Float output is not rounded.
- Temperature-only Arrhenius; no humidity, voltage or other stress models, no Weibull or lognormal fits.
- The Boltzmann constant is a fixed value in the source; the unit does not verify standards.
- Lone surrogates (category Cs) get no new refusal; this is a disclosed residual of the unit.
- Tests are builder-run on CPython 3.12.14; the full repository suite was not run. This is builder-stated evidence only and claims no closure.
